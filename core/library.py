"""Local material storage. Original files and ordered page records are independent of exports."""
from contextlib import contextmanager
from dataclasses import dataclass
import copy
import hashlib
import io
import json
import re
import shutil
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
import pypdfium2 as pdfium


IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff'}
PDF_LOCK = threading.Lock()  # PDFium is not thread safe, including across documents.


def natural_key(path):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)', str(path))]


def timestamp():
    return int(time.time() * 1000)


def course_identity(course, user_id, tenant_id):
    value = json.dumps([tenant_id, user_id, course['course_id'], course['sub_id']], ensure_ascii=False)
    return 'scut:' + hashlib.sha256(value.encode()).hexdigest()


def offering_identity(course, user_id, tenant_id):
    value = json.dumps([tenant_id, user_id, str(course['course_id'])], ensure_ascii=False)
    return 'course:' + hashlib.sha256(value.encode()).hexdigest()


class Library:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ('materials', 'temporary', 'exports'):
            (self.root / name).mkdir(exist_ok=True)
        self.db = self.root / 'library.sqlite'
        self.lock = threading.RLock()
        with self.connection() as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS materials (id TEXT PRIMARY KEY, source_key TEXT UNIQUE, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS courses (id TEXT PRIMARY KEY, data TEXT NOT NULL);
            ''')
            version = con.execute('PRAGMA user_version').fetchone()[0]
            if version < 2:
                if con.execute('SELECT count(*) FROM materials').fetchone()[0]:
                    backup = sqlite3.connect(self.root / 'before-courses.sqlite')
                    try:
                        con.backup(backup)
                    finally:
                        backup.close()
                con.execute('PRAGMA user_version=2')

    def courses(self):
        with self.connection() as con:
            return [json.loads(r[0]) for r in con.execute('SELECT data FROM courses')]

    def save_course(self, title, course_id=None, term='', cover_style=None, cover_palette=None):
        title = str(title).strip()[:120]
        if not title:
            raise ValueError('请填写课程名称。')
        course_id = course_id or uuid.uuid4().hex
        existing = next((c for c in self.courses() if c['id'] == course_id), {})
        course = {'id': course_id, 'title': title, 'term': str(term).strip()[:80],
                  'coverStyle': existing.get('coverStyle', '') if cover_style is None else str(cover_style).strip()[:40],
                  'coverPalette': existing.get('coverPalette', '') if cover_palette is None else str(cover_palette).strip()[:40]}
        with self.connection() as con:
            con.execute('INSERT OR REPLACE INTO courses VALUES(?,?)', (course_id, json.dumps(course, ensure_ascii=False)))
        return course

    def set_course_cover(self, course_id, style='', palette=''):
        course = next((c for c in self.courses() if c['id'] == course_id), None)
        if not course:
            raise ValueError('课程不存在。')
        return self.save_course(course['title'], course_id, course.get('term', ''), style, palette)

    def attach_platform(self, material_id, lecture, user_id, tenant_id):
        cid = offering_identity(lecture, user_id, tenant_id)
        if not any(c['id'] == cid for c in self.courses()):
            self.save_course(lecture['title'], cid)
        m = self.get(material_id)
        # A manual assignment wins over subsequent scans.
        return self.update(material_id, courseId=m.get('courseId') or cid,
                           platformCourseId=str(lecture['course_id']), lectureId=str(lecture['sub_id']))

    def assign(self, ids, course_id):
        if course_id and not any(c['id'] == course_id for c in self.courses()):
            raise ValueError('课程不存在。')
        with self.connection() as con:
            materials = [self.get(mid) for mid in dict.fromkeys(ids)]
            for m in materials:
                m['courseId'] = course_id
                self._put(con, m)

    def mark_reviewed(self, mid, revision):
        with self.connection() as con:
            m = self.get(mid)
            if m['revision'] != revision or m['deleted']:
                raise ValueError('课件已更新，请重新确认整理状态。')
            m.update(reviewRevision=revision, touched=timestamp())
            self._put(con, m)
        return m

    @contextmanager
    def connection(self):
        with self.lock:
            con = sqlite3.connect(self.db, timeout=30)
            try:
                with con:
                    yield con
            finally:
                con.close()

    def resolve(self, relative):
        result = (self.root / relative).resolve()
        if not result.is_relative_to(self.root):
            raise ValueError('资料库文件路径无效。')
        return result

    def materials(self):
        with self.connection() as con:
            return [json.loads(row[0]) for row in con.execute('SELECT data FROM materials')]

    def get(self, material_id):
        with self.connection() as con:
            row = con.execute('SELECT data FROM materials WHERE id=?', (material_id,)).fetchone()
        if not row:
            raise ValueError('未找到这份课件。')
        return json.loads(row[0])

    def find_source(self, source_key):
        with self.connection() as con:
            row = con.execute('SELECT data FROM materials WHERE source_key=?', (source_key,)).fetchone()
        return json.loads(row[0]) if row else None

    def _put(self, con, m):
        con.execute('INSERT INTO materials VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',
                    (m['id'], m['sourceKey'], json.dumps(m, ensure_ascii=False)))

    def update(self, material_id, **changes):
        with self.connection() as con:
            row = con.execute('SELECT data FROM materials WHERE id=?', (material_id,)).fetchone()
            if not row:
                raise ValueError('课件不存在。')
            m = json.loads(row[0])
            m.update(changes)
            self._put(con, m)
        return m

    def set_selection(self, material_id, excluded, expected_revision):
        with self.connection() as con:
            m = self.get(material_id)
            if m['revision'] != expected_revision:
                raise ValueError('课件已更新，请重新打开后再整理。')
            if not isinstance(excluded, list) or any(type(p) is not int or not 1 <= p <= m['pages'] for p in excluded):
                raise ValueError('页面范围无效。')
            selected = sorted(set(excluded))
            if selected != m['excluded']:
                m.update(excluded=selected, edited=True, revision=m['revision']+1, touched=timestamp())
                self._put(con, m)
        return m

    def task_put(self, task):
        with self.connection() as con:
            con.execute('INSERT OR REPLACE INTO tasks VALUES(?,?)', (task['id'], json.dumps(task, ensure_ascii=False)))

    def tasks(self):
        with self.connection() as con:
            return [json.loads(r[0]) for r in con.execute('SELECT data FROM tasks ORDER BY rowid')]

    def setting(self, key, default=None):
        with self.connection() as con:
            row = con.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key, value):
        with self.connection() as con:
            con.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, json.dumps(value, ensure_ascii=False)))

    def payload(self):
        result = self.materials()
        for m in result:
            m['media'] = [{'src': self.resolve(p['preview']).as_uri(), 'thumb': self.resolve(p['thumb']).as_uri()}
                          for p in m['files']]
            m.pop('files', None)
        return result

    @contextmanager
    def new_material(self):
        mid = uuid.uuid4().hex
        directory = self.root / 'materials' / mid
        directory.mkdir()
        try:
            yield mid, directory
        finally:
            with self.connection() as con:
                committed = con.execute('SELECT 1 FROM materials WHERE id=?', (mid,)).fetchone()
            if not committed and directory.resolve().parent == (self.root / 'materials').resolve():
                # Only a directory created by this operation, never imported source files.
                shutil.rmtree(directory)

    def prepare_images(self, files, title, day, source_key=None, checkpoint=lambda: None, progress=lambda d,t: None):
        if not files:
            raise ValueError('没有可以导入的图片。')
        with self.new_material() as (mid, directory):
            records = []
            for i, src in enumerate(files, 1):
                checkpoint()
                source = Path(src)
                with Image.open(source) as original:
                    original.load()
                    image = ImageOps.exif_transpose(original).convert('RGB')
                    dest = directory / f'{i:05d}{source.suffix.lower()}'
                    shutil.copy2(source, dest)
                    preview = directory / f'{i:05d}-preview.jpg'
                    image.thumbnail((1800, 1800))
                    image.save(preview, quality=90)
                    thumb = directory / f'{i:05d}-thumb.jpg'
                    image.thumbnail((480, 360))
                    image.save(thumb, quality=85)
                    image.close()
                records.append({'original': dest.relative_to(self.root).as_posix(),
                                'preview': preview.relative_to(self.root).as_posix(),
                                'thumb': thumb.relative_to(self.root).as_posix()})
                progress(i, len(files))
            checkpoint()
            return self._commit(mid, records, title, day, source_key, 'image')

    def prepare_pdf(self, source, checkpoint=lambda: None, progress=lambda d,t: None):
        with self.new_material() as (mid, directory):
            source = Path(source)
            dest = directory / 'original.pdf'
            shutil.copy2(source, dest)
            records = []
            with PDF_LOCK:
                doc = pdfium.PdfDocument(str(dest))
                try:
                    for i in range(len(doc)):
                        checkpoint()
                        page = doc[i]
                        try:
                            bitmap = page.render(scale=min(2.0, 1600 / max(page.get_size())))
                            try:
                                image = bitmap.to_pil().convert('RGB')
                                preview = directory / f'{i+1:05d}-preview.jpg'
                                image.save(preview, quality=90)
                                image.thumbnail((480, 360))
                                thumb = directory / f'{i+1:05d}-thumb.jpg'
                                image.save(thumb, quality=85)
                                image.close()
                            finally:
                                bitmap.close()
                        finally:
                            page.close()
                        records.append({'original': dest.relative_to(self.root).as_posix(), 'pdfPage': i,
                                        'preview': preview.relative_to(self.root).as_posix(),
                                        'thumb': thumb.relative_to(self.root).as_posix()})
                        progress(i+1, len(doc))
                finally:
                    doc.close()
            if not records:
                raise ValueError('PDF 中没有页面。')
            checkpoint()
            return self._commit(mid, records, source.stem, time.strftime('%Y-%m-%d'), None, 'pdf')

    def _commit(self, mid, records, title, day, source_key, kind):
        m = {'id': mid, 'title': title or '未命名课件', 'topic': '课堂课件' if source_key else '本地资料',
             'day': day, 'pages': len(records), 'files': records, 'sourceKey': source_key or 'local:'+mid,
             'source': 'platform' if source_key else 'import', 'kind': kind,
             'excluded': [], 'edited': False, 'exported': False, 'revision': 0,
             'exportRevision': None, 'exportName': '', 'exportPath': '', 'lastPage': 1,
             'deleted': False, 'touched': timestamp()}
        with self.connection() as con:
            self._put(con, m)
        return m

    def export_snapshot(self, mid):
        m = self.get(mid)
        if m['deleted']:
            raise ValueError('请先从回收站恢复课件。')
        snapshot = copy.deepcopy(m)
        snapshot['files'] = [p for i,p in enumerate(m['files'], 1) if i not in m['excluded']]
        if not snapshot['files']:
            raise ValueError('至少保留一页后才能导出。')
        return snapshot

    def export_pdf(self, snapshot, destination, checkpoint=lambda: None, progress=lambda d,t: None, record_export=True):
        dest = Path(destination).resolve()
        if dest.suffix.lower() != '.pdf':
            raise ValueError('导出文件必须使用 .pdf 后缀。')
        if dest.is_relative_to(self.root) and not dest.is_relative_to(self.root / 'exports'):
            raise ValueError('请勿将导出文件保存到资料库内部素材目录。')
        dest.parent.mkdir(parents=True, exist_ok=True)
        temporary = dest.with_name(f'.{dest.stem}-{uuid.uuid4().hex}.part')
        writer = PdfWriter()
        readers = []
        pdf_reader = None
        try:
            if snapshot['kind'] == 'pdf':
                pdf_reader = PdfReader(self.resolve(snapshot['files'][0]['original']))
            for i, record in enumerate(snapshot['files'], 1):
                checkpoint()
                if pdf_reader:
                    writer.add_page(pdf_reader.pages[record['pdfPage']])
                else:
                    with Image.open(self.resolve(record['original'])) as raw:
                        image = ImageOps.exif_transpose(raw).convert('RGB')
                        stream = io.BytesIO()
                        image.save(stream, format='PDF', resolution=144)
                        image.close()
                        stream.seek(0)
                        reader = PdfReader(stream)
                        readers.append(reader)
                        writer.add_page(reader.pages[0])
                progress(i, len(snapshot['files']))
            checkpoint()
            writer.write(str(temporary))
            check = PdfReader(temporary)
            if len(check.pages) != len(snapshot['files']):
                raise RuntimeError('PDF 页数校验失败。')
            check.close()
            checkpoint()
            temporary.replace(dest)
        finally:
            writer.close()
            if pdf_reader:
                pdf_reader.close()
            for reader in readers:
                reader.close()
            temporary.unlink(missing_ok=True)
        if record_export:
            self.update(snapshot['id'], exported=True, exportRevision=snapshot['revision'],
                        exportName=dest.name, exportPath=str(dest), touched=timestamp())
        return dest

    def export_combined(self, snapshots, destination, checkpoint=lambda: None, progress=lambda d,t: None):
        dest = Path(destination).resolve()
        if dest.suffix.lower() != '.pdf' or (dest.is_relative_to(self.root) and not dest.is_relative_to(self.root / 'exports')):
            raise ValueError('请选择资料库素材目录以外的 PDF 路径。')
        if not snapshots:
            raise ValueError('请先选择课件。')
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_name('.' + uuid.uuid4().hex + '.part')
        pieces = []
        writer = PdfWriter()
        try:
            for i, snapshot in enumerate(snapshots):
                checkpoint()
                piece = self.root / 'exports' / ('.batch-' + uuid.uuid4().hex + '.pdf')
                pieces.append(piece)
                self.export_pdf(snapshot, piece, checkpoint, record_export=False)
                writer.append(str(piece), outline_item=f"{snapshot['day']} · {snapshot.get('note') or snapshot['title']}")
                progress(i+1, len(snapshots))
            writer.write(str(temp))
            with PdfReader(temp) as check:
                if len(check.pages) != sum(len(m['files']) for m in snapshots):
                    raise RuntimeError('合并页数校验失败。')
            checkpoint()
            temp.replace(dest)
        finally:
            writer.close()
            temp.unlink(missing_ok=True)
            for piece in pieces:
                piece.unlink(missing_ok=True)
        for snapshot in snapshots:
            self.update(snapshot['id'], exported=True, exportRevision=snapshot['revision'],
                        exportName=dest.name, exportPath=str(dest))
        return dest

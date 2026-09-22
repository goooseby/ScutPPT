"""Qt bridge: native dialogs and authentication stay outside the web UI."""
import copy
import datetime
import json
import re
import os
import shutil
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, QUrl, QTimer, QStandardPaths
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QDialog

from auth.browser_login import BrowserLoginDialog
from core.config import ConfigStore
from core.downloader import RuntimeCfg, make_session, fetch_schedules_in_range, get_ppt_urls, download_images, safe_name
from core.library import Library, IMAGE_EXTENSIONS, course_identity, offering_identity, natural_key, timestamp
from core.version import VERSION
from core.update import UpdateClient


class Control:
    def __init__(self):
        self.paused = threading.Event()
        self.paused.set()
        self.cancelled = threading.Event()

    def checkpoint(self):
        while True:
            if self.cancelled.is_set():
                raise InterruptedError('已取消')
            if self.paused.wait(0.15):
                if self.cancelled.is_set():
                    raise InterruptedError('已取消')
                return


class DesktopBridge(QObject):
    response = Signal(str, str)
    changed = Signal(str)
    taskChanged = Signal(str)
    notice = Signal(str)
    _progress = Signal(str, int, str)
    _finished = Signal(str, object, object)
    _update_reply = Signal(str, object, object)
    updateProgress = Signal(int, int)

    def __init__(self, base_dir, parent=None, library_root=None):
        super().__init__(parent)
        self.base = Path(base_dir).resolve()
        self.settings_file = self.base / 'app-settings.json'
        self.preferences = {}
        if self.settings_file.exists():
            self.preferences = json.loads(self.settings_file.read_text(encoding='utf-8'))
        self.library = Library(Path(library_root or self.preferences.get('libraryDir') or self.base / 'library'))
        self.app_cfg = ConfigStore(self.base).load()
        self.auth = None
        self.auth_generation = 0
        self.login_dialog = None
        self.courses = []
        self.scan_error = ''
        self.scanned = False
        self.controls = {}
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix='keye')
        self.updates = UpdateClient(Path(sys.executable).parent) if getattr(sys, 'frozen', False) else None
        self.update_package = None
        self.update_busy = False
        self.update_cancel = threading.Event()
        self.jobs = self.library.tasks()
        for task in self.jobs:
            if task['status'] in ('running', 'paused'):
                task.update(status='failed', error='程序上次退出时任务尚未完成，请重试。')
                self.library.task_put(task)
        self._progress.connect(self.on_progress)
        self._finished.connect(self.on_finished)
        self._update_reply.connect(self.finish_update_request)

    def settings(self):
        return {**{'exportMode': 'review', 'exportDir': self.app_cfg.download_dir or '',
                    'maxWorkers': self.app_cfg.max_workers, 'timeout': self.app_cfg.timeout,
                    'retries': self.app_cfg.retries, 'sleepMs': self.app_cfg.sleep_ms},
                **self.library.setting('settings', {}), 'libraryDir': str(self.library.root)}

    def snapshot(self):
        return {'materials': self.library.payload(), 'courseLibrary': self.library.courses(),
                'reviewQueue': self.library.setting('reviewQueue', []), 'tasks': self.jobs, 'settings': self.settings(),
                'lastMaterial': self.library.setting('lastMaterial'), 'loggedIn': self.auth is not None,
                'courses': self.courses, 'scanned': self.scanned, 'scanError': self.scan_error,
                'appVersion': VERSION,
                'packaged': self.updates is not None,
                'scanning': any(t['type']=='scan' and t['status']=='running' for t in self.jobs)}

    def publish(self):
        self.changed.emit(json.dumps(self.snapshot(), ensure_ascii=False))

    @Slot(str, str, str)
    def request(self, request_id, command, payload):
        try:
            if command in ('checkUpdate', 'downloadUpdate'):
                self.begin_update_request(request_id, command)
                return
            if command == 'login':
                # Return from the WebChannel IPC call before opening another web view.
                # A nested dialog.exec() here stalls Chromium until that dialog closes.
                QTimer.singleShot(0, lambda: self.begin_login(request_id))
                return
            result = self.dispatch(command, json.loads(payload))
            self.response.emit(request_id, json.dumps({'ok': True, 'result': result}, ensure_ascii=False))
        except Exception as exc:
            self.response.emit(request_id, json.dumps({'ok': False, 'error': self.clean_error(exc)}, ensure_ascii=False))

    def begin_update_request(self, request_id, command):
        if not self.updates:
            raise ValueError('源码运行不支持自动更新，请使用打包版本。')
        if self.update_busy:
            raise ValueError('更新操作正在进行，请稍候。')
        if command == 'downloadUpdate' and not self.updates.available:
            raise ValueError('请先检查更新。')
        self.update_busy = True
        self.update_cancel.clear()
        def work():
            try:
                if command == 'checkUpdate':
                    result = self.updates.check()
                    self.update_package = None
                else:
                    package = self.updates.download(
                        lambda done, total: self.updateProgress.emit(done, total),
                        self.update_cancel.is_set)
                    self.update_package = package
                    result = {'ready': True}
                self._update_reply.emit(request_id, result, None)
            except Exception as exc:
                self._update_reply.emit(request_id, None, self.clean_error(exc))
        self.executor.submit(work)

    def finish_update_request(self, request_id, result, error):
        self.update_busy = False
        self.response.emit(request_id, json.dumps(
            {'ok': error is None, 'result': result, 'error': error}, ensure_ascii=False))

    def begin_login(self, request_id):
        try:
            if self.login_dialog is not None:
                self.login_dialog.raise_()
                self.login_dialog.activateWindow()
                raise ValueError('登录窗口已打开，请先完成或关闭该窗口。')
            dialog = BrowserLoginDialog(self.parent())
            self.login_dialog = dialog

            def finished(result):
                try:
                    parsed = dialog.parsed
                    imported = bool((result == QDialog.Accepted or dialog.auth_detected) and parsed and parsed.cookie_str
                                    and parsed.user_id and parsed.tenant_id and parsed.jwt_token)
                    if imported:
                        self.auth = parsed
                        self.auth_generation += 1
                        self.courses = []
                        self.scanned = False
                    self.publish()
                    self.response.emit(request_id, json.dumps({'ok': True, 'result': imported}))
                except Exception as exc:
                    self.response.emit(request_id, json.dumps({'ok': False, 'error': self.clean_error(exc)}))
                finally:
                    self.login_dialog = None
                    dialog.deleteLater()

            dialog.finished.connect(finished)
            dialog.open()
        except Exception as exc:
            self.response.emit(request_id, json.dumps({'ok': False, 'error': self.clean_error(exc)}))

    @staticmethod
    def clean_error(exc):
        message = str(exc)
        message = re.sub(r'(?i)(token|authorization|cookie)(=|:)[^\s&]+', r'\1=[已隐藏]', message)
        message = re.sub(r'eyJ[\w-]+\.[\w-]+\.[\w-]+', '[登录凭据已隐藏]', message)
        return message[:700] or type(exc).__name__

    def runtime(self, start='', end=''):
        if not self.auth:
            raise ValueError('请先连接学校平台并导入登录态。')
        settings = self.settings()
        return RuntimeCfg(self.auth.cookie_str, self.auth.jwt_token, self.auth.authorization,
                          self.auth.user_id, self.auth.tenant_id, start, end,
                          timeout=int(settings['timeout']), retries=int(settings['retries']),
                          sleep_ms=int(settings['sleepMs']), max_workers=int(settings['maxWorkers']))

    def dispatch(self, command, data):
        if command == 'snapshot':
            return self.snapshot()
        if command == 'installUpdate':
            if not self.updates or not self.update_package or not self.update_package.is_file():
                raise ValueError('请先下载并校验更新。')
            if self.update_busy:
                raise ValueError('请等待更新下载完成。')
            if self.controls:
                raise ValueError('请等待后台任务完成后再更新。')
            stage = self.update_package.parent
            helper = Path(sys.executable).parent / 'KeyeUpdater.exe'
            if not helper.is_file():
                raise ValueError('更新助手缺失，请手动安装完整版本。')
            detached = stage / 'KeyeUpdater.exe'
            shutil.copy2(helper, detached)
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            subprocess.Popen([str(detached), '--install', str(self.updates.install_dir),
                              '--package', str(self.update_package),
                              '--sha256', self.updates.available['sha256'],
                              '--pid', str(os.getpid())], cwd=str(stage), creationflags=flags)
            QTimer.singleShot(0, self.parent().close)
            return True
        if command == 'openRelease':
            QDesktopServices.openUrl(QUrl(f'https://github.com/goooseby/ScutPPT/releases/latest'))
            return True
        if command == 'saveCourse':
            result = self.library.save_course(data['title'], data.get('id'), data.get('term', ''),
                                              data.get('coverStyle'), data.get('coverPalette'))
            self.publish()
            return result
        if command == 'courseCover':
            result = self.library.set_course_cover(data['id'], data.get('style', ''), data.get('palette', ''))
            self.publish()
            return result
        if command == 'assignCourse':
            self.library.assign(data['ids'], data.get('courseId'))
            self.publish()
            return True
        if command == 'reviewed':
            self.library.mark_reviewed(data['id'], data['revision'])
            self.publish()
            return True
        if command == 'reviewQueue':
            ids = list(dict.fromkeys(data['ids']))
            for mid in ids:
                if self.library.get(mid)['deleted']:
                    raise ValueError('请先恢复课件。')
            self.library.set_setting('reviewQueue', ids)
            self.publish()
            return True
        if command == 'materialNote':
            self.library.update(data['id'], note=str(data.get('note', '')).strip()[:120])
            self.publish()
            return True
        if command == 'batchExport':
            return self.batch_export(data)
        if command == 'quickExport':
            m = self.library.get(data['id'])
            root = self.ensure_export_root()
            if root is None:
                return False
            destination = self.unique_export_path(m, root)
            self.start_export(m['id'], destination)
            return str(destination)
        if command == 'logout':
            self.auth = None
            self.auth_generation += 1
            self.courses = []
            self.scanned = False
            self.publish()
            return True
        if command == 'scan':
            if any(t['type']=='scan' and t['status']=='running' for t in self.jobs):
                raise ValueError('正在扫描，请稍候。')
            start, end = data['start'], data['end']
            a, b = datetime.date.fromisoformat(start), datetime.date.fromisoformat(end)
            if a > b:
                raise ValueError('开始日期不能晚于结束日期。')
            cfg = self.runtime(start, end)
            self.scanned = False
            self.scan_error = ''
            def work(control, progress):
                with make_session(cfg) as session:
                    found = fetch_schedules_in_range(cfg, session)
                control.checkpoint()
                for c in found:
                    c['id'] = course_identity(c, cfg.user_id, cfg.tenant_id)
                    c['groupId'] = offering_identity(c, cfg.user_id, cfg.tenant_id)
                    c['topic'] = '课堂课件'
                return found
            self.submit('scan', f'扫描课表 · {start} 至 {end}', work, authGeneration=self.auth_generation)
            return True
        if command == 'download':
            wanted = set(data.get('ids', []))
            courses = [c for c in self.courses if c['id'] in wanted]
            if not courses:
                raise ValueError('请先扫描并选择课程。')
            self.runtime()
            if data.get('direct') and self.ensure_export_root() is None:
                return False
            for c in courses:
                self.download(c, bool(data.get('direct')))
            return bool(courses)
        if command == 'selection':
            self.library.set_selection(data['id'], data['excluded'], data['revision'])
            self.publish()
            return True
        if command == 'openMaterial':
            m = self.library.get(data['id'])
            if m['deleted']:
                raise ValueError('请先恢复课件。')
            self.library.set_setting('lastMaterial', m['id'])
            return True
        if command == 'lastPage':
            m = self.library.get(data['id'])
            self.library.update(m['id'], lastPage=max(1, min(m['pages'], int(data['page']))))
            return True
        if command == 'trash':
            self.library.update(data['id'], deleted=bool(data['deleted']))
            self.publish()
            return True
        if command == 'export':
            m = self.library.get(data['id'])
            configured = self.configured_export_root()
            if configured is not None:
                try:
                    self.prepare_export_root(configured)
                except OSError:
                    configured = self.ensure_export_root()
                    if configured is None:
                        return False
            directory = self.export_directory(m, configured) if configured else self.suggested_export_root()
            if configured:
                directory.mkdir(parents=True, exist_ok=True)
            default = directory / (safe_name(data.get('name') or f"{m['day']}_{m['title']}").removesuffix('.pdf') + '.pdf')
            filename, _ = QFileDialog.getSaveFileName(self.parent(), '导出课件 PDF', str(default), 'PDF 文件 (*.pdf)')
            if not filename:
                return False
            if configured is None:
                self.save_export_root(Path(filename).parent)
            self.start_export(m['id'], Path(filename))
            return True
        if command == 'import':
            return self.choose_import(data.get('kind', 'files'), data.get('courseId'))
        if command == 'task':
            task = next((t for t in self.jobs if t['id']==data['id']), None)
            if not task:
                raise ValueError('任务不存在。')
            action = data['action']
            control = self.controls.get(task['id'])
            if action == 'retry':
                if task['status'] not in ('failed', 'cancelled'):
                    raise ValueError('仅可重试失败或取消的任务。')
                if task['type'] == 'download':
                    cfg = self.runtime()
                    c = task['course']
                    if course_identity(c, cfg.user_id, cfg.tenant_id) != c['id']:
                        raise ValueError('请用获取该课件时的学校账号登录，或重新扫描。')
                    if task.get('direct') and self.ensure_export_root() is None:
                        return False
                    self.download(c, task.get('direct', False))
                elif task['type'] == 'export':
                    return self.dispatch('export', {'id': task['materialId']})
                elif task['type'] == 'import':
                    self.import_paths(task['paths'], task.get('folder', False), task.get('courseId'))
                elif task['type'] == 'batch':
                    return self.batch_export({'ids': task['materialIds'], 'mode': task['mode']})
                else:
                    raise ValueError('请在获取课件页面重新扫描。')
            elif control and task['status'] in ('running', 'paused'):
                if action == 'cancel':
                    control.cancelled.set()
                    control.paused.set()
                    task['message'] = '正在取消，等待正在写入的文件处理结束…'
                elif task['status'] == 'running':
                    control.paused.clear()
                    task['status'] = 'paused'
                else:
                    control.paused.set()
                    task['status'] = 'running'
                self.library.task_put(task)
                self.publish()
            return True
        if command == 'openExport':
            path = Path(self.library.get(data['id'])['exportPath'])
            if not path.is_file():
                raise ValueError('导出文件不存在，可能已被移动。请重新导出。')
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
            return True
        if command == 'openLibrary':
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.library.root)))
            return True
        if command == 'settings':
            values = self.settings()
            if 'exportMode' in data:
                if data['exportMode'] not in ('review', 'direct'):
                    raise ValueError('获取方式无效。')
                values['exportMode'] = data['exportMode']
            for key, lo, hi in [('maxWorkers',1,32),('timeout',5,600),('retries',1,10),('sleepMs',0,5000)]:
                if key in data:
                    value = int(data[key])
                    if not lo <= value <= hi:
                        raise ValueError(f'{key} 的值超出范围。')
                    values[key] = value
            self.library.set_setting('settings', values)
            self.publish()
            return True
        if command == 'chooseExportDir':
            path = QFileDialog.getExistingDirectory(self.parent(), '选择默认 PDF 导出目录',
                                                    str(self.configured_export_root() or self.suggested_export_root()))
            if path:
                self.save_export_root(Path(path))
            return bool(path)
        if command == 'chooseLibrary':
            if self.controls:
                raise ValueError('请等待任务结束后再切换资料库。')
            path = QFileDialog.getExistingDirectory(self.parent(), '选择或创建资料库（不会移动当前资料）', str(self.library.root.parent))
            if not path:
                return False
            self.library = Library(Path(path))
            self.preferences['libraryDir'] = str(self.library.root)
            temporary = self.settings_file.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.preferences, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(self.settings_file)
            self.jobs = self.library.tasks()
            for t in self.jobs:
                if t['status'] in ('running', 'paused'):
                    t.update(status='failed', error='任务未完成，请重试。')
                    self.library.task_put(t)
            self.publish()
            return True
        raise ValueError('不支持的操作。')

    def submit(self, kind, title, work, **metadata):
        task = {'id': uuid.uuid4().hex, 'type': kind, 'title': title, 'status': 'running',
                'progress': 0, 'message': '准备中', 'error': '', 'created': timestamp(), **metadata}
        control = Control()
        self.controls[task['id']] = control
        self.jobs.append(task)
        self.library.task_put(task)
        def run():
            try:
                result = work(control, lambda pct, msg: self._progress.emit(task['id'], pct, msg))
                self._finished.emit(task['id'], result, None)
            except Exception as exc:
                self._finished.emit(task['id'], None, exc)
        self.executor.submit(run)
        self.publish()
        return task

    @Slot(str, int, str)
    def on_progress(self, task_id, percent, message):
        task = next(t for t in self.jobs if t['id']==task_id)
        task.update(progress=percent, message=message)
        self.taskChanged.emit(json.dumps(task, ensure_ascii=False))

    @Slot(str, object, object)
    def on_finished(self, task_id, result, error):
        task = next(t for t in self.jobs if t['id']==task_id)
        self.controls.pop(task_id, None)
        if error:
            task.update(status='cancelled' if isinstance(error, InterruptedError) else 'failed', error=self.clean_error(error))
            if task['type']=='scan':
                self.scan_error = task['error']
        else:
            task.update(status='done', progress=100, message='已完成')
            if task['type']=='scan':
                if task.get('authGeneration') == self.auth_generation:
                    self.courses = result
                    self.scanned = True
                    for lecture in result:
                        existing = self.library.find_source(lecture['id'])
                        if existing:
                            self.library.attach_platform(existing['id'], lecture, self.auth.user_id, self.auth.tenant_id)
                else:
                    task.update(status='cancelled', message='登录账号已变化，请重新扫描。')
            elif task['type'] in ('download', 'import'):
                task['materialId'] = result[0]['id'] if isinstance(result, list) else result['id']
                if task.get('direct'):
                    m = result
                    destination = self.export_directory(m) / (safe_name(f"{m['day']}_{m['title']}")+f"_{m['id'][:6]}.pdf")
                    # Automatic export never overwrites an existing result.
                    if destination.exists():
                        destination = destination.with_stem(destination.stem+'_'+uuid.uuid4().hex[:6])
                    try:
                        self.start_export(m['id'], destination)
                    except Exception as exc:
                        task['message'] = '下载完成，但自动导出未能开始。请打开课件手动导出。'
                        task['error'] = self.clean_error(exc)
        self.library.task_put(task)
        self.publish()
        self.notice.emit(f"{task['title']}：" + ('已完成' if not error else task['error']))

    def download(self, course, direct=False):
        existing = self.library.find_source(course['id'])
        if existing:
            if existing['deleted']:
                self.library.update(existing['id'], deleted=False)
                self.publish()
            return
        if any(t.get('sourceKey')==course['id'] and t['status'] in ('running', 'paused') for t in self.jobs):
            return
        cfg = self.runtime()
        library = self.library
        def work(control, progress):
            directory = library.root / 'temporary' / course['id'].split(':')[-1]
            directory.mkdir(parents=True, exist_ok=True)
            with make_session(cfg) as session:
                control.checkpoint()
                urls = get_ppt_urls(cfg, session, course['course_id'], course['sub_id'])
                if not urls:
                    raise ValueError('这节课没有可获取的 PPT 页面。')
                files = download_images(cfg, session, urls, directory, checkpoint_fn=control.checkpoint,
                    progress_fn=lambda d,t: progress(int(d/t*80), f'下载页面 {d}/{t}'))
            # Do not silently generate an incomplete PDF when any page failed.
            from PIL import Image
            for file in files:
                control.checkpoint()
                if not file.exists():
                    raise RuntimeError('部分页面下载失败，点击重试可继续下载；尚未生成不完整课件。')
                with Image.open(file) as image:
                    image.verify()
            m = library.prepare_images(files, course['title'], course['day'], course['id'], control.checkpoint,
                                       lambda d,t: progress(80+int(d/t*20), f'建立预览 {d}/{t}'))
            m = library.attach_platform(m['id'], course, cfg.user_id, cfg.tenant_id)
            # These are this task's temporary files, now safely copied into materials.
            for file in files:
                file.unlink(missing_ok=True)
            return m
        self.submit('download', course['title']+' · '+course['day'], work, course=copy.deepcopy(course),
                    sourceKey=course['id'], direct=direct)

    def suggested_export_root(self):
        documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        return Path(documents) if documents else Path.home()

    def configured_export_root(self):
        value = str(self.settings().get('exportDir') or '').strip()
        return Path(value) if value else None

    def save_export_root(self, root):
        root = Path(root).resolve()
        self.prepare_export_root(root)
        values = self.settings()
        values['exportDir'] = str(root)
        values.pop('libraryDir', None)
        self.library.set_setting('settings', values)
        self.publish()
        return root

    @staticmethod
    def prepare_export_root(root):
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        probe = root / f'.keye-write-test-{uuid.uuid4().hex}.tmp'
        try:
            probe.write_bytes(b'keye')
        finally:
            probe.unlink(missing_ok=True)
        return root

    def ensure_export_root(self):
        root = self.configured_export_root()
        if root is not None:
            try:
                return self.prepare_export_root(root)
            except OSError:
                title = '原默认目录不可用，请重新选择 PDF 保存目录'
        else:
            title = '首次导出：选择默认 PDF 保存目录'
        path = QFileDialog.getExistingDirectory(self.parent(), title, str(self.suggested_export_root()))
        if not path:
            return None
        try:
            return self.save_export_root(Path(path))
        except OSError as exc:
            raise ValueError(f'无法使用所选目录：{exc}') from exc

    def export_directory(self, material, root=None):
        course = next((c for c in self.library.courses() if c['id'] == material.get('courseId')), None)
        root = Path(root or self.configured_export_root() or self.suggested_export_root())
        if not course:
            return root / '未归类'
        if course.get('term'):
            root /= safe_name(course['term'])
        return root / (safe_name(course['title']) + '_' + course['id'][-6:])

    def unique_export_path(self, material, root=None):
        directory = self.export_directory(material, root)
        discriminator = material.get('lectureId') or material['id'][:6]
        stem = safe_name(f"{material['day']}_{material.get('note') or material['title']}_{discriminator}")
        destination = directory / f'{stem}.pdf'
        number = 2
        while destination.exists():
            destination = directory / f'{stem} ({number}).pdf'
            number += 1
        return destination

    def batch_export(self, data):
        library = self.library
        snapshots = [library.export_snapshot(mid) for mid in dict.fromkeys(data['ids'])]
        snapshots.sort(key=lambda m: (m['day'], natural_key(m.get('lectureId', '')), m['id']))
        if not snapshots:
            raise ValueError('请选择需要导出的课件。')
        mode = data.get('mode', 'separate')
        if mode not in ('separate', 'combined'):
            raise ValueError('导出方式无效。')
        quick = bool(data.get('quick'))
        if mode == 'combined':
            configured = self.configured_export_root()
            if configured is not None:
                try:
                    self.prepare_export_root(configured)
                except OSError:
                    configured = self.ensure_export_root()
                    if configured is None:
                        return False
            directory = self.export_directory(snapshots[0], configured) if configured else self.suggested_export_root()
            if configured:
                directory.mkdir(parents=True, exist_ok=True)
            filename, _ = QFileDialog.getSaveFileName(self.parent(), '合并选中课件',
                str(directory / '课程选集.pdf'), 'PDF 文件 (*.pdf)')
            if filename and configured is None:
                self.save_export_root(Path(filename).parent)
        elif quick:
            root = self.ensure_export_root()
            filename = str(root) if root is not None else ''
        else:
            configured = self.configured_export_root()
            filename = QFileDialog.getExistingDirectory(self.parent(), '选择导出根目录（自动按课程整理）',
                                                        str(configured or self.suggested_export_root()))
            if filename and configured is None:
                self.save_export_root(Path(filename))
        if not filename:
            return False
        destinations = [self.unique_export_path(m, filename) for m in snapshots]
        def work(control, progress):
            if mode == 'combined':
                return str(library.export_combined(snapshots, filename, control.checkpoint,
                    lambda d,t: progress(int(d/t*95), f'合并课件 {d}/{t}')))
            for i, (m, dest) in enumerate(zip(snapshots, destinations)):
                library.export_pdf(m, dest, control.checkpoint,
                    lambda d,t: progress(int((i+d/t)/len(snapshots)*95), f'导出课件 {i+1}/{len(snapshots)}'))
            return filename
        self.submit('batch', f'导出 {len(snapshots)} 份课件', work,
                    materialIds=[m['id'] for m in snapshots], mode=mode, materialId=snapshots[0]['id'])
        return True

    def start_export(self, mid, destination):
        if any(t.get('materialId')==mid and t['type']=='export' and t['status'] in ('running', 'paused') for t in self.jobs):
            raise ValueError('这份课件正在导出，请等待完成。')
        library = self.library
        snapshot = library.export_snapshot(mid)
        def work(control, progress):
            return str(library.export_pdf(snapshot, destination, control.checkpoint,
                        lambda d,t: progress(int(d/t*95), f'合并页面 {d}/{t}')))
        return self.submit('export', snapshot['title']+' · PDF', work, materialId=mid,
                           output=str(destination), pageCount=len(snapshot['files']))

    def choose_import(self, kind, course_id=None):
        if kind == 'folder':
            path = QFileDialog.getExistingDirectory(self.parent(), '导入图片目录或旧版下载目录')
            if not path:
                return False
            self.import_paths([path], True, course_id)
        else:
            paths, _ = QFileDialog.getOpenFileNames(self.parent(), '导入 PDF 或图片', '',
                '课件文件 (*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)')
            if not paths:
                return False
            self.import_paths(paths, course_id=course_id)
        return True

    def import_paths(self, paths, folder=False, course_id=None):
        library = self.library
        def work(control, progress):
            groups = []
            if folder:
                root = Path(paths[0]).resolve()
                if root == library.root or library.root.is_relative_to(root) or root.is_relative_to(library.root):
                    raise ValueError('不能把当前资料库目录重新导入自身。')
                images_by_parent = {}
                pdfs = []
                for p in root.rglob('*'):
                    control.checkpoint()
                    if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
                        images_by_parent.setdefault(p.parent, []).append(p)
                    elif p.is_file() and p.suffix.lower()=='.pdf':
                        pdfs.append(p)
                groups = [sorted(files, key=natural_key) for files in images_by_parent.values()]
                groups.extend([[p] for p in sorted(pdfs, key=natural_key)
                               if p.parent not in images_by_parent and p.parent/'images' not in images_by_parent])
            else:
                groups = [[Path(p)] for p in paths if Path(p).suffix.lower()=='.pdf']
                images = [Path(p) for p in paths if Path(p).suffix.lower() in IMAGE_EXTENSIONS]
                if images:
                    groups.append(sorted(images, key=natural_key))
            if not groups:
                raise ValueError('没有找到可导入的 PDF 或图片。')
            imported = []
            for index, group in enumerate(groups):
                control.checkpoint()
                def report(d,t):
                    progress(int((index+d/t)/len(groups)*100), f'导入资料 {index+1}/{len(groups)} · 页面 {d}/{t}')
                if group[0].suffix.lower()=='.pdf':
                    m = library.prepare_pdf(group[0], control.checkpoint, report)
                else:
                    title = group[0].parent.parent.name if group[0].parent.name=='images' else group[0].parent.name
                    m = library.prepare_images(group, title, datetime.date.today().isoformat(),
                                               checkpoint=control.checkpoint, progress=report)
                if course_id:
                    library.assign([m['id']], course_id)
                    m = library.get(m['id'])
                imported.append(m)
            return imported
        self.submit('import', '导入本地资料', work, paths=list(map(str, paths)), folder=folder, courseId=course_id)

    def shutdown(self):
        self.update_cancel.set()
        for control in self.controls.values():
            control.cancelled.set()
            control.paused.set()
        self.executor.shutdown(wait=False, cancel_futures=True)

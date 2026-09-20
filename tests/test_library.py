import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
import pypdfium2 as pdfium

from core.library import Library, course_identity


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = Library(self.root / 'library')
        self.files = []
        for i, color in enumerate(('red','green','blue'), 1):
            file = self.root / f'{i}.png'
            Image.new('RGB', (640,360), color).save(file)
            self.files.append(file)
        self.m = self.library.prepare_images(self.files, '真实文件测试', '2026-09-05')

    def tearDown(self):
        self.temp.cleanup()

    def test_course_identity_assignment_and_explicit_review(self):
        first = {'course_id': 'one', 'sub_id': '1', 'title': '同名课程'}
        second = {**first, 'sub_id': '2'}
        a = self.library.attach_platform(self.m['id'], first, 'user', 'school')
        other = self.library.prepare_images(self.files[:1], '同名课程', '2026-09-06')
        b = self.library.attach_platform(other['id'], second, 'user', 'school')
        self.assertEqual(a['courseId'], b['courseId'])
        third = self.library.prepare_images(self.files[:1], '同名课程', '2026-09-07')
        c = self.library.attach_platform(third['id'], second, 'another', 'school')
        self.assertNotEqual(a['courseId'], c['courseId'])
        self.library.mark_reviewed(a['id'], 0)
        self.assertEqual(self.library.get(a['id'])['reviewRevision'], 0)
        self.assertFalse(self.library.get(a['id'])['exported'])
        self.library.set_selection(a['id'], [2], 0)
        changed = self.library.get(a['id'])
        self.assertNotEqual(changed['revision'], changed['reviewRevision'])
        with self.assertRaises(ValueError):
            self.library.mark_reviewed(a['id'], 0)
        custom = self.library.save_course('手动课程', term='2026 秋季')
        styled = self.library.set_course_cover(custom['id'], 'orbit', 'ocean')
        self.assertEqual((styled['coverStyle'], styled['coverPalette']), ('orbit', 'ocean'))
        renamed = self.library.save_course('手动课程（改名）', custom['id'], '2026 秋季')
        self.assertEqual((renamed['coverStyle'], renamed['coverPalette']), ('orbit', 'ocean'))
        self.library.assign([a['id']], custom['id'])
        again = self.library.attach_platform(a['id'], first, 'user', 'school')
        self.assertEqual(again['courseId'], custom['id'])
        self.assertEqual(again['excluded'], [2])

    def test_old_database_backup_and_idempotent_upgrade(self):
        self.library.set_selection(self.m['id'], [2], 0)
        with self.library.connection() as con:
            con.execute('PRAGMA user_version=1')
        upgraded = Library(self.library.root)
        self.assertTrue((self.library.root / 'before-courses.sqlite').is_file())
        self.assertEqual(upgraded.get(self.m['id'])['excluded'], [2])
        self.assertIsNone(upgraded.get(self.m['id']).get('courseId'))
        self.assertEqual(Library(self.library.root).get(self.m['id'])['revision'], 1)

    def test_combined_export_bookmarks_and_cancel(self):
        other = self.library.prepare_images(self.files[:1], '第二课', '2026-09-06')
        self.library.set_selection(self.m['id'], [2], 0)
        snapshots = [self.library.export_snapshot(self.m['id']), self.library.export_snapshot(other['id'])]
        path = self.root / 'combined.pdf'
        self.library.export_combined(snapshots, path)
        with PdfReader(path) as reader:
            self.assertEqual(len(reader.pages), 3)
            self.assertEqual(len(reader.outline), 2)
            self.assertEqual(reader.get_destination_page_number(reader.outline[1]), 2)
        before = path.read_bytes()
        def cancel():
            raise InterruptedError()
        with self.assertRaises(InterruptedError):
            self.library.export_combined(snapshots, path, cancel)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(list((self.library.root / 'exports').glob('.batch-*')))

    def test_selection_persists_and_export_preserves_order(self):
        self.library.set_selection(self.m['id'], [2], 0)
        library = Library(self.library.root)
        snapshot = library.export_snapshot(self.m['id'])
        self.assertEqual(library.get(self.m['id'])['excluded'], [2])
        result = library.export_pdf(snapshot, self.root / 'selected.pdf')
        reader = PdfReader(result)
        self.assertEqual(len(reader.pages), 2)
        reader.close()
        doc = pdfium.PdfDocument(str(result))
        colors = []
        for i in range(len(doc)):
            page = doc[i]
            bitmap = page.render(scale=0.5)
            image = bitmap.to_pil()
            colors.append(image.getpixel((10,10))[:3])
            bitmap.close()
            page.close()
        doc.close()
        self.assertGreater(colors[0][0], 240)
        self.assertGreater(colors[1][2], 240)
        self.assertTrue(all(p.exists() for p in self.files))
        self.assertTrue(all(library.resolve(p['original']).exists() for p in self.m['files']))

    def test_pdf_import_uses_original_pages(self):
        source = self.library.export_pdf(self.library.export_snapshot(self.m['id']), self.root / 'source.pdf')
        imported = self.library.prepare_pdf(source)
        self.assertEqual(imported['pages'], 3)
        self.library.set_selection(imported['id'], [1,3], 0)
        output = self.library.export_pdf(self.library.export_snapshot(imported['id']), self.root / 'one.pdf')
        a, b = PdfReader(source), PdfReader(output)
        self.assertEqual(len(b.pages), 1)
        self.assertEqual(a.pages[1].get_contents().get_data(), b.pages[0].get_contents().get_data())
        a.close(); b.close()

    def test_concurrent_edit_does_not_mark_new_version_exported(self):
        snapshot = self.library.export_snapshot(self.m['id'])
        self.library.set_selection(self.m['id'], [1], 0)
        self.library.export_pdf(snapshot, self.root / 'snapshot.pdf')
        m = self.library.get(self.m['id'])
        self.assertNotEqual(m['revision'], m['exportRevision'])
        with self.assertRaises(ValueError):
            self.library.set_selection(m['id'], [2], 0)

    def test_cancel_keeps_previous_output_and_all_excluded_is_rejected(self):
        output = self.root / 'keep.pdf'
        output.write_bytes(b'previous file')
        def cancel():
            raise InterruptedError()
        with self.assertRaises(InterruptedError):
            self.library.export_pdf(self.library.export_snapshot(self.m['id']), output, cancel)
        self.assertEqual(output.read_bytes(), b'previous file')
        self.library.set_selection(self.m['id'], [1,2,3], 0)
        with self.assertRaises(ValueError):
            self.library.export_snapshot(self.m['id'])

    def test_trash_paths_and_account_identity(self):
        self.library.update(self.m['id'], deleted=True)
        with self.assertRaises(ValueError):
            self.library.export_snapshot(self.m['id'])
        self.library.update(self.m['id'], deleted=False)
        self.assertEqual(len(self.library.export_snapshot(self.m['id'])['files']), 3)
        with self.assertRaises(ValueError):
            self.library.resolve('../outside')
        c = {'course_id':'1','sub_id':'2'}
        self.assertNotEqual(course_identity(c,'a','t'),course_identity(c,'b','t'))

    def test_failed_import_cleans_only_its_new_directory(self):
        before = set((self.library.root / 'materials').iterdir())
        broken = self.root / 'broken.png'
        broken.write_bytes(b'not an image')
        with self.assertRaises(Exception):
            self.library.prepare_images([self.files[0], broken], 'broken', '2026-09-05')
        self.assertEqual(set((self.library.root / 'materials').iterdir()), before)
        self.assertTrue(broken.exists())
        self.assertTrue(self.files[0].exists())


if __name__ == '__main__':
    unittest.main()

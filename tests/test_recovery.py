import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from PIL import Image
from core.downloader import RuntimeCfg, fetch_schedules_in_range, download_course_to_pdf


class Response:
    status_code = 200
    headers = {'Content-Type': 'application/json'}

    def __init__(self, data=None, content=b''):
        self.data = data
        self.content = content

    def json(self):
        return self.data

    def iter_content(self, size):
        yield self.content


class FakePlatform:
    def __init__(self):
        self.ranges = []
        buf = io.BytesIO()
        Image.new('RGB', (64, 48), 'blue').save(buf, format='PNG')
        self.png = buf.getvalue()

    def get(self, url, **kwargs):
        if 'get-week-schedules' in url:
            query = parse_qs(urlsplit(url).query)
            self.ranges.append((query['start_at'][0], query['end_at'][0]))
            return Response({'result': {'list': [{'day': '2025-09-01', 'course': [
                {'id': '1', 'course_id': '2', 'course_title': '测试课程'}
            ]}]}})
        if 'search-ppt' in url:
            return Response({'list': [
                {'content': json.dumps({'pptimgurl': f'https://example.test/{n}.png'})}
                for n in (1, 2, 1)
            ]})
        return Response(content=self.png)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.cfg = RuntimeCfg('', 'test', 'Bearer test', '1', '2',
                              '2025-09-01', '2025-09-10', sleep_ms=0, max_workers=2)
        self.session = FakePlatform()

    def test_scan_and_parallel_pdf_download(self):
        courses = fetch_schedules_in_range(self.cfg, self.session)
        self.assertEqual(len(courses), 1)
        self.assertEqual(self.session.ranges, [('2025-09-01', '2025-09-07'),
                                              ('2025-09-08', '2025-09-10')])
        with tempfile.TemporaryDirectory() as directory:
            with patch('core.downloader._get_thread_session', return_value=self.session):
                pdf = download_course_to_pdf(self.cfg, self.session, courses[0],
                                             Path(directory), keep_images=False)
            contents = pdf.read_bytes()
            self.assertTrue(contents.startswith(b'%PDF'))
            self.assertIn(b'/Count 2', contents)
            self.assertFalse((pdf.parent / 'images').exists())
            with patch('core.downloader.get_ppt_urls', side_effect=AssertionError('must skip')):
                self.assertEqual(download_course_to_pdf(
                    self.cfg, self.session, courses[0], Path(directory), False), pdf)

    def test_cancel_cleans_unfinished_course(self):
        course = {'title': 'demo', 'day': '2025-09-01', 'course_id': '2', 'sub_id': '1'}
        def cancel():
            raise InterruptedError('cancelled')
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(InterruptedError):
                download_course_to_pdf(self.cfg, self.session, course, Path(directory),
                                       True, checkpoint_fn=cancel)
            self.assertFalse((Path(directory) / 'demo_2' / '2025-09-01_1').exists())


if __name__ == '__main__':
    unittest.main()

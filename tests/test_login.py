"""Regression: a real browser login dialog must load while its WebChannel call is pending."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from shiboken6 import delete

from app import KeyeWindow
from auth.browser_login import BrowserLoginDialog, CookieCollector


def wait(ms=30):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def until(predicate, seconds=8):
    deadline = time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():
            return
        wait()
    raise AssertionError('Timed out waiting for login condition')


def cookie(name, value, domain='.video.jw.scut.edu.cn'):
    item = QNetworkCookie(name.encode(), value.encode())
    item.setDomain(domain)
    item.setPath('/')
    return item


class LoginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_real_login_page_loads_before_channel_request_returns(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/'login.html'
            file.write_text('<html><body><h1>School sign in fixture</h1><input name="account"></body></html>')
            window = KeyeWindow(tmp, Path(tmp)/'library')
            window.show()
            loaded = []
            window.web.loadFinished.connect(loaded.append)
            results = []
            window.bridge.response.connect(lambda key, value: results.append(json.loads(value)) if key=='login-test' else None)
            dialog = None
            try:
                until(lambda: bool(loaded))
                with patch('auth.browser_login.TARGET_URL', QUrl.fromLocalFile(str(file)).toString()):
                    # The transport call originates in the actual app renderer, not a direct Python call.
                    window.page.runJavaScript("desktop.request('login-test','login','{}')")
                    until(lambda: window.bridge.login_dialog is not None)
                    dialog = window.bridge.login_dialog
                    until(lambda: dialog.load_state=='ready')
                    self.assertTrue(dialog.isVisible())
                    self.assertEqual(results, [])  # Awaiting user input; page has already loaded.
                    contents = []
                    dialog.page.toPlainText(contents.append)
                    until(lambda: bool(contents))
                    self.assertIn('School sign in fixture', contents[0])
                    dialog.on_extract()
                    self.assertIsNone(dialog.parsed)
                    self.assertTrue(dialog.isVisible())
                    token='eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.signature'
                    dialog.collector._on_cookie_added(cookie('JWTUser', quote(json.dumps({'id':5,'tenant_id':9}))))
                    dialog.collector._on_cookie_added(cookie('_token', token))
                    until(lambda: dialog.auth_detected)
                    self.assertFalse(dialog.btn_extract.isEnabled())
                    until(lambda: bool(results))
                    self.assertTrue(results[-1]['result'])
                    self.assertEqual(window.bridge.auth.user_id, '5')
                    self.assertEqual(window.bridge.auth.jwt_token, token)
                    self.assertIsNone(window.bridge.login_dialog)
            finally:
                if window.bridge.login_dialog:
                    window.bridge.login_dialog.reject()
                window.close()
                delete(window.page)
                delete(window.profile)
                wait()

    def test_failed_page_reports_error_and_retry_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing=Path(tmp)/'missing.html'
            with patch('auth.browser_login.TARGET_URL', QUrl.fromLocalFile(str(missing)).toString()):
                dialog=BrowserLoginDialog()
                dialog.show()
                try:
                    until(lambda: dialog.load_state=='failed')
                    self.assertIn('失败', dialog.load_label.text())
                    self.assertFalse(dialog.load_progress.isVisible())
                    self.assertTrue(dialog.btn_retry.isEnabled())
                    missing.write_text('<html><body>Recovered</body></html>')
                    dialog.retry_load()
                    until(lambda: dialog.load_state=='ready')
                    dialog.on_renderer_terminated(QWebEnginePage.RenderProcessTerminationStatus.CrashedTerminationStatus, 1)
                    self.assertIn('异常退出', dialog.load_label.text())
                finally:
                    dialog.close()
                    delete(dialog)

    def test_cookie_domains_removal_and_incomplete_import(self):
        collector=CookieCollector(QWebEngineProfile.defaultProfile())
        try:
            video=cookie('_token','video-value')
            collector._on_cookie_added(video)
            collector._on_cookie_added(cookie('_token','sso-value','sso.scut.edu.cn'))
            collector._on_cookie_added(cookie('_token','unrelated','not-scut.edu.cn'))
            self.assertEqual(collector.cookies['_token'], 'video-value')
            collector._on_cookie_added(cookie('_token','new-value'))
            collector._on_cookie_removed(video)  # Removal of an old value must not erase its replacement.
            self.assertEqual(collector.cookies['_token'], 'new-value')
            collector._on_cookie_removed(cookie('_token','new-value'))
            self.assertNotIn('_token', collector.cookies)
        finally:
            delete(collector)


if __name__=='__main__':
    unittest.main()

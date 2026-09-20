import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


class GuiTests(unittest.TestCase):
    def test_windows_and_embedded_browser(self):
        from PySide6.QtCore import QEventLoop, QTimer
        from PySide6.QtWidgets import QApplication
        from core.config import AppConfig
        from main import MainWindow
        from ui.settings_dialog import SettingsDialog
        from ui.theme import apply_app_theme
        from auth.browser_login import BrowserLoginDialog

        app = QApplication.instance() or QApplication([])
        apply_app_theme(app)
        with patch('main.ConfigStore.load', return_value=AppConfig(download_dir='.')):
            window = MainWindow()
        settings = SettingsDialog(window.app_cfg, window)
        with patch('auth.browser_login.TARGET_URL', 'about:blank'):
            login = BrowserLoginDialog(window)
        loop = QEventLoop()
        loaded = []
        login.web.loadFinished.connect(lambda ok: (loaded.append(ok), loop.quit()))
        login.web.setHtml('<html><body>GetPPTApp browser check</body></html>')
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(15000)
        window.show()
        settings.show()
        login.show()
        loop.exec()
        timer.stop()
        login.close()
        settings.close()
        window.close()
        app.processEvents()
        self.assertTrue(loaded and loaded[-1], 'Embedded browser failed to load local HTML')


if __name__ == '__main__':
    unittest.main()

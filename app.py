"""课页: the production desktop entry point. Legacy downloader remains in main.py."""
import os
import sys
import ctypes
from pathlib import Path
from core.webengine import configure_webengine

# The school site rejects traffic through many system proxies as off-campus.
# Qt WebEngine's GPU compositor is also unreliable on some Windows machines
# with virtual display adapters.  The UI is deliberately light enough for the
# software compositor, which avoids DirectComposition/shared-texture failures.
configure_webengine()

from PySide6.QtCore import QLockFile, QTimer, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from core.desktop import DesktopBridge


class LocalPage(QWebEnginePage):
    def __init__(self, profile, parent, entry):
        super().__init__(profile, parent)
        self.entry = entry

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        # Privileged native bridge is attached only to our packaged UI.
        return url.isLocalFile() and Path(url.toLocalFile()).resolve() == self.entry


class KeyeWindow(QMainWindow):
    def __init__(self, base=None, library_root=None):
        super().__init__()
        resource_base = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)).resolve()
        default_base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
        self.base = Path(base or default_base).resolve()
        self.setWindowTitle('课页 · 个人课件资料库')
        self.setWindowIcon(QIcon(str(resource_base / 'assets' / 'app-icon.ico')))
        self.resize(1440, 960)
        self.web = QWebEngineView(self)
        self.web.settings().setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, False)
        self.web.settings().setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, False)
        self.profile = QWebEngineProfile(self)
        self.entry = resource_base / 'web' / 'index.html'
        self.page = LocalPage(self.profile, self.web, self.entry.resolve())
        self.web.setPage(self.page)
        self.channel = QWebChannel(self.page)
        self.bridge = DesktopBridge(self.base, self, library_root)
        self.channel.registerObject('desktop', self.bridge)
        self.page.setWebChannel(self.channel)
        self.setCentralWidget(self.web)
        self.web.setUrl(QUrl.fromLocalFile(str(self.entry)))
        self.closing = False
        self.close_timer = QTimer(self)
        self.close_timer.setInterval(250)
        self.close_timer.timeout.connect(self.finish_close)

    def finish_close(self):
        if not self.bridge.controls:
            self.close_timer.stop()
            self.close()

    def closeEvent(self, event):
        if self.bridge.controls:
            if not self.closing:
                result = QMessageBox.question(self, '退出课页', '仍有后台任务。取消任务并退出？已完成的资料与筛选记录会保留。')
                if result != QMessageBox.Yes:
                    event.ignore()
                    return
                self.closing = True
                for control in self.bridge.controls.values():
                    control.cancelled.set()
                    control.paused.set()
                self.bridge.notice.emit('正在取消任务，等待当前网络请求和文件写入结束后退出…')
                self.close_timer.start()
            event.ignore()
            return
        self.bridge.shutdown()
        event.accept()


def main():
    if sys.platform == 'win32':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Keye.CourseLibrary.1')
    app = QApplication(sys.argv)
    app.setApplicationName('Keye')
    app.setApplicationDisplayName('课页')
    resource_base = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)).resolve()
    app.setWindowIcon(QIcon(str(resource_base / 'assets' / 'app-icon.ico')))
    base = Path(__file__).parent
    lock = QLockFile(str(base / '.keye-lock'))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, '课页已运行', '请使用已经打开的课页窗口。')
        return 0
    window = KeyeWindow()
    window.show()
    result = app.exec()
    # Ensure the page is released before its profile.
    from shiboken6 import delete
    delete(window.page)
    delete(window.profile)
    lock.unlock()
    return result


if __name__ == '__main__':
    sys.exit(main())

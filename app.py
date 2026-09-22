"""课页: the production desktop entry point. Legacy downloader remains in main.py."""
import os
import sys
import ctypes
import json
import shutil
from pathlib import Path
from core.webengine import configure_webengine

# The school site rejects traffic through many system proxies as off-campus.
# Qt WebEngine's GPU compositor is also unreliable on some Windows machines
# with virtual display adapters.  The UI is deliberately light enough for the
# software compositor, which avoids DirectComposition/shared-texture failures.
configure_webengine()

from PySide6.QtCore import QEvent, QLockFile, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QToolButton, QVBoxLayout, QWidget
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from core.desktop import DesktopBridge
from core.version import VERSION


def default_runtime_base():
    """Share the repository library between source and in-repo test builds."""
    source_root = Path(__file__).parent.resolve()
    if not getattr(sys, 'frozen', False):
        return source_root
    executable_dir = Path(sys.executable).parent.resolve()
    if executable_dir.parent.name.lower() == 'release':
        project_root = executable_dir.parent.parent
        if (project_root / '.git').is_dir() and (project_root / 'Keye.spec').is_file():
            return project_root
    return executable_dir


def cleanup_completed_update():
    if not getattr(sys, 'frozen', False):
        return
    install_dir = Path(sys.executable).parent.resolve()
    stage = install_dir / '.keye-update' / ('v' + VERSION)
    marker = stage / 'update-success.json'
    try:
        if marker.is_file() and json.loads(marker.read_text(encoding='utf-8')).get('version') == VERSION:
            shutil.rmtree(stage)
    except (OSError, ValueError):
        pass  # Retry on a later launch if the helper has not exited yet.


class WindowButton(QToolButton):
    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(46, 35)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setProperty('windowControl', kind)
        label = {'minimize': '最小化', 'maximize': '最大化', 'close': '关闭'}[kind]
        self.setToolTip(label)
        self.setAccessibleName(label)
        self.restoring = False

    def set_restoring(self, restoring):
        if self.kind == 'maximize':
            self.restoring = restoring
            label = '还原' if restoring else '最大化'
            self.setToolTip(label)
            self.setAccessibleName(label)
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor('#ffffff') if self.kind == 'close' and self.underMouse() else QColor('#243a32')
        painter.setPen(QPen(color, 1.35))
        center_x, center_y = self.width() // 2, self.height() // 2
        if self.kind == 'minimize':
            painter.drawLine(center_x - 5, center_y + 3, center_x + 5, center_y + 3)
        elif self.kind == 'close':
            painter.drawLine(center_x - 4, center_y - 4, center_x + 4, center_y + 4)
            painter.drawLine(center_x + 4, center_y - 4, center_x - 4, center_y + 4)
        elif self.restoring:
            painter.drawRect(center_x - 3, center_y - 3, 8, 8)
            painter.drawLine(center_x - 5, center_y + 3, center_x - 5, center_y - 5)
            painter.drawLine(center_x - 5, center_y - 5, center_x + 3, center_y - 5)
        else:
            painter.drawRect(center_x - 5, center_y - 5, 10, 10)


class TitleBar(QWidget):
    def __init__(self, window, icon_path):
        super().__init__(window)
        self.host = window
        self.setObjectName('customTitleBar')
        self.setFixedHeight(36)
        self.setStyleSheet('''
            QWidget#customTitleBar { background: #f7faf8; border-bottom: 1px solid #d5ded9; }
            QLabel#titleIcon { border: 0; background: transparent; }
            QLabel#titleName { color: #102a22; }
            QLabel#titleDetail { color: #687a72; }
            QToolButton { border: 0; border-radius: 0; background: transparent; padding: 0; }
            QToolButton:hover { background: #e7efeb; }
            QToolButton:pressed { background: #dce8e2; }
            QToolButton[windowControl="close"]:hover { background: #c94b45; color: white; }
            QToolButton[windowControl="close"]:pressed { background: #ad3d38; color: white; }
        ''')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(7)

        icon = QLabel(self)
        icon.setObjectName('titleIcon')
        icon.setFixedSize(22, 22)
        icon.setPixmap(QIcon(str(icon_path)).pixmap(22, 22))
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(icon)

        title = QLabel('课页', self)
        title.setObjectName('titleName')
        title_font = QFont('Microsoft YaHei UI', 9)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(title)
        detail = QLabel('· 个人课件资料库', self)
        detail.setObjectName('titleDetail')
        detail.setFont(QFont('Microsoft YaHei UI', 8))
        detail.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(detail)
        layout.addStretch(1)

        self.minimize_button = WindowButton('minimize', self)
        self.maximize_button = WindowButton('maximize', self)
        self.close_button = WindowButton('close', self)
        self.minimize_button.clicked.connect(window.showMinimized)
        self.maximize_button.clicked.connect(window.toggle_maximized)
        self.close_button.clicked.connect(window.close)
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

    def sync_window_state(self):
        self.maximize_button.set_restoring(self.host.isMaximized())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.host.windowHandle():
            self.host.windowHandle().startSystemMove()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.host.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


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
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        resource_base = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)).resolve()
        default_base = default_runtime_base()
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
        container = QWidget(self)
        container.setObjectName('windowSurface')
        container.setStyleSheet('QWidget#windowSurface { background: #f7faf8; }')
        window_layout = QVBoxLayout(container)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(0)
        self.title_bar = TitleBar(self, resource_base / 'assets' / 'app-icon.ico')
        window_layout.addWidget(self.title_bar)
        window_layout.addWidget(self.web, 1)
        self.setCentralWidget(container)
        self.web.setUrl(QUrl.fromLocalFile(str(self.entry)))
        self.closing = False
        self.close_timer = QTimer(self)
        self.close_timer.setInterval(250)
        self.close_timer.timeout.connect(self.finish_close)

    def toggle_maximized(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()
        self.title_bar.sync_window_state()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, 'title_bar'):
            self.title_bar.sync_window_state()
        super().changeEvent(event)

    def nativeEvent(self, event_type, message):
        if sys.platform == 'win32' and not self.isMaximized() and not self.isFullScreen():
            import ctypes.wintypes
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == 0x0084:  # WM_NCHITTEST
                rect = ctypes.wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(int(self.winId()), ctypes.byref(rect))
                x = ctypes.c_short(msg.lParam & 0xffff).value
                y = ctypes.c_short((msg.lParam >> 16) & 0xffff).value
                border = max(6, round(7 * self.devicePixelRatioF()))
                left, right = x < rect.left + border, x >= rect.right - border
                top, bottom = y < rect.top + border, y >= rect.bottom - border
                hit = {(True, False, True, False): 13,   # HTTOPLEFT
                       (False, True, True, False): 14,   # HTTOPRIGHT
                       (True, False, False, True): 16,   # HTBOTTOMLEFT
                       (False, True, False, True): 17}.get((left, right, top, bottom))
                if hit:
                    return True, hit
                if left:
                    return True, 10  # HTLEFT
                if right:
                    return True, 11  # HTRIGHT
                if top:
                    return True, 12  # HTTOP
                if bottom:
                    return True, 15  # HTBOTTOM
        return super().nativeEvent(event_type, message)

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
    app.setApplicationVersion(VERSION)
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
    QTimer.singleShot(15000, cleanup_completed_update)
    result = app.exec()
    # Ensure the page is released before its profile.
    from shiboken6 import delete
    delete(window.page)
    delete(window.profile)
    lock.unlock()
    return result


if __name__ == '__main__':
    sys.exit(main())

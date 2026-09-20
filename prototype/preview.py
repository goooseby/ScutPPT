"""Open the interactive prototype in a separate desktop window."""
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView


def main():
    app = QApplication(sys.argv)
    view = QWebEngineView()
    # Keep prototype state separate from the school's login browser profile.
    profile = QWebEngineProfile('GetPPTPrototype', view)
    storage = Path(__file__).parent / '.browser-data'
    profile.setPersistentStoragePath(str(storage / 'storage'))
    profile.setCachePath(str(storage / 'cache'))
    page = QWebEnginePage(profile, view)
    view.setPage(page)
    view.setWindowTitle('GetPPTApp · 交互原型（示例数据）')
    view.resize(1440, 960)
    view.setUrl(QUrl.fromLocalFile(str(Path(__file__).with_name('index.html').resolve())))
    view.show()
    result = app.exec()
    # Destroy the page before its profile so Chromium can flush stored state.
    from shiboken6 import delete
    delete(page)
    delete(profile)
    return result


if __name__ == '__main__':
    sys.exit(main())

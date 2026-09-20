"""Exercise the prototype in a real Qt browser; no school or file data is used."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu --disable-renderer-backgrounding --disable-background-timer-throttling')
from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView


class Page(QWebEnginePage):
    errors = []

    def javaScriptConsoleMessage(self, level, message, line, source):
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.errors.append(f'{source}:{line}: {message}')


def run():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='getppt-prototype-check-') as directory:
        profile = QWebEngineProfile(app)
        profile.setPersistentStoragePath(directory)
        view = QWebEngineView()
        page = Page(profile, view)
        view.setPage(page)
        view.resize(1440, 960)
        view.show()

        def wait(milliseconds=100):
            loop = QEventLoop()
            QTimer.singleShot(milliseconds, loop.quit)
            loop.exec()

        def js(source):
            result = []
            loop = QEventLoop()
            def done(value):
                result.append(value)
                loop.quit()
            page.runJavaScript(source, done)
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(loop.quit)
            timer.start(5000)
            loop.exec()
            timer.stop()
            if not result:
                raise AssertionError(f'JavaScript timed out: {source}')
            return result[0]

        def until(expression, timeout=8):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if js(expression):
                    return
                wait(70)
            raise AssertionError(f'Condition did not become true: {expression}')

        def click(selector):
            assert js(f'!!document.querySelector({json.dumps(selector)})'), selector
            js(f'document.querySelector({json.dumps(selector)}).click()')
            wait(60)

        def snap(name):
            # Offscreen Chromium can present frames at a lower rate than DOM updates.
            js("document.querySelector('#toast').classList.remove('show')")
            wait(1300)
            output = Path(__file__).parent / 'review'
            output.mkdir(exist_ok=True)
            assert view.grab().save(str(output / f'{name}.png'))

        page.load(QUrl.fromLocalFile(str(Path(__file__).with_name('index.html').resolve())))
        until("document.querySelectorAll('.course-card').length === 6")
        snap('01-library')
        click('[data-open="operations"]')
        until("view.page==='editor'")
        until("document.querySelectorAll('.page-tile').length === 18")
        snap('02-editor')
        click('[data-action="range"]')
        js("document.querySelector('#range-from').value=2; document.querySelector('#range-to').value=6")
        click('[data-action="confirm-range"]')
        assert js('view.selected.size') == 5
        click('[data-action="exclude"]')
        assert js('material().excluded.length') == 8
        click('[data-action="undo"]')
        assert js('material().excluded.length') == 5
        click('[data-toggle-page="2"]')
        assert js('material().excluded.includes(2)')
        click('[data-page-filter="kept"]')
        assert js("document.querySelectorAll('.page-tile').length") == 12
        click('[data-page-filter="all"]')
        click('[data-action="fullscreen"]')
        click('[data-action="next"]')
        assert js('view.currentPage') == 2
        click('[data-action="close-modal"]')
        click('[data-action="export"]')
        snap('03-export')
        click('[data-action="confirm-export"]')
        until("state.tasks.some(t=>t.type==='export'&&t.status==='done')")
        assert js("statusOf(material())") == 'exported'
        click('[data-toggle-page="3"]')
        assert js("statusOf(material())") == 'changed', js('JSON.stringify(material())')
        reloaded = []
        def on_reload(ok):
            reloaded.append(ok)
        page.loadFinished.connect(on_reload)
        page.triggerAction(QWebEnginePage.WebAction.Reload)
        deadline = time.monotonic() + 8
        while not reloaded and time.monotonic() < deadline:
            wait(80)
        assert reloaded and reloaded[-1], 'Reload failed'
        page.loadFinished.disconnect(on_reload)
        until("typeof material==='function' && material()?.excluded.includes(3)")
        assert js("statusOf(material())") == 'changed', js('JSON.stringify(material())')
        click('[data-nav="acquire"]')
        click('[data-action="login"]')
        click('[data-action="confirm-login"]')
        click('[data-action="scan"]')
        until("document.querySelectorAll('[data-scan-select]').length === 3")
        snap('04-acquire')
        click('#scan-all')
        assert js('view.scanSelected.size') == 3
        click('[data-action="download"]')
        click('[data-nav="tasks"]')
        snap('05-tasks')
        click('[data-task-toggle]')
        assert js("state.tasks.some(t=>t.status==='paused')")
        paused_id = js("state.tasks.find(t=>t.status==='paused').id")
        click(f'[data-task-toggle="{paused_id}"]')
        until("state.tasks.filter(t=>t.type==='download').every(t=>t.status==='done')", 12)
        assert js('activeMaterials().length') == 9
        click('[data-nav="library"]')
        click('[data-menu="network"]')
        click('[data-delete-material="network"]')
        click('[data-filter="trash"]')
        assert js("document.querySelectorAll('.course-card').length") == 1
        click('[data-restore="network"]')
        assert js('activeMaterials().length') == 9
        click('[data-nav="settings"]')
        snap('06-settings')
        click('[data-nav="library"]')
        js("view.filter='all';renderLibrary()")
        view.resize(1000, 780)
        wait(200)
        assert js('document.documentElement.scrollWidth <= window.innerWidth')
        snap('07-compact-library')
        click('[data-open="operations"]')
        until("view.page==='editor'")
        assert js('document.documentElement.scrollWidth <= window.innerWidth')
        snap('08-compact-editor')
        assert not page.errors, page.errors
        print('PASS: library, selection, range, exclude/restore, undo, preview, export state, persistence, acquisition, background tasks, pause/resume, trash and responsive layout')
        print('Screenshots: prototype/review/')
        view.close()
        page.deleteLater()
        view.deleteLater()
        wait(150)
        profile.deleteLater()
        wait(150)


if __name__ == '__main__':
    run()

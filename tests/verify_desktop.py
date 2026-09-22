"""Full UI/native bridge/download/file pipeline check using a local HTTP fixture."""
import functools
import json
import os
import sys
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu --disable-renderer-backgrounding --disable-background-timer-throttling')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader
from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog
from auth.browser_login import ParsedAuth
from app import KeyeWindow


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class Login(QDialog):
    parsed = ParsedAuth('test=fixture', 'fixture-user', 'fixture-school', 'test')
    def __init__(self, *args): super().__init__(*args)
    def open(self):
        super().open()
        QTimer.singleShot(0, self.accept)


def run():
    app = QApplication([])
    with tempfile.TemporaryDirectory(prefix='keye-integration-') as directory:
        root = Path(directory)
        fixture = root / 'fixture'
        fixture.mkdir()
        for i, color in enumerate(('#edf4ed','#edf2fa','#faf3e8'), 1):
            image = Image.new('RGB', (1280,720), color)
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 50)
            draw.text((80,100), '课页 · 本地联调测试', fill='#3e5c4b', font=font)
            draw.text((80,220), f'第 {i} 页：真实图片文件', fill='#3e5c4b', font=font)
            draw.rectangle((80,370,1200,375), fill='#8caf91')
            draw.text((80,470), '下载 → 预览 → 筛选 → 导出', fill='#627966', font=font)
            image.save(fixture / f'{i}.png')
        handler = functools.partial(Handler, directory=str(fixture))
        server = ThreadingHTTPServer(('127.0.0.1',0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}'
        window = KeyeWindow(root, root / 'library')
        window.show()
        window.bridge.library.set_setting('settings', {'sleepMs':0,'retries':1,'timeout':5,'maxWorkers':2})
        page = window.page
        def wait(ms=80):
            loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
        def js(source):
            values=[];loop=QEventLoop()
            def done(value): values.append(value);loop.quit()
            page.runJavaScript(source,done)
            timer=QTimer();timer.setSingleShot(True);timer.timeout.connect(loop.quit);timer.start(5000)
            loop.exec();timer.stop()
            assert values, f'JS callback timeout: {source}'
            return values[0]
        def until(source, seconds=15):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                if js(source):return
                wait()
            raise AssertionError(source+'\n'+str(js('document.body.innerText')))
        def click(selector):
            assert js(f'!!document.querySelector({json.dumps(selector)})'),selector
            js(f'document.querySelector({json.dumps(selector)}).click()');wait()
        def shot(name):
            js("document.querySelector('#toast').classList.remove('show')")
            wait(1200)
            output=Path(__file__).resolve().parents[1]/'review'
            output.mkdir(exist_ok=True)
            assert window.web.grab().save(str(output/(name+'.png')))
        def window_shot(name):
            wait(300)
            output=Path(__file__).resolve().parents[1]/'review'
            output.mkdir(exist_ok=True)
            assert window.grab().save(str(output/(name+'.png')))
        try:
            until("typeof ready!=='undefined' && ready")
            assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
            assert window.title_bar.height()==36
            assert window.title_bar.close_button.accessibleName()=='关闭'
            window_shot('keye-custom-titlebar')
            assert js('state.materials.length')==0
            shot('keye-empty-library')
            click('[data-nav="about"]');until("view.page==='about'")
            assert js("document.querySelectorAll('.about-card').length")==3
            assert js("document.querySelector('[data-nav=about]').classList.contains('active')")
            click('[data-action="show-help"]');until('modal.open')
            click('[data-action="close-modal"]')
            shot('keye-about')
            click('[data-nav="library"]');until("view.page==='library'")
            with patch('core.desktop.BrowserLoginDialog',Login), patch('core.desktop.fetch_schedules_in_range',return_value=[
                {'title':'联调课程','course_id':'course-1','sub_id':'sub-1','day':'2026-09-05'}
            ]), patch('core.desktop.get_ppt_urls',return_value=[f'{url}/{i}.png' for i in (1,2,3)]):
                click('[data-nav="acquire"]');until("view.page==='acquire'")
                click('[data-action="login"]');until('view.loggedIn && view.scanned')
                click('#scan-all');click('[data-action="download"]')
                until("state.tasks.some(t=>t.type==='download' && t.status==='done')")
            assert js('state.materials.length')==1
            mid=js('state.materials[0].id')
            click('[data-nav="library"]');until("view.page==='library'")
            shot('keye-library')
            cid=js('state.materials[0].courseId')
            click(f'[data-nav="course/{cid}"]');until("view.page==='course'")
            click(f'[data-course-session="{mid}"]');until("view.page==='editor'")
            until("[...document.querySelectorAll('.page-art img')].every(img=>img.complete && img.naturalWidth>0)")
            assert not js("!!document.querySelector('.lecture-rail')")
            assert js("getComputedStyle(document.querySelector('.editor-toolbar')).position")=='sticky'
            assert js("getComputedStyle(document.querySelector('.preview-panel')).position")=='sticky'
            columns=js("getComputedStyle(document.querySelector('.pages-grid')).getPropertyValue('grid-template-columns')")
            assert len(columns.split())==4,columns
            click('[data-toggle-page="2"]');until('material().excluded.includes(2) && !view.saving')
            assert window.bridge.library.get(mid)['excluded']==[2]
            click('[data-page-check="1"]')
            js("document.querySelector('[data-page-check=\"3\"]').dispatchEvent(new MouseEvent('click',{bubbles:true,shiftKey:true}))")
            until("[1,2,3].every(p=>view.selected.has(p))")
            assert js('view.selected.size')==3
            shot('keye-editor')
            click('[data-action="fullscreen"]');until("modal.open&&modal.classList.contains('fullscreen-modal')")
            js("document.querySelector('#modal-content').dataset.stablePreview='yes'")
            click('[data-action="next"]');until('view.currentPage===2')
            assert js("document.querySelector('#modal-content').dataset.stablePreview==='yes'")
            assert js("document.querySelector('.fullscreen-shortcuts').innerText.includes('E')")
            # A burst of navigation must collapse to the final paint and final
            # persisted page instead of flooding WebChannel and the compositor.
            js("for(let i=0;i<900;i++)preview(i%3+1)")
            until("view.currentPage===3&&document.querySelector('#fullscreen-page').innerText.startsWith('3 /')")
            until("document.querySelector('#fullscreen-stage img').src===material().media[2].src")
            wait(400)
            assert window.bridge.library.get(mid)['lastPage']==3
            preview_node=js("document.querySelector('#modal-content').dataset.stablePreview")
            assert preview_node=='yes'
            js("preview(2)");until("view.currentPage===2&&document.querySelector('#fullscreen-page').innerText.startsWith('2 /')")
            before=js('material().excluded.includes(2)')
            js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'e',bubbles:true}))")
            until(f"material().excluded.includes(2)==={str(not before).lower()}&&!view.saving")
            assert js("modal.open&&modal.classList.contains('fullscreen-modal')")
            js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'e',bubbles:true}))")
            until(f"material().excluded.includes(2)==={str(before).lower()}&&!view.saving")
            shot('keye-fullscreen')
            click('[data-action="close-modal"]')
            assert js("state.settings.exportDir==='' ")
            exports_before=js("state.tasks.filter(t=>t.type==='export').length")
            # First export asks only when it is needed. Cancelling starts no task
            # and keeps the setting empty; a real choice is persisted immediately.
            with patch('core.desktop.QFileDialog.getExistingDirectory',return_value=''):
                click('[data-action="quick-export"]')
            assert js("state.tasks.filter(t=>t.type==='export').length")==exports_before
            assert window.bridge.settings()['exportDir']==''
            first_export_root=root/'remembered-exports'
            with patch('core.desktop.QFileDialog.getExistingDirectory',return_value=str(first_export_root)):
                click('[data-action="quick-export"]')
            until(f"state.tasks.filter(t=>t.type==='export').length>{exports_before} && state.tasks.filter(t=>t.type==='export').at(-1).status==='done'")
            assert Path(window.bridge.settings()['exportDir'])==first_export_root.resolve()
            exports_before=js("state.tasks.filter(t=>t.type==='export').length")
            with patch('core.desktop.QFileDialog.getExistingDirectory',side_effect=AssertionError('saved export directory should be reused')):
                click('[data-action="quick-export"]')
            until(f"state.tasks.filter(t=>t.type==='export').length>{exports_before} && state.tasks.filter(t=>t.type==='export').at(-1).status==='done'")
            quick=Path(window.bridge.library.get(mid)['exportPath'])
            assert quick.is_file() and len(PdfReader(quick).pages)==2
            assert window.bridge.library.get(mid).get('reviewRevision') is None
            output=root/'selected.pdf'
            with patch('core.desktop.QFileDialog.getSaveFileName',return_value=(str(output),'PDF')):
                click('[data-action="export"]');click('[data-action="confirm-export"]')
                until("state.tasks.some(t=>t.type==='export' && t.status==='done')")
            reader=PdfReader(output);assert len(reader.pages)==2;reader.close()
            click('[data-toggle-page="3"]');until("statusOf(material())==='changed'")
            window.web.reload();wait(700)
            until("typeof ready!=='undefined' && ready && state.materials[0].excluded.length===2")
            assert js("statusOf(state.materials[0])")=='changed'
            # Import the actually exported PDF through the same native dialog/worker path.
            click('[data-nav="library"]');until("view.page==='library'")
            with patch('core.desktop.QFileDialog.getOpenFileNames',return_value=([str(output)],'PDF')):
                click('[data-action="import"]');click('[data-action="import-files"]')
                until('state.materials.length===2')
            assert js("state.materials.some(m=>m.kind==='pdf'&&m.pages===2)")
            # A missing page must not publish an incomplete material; retry resumes safely.
            with patch('core.desktop.fetch_schedules_in_range',return_value=[
                {'title':'失败与重试','course_id':'course-2','sub_id':'sub-2','day':'2026-09-05'}
            ]):
                click('[data-nav="acquire"]');until("view.page==='acquire'")
                click('[data-action="scan"]');until("view.scanned && availableCourses[0]?.title==='失败与重试'")
            with patch('core.desktop.get_ppt_urls',return_value=[f'{url}/1.png',f'{url}/missing.png']):
                click('#scan-all');click('[data-action="download"]')
                until("state.tasks.some(t=>t.type==='download' && t.status==='failed')")
            assert js('state.materials.length')==2
            click('[data-nav="tasks"]');until("view.page==='tasks'")
            with patch('core.desktop.get_ppt_urls',return_value=[f'{url}/{i}.png' for i in (1,2,3)]):
                click('[data-task-retry]')
                until('state.materials.length===3')
            # Exercise real task control without depending on a network timing race.
            def controlled_work(control, progress):
                for index in range(40):
                    control.checkpoint()
                    progress(index*2, '控制流程检查')
                    time.sleep(0.03)
                return []
            controlled=window.bridge.submit('scan', '暂停与取消检查', controlled_work)
            window.bridge.dispatch('task', {'id':controlled['id'],'action':'toggle'})
            assert controlled['status']=='paused'
            wait(150)
            paused_progress=controlled['progress']
            wait(150)
            assert controlled['progress']==paused_progress
            window.bridge.dispatch('task', {'id':controlled['id'],'action':'toggle'})
            wait(150)
            assert controlled['status']=='running'
            window.bridge.dispatch('task', {'id':controlled['id'],'action':'cancel'})
            until("state.tasks.some(t=>t.id==='"+controlled['id']+"' && t.status==='cancelled')")
            # Automatic export writes a real file without requiring an export dialog.
            with patch('core.desktop.fetch_schedules_in_range',return_value=[
                {'title':'直接导出课程','course_id':'course-3','sub_id':'sub-3','day':'2026-09-05'}
            ]), patch('core.desktop.get_ppt_urls',return_value=[f'{url}/{i}.png' for i in (1,2)]):
                click('[data-nav="acquire"]');until("view.page==='acquire'")
                click('[data-action="scan"]');until("view.scanned && availableCourses[0]?.title==='直接导出课程'")
                click('#scan-all');click('#direct-export');click('[data-action="download"]')
                until("state.materials.some(m=>m.title==='直接导出课程' && m.exported)")
            direct=next(m for m in window.bridge.library.materials() if m['title']=='直接导出课程')
            assert Path(direct['exportPath']).is_file()
            reader=PdfReader(direct['exportPath']);assert len(reader.pages)==2;reader.close()
            click('[data-nav="tasks"]');until("view.page==='tasks'")
            shot('keye-tasks')
            # Semester-sized collection: twenty lectures, six pending, review recent three.
            lib=window.bridge.library
            for i in range(1,20):
                m=lib.prepare_images([fixture/'1.png',fixture/'2.png'], '联调课程', f'2026-09-{i+6:02d}')
                lib.assign([m['id']], cid)
            course_items=sorted([m for m in lib.materials() if m.get('courseId')==cid],key=lambda m:m['day'])
            for m in course_items[:14]:lib.mark_reviewed(m['id'],m['revision'])
            window.bridge.publish();wait()
            js("navigate('library')");until("view.page==='library'")
            click(f'[data-nav="course/{cid}"]');until("view.page==='course'")
            assert js('sessions(view.courseId).length')==20
            assert js('sessions(view.courseId).filter(m=>!reviewed(m)).length')==6
            shot('keye-course-semester')
            click('[data-course-action="recent"]')
            assert js('view.courseSelected.size')==3
            click('[data-course-action="selected"]');until("view.page==='editor'")
            assert js('queueMaterials().length')==3
            shot('keye-course-review')
            first=js('material().id')
            click('[data-toggle-page="2"]');until('!view.saving && material().excluded.includes(2)')
            click('[data-course-action="complete"]');until(f"material()?.id!=='{first}'")
            assert lib.get(first)['reviewRevision']==lib.get(first)['revision']
            window.web.reload();wait(700);until("typeof ready!=='undefined' && ready && view.page==='editor'")
            assert js('queueMaterials().length')==3
            second=js('material().id')
            click('[data-course-action="complete"]');until(f"material()?.id!=='{second}'")
            click('[data-course-action="complete"]');until("view.page==='course'")
            assert js('sessions(view.courseId).filter(m=>!reviewed(m)).length')==3
            click('[data-course-action="recent"]')
            combined=root/'semester.pdf'
            with patch('core.desktop.QFileDialog.getSaveFileName',return_value=(str(combined),'PDF')):
                click('[data-course-action="batch"]')
                js("document.querySelector('#batch-mode').value='combined'")
                click('[data-course-action="confirm-batch"]')
                until("state.tasks.some(t=>t.type==='batch'&&t.status==='done')")
            with PdfReader(combined) as reader:
                assert len(reader.pages)==5
                assert len(reader.outline)==3
            js("navigate('course/"+cid+"')");until("view.page==='course'")
            click('[data-course-action="recent"]')
            with patch('core.desktop.QFileDialog.getExistingDirectory',return_value=str(root/'batch')):
                click('[data-course-action="batch"]');click('[data-course-action="confirm-batch"]')
                until("state.tasks.filter(t=>t.type==='batch'&&t.status==='done').length===2")
            assert len(list((root/'batch').rglob('*.pdf')))==3
            # New course / local assignment uses the same real UI commands.
            js("navigate('course/unfiled')");until("view.page==='course'")
            imported=js('sessions("unfiled")[0].id')
            click(f'[data-session-select="{imported}"]');click('[data-course-action="assign"]')
            js("document.querySelector('#assign-new').value='本地笔记'")
            click('[data-course-action="confirm-assign"]')
            until("courseById(view.courseId).title==='本地笔记'")
            assert lib.get(imported)['courseId']
            click(f'[data-note="{imported}"]')
            js("document.querySelector('#session-note').value='章节复习'")
            click(f'[data-save-note="{imported}"]')
            assert lib.get(imported)['note']=='章节复习'
            # Scan groups support selecting new lectures as a course and partial selection.
            with patch('core.desktop.fetch_schedules_in_range',return_value=[
                {'title':'课程甲','course_id':'group-a','sub_id':'a1','day':'2026-09-01'},
                {'title':'课程甲','course_id':'group-a','sub_id':'a2','day':'2026-09-02'},
                {'title':'课程乙','course_id':'group-b','sub_id':'b1','day':'2026-09-02'}
            ]):
                click('[data-nav="acquire"]');click('[data-action="scan"]')
                until('view.scanned && availableCourses.length===3')
            assert js("document.querySelectorAll('.scan-course').length")==2
            click('[data-scan-group]');assert js('view.scanSelected.size')==2
            click('[data-scan-expand]');click('[data-scan-select]')
            assert js('view.scanSelected.size')==1
            assert js("document.querySelector('[data-scan-group]').indeterminate")
            shot('keye-grouped-scan')
            print('PASS: 20 lectures / 6 pending, recent-three scope, explicit completion, queue reload, bookmarked merge, course-folder batch export')
            print('PASS: real WebChannel, login handoff, scan, HTTP downloads, previews, SQLite edits, PDF export/import, reload, retry, pause/resume/cancel and direct export')
        finally:
            for control in window.bridge.controls.values():
                control.cancelled.set();control.paused.set()
            deadline=time.monotonic()+15
            while window.bridge.controls and time.monotonic()<deadline:wait()
            window.close()
            server.shutdown();server.server_close()
            from shiboken6 import delete
            delete(window.page);delete(window.profile)
            wait()


if __name__=='__main__':
    run()

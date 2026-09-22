"""Render every major screen and check common visual regressions."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS','--disable-gpu --disable-renderer-backgrounding --disable-background-timer-throttling')

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))

from PySide6.QtCore import QEventLoop,QPoint,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from preview import PreviewWindow,seed_library


def run():
    app=QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='keye-visual-check-',ignore_cleanup_errors=True) as directory:
        seed_library(Path(directory)/'library')
        window=PreviewWindow(directory);window.resize(1440,960);window.show();page=window.page

        def wait(ms=100):
            loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
        def js(source):
            result=[];loop=QEventLoop()
            page.runJavaScript(source,lambda value:(result.append(value),loop.quit()))
            timer=QTimer();timer.setSingleShot(True);timer.timeout.connect(loop.quit);timer.start(5000);loop.exec();timer.stop()
            if not result:raise AssertionError(f'JavaScript timeout: {source}')
            return result[0]
        def until(source,seconds=12):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                if js(source):return
                wait(80)
            raise AssertionError(source)
        def snap(name):
            js("document.querySelector('#toast').classList.remove('show')")
            wait(900);output=HERE/'review';output.mkdir(exist_ok=True)
            assert window.web.grab().save(str(output/f'{name}.png'))
        def assert_layout():
            report=json.loads(js("""JSON.stringify((()=>{const bad=[...document.querySelectorAll('button, input, select, .badge, h1, h2, h3')].filter(e=>{const r=e.getBoundingClientRect(),scroller=e.closest('.table-wrap');return r.width>0&&r.right>innerWidth+2&&!(scroller&&scroller.scrollWidth>scroller.clientWidth)});return {page:view.page,scroll:document.documentElement.scrollWidth,width:innerWidth,bad:bad.slice(0,8).map(e=>e.outerHTML.slice(0,120))}})())"""))
            assert report['scroll']<=report['width']+1,report
            assert not report['bad'],report

        until("typeof ready!=='undefined'&&ready&&(state.courseLibrary||[]).length===3")
        assert_layout();snap('01-library-wide')
        js("navigate('course/demo-network')");until("view.page==='course'");assert_layout();snap('02-course-wide')
        hover=json.loads(js("""JSON.stringify((()=>{const r=document.querySelector('tbody tr:nth-child(2) .session-title').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})())"""))
        QTest.mouseMove(window.web,QPoint(round(hover['x']),round(hover['y'])));wait(180);snap('02a-course-hover')
        alignment=json.loads(js("""JSON.stringify((()=>{const a=document.querySelector('.session-actions'),buttons=[...a.children].filter(x=>x.tagName==='BUTTON'),rects=buttons.map(x=>x.getBoundingClientRect());return {tops:rects.map(r=>r.top),heights:rects.map(r=>r.height),gap:rects[1].left-rects[0].right}})())"""))
        assert max(alignment['tops'])-min(alignment['tops'])<=1,alignment
        assert max(alignment['heights'])-min(alignment['heights'])<=1,alignment
        assert alignment['gap']>=7,alignment
        js("document.querySelector('tbody tr:last-child .session-more').click()");wait(100)
        assert js("!!document.querySelector('.session-menu')&&!document.querySelector('#modal').open")
        menu=json.loads(js("""JSON.stringify((()=>{const r=document.querySelector('.session-menu').getBoundingClientRect();return {top:r.top,right:r.right,bottom:r.bottom,width:r.width,buttons:[...document.querySelectorAll('.session-menu button')].map(b=>{const x=b.getBoundingClientRect();return {left:x.left,right:x.right,top:x.top,bottom:x.bottom}})}})())"""))
        assert menu['top']>=0 and menu['right']<=1440 and menu['bottom']<=960,menu
        assert len(menu['buttons'])==2 and menu['buttons'][1]['top']>=menu['buttons'][0]['bottom'],menu
        snap('02b-course-menu')
        js("document.querySelector('.session-menu [data-mark-reviewed]:not(:disabled)').click()");wait(120)
        assert not js("!!document.querySelector('.session-menu')")
        js("document.querySelector('tbody tr td:nth-child(3)').click()");until("view.page==='editor'")
        js("navigate('course/demo-network')");until("view.page==='course'")
        mid=js("sessions('demo-network')[6].id")
        js(f"openMaterial({json.dumps(mid)})");until("view.page==='editor'");assert_layout()
        assert not js("!!document.querySelector('.lecture-rail')")
        assert js("getComputedStyle(document.querySelector('.editor-toolbar')).position")=='sticky'
        assert js("getComputedStyle(document.querySelector('.preview-panel')).position")=='sticky'
        grid=json.loads(js("""JSON.stringify((()=>{const node=document.querySelector('.pages-grid'),style=getComputedStyle(node);return {display:style.display,columns:style.getPropertyValue('grid-template-columns'),width:node.getBoundingClientRect().width,viewport:innerWidth}})())"""))
        print('Editor grid:',grid)
        assert len(grid['columns'].split())==4,grid
        snap('03-editor-wide')
        js("document.querySelector('.pages-grid').style.paddingBottom='1000px';main.scrollTop=450");wait(250)
        sticky=json.loads(js("""JSON.stringify((()=>{const mainRect=main.getBoundingClientRect(),toolbar=document.querySelector('.editor-toolbar').getBoundingClientRect(),preview=document.querySelector('.preview-panel').getBoundingClientRect();return {scroll:main.scrollTop,mainTop:mainRect.top,toolbarTop:toolbar.top,previewTop:preview.top}})())"""))
        assert sticky['scroll']>300,sticky
        assert 20<=sticky['toolbarTop']-sticky['mainTop']<=45,sticky
        assert abs(sticky['previewTop']-(sticky['toolbarTop']+76))<=2,sticky
        snap('03a-editor-scrolled')
        js("main.scrollTop=0;document.querySelector('.pages-grid').style.paddingBottom=''");wait(120)
        js("document.querySelector('[data-action=\"range\"]').click()");wait(150);assert_layout();snap('04-range-dialog')
        js("closeModal();navigate('acquire')");until("view.page==='acquire'");assert_layout();snap('05-acquire-wide')
        js("navigate('tasks')");until("view.page==='tasks'");assert_layout();snap('06-tasks-wide')
        js("navigate('settings')");until("view.page==='settings'");assert_layout();snap('07-settings-wide')
        window.resize(1000,760);wait(350)
        js("navigate('course/demo-network')");until("view.page==='course'");assert_layout();snap('08-course-compact')
        js(f"openMaterial({json.dumps(mid)})");until("view.page==='editor'");assert_layout();snap('09-editor-compact')
        assert js("getComputedStyle(document.documentElement).fontSize") in ('14px','15px')
        print('PASS: refreshed library, course, editor, dialog, acquire, tasks, settings and compact layouts')
        print(f'Screenshots: {HERE / "review"}')
        window.close();wait(200)
        from shiboken6 import delete
        delete(window.page);delete(window.profile);delete(window);wait(200)


if __name__=='__main__':run()

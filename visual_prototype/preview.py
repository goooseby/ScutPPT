"""Open the visual refresh against disposable demo data."""
import ctypes
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QUrl, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from core.desktop import DesktopBridge
from core.library import Library


HERE = Path(__file__).parent


def create_slides(folder):
    folder.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 48)
    small = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 24)
    colors = [('#edf4ef','#315f50'),('#eef2f8','#405b78'),('#f8f2e7','#725c31'),('#f2eff7','#65567b'),('#e9f4f3','#276667'),('#f7eeee','#795252')]
    paths=[]
    titles=['课程概览','核心概念','示例推导','课堂练习','重点回顾','本节小结']
    for index,((bg,ink),title) in enumerate(zip(colors,titles),1):
        path=folder/f'{index}.png';paths.append(path)
        if path.exists():continue
        image=Image.new('RGB',(1280,720),bg);draw=ImageDraw.Draw(image)
        draw.rectangle((0,0,1280,10),fill=ink)
        draw.text((86,80),'课页 · 视觉优化示例',font=small,fill=ink)
        draw.text((86,195),title,font=font,fill=ink)
        draw.line((86,290,1160,290),fill=ink,width=3)
        draw.text((86,355),f'第 {index} 页　清晰、专注、有层级的课件预览',font=small,fill=ink)
        draw.rounded_rectangle((870,420,1150,590),radius=20,outline=ink,width=5)
        image.save(path)
    return paths


def seed_library(path):
    library=Library(path)
    if library.materials():return library
    slides=create_slides(path/'demo-source')
    courses=[
        library.save_course('计算机网络','demo-network','2026 秋季'),
        library.save_course('数据结构','demo-data','2026 秋季'),
        library.save_course('高等数学','demo-math','2026 秋季'),
    ]
    specs=[(courses[0],8,'网络协议与分层'),(courses[1],5,'树、图与查找'),(courses[2],4,'微分与积分')]
    all_items=[]
    day=1
    for course,count,note in specs:
        for index in range(count):
            date=f'2026-09-{day:02d}';day+=1
            material=library.prepare_images(slides[:4+(index%3)],course['title'],date,f'demo:{course["id"]}:{index}')
            library.assign([material['id']],course['id'])
            material=library.update(material['id'],note=f'{note} · 第 {index+1} 讲',lectureId=str(index+1))
            if index%4==1:
                material=library.set_selection(material['id'],[2],material['revision'])
            if index < count-2:
                library.mark_reviewed(material['id'],material['revision'])
            if index%3==0:
                material=library.get(material['id'])
                library.update(material['id'],exported=True,exportRevision=material['revision'],exportName=f'{course["title"]}-{date}.pdf')
            all_items.append(library.get(material['id']))
    last=all_items[-3]
    library.set_setting('lastMaterial',last['id'])
    library.set_setting('reviewQueue',[m['id'] for m in all_items[-3:]])
    tasks=[
        {'id':'demo-task-1','type':'export','title':'计算机网络 · 合并导出','status':'done','progress':100,'message':'已完成','error':'','materialId':all_items[0]['id']},
        {'id':'demo-task-2','type':'download','title':'数据结构 · 2026-09-11','status':'done','progress':100,'message':'已获取 6 页','error':'','materialId':all_items[10]['id']},
        {'id':'demo-task-3','type':'download','title':'高等数学 · 2026-09-16','status':'failed','progress':42,'message':'下载中断','error':'网络连接中断，可以稍后重试。','materialId':all_items[-2]['id']},
    ]
    for task in tasks:library.task_put(task)
    return library


class PrototypeBridge(DesktopBridge):
    @Slot(str,str,str)
    def request(self,request_id,command,payload):
        if command=='login':
            self.response.emit(request_id,json.dumps({'ok':True,'result':True},ensure_ascii=False));self.publish();return
        if command=='scan':
            self.scanned=True;self.publish();self.response.emit(request_id,json.dumps({'ok':True,'result':True},ensure_ascii=False));return
        super().request(request_id,command,payload)


class PreviewWindow(QMainWindow):
    def __init__(self,work):
        super().__init__();self.work=Path(work)
        self.setWindowTitle('课页 · 视觉优化原型（示例数据）')
        icon=QIcon(str(HERE/'app-icon.ico'));self.setWindowIcon(icon)
        self.resize(1440,960)
        self.web=QWebEngineView(self);self.profile=QWebEngineProfile('KeyeVisualPrototype',self)
        self.profile.setPersistentStoragePath(str(self.work/'browser'))
        self.page=QWebEnginePage(self.profile,self.web);self.web.setPage(self.page)
        self.bridge=PrototypeBridge(HERE,self,self.work/'library')
        self.bridge.auth=SimpleNamespace(user_id='demo',tenant_id='demo',cookie_str='demo',jwt_token='demo')
        self.bridge.scanned=True
        self.bridge.courses=[
            {'id':f'scan-{c}-{i}','groupId':c,'course_id':c,'sub_id':str(i),'title':title,'day':f'2026-09-{18+i:02d}'}
            for c,title in [('network','计算机网络'),('design','软件设计基础'),('english','学术英语')]
            for i in range(1,4)
        ]
        self.channel=QWebChannel(self.page);self.channel.registerObject('desktop',self.bridge);self.page.setWebChannel(self.channel)
        self.setCentralWidget(self.web);self.web.setUrl(QUrl.fromLocalFile(str(HERE/'index.html')))

    def closeEvent(self,event):
        self.bridge.shutdown();event.accept()


def main():
    if sys.platform=='win32':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Keye.VisualPrototype.0.4')
    app=QApplication(sys.argv);app.setApplicationName('KeyeVisualPrototype');app.setApplicationDisplayName('课页 · 视觉优化原型')
    app.setWindowIcon(QIcon(str(HERE/'app-icon.ico')))
    temporary=tempfile.TemporaryDirectory(prefix='keye-visual-prototype-')
    seed_library(Path(temporary.name)/'library')
    window=PreviewWindow(temporary.name);window.show()
    result=app.exec();temporary.cleanup();return result


if __name__=='__main__':sys.exit(main())

import sys
import datetime
from typing import Optional, List, Dict, Tuple
from collections import defaultdict
from pathlib import Path
import threading


from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QLineEdit, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QFrame, QFileDialog,
    QProgressBar, QDialog,QMessageBox,QProgressBar
)

from ui.theme import apply_app_theme
from ui.settings_dialog import SettingsDialog
from auth.browser_login import BrowserLoginDialog

from core.config import ConfigStore, AppConfig
from core.downloader import (
    RuntimeCfg, make_session, fetch_schedules_in_range,
    download_course_to_pdf
)


def now_ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("card", True)
        self.setFrameShape(QFrame.NoFrame)


# -------------------- Scan Worker --------------------
class ScanWorker(QThread):
    log = Signal(str)
    done = Signal(list)          # courses
    failed = Signal(str)

    def __init__(self, rt_cfg: RuntimeCfg, parent=None):
        super().__init__(parent)
        self.rt_cfg = rt_cfg

    def run(self):
        try:
            session = make_session(self.rt_cfg)
            courses = fetch_schedules_in_range(self.rt_cfg, session)
            self.done.emit(courses)
        except Exception as e:
            self.failed.emit(str(e))


# -------------------- Download Worker (Pause/Resume/Cancel + Progress) --------------------
class DownloadWorker(QThread):
    log = Signal(str)
    progress = Signal(int, int, str)    # done_count, total, status_text
    done = Signal(int, int)             # success, total
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, rt_cfg: RuntimeCfg, app_cfg: AppConfig, courses: List[Dict], parent=None):
        super().__init__(parent)
        self.rt_cfg = rt_cfg
        self.app_cfg = app_cfg
        self.courses = courses

        self._pause_event = threading.Event()
        self._pause_event.set()  # 初始不暂停
        self._cancel = False

    def request_pause(self):
        self._pause_event.clear()

    def request_resume(self):
        self._pause_event.set()

    def request_cancel(self):
        self._cancel = True
        # 如果在暂停中，先放开让线程能退出
        self._pause_event.set()

    def _checkpoint(self):
        # 取消优先
        if self._cancel:
            raise InterruptedError("cancelled")
        # 暂停：阻塞等待
        self._pause_event.wait()

    def run(self):
        try:
            if not self.app_cfg.download_dir:
                raise RuntimeError("未设置下载目录。")

            out_dir = Path(self.app_cfg.download_dir)
            out_dir.mkdir(parents=True, exist_ok=True)

            session = make_session(self.rt_cfg)

            total = len(self.courses)
            success = 0
            finished = 0

            self.log.emit(f"开始下载：{total} 节课 -> {out_dir}")
            self.progress.emit(0, total, "准备开始…")

            for idx, c in enumerate(self.courses, start=1):
                self._checkpoint()

                title = c.get("title", "")
                day = c.get("day", "")
                status = f"({idx}/{total}) {title} [{day}]"
                self.progress.emit(finished, total, status)
                self.log.emit(f"处理：{status}")

                try:
                    # download_course_to_pdf 内部会逐张下载，我们在它内部也插 checkpoint
                    pdf = download_course_to_pdf(
                        cfg=self.rt_cfg,
                        session=session,
                        course=c,
                        out_dir=out_dir,
                        keep_images=self.app_cfg.keep_images,
                        log_fn=lambda m: self.log.emit(m),
                        checkpoint_fn=self._checkpoint,          # NEW: 支持暂停/取消
                        cancel_cleanup=True                      # NEW: 如果 cancel，清理当前节课目录
                    )
                    success += 1
                except InterruptedError:
                    # 用户取消：退出
                    self.log.emit("⏹️ 已取消下载。")
                    self.cancelled.emit()
                    return
                except Exception as e:
                    self.log.emit(f"❌ 失败：{title} [{day}] -> {e}")

                finished += 1
                self.progress.emit(finished, total, f"已完成 {finished}/{total}")

            self.log.emit(f"全部结束：成功 {success}/{total}")
            self.progress.emit(total, total, "全部完成")
            self.done.emit(success, total)

        except Exception as e:
            self.failed.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GetPPTApp")
        self.resize(1080, 800)

        self.base_dir = Path(__file__).resolve().parent
        self.store = ConfigStore(self.base_dir)
        self.app_cfg: AppConfig = self.store.load()

        # 登录态
        self.cookie_str: Optional[str] = None
        self.user_id: Optional[str] = None
        self.tenant_id: Optional[str] = None
        self.jwt_token: Optional[str] = None

        # 扫描结果
        self.courses: List[Dict] = []

        # Workers
        self.scan_worker: Optional[ScanWorker] = None
        self.dl_worker: Optional[DownloadWorker] = None

        self._build_ui()
        self.log("程序启动。")
        self._ensure_download_dir_on_start()

    # ---------- UI ----------
    def _build_ui(self):
        # Header left
        self.title = QLabel("GetPPTApp")
        self.title.setObjectName("Title")

        self.subtitle = QLabel("登录后扫描课表，筛选并勾选课程，批量下载 PPT 并合并为 PDF。")
        self.subtitle.setObjectName("SubTitle")

        self.status = QLabel("状态：未登录")
        self.status.setObjectName("SubTitle")

        header_left = QVBoxLayout()
        header_left.addWidget(self.title)
        header_left.addWidget(self.subtitle)
        header_left.addSpacing(4)
        header_left.addWidget(self.status)

        # Header right buttons (同级：登录/扫描/设置)
        self.btn_login = QPushButton("登录并导入")
        self.btn_login.setProperty("primary", True)
        self.btn_login.clicked.connect(self.do_login)

        self.btn_scan = QPushButton("扫描课表")
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_scan.setEnabled(False)

        self.btn_settings = QPushButton("设置")
        self.btn_settings.clicked.connect(self.open_settings)

        header_right = QHBoxLayout()
        header_right.addStretch(1)
        header_right.addWidget(self.btn_login)
        header_right.addWidget(self.btn_scan)
        header_right.addWidget(self.btn_settings)

        header_card = Card()
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.addLayout(header_left)
        header_layout.addLayout(header_right)

        # Filter bar
        self.start_at = QLineEdit("2025-09-01")
        self.end_at = QLineEdit("2025-09-28")
        self.search = QLineEdit("")
        self.search.setPlaceholderText("筛选：输入关键字（课程名/日期），例如：运筹 / 数据库 / 09-03")
        self.search.textChanged.connect(self.apply_filter)

        self.btn_all = QPushButton("全选")
        self.btn_all.clicked.connect(self.select_all_visible)
        self.btn_all.setEnabled(False)

        self.btn_inv = QPushButton("反选")
        self.btn_inv.clicked.connect(self.invert_selection_visible)
        self.btn_inv.setEnabled(False)

        self.btn_download = QPushButton("下载选中")
        self.btn_download.setProperty("primary", True)
        self.btn_download.clicked.connect(self.start_download)
        self.btn_download.setEnabled(False)

        # Pause/Resume/Cancel
        self.btn_pause = QPushButton("暂停")
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_pause.setEnabled(False)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.cancel_download)
        self.btn_cancel.setEnabled(False)

        self.btn_log = QPushButton("显示日志")
        self.btn_log.clicked.connect(self.toggle_log)

        filter_card = Card()
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(16, 12, 16, 12)
        filter_layout.addWidget(QLabel("开始"))
        filter_layout.addWidget(self.start_at)
        filter_layout.addWidget(QLabel("结束"))
        filter_layout.addWidget(self.end_at)
        filter_layout.addSpacing(10)
        filter_layout.addWidget(self.search, stretch=1)
        filter_layout.addSpacing(10)
        filter_layout.addWidget(self.btn_all)
        filter_layout.addWidget(self.btn_inv)
        filter_layout.addWidget(self.btn_download)
        filter_layout.addWidget(self.btn_pause)
        filter_layout.addWidget(self.btn_cancel)
        filter_layout.addWidget(self.btn_log)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)

        # Progress bar + status
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(True)

        self.progress_text = QLabel("就绪")
        self.progress_text.setObjectName("SubTitle")

        prog_row = QHBoxLayout()
        prog_row.addWidget(self.progress_text, stretch=1)
        prog_row.addWidget(self.progress)

        # Log panel
        self.out = QTextEdit()
        self.out.setReadOnly(True)
        self.out.setProperty("log", True)
        self.out.setVisible(False)

        main_card = Card()
        main_layout = QVBoxLayout(main_card)
        main_layout.setContentsMargins(16, 14, 16, 14)

        self.dir_hint = QLabel(self._download_dir_text())
        self.dir_hint.setObjectName("SubTitle")

        main_layout.addWidget(self.dir_hint)
        main_layout.addLayout(prog_row)
        main_layout.addSpacing(8)
        main_layout.addWidget(QLabel("课程列表（按课程名分组，可折叠；勾选后用于下载）"))
        main_layout.addWidget(self.tree, stretch=2)

        main_layout.addSpacing(8)
        self.log_title = QLabel("运行日志（默认隐藏）")
        self.log_title.setObjectName("SubTitle")
        self.log_title.setVisible(False)
        main_layout.addWidget(self.log_title)
        main_layout.addWidget(self.out, stretch=1)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)
        root_layout.addWidget(header_card)
        root_layout.addWidget(filter_card)
        root_layout.addWidget(main_card, stretch=1)
        self.setCentralWidget(root)

    # ---------- config ----------
    def _download_dir_text(self) -> str:
        d = self.app_cfg.download_dir or "未设置（点击设置或选择下载目录）"
        keep = "保留原图" if self.app_cfg.keep_images else "不保留原图（合并后删除）"
        return f"保存路径：{d}    |    原图：{keep}    |    并发：{self.app_cfg.max_workers}"

    def _save_config(self):
        self.store.save(self.app_cfg)
        self.dir_hint.setText(self._download_dir_text())

    def _ensure_download_dir_on_start(self):
        if self.app_cfg.download_dir:
            return
        QMessageBox.information(self, "首次使用", "请先选择下载保存目录（只需选一次，之后默认使用）。")
        self.pick_download_dir()

    def pick_download_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择下载保存目录")
        if path:
            self.app_cfg.download_dir = path
            self._save_config()
            self.log(f"已设置保存路径：{path}")

    def open_settings(self):
        dlg = SettingsDialog(self.app_cfg, self)
        if dlg.exec() == QDialog.Accepted:
            self.app_cfg = dlg.result
            self._save_config()
            self.log("设置已保存。")

    # ---------- logging ----------
    def log(self, msg: str):
        self.out.append(f"[{now_ts()}] {msg}")

    def toggle_log(self):
        vis = not self.out.isVisible()
        self.out.setVisible(vis)
        self.log_title.setVisible(vis)
        self.btn_log.setText("隐藏日志" if vis else "显示日志")

    # ---------- auth ----------
    def do_login(self):
        dlg = BrowserLoginDialog(self)
        dlg.exec()

        if not dlg.parsed:
            QMessageBox.warning(self, "未导入", "没有拿到导入结果。请在登录窗口中点击“导入登录态”。")
            return

        p = dlg.parsed
        if not (p.user_id and p.tenant_id and p.jwt_token and p.cookie_str):
            QMessageBox.warning(self, "导入不完整", "未解析到完整的 user_id/tenant_id/token。")
            return

        self.cookie_str = p.cookie_str
        self.user_id = p.user_id
        self.tenant_id = p.tenant_id
        self.jwt_token = p.jwt_token

        self.status.setText(f"状态：已登录（user_id={self.user_id}, tenant_id={self.tenant_id}）")
        self.btn_scan.setEnabled(True)
        self.log("登录态导入成功。可以扫描课表。")

    def _build_rt_cfg(self) -> RuntimeCfg:
        return RuntimeCfg(
            cookie_str=self.cookie_str,
            token=self.jwt_token,
            authorization=f"Bearer {self.jwt_token}",
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            start_at=self.start_at.text().strip(),
            end_at=self.end_at.text().strip(),
            timeout=int(self.app_cfg.timeout),
            retries=int(self.app_cfg.retries),
            sleep_ms=int(self.app_cfg.sleep_ms),
            max_workers=int(self.app_cfg.max_workers),
        )

    # ---------- scan (background) ----------
    def start_scan(self):
        if not (self.cookie_str and self.user_id and self.tenant_id and self.jwt_token):
            QMessageBox.warning(self, "未登录", "请先登录并导入。")
            return

        rt = self._build_rt_cfg()
        self.progress_text.setText("正在扫描课表…")
        self.progress.setRange(0, 0)  # busy mode
        self.log(f"开始扫描课表：{rt.start_at} ~ {rt.end_at}")

        self._lock_main_buttons(True)

        self.scan_worker = ScanWorker(rt, self)
        self.scan_worker.done.connect(self.on_scan_done)
        self.scan_worker.failed.connect(self.on_scan_failed)
        self.scan_worker.start()

    def on_scan_failed(self, err: str):
        QMessageBox.critical(self, "扫描失败", err)
        self.log(f"❌ 扫描失败：{err}")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_text.setText("扫描失败")
        self._lock_main_buttons(False)

    def on_scan_done(self, courses: list):
        self.courses = courses
        self.render_grouped_tree(courses)
        self.apply_filter()

        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_text.setText("扫描完成")

        if not courses:
            self.log("⚠️ 扫描完成，但未发现任何课程。")
        else:
            self.log(f"✅ 扫描完成：共发现 {len(courses)} 节课（按 sub_id 去重）。")
            self.btn_all.setEnabled(True)
            self.btn_inv.setEnabled(True)
            self.btn_download.setEnabled(True)

        self._lock_main_buttons(False)

    # ---------- grouping + filter ----------
    def _group_courses(self, courses: List[Dict]) -> List[Tuple[str, List[Dict]]]:
        mp = defaultdict(list)
        for c in courses:
            mp[str(c.get("title", "未命名课程"))].append(c)

        grouped = []
        for title, items in mp.items():
            items.sort(key=lambda x: (x.get("day", ""), x.get("sub_id", "")))
            grouped.append((title, items))

        grouped.sort(key=lambda x: x[0])
        return grouped

    def render_grouped_tree(self, courses: List[Dict]):
        self.tree.clear()

        grouped = self._group_courses(courses)
        for title, items in grouped:
            parent = QTreeWidgetItem(self.tree)
            parent.setText(0, f"{title}   （{len(items)} 节）")
            parent.setFlags(parent.flags() | Qt.ItemIsUserCheckable)
            parent.setCheckState(0, Qt.Unchecked)
            parent.setData(0, Qt.UserRole, {"type": "group", "title": title})

            for c in items:
                child = QTreeWidgetItem(parent)
                child.setText(0, f"[{c['day']}]  sub_id={c['sub_id']}   course_id={c['course_id']}")
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)
                child.setData(0, Qt.UserRole, {"type": "item", "course": c})

            parent.setExpanded(True)

        self.tree.itemChanged.connect(self.on_tree_item_changed)

    def on_tree_item_changed(self, item: QTreeWidgetItem, col: int):
        payload = item.data(0, Qt.UserRole) or {}
        if payload.get("type") != "group":
            return
        state = item.checkState(0)
        for i in range(item.childCount()):
            item.child(i).setCheckState(0, state)

    def apply_filter(self):
        kw = self.search.text().strip().lower()
        root = self.tree.invisibleRootItem()

        for gi in range(root.childCount()):
            group = root.child(gi)
            title = group.text(0).lower()
            group_match = (not kw) or (kw in title)
            any_child_visible = False

            for ci in range(group.childCount()):
                child = group.child(ci)
                payload = child.data(0, Qt.UserRole) or {}
                c = (payload.get("course") or {})
                line = f"{c.get('day','')} {c.get('sub_id','')} {c.get('course_id','')}".lower()
                child_match = group_match or (not kw) or (kw in line)
                child.setHidden(not child_match)
                if child_match:
                    any_child_visible = True

            group.setHidden(not any_child_visible)

    def _iter_visible_items(self):
        root = self.tree.invisibleRootItem()
        for gi in range(root.childCount()):
            group = root.child(gi)
            if group.isHidden():
                continue
            for ci in range(group.childCount()):
                child = group.child(ci)
                if not child.isHidden():
                    yield child

    def select_all_visible(self):
        count = 0
        for child in self._iter_visible_items():
            child.setCheckState(0, Qt.Checked)
            count += 1
        self.log(f"已全选（当前筛选可见项）：{count} 项。")

    def invert_selection_visible(self):
        count = 0
        for child in self._iter_visible_items():
            child.setCheckState(0, Qt.Unchecked if child.checkState(0) == Qt.Checked else Qt.Checked)
            count += 1
        self.log(f"已反选（当前筛选可见项）：{count} 项。")

    def get_selected_courses(self) -> List[Dict]:
        selected = []
        root = self.tree.invisibleRootItem()
        for gi in range(root.childCount()):
            group = root.child(gi)
            for ci in range(group.childCount()):
                child = group.child(ci)
                if child.checkState(0) == Qt.Checked:
                    payload = child.data(0, Qt.UserRole) or {}
                    c = (payload.get("course") or {})
                    if c:
                        selected.append(c)
        return selected

    # ---------- download ----------
    def start_download(self):
        if not self.app_cfg.download_dir:
            QMessageBox.information(self, "需要设置保存路径", "请先选择下载保存路径。")
            self.pick_download_dir()
            if not self.app_cfg.download_dir:
                return

        if not (self.cookie_str and self.user_id and self.tenant_id and self.jwt_token):
            QMessageBox.warning(self, "未登录", "请先登录并导入。")
            return

        selected = self.get_selected_courses()
        if not selected:
            QMessageBox.information(self, "提示", "请至少勾选一节课。")
            return

        rt = self._build_rt_cfg()

        # UI 状态
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_text.setText("开始下载…")

        self.btn_pause.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.btn_pause.setText("暂停")

        self._lock_main_buttons(True)
        self.btn_pause.setEnabled(True)
        self.btn_cancel.setEnabled(True)

        self.dl_worker = DownloadWorker(rt, self.app_cfg, selected, self)
        self.dl_worker.log.connect(self.log)
        self.dl_worker.progress.connect(self.on_download_progress)
        self.dl_worker.failed.connect(self.on_download_failed)
        self.dl_worker.done.connect(self.on_download_done)
        self.dl_worker.cancelled.connect(self.on_download_cancelled)
        self.dl_worker.start()

        self.log(f"开始下载任务：{len(selected)} 节课。")

    def on_download_progress(self, done_count: int, total: int, status: str):
        self.progress_text.setText(status)
        if total <= 0:
            self.progress.setValue(0)
            return
        pct = int(done_count * 100 / total)
        self.progress.setValue(pct)

    def toggle_pause(self):
        if not self.dl_worker:
            return
        if self.btn_pause.text() == "暂停":
            self.dl_worker.request_pause()
            self.btn_pause.setText("继续")
            self.progress_text.setText("已暂停")
            self.log("⏸️ 已暂停。")
        else:
            self.dl_worker.request_resume()
            self.btn_pause.setText("暂停")
            self.log("▶️ 继续下载。")

    def cancel_download(self):
        if not self.dl_worker:
            return
        r = QMessageBox.question(
            self, "取消下载",
            "确定要取消吗？\n将清理“正在下载的那一节课”的临时目录，已完成的文件不会删除。",
            QMessageBox.Yes | QMessageBox.No
        )
        if r == QMessageBox.Yes:
            self.dl_worker.request_cancel()

    def on_download_failed(self, err: str):
        QMessageBox.critical(self, "下载失败", err)
        self.log(f"❌ 下载失败：{err}")
        self.progress_text.setText("下载失败")
        self._unlock_after_task()

    def on_download_done(self, success: int, total: int):
        QMessageBox.information(self, "完成", f"下载完成：成功 {success}/{total}\n保存路径：{self.app_cfg.download_dir}")
        self.progress_text.setText("下载完成")
        self.progress.setValue(100)
        self._unlock_after_task()

    def on_download_cancelled(self):
        QMessageBox.information(self, "已取消", "下载已取消。已完成的文件保留，正在处理的半成品已清理。")
        self.progress_text.setText("已取消")
        self._unlock_after_task()

    # ---------- lock/unlock ----------
    def _lock_main_buttons(self, locked: bool):
        # locked=True 表示任务运行中（扫描/下载）
        self.btn_login.setEnabled(not locked)
        self.btn_scan.setEnabled((not locked) and (self.cookie_str is not None))
        self.btn_settings.setEnabled(not locked)
        self.btn_download.setEnabled(not locked and bool(self.courses))
        self.btn_all.setEnabled(not locked and bool(self.courses))
        self.btn_inv.setEnabled(not locked and bool(self.courses))

    def _unlock_after_task(self):
        self._lock_main_buttons(False)
        self.btn_pause.setEnabled(False)
        self.btn_cancel.setEnabled(False)

    # ---------- helpers ----------
    def _download_dir_text(self) -> str:
        d = self.app_cfg.download_dir or "未设置（点击设置或选择下载目录）"
        keep = "保留原图" if self.app_cfg.keep_images else "不保留原图（合并后删除）"
        return f"保存路径：{d}    |    原图：{keep}    |    并发：{self.app_cfg.max_workers}"


def main():
    app = QApplication(sys.argv)
    apply_app_theme(app)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

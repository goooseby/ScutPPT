from dataclasses import replace
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QCheckBox, QFileDialog, QMessageBox, QFrame
)
from PySide6.QtCore import Qt

from core.config import AppConfig


class SettingsDialog(QDialog):
    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(680, 360)

        self._orig = cfg
        self._result = cfg

        # --- 下载目录 ---
        self.ed_dir = QLineEdit(cfg.download_dir or "")
        self.ed_dir.setPlaceholderText("请选择下载保存目录（只需选一次，之后默认使用）")

        btn_pick = QPushButton("选择文件夹")
        btn_pick.clicked.connect(self.pick_dir)

        row_dir = QHBoxLayout()
        row_dir.addWidget(QLabel("保存路径"))
        row_dir.addWidget(self.ed_dir, stretch=1)
        row_dir.addWidget(btn_pick)

        # --- 参数 ---
        self.sp_workers = QSpinBox()
        self.sp_workers.setRange(1, 64)
        self.sp_workers.setValue(int(cfg.max_workers))

        self.sp_timeout = QSpinBox()
        self.sp_timeout.setRange(5, 600)
        self.sp_timeout.setValue(int(cfg.timeout))

        self.sp_retries = QSpinBox()
        self.sp_retries.setRange(0, 20)
        self.sp_retries.setValue(int(cfg.retries))

        self.sp_sleep = QSpinBox()
        self.sp_sleep.setRange(0, 5000)
        self.sp_sleep.setValue(int(cfg.sleep_ms))

        self.chk_keep = QCheckBox("保留原图（images 文件夹）")
        self.chk_keep.setChecked(bool(cfg.keep_images))

        grid = QFrame()
        g = QVBoxLayout(grid)
        g.setContentsMargins(0, 0, 0, 0)

        def row(label, widget):
            r = QHBoxLayout()
            r.addWidget(QLabel(label))
            r.addWidget(widget)
            r.addStretch(1)
            g.addLayout(r)

        row("并发数 max_workers", self.sp_workers)
        row("超时 timeout（秒）", self.sp_timeout)
        row("重试 retries（次）", self.sp_retries)
        row("请求间隔 sleep_ms（毫秒）", self.sp_sleep)
        g.addWidget(self.chk_keep, alignment=Qt.AlignLeft)

        # --- 按钮区 ---
        btn_default = QPushButton("恢复默认")
        btn_default.clicked.connect(self.reset_default)

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("保存")
        btn_ok.setProperty("primary", True)
        btn_ok.clicked.connect(self.on_save)

        row_btn = QHBoxLayout()
        row_btn.addWidget(btn_default)
        row_btn.addStretch(1)
        row_btn.addWidget(btn_cancel)
        row_btn.addWidget(btn_ok)

        layout = QVBoxLayout(self)
        layout.addLayout(row_dir)
        layout.addSpacing(10)
        layout.addWidget(QLabel("下载力度参数（默认已可用，通常不需要改）："))
        layout.addWidget(grid)
        layout.addStretch(1)
        layout.addLayout(row_btn)

    def pick_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择下载保存目录")
        if path:
            self.ed_dir.setText(path)

    def reset_default(self):
        self.sp_workers.setValue(8)
        self.sp_timeout.setValue(60)
        self.sp_retries.setValue(3)
        self.sp_sleep.setValue(200)
        self.chk_keep.setChecked(False)

    def on_save(self):
        d = self.ed_dir.text().strip()
        if not d:
            QMessageBox.warning(self, "提示", "请先选择下载保存目录。")
            return

        self._result = replace(
            self._orig,
            download_dir=d,
            max_workers=int(self.sp_workers.value()),
            timeout=int(self.sp_timeout.value()),
            retries=int(self.sp_retries.value()),
            sleep_ms=int(self.sp_sleep.value()),
            keep_images=bool(self.chk_keep.isChecked())
        )
        self.accept()

    @property
    def result(self) -> AppConfig:
        return self._result

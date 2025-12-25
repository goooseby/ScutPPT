import re
import json
import urllib.parse
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel,
    QMessageBox, QFrame, QSizePolicy
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile


TARGET_URL = "https://video.jw.scut.edu.cn/"
# 关键：收集 scut.edu.cn 全域 cookie，支持 CAS/SSO
TARGET_HOST_SUFFIX = "scut.edu.cn"
JWT_RE = re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")


@dataclass
class ParsedAuth:
    cookie_str: str
    user_id: Optional[str]
    tenant_id: Optional[str]
    jwt_token: Optional[str]

    @property
    def authorization(self) -> Optional[str]:
        return f"Bearer {self.jwt_token}" if self.jwt_token else None


def _mask_secret(s: str, keep: int = 10) -> str:
    s = (s or "").strip()
    if len(s) <= keep * 2:
        return s
    return f"{s[:keep]}...{s[-keep:]}"


def _parse_jwtuser(cookie_value: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        decoded = urllib.parse.unquote(cookie_value)
        obj = json.loads(decoded)
        user_id = str(obj.get("id")) if obj.get("id") is not None else None
        tenant_id = str(obj.get("tenant_id")) if obj.get("tenant_id") is not None else None
        return user_id, tenant_id
    except Exception:
        return None, None


def _extract_jwt_from_token_cookie(token_cookie_value: str) -> Optional[str]:
    try:
        decoded = urllib.parse.unquote(token_cookie_value)
    except Exception:
        decoded = token_cookie_value

    m = JWT_RE.search(decoded)
    return m.group(0) if m else None


class CookieCollector:
    def __init__(self, profile: QWebEngineProfile):
        self.profile = profile
        self.cookies: Dict[str, str] = {}
        store = self.profile.cookieStore()
        store.cookieAdded.connect(self._on_cookie_added)

    def _on_cookie_added(self, cookie):
        name = bytes(cookie.name()).decode("utf-8", errors="ignore")
        value = bytes(cookie.value()).decode("utf-8", errors="ignore")
        domain = cookie.domain()
        if TARGET_HOST_SUFFIX in domain:
            self.cookies[name] = value

    def build_cookie_str(self) -> str:
        return "; ".join([f"{k}={v}" for k, v in self.cookies.items()])

    def parse_auth(self) -> ParsedAuth:
        cookie_str = self.build_cookie_str()

        user_id, tenant_id = None, None
        jwt_token = None

        if "JWTUser" in self.cookies:
            user_id, tenant_id = _parse_jwtuser(self.cookies["JWTUser"])

        if "_token" in self.cookies:
            jwt_token = _extract_jwt_from_token_cookie(self.cookies["_token"])

        return ParsedAuth(cookie_str=cookie_str, user_id=user_id, tenant_id=tenant_id, jwt_token=jwt_token)


class BrowserLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录 - 华工视频平台")
        self.resize(1100, 760)

        self.profile = QWebEngineProfile.defaultProfile()
        self.collector = CookieCollector(self.profile)
        self.parsed: Optional[ParsedAuth] = None

        self.web = QWebEngineView()
        self.web.setUrl(QUrl(TARGET_URL))

        # 顶部小工具条
        bar = QFrame()
        bar.setProperty("card", True)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(10, 8, 10, 8)

        self.tip = QLabel("提示：先在网页完成登录，再点击“导入登录态”。")
        self.tip.setObjectName("SubTitle")

        self.btn_home = QPushButton("首页")
        self.btn_home.clicked.connect(lambda: self.web.setUrl(QUrl(TARGET_URL)))

        self.btn_extract = QPushButton("导入登录态")
        self.btn_extract.setProperty("primary", True)
        self.btn_extract.clicked.connect(self.on_extract)

        self.btn_toggle = QPushButton("显示调试信息")
        self.btn_toggle.clicked.connect(self.toggle_debug)

        bar_layout.addWidget(self.tip)
        bar_layout.addStretch(1)
        bar_layout.addWidget(self.btn_home)
        bar_layout.addWidget(self.btn_toggle)
        bar_layout.addWidget(self.btn_extract)

        # 调试输出区（默认隐藏）
        self.debug = QTextEdit()
        self.debug.setReadOnly(True)
        self.debug.setVisible(False)
        self.debug.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.debug.setFixedHeight(170)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(bar)
        layout.addWidget(self.web, stretch=1)
        layout.addWidget(self.debug)

    def toggle_debug(self):
        vis = not self.debug.isVisible()
        self.debug.setVisible(vis)
        self.btn_toggle.setText("隐藏调试信息" if vis else "显示调试信息")

    def on_extract(self):
        parsed = self.collector.parse_auth()
        self.parsed = parsed

        lines = []
        lines.append(f"当前页面：{self.web.url().toString()}")
        lines.append(f"Cookie数量（*.{TARGET_HOST_SUFFIX}）：{len(self.collector.cookies)}")
        lines.append(f"user_id：{parsed.user_id or '未解析到'}")
        lines.append(f"tenant_id：{parsed.tenant_id or '未解析到'}")
        lines.append(f"jwt_token：{_mask_secret(parsed.jwt_token) if parsed.jwt_token else '未提取到'}")
        lines.append("Cookie键名：")
        lines.append(", ".join(sorted(self.collector.cookies.keys())))
        self.debug.setPlainText("\n".join(lines))

        if parsed.user_id and parsed.tenant_id and parsed.jwt_token:
            QMessageBox.information(self, "导入成功", "已导入登录态。可以关闭此窗口回主界面继续。")
        else:
            QMessageBox.warning(self, "导入不完整", "登录态不完整。请确认已成功登录后再点导入。")
            self.debug.setVisible(True)
            self.btn_toggle.setText("隐藏调试信息")

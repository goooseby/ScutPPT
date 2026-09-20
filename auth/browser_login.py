import re
import json
import os
import urllib.parse
from collections import deque
import datetime
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from core.webengine import configure_webengine

configure_webengine()

from PySide6.QtCore import QUrl, QObject, QTimer, Slot
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel,
    QMessageBox, QFrame, QSizePolicy, QProgressBar
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineLoadingInfo


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
    return "已提取（内容隐藏）" if s else "未提取到"


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


class CookieCollector(QObject):
    def __init__(self, profile: QWebEngineProfile, parent=None):
        super().__init__(parent)
        self.profile = profile
        self._cookies = {}
        store = self.profile.cookieStore()
        store.cookieAdded.connect(self._on_cookie_added)
        store.cookieRemoved.connect(self._on_cookie_removed)
        store.loadAllCookies()

    @Slot(QNetworkCookie)
    def _on_cookie_added(self, cookie):
        name = bytes(cookie.name()).decode("utf-8", errors="ignore")
        value = bytes(cookie.value()).decode("utf-8", errors="ignore")
        domain = cookie.domain()
        domain = domain.lstrip('.').lower()
        if domain == TARGET_HOST_SUFFIX or domain.endswith('.' + TARGET_HOST_SUFFIX):
            self._cookies[(domain, cookie.path() or '/', name)] = value

    @Slot(QNetworkCookie)
    def _on_cookie_removed(self, cookie):
        key = (cookie.domain().lstrip('.').lower(), cookie.path() or '/',
               bytes(cookie.name()).decode('utf-8', errors='ignore'))
        value = bytes(cookie.value()).decode('utf-8', errors='ignore')
        if self._cookies.get(key) == value:
            self._cookies.pop(key, None)

    @property
    def cookies(self):
        # SSO and video hosts may use identical cookie names. Prefer video cookies,
        # and do not import host-specific SSO cookies into video API requests.
        host = 'video.jw.scut.edu.cn'
        result = {}
        for (domain, path, name), value in sorted(self._cookies.items(), key=lambda item: (len(item[0][0]), len(item[0][1]))):
            if host == domain or host.endswith('.' + domain):
                result[name] = value
        return result

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
        self.collector = CookieCollector(self.profile, self)
        self.parsed: Optional[ParsedAuth] = None
        self.events = deque(maxlen=50)
        self.load_state = 'waiting'
        self.auth_detected = False

        self.web = QWebEngineView(self)
        self.page = QWebEnginePage(self.profile, self.web)
        self.web.setPage(self.page)

        # 顶部小工具条
        bar = QFrame()
        bar.setProperty("card", True)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(10, 8, 10, 8)

        self.tip = QLabel("请在网页中完成登录，课页会自动检测并连接。")
        self.tip.setObjectName("SubTitle")

        self.btn_home = QPushButton("首页")
        self.btn_home.clicked.connect(lambda: self.web.setUrl(QUrl(TARGET_URL)))

        self.btn_retry = QPushButton('重新加载')
        self.btn_retry.clicked.connect(self.retry_load)

        self.btn_extract = QPushButton("立即检测")
        self.btn_extract.setProperty("primary", True)
        self.btn_extract.clicked.connect(self.on_extract)

        self.btn_toggle = QPushButton("显示调试信息")
        self.btn_toggle.clicked.connect(self.toggle_debug)

        bar_layout.addWidget(self.tip)
        bar_layout.addStretch(1)
        bar_layout.addWidget(self.btn_home)
        bar_layout.addWidget(self.btn_retry)
        bar_layout.addWidget(self.btn_toggle)
        bar_layout.addWidget(self.btn_extract)

        # 调试输出区（默认隐藏）
        self.debug = QTextEdit()
        self.debug.setReadOnly(True)
        self.debug.setVisible(False)
        self.debug.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.debug.setFixedHeight(170)

        self.load_label = QLabel('正在准备学校网页登录…')
        self.load_label.setWordWrap(True)
        self.load_progress = QProgressBar()
        self.load_progress.setRange(0, 100)
        self.load_progress.setValue(0)
        self.load_progress.setFixedWidth(150)
        status_layout = QHBoxLayout()
        status_layout.addWidget(self.load_label, stretch=1)
        status_layout.addWidget(self.load_progress)

        self.slow_timer = QTimer(self)
        self.slow_timer.setSingleShot(True)
        self.slow_timer.setInterval(20000)
        self.slow_timer.timeout.connect(self.on_slow_load)
        self.auth_timer = QTimer(self)
        self.auth_timer.setInterval(700)
        self.auth_timer.timeout.connect(self.detect_auth)
        self.auth_timer.start()
        self.web.loadStarted.connect(self.on_load_started)
        self.web.loadProgress.connect(self.load_progress.setValue)
        self.web.loadFinished.connect(self.on_load_finished)
        self.page.loadingChanged.connect(self.on_loading_changed)
        self.page.renderProcessTerminated.connect(self.on_renderer_terminated)
        self.page.certificateError.connect(self.on_certificate_error)
        self.page.urlChanged.connect(self.on_url_changed)
        self.page.newWindowRequested.connect(lambda request: request.openIn(self.page))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(bar)
        layout.addLayout(status_layout)
        layout.addWidget(self.web, stretch=1)
        layout.addWidget(self.debug)
        self.finished.connect(lambda _: (self.slow_timer.stop(), self.auth_timer.stop()))
        # Connect diagnostics before the first navigation, so no failure is missed.
        self.web.setUrl(QUrl(TARGET_URL))

    def record(self, message):
        self.events.append(f"[{datetime.datetime.now():%H:%M:%S}] {message}")
        self.debug.setPlainText('\n'.join(self.events))

    def on_load_started(self):
        self.load_state = 'loading'
        self.load_label.setText('正在加载学校网页，请稍候…')
        self.load_progress.setValue(0)
        self.load_progress.setVisible(True)
        self.slow_timer.start()
        self.record('网页开始加载')

    def on_url_changed(self, url):
        # SSO query strings contain login tickets; diagnostics only show the host.
        self.record('当前网站：' + (url.host() or '本地页面'))

    def on_load_finished(self, ok):
        self.slow_timer.stop()
        self.load_progress.setVisible(False)
        if ok:
            self.load_state = 'ready'
            self.load_label.setText('网页已加载。请完成学校登录，课页正在后台自动检测…')
            self.record('网页加载完成')
        elif self.load_state != 'failed':
            self.show_load_error('网页加载未完成，请检查网络后点击“重新加载”。')

    def on_loading_changed(self, info):
        if info.status() == QWebEngineLoadingInfo.LoadStatus.LoadFailedStatus:
            domain = info.errorDomain()
            if domain == QWebEngineLoadingInfo.ErrorDomain.CertificateErrorDomain:
                reason = '网站证书校验失败，请检查系统时间、网络或代理设置。'
            elif domain == QWebEngineLoadingInfo.ErrorDomain.DnsErrorDomain:
                reason = '无法解析学校网站地址，请检查网络或 DNS。'
            elif info.errorCode() == 403:
                reason = '学校网站拒绝了当前网络出口。课页已绕过系统代理直连；请重新加载，或确认校园网 / 学校 SSLVPN 已连接。'
            else:
                reason = '学校网页加载失败，请检查网络后重试。'
            self.show_load_error(f'{reason}（错误码 {info.errorCode()}）')
            self.record(f'加载失败：{domain.name} / {info.errorCode()}')

    def show_load_error(self, message):
        self.load_state = 'failed'
        self.slow_timer.stop()
        self.load_progress.setVisible(False)
        self.load_label.setText(message)
        self.record(message)
        self.debug.setVisible(True)
        self.btn_toggle.setText('隐藏调试信息')

    def on_slow_load(self):
        if self.load_state == 'loading':
            self.load_label.setText('网页加载超过 20 秒，仍在等待响应。可以检查网络，或点击“重新加载”。')
            self.record('网页响应较慢：超过 20 秒')

    def on_renderer_terminated(self, status, exit_code):
        self.show_load_error(f'内置浏览器进程异常退出（{status.name}，{exit_code}），请点击“重新加载”。')

    def on_certificate_error(self, error):
        error.rejectCertificate()
        self.show_load_error('网站证书校验失败，未继续连接。请检查系统时间、网络或代理设置。')

    def retry_load(self):
        url = self.web.url()
        if url.scheme() not in ('https', 'http'):
            url = QUrl(TARGET_URL)
        self.record('重新加载网页')
        self.web.setUrl(url)

    def toggle_debug(self):
        vis = not self.debug.isVisible()
        self.debug.setVisible(vis)
        self.btn_toggle.setText("隐藏调试信息" if vis else "显示调试信息")

    def on_extract(self):
        self.detect_auth(show_incomplete=True)

    def detect_auth(self, show_incomplete=False):
        if self.auth_detected:
            return
        parsed = self.collector.parse_auth()
        self.parsed = None
        if parsed.cookie_str and parsed.user_id and parsed.tenant_id and parsed.jwt_token:
            self.auth_detected = True
            self.parsed = parsed
            self.auth_timer.stop()
            self.tip.setText('登录成功，课页已连接并将自动扫描课表。此窗口即将关闭。')
            self.load_label.setText('已检测到完整登录状态，可以关闭此页面。课表会自动扫描。')
            self.load_progress.setVisible(False)
            self.btn_extract.setEnabled(False)
            self.record('已自动检测到完整登录状态，正在返回课页')
            QTimer.singleShot(900, self.accept)
        elif show_incomplete:
            self.record(f"平台 Cookie：{len(self.collector.cookies)} 项；"
                        f"用户信息：{'已提取' if parsed.user_id else '未解析到'}；"
                        f"租户信息：{'已提取' if parsed.tenant_id else '未解析到'}；"
                        f"登录令牌：{_mask_secret(parsed.jwt_token)}")
            self.tip.setText('尚未完成登录。请继续操作，课页会自动检测，无需再次点击。')
            self.debug.setVisible(True)
            self.btn_toggle.setText("隐藏调试信息")

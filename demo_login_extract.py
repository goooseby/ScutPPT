import sys
import re
import json
import urllib.parse
from dataclasses import dataclass
from typing import Dict, Tuple, Optional

from PySide6.QtCore import Qt, QDateTime, QUrl
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QMessageBox
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile


TARGET_URL = "https://video.jw.scut.edu.cn/"
TARGET_HOST_SUFFIX = "jw.scut.edu.cn"

JWT_RE = re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")


@dataclass
class ParsedAuth:
    cookie_str: str
    user_id: Optional[str]
    tenant_id: Optional[str]
    jwt_token: Optional[str]


def mask_secret(s: str, keep: int = 10) -> str:
    s = s.strip()
    if len(s) <= keep * 2:
        return s
    return f"{s[:keep]}...{s[-keep:]}"


def parse_jwtuser(cookie_value: str) -> Tuple[Optional[str], Optional[str]]:
    """
    JWTUser 是 URL 编码的 JSON，例如：
    %7B%22account%22%3A...%2C%22id%22%3A653414%2C%22tenant_id%22%3A21%7D
    """
    try:
        decoded = urllib.parse.unquote(cookie_value)
        obj = json.loads(decoded)
        user_id = str(obj.get("id")) if obj.get("id") is not None else None
        tenant_id = str(obj.get("tenant_id")) if obj.get("tenant_id") is not None else None
        return user_id, tenant_id
    except Exception:
        return None, None


def extract_jwt_from_token_cookie(token_cookie_value: str) -> Optional[str]:
    """
    _token 的值通常是 URL 编码的复杂结构，但里面往往包含 JWT（eyJ...xxx.yyy.zzz）
    我们用正则直接抓 JWT，鲁棒性最好。
    """
    try:
        decoded = urllib.parse.unquote(token_cookie_value)
    except Exception:
        decoded = token_cookie_value

    m = JWT_RE.search(decoded)
    return m.group(0) if m else None


class CookieCollector:
    """
    通过 QWebEngineProfile.cookieStore() 监听 cookieAdded，
    把浏览器会话中的 cookie 都收集起来（包含 HttpOnly）。
    """
    def __init__(self, profile: QWebEngineProfile):
        self.profile = profile
        self.cookies: Dict[str, str] = {}     # name -> value（简单存）
        self.cookie_domains: Dict[str, str] = {}  # name -> domain（调试用）
        self._bind()

    def _bind(self):
        store = self.profile.cookieStore()
        store.cookieAdded.connect(self._on_cookie_added)

    def _on_cookie_added(self, cookie):
        # cookie 是 QNetworkCookie
        name = bytes(cookie.name()).decode("utf-8", errors="ignore")
        value = bytes(cookie.value()).decode("utf-8", errors="ignore")
        domain = cookie.domain()

        # 只收集目标域相关 cookie（避免把无关站点的也塞进来）
        # domain 可能是 ".jw.scut.edu.cn" 或 "video.jw.scut.edu.cn"
        if TARGET_HOST_SUFFIX in domain:
            self.cookies[name] = value
            self.cookie_domains[name] = domain

    def build_cookie_str(self) -> str:
        # 按 name=value; name=value 拼接
        parts = []
        for k, v in self.cookies.items():
            parts.append(f"{k}={v}")
        return "; ".join(parts)

    def parse_auth(self) -> ParsedAuth:
        cookie_str = self.build_cookie_str()

        user_id = None
        tenant_id = None
        jwt_token = None

        if "JWTUser" in self.cookies:
            user_id, tenant_id = parse_jwtuser(self.cookies["JWTUser"])

        # 优先从 _token 抽 JWT（你给的 cookie 里就是这个）
        if "_token" in self.cookies:
            jwt_token = extract_jwt_from_token_cookie(self.cookies["_token"])

        return ParsedAuth(
            cookie_str=cookie_str,
            user_id=user_id,
            tenant_id=tenant_id,
            jwt_token=jwt_token
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Milestone 0 - 内置登录 + 导出 Cookie + 解析 user_id/tenant_id/token")
        self.resize(1100, 760)

        # WebEngine 使用默认 Profile（持久化策略由 Qt 决定；demo 阶段够用）
        self.profile = QWebEngineProfile.defaultProfile()
        self.collector = CookieCollector(self.profile)

        self.web = QWebEngineView()
        self.web.setUrl(QUrl(TARGET_URL))

        self.btn_extract = QPushButton("我已登录 → 导入并解析登录态")
        self.btn_extract.clicked.connect(self.on_extract)

        self.btn_open = QPushButton("重新打开首页")
        self.btn_open.clicked.connect(lambda: self.web.setUrl(QUrl(TARGET_URL)))

        self.status_label = QLabel("说明：先在上方网页完成登录（账号/扫码/验证码都行），再点击导入。")
        self.status_label.setWordWrap(True)

        self.out = QTextEdit()
        self.out.setReadOnly(True)

        top_btns = QHBoxLayout()
        top_btns.addWidget(self.btn_open)
        top_btns.addWidget(self.btn_extract)
        top_btns.addStretch(1)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.web, stretch=6)
        layout.addLayout(top_btns)
        layout.addWidget(self.status_label)
        layout.addWidget(self.out, stretch=3)

        self.setCentralWidget(container)

    def on_extract(self):
        parsed = self.collector.parse_auth()

        # 基本判定：cookie 是否足够
        has_jwtuser = "JWTUser" in self.collector.cookies
        has_token_cookie = "_token" in self.collector.cookies

        # 输出（注意：不要输出完整 token/cookie）
        lines = []
        lines.append(f"导入时间：{QDateTime.currentDateTime().toString('yyyy-MM-dd HH:mm:ss')}")
        lines.append(f"当前页面：{self.web.url().toString()}")
        lines.append("")

        lines.append(f"Cookie 收集情况：共 {len(self.collector.cookies)} 个（仅限 *.{TARGET_HOST_SUFFIX}）")
        lines.append(f"是否发现 JWTUser：{'是' if has_jwtuser else '否'}")
        lines.append(f"是否发现 _token：{'是' if has_token_cookie else '否'}")
        lines.append("")

        lines.append("解析结果：")
        lines.append(f"- user_id：{parsed.user_id or '（未解析到）'}")
        lines.append(f"- tenant_id：{parsed.tenant_id or '（未解析到）'}")
        lines.append(f"- jwt_token：{mask_secret(parsed.jwt_token) if parsed.jwt_token else '（未提取到）'}")
        lines.append("")

        # 只显示 cookie 的“键名列表”，避免泄露值
        lines.append("Cookie 键名（用于诊断，不含值）：")
        keys = sorted(list(self.collector.cookies.keys()))
        lines.append(", ".join(keys))
        lines.append("")

        # 诊断提示
        if not parsed.user_id or not parsed.tenant_id:
            lines.append("⚠️ 未解析到 user_id/tenant_id：通常意味着 JWTUser 不存在或格式变化。")
        if not parsed.jwt_token:
            lines.append("⚠️ 未提取到 jwt_token：可能 _token 的结构变化，或 token 不在 cookie 中。")
            lines.append("   解决思路：后续可改为从网络请求 URL/Authorization 里抓 token（仍然在内置浏览器内完成）。")

        self.out.setPlainText("\n".join(lines))

        # 成功判断（Milestone 0 通过条件）
        if parsed.user_id and parsed.tenant_id and parsed.jwt_token:
            QMessageBox.information(
                self,
                "Milestone 0 通过",
                "已成功从内置登录态解析出 user_id / tenant_id / jwt_token。\n"
                "下一步可以把你原来的“扫课表/下载PPT”核心接进来。"
            )
        else:
            QMessageBox.warning(
                self,
                "Milestone 0 未完全通过",
                "已导入 cookie，但未能完整解析 user_id/tenant_id/token。\n"
                "请把下方输出截图发我（不要贴完整 cookie/token），我来判断下一步用哪种兜底提取方案。"
            )


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

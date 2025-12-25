from pathlib import Path

def apply_app_theme(app):
    """
    读取 ui/style.qss 并应用到整个 QApplication
    """
    qss_path = Path(__file__).resolve().parent / "style.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

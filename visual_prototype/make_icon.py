"""Render the canonical SVG logo to the PNG and Windows ICO app assets."""
from pathlib import Path
import shutil

from PIL import Image
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
PROTOTYPE = ROOT / "visual_prototype"


def build():
    app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(QByteArray((ASSETS / "app-icon.svg").read_bytes()))
    if not renderer.isValid():
        raise RuntimeError("assets/app-icon.svg is not a valid SVG")

    canvas = QImage(1024, 1024, QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, 1024, 1024))
    painter.end()

    source_path = ASSETS / ".app-icon-source.png"
    if not canvas.save(str(source_path), "PNG"):
        raise RuntimeError("failed to render app icon")
    try:
        with Image.open(source_path) as source:
            icon = source.convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS)
            icon.save(ASSETS / "app-icon.png", optimize=True)
            icon.save(
                ASSETS / "app-icon.ico",
                format="ICO",
                sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
                       (48, 48), (64, 64), (128, 128), (256, 256)],
            )
    finally:
        source_path.unlink(missing_ok=True)

    for name in ("app-icon.svg", "app-icon.png", "app-icon.ico"):
        shutil.copyfile(ASSETS / name, PROTOTYPE / name)


if __name__ == "__main__":
    build()

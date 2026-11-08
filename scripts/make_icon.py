from pathlib import Path
import sys

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

root = Path(__file__).resolve().parents[1]
assets = root / "deskpdf" / "assets"
app = QGuiApplication([])
image = QImage(1024, 1024, QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.transparent)
painter = QPainter(image)
QSvgRenderer(str(assets / "icon.svg")).render(painter)
painter.end()
image.save(str(assets / "icon.png"))
with Image.open(assets / "icon.png") as source:
    source.save(assets / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    if sys.platform == "darwin":
        source.save(assets / "icon.icns", format="ICNS")

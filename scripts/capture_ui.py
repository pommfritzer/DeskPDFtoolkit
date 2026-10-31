import os
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pymupdf as pdf
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from deskpdf.app import Window
from deskpdf.catalog import TOOL_BY_ID
from deskpdf.theme import STYLE

root = Path(__file__).resolve().parents[1]
folder = root / "docs" / "screenshots"
folder.mkdir(parents=True, exist_ok=True)
sample = root / "build" / "Project brief.pdf"
sample.parent.mkdir(exist_ok=True)
with pdf.open() as document:
    page = document.new_page(width=595, height=842)
    page.draw_rect(pdf.Rect(0, 0, 595, 130), fill=(.15, .31, .23), color=None)
    page.insert_text((45, 65), "STUDIO / FIELD NOTES", fontsize=12, color=(.78, .88, .7))
    page.insert_text((45, 100), "A clearer kind of work.", fontsize=27, color=(1, 1, 1))
    page.insert_text((45, 180), "Project brief", fontsize=24, color=(.15, .25, .2))
    page.insert_text((45, 220), "A considered approach to everyday documents.", fontsize=12)
    for index, text in enumerate(["01   Make room for the important things.", "02   Keep the process simple and local.", "03   Create something worth keeping."]):
        page.draw_line((45, 280 + index * 75), (550, 280 + index * 75), color=(.82, .86, .8))
        page.insert_text((45, 310 + index * 75), text, fontsize=14)
    page.insert_text((45, 765), "DESKPDF   /   SAMPLE DOCUMENT", fontsize=10, color=(.4, .5, .4))
    document.new_page()
    document.save(sample)
app = QApplication([])
for font in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
    path = Path("C:/Windows/Fonts") / font
    if path.exists():
        QFontDatabase.addApplicationFont(str(path))
app.setStyle("Fusion")
app.setStyleSheet(STYLE)
window = Window()
window.show()
app.processEvents()
window.grab().save(str(folder / "library.png"))
window.select_tool(TOOL_BY_ID["extract"])
window.add_paths([str(sample)])
window.fields["pages"].setText("1")
app.processEvents()
window.grab().save(str(folder / "workbench.png"))
window.resize(960, 680)
app.processEvents()
window.grab().save(str(root / "build" / "minimum-size.png"))
window.close()

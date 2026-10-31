import math

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget


class AmbientBackground(QWidget):
    def __init__(self):
        super().__init__()
        self.phase = 0
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.advance)
        self.timer.start()

    def advance(self):
        if self.window().isMinimized() or not self.isVisible():
            return
        self.phase += .004
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor("#092e2b"))
        gradient.setColorAt(.55, QColor("#235c48"))
        gradient.setColorAt(1, QColor("#101f30"))
        painter.fillRect(self.rect(), gradient)
        for band in range(7):
            wave = QPainterPath()
            for x in range(-40, self.width() + 50, 16):
                y = self.height() * (.42 + band * .055) + math.sin(x / 360 + self.phase + band * .22) * 95 + math.sin(x / 650 - self.phase) * 60
                if x == -40:
                    wave.moveTo(x, y)
                else:
                    wave.lineTo(x, y)
            painter.setPen(QPen(QColor(133, 210, 167, 14 + band * 2), 18 + band * 9))
            painter.drawPath(wave)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(177, 190, 188, 65))
        for x in range(20, self.width(), 34):
            for y in range(20, self.height(), 34):
                painter.drawEllipse(x, y, 2, 2)


def tool_icon(tool):
    drawings = {
        "Organize": '<rect x="17" y="19" width="30" height="39" rx="4"/><rect x="28" y="10" width="30" height="39" rx="4"/><path d="M35 29h15m-6-6 6 6-6 6"/>',
        "Optimize": '<path d="M15 13h16v16H15zm28 0h16v16H43zM15 43h16v16H15zm28 0h16v16H43zM25 25l11 11m11-11L36 36m-11 11 11-11m11 11L36 36"/>',
        "Convert": '<path d="M13 17h39l-8-8m8 8-8 8M59 55H20l8 8m-8-8 8-8"/><rect x="26" y="28" width="20" height="17" rx="3"/>',
        "Edit & sign": '<path d="M16 53l4-15L47 11l13 13-27 27-17 2zm7-17 13 13M43 15l13 13M15 63h45"/>',
        "Security": '<rect x="17" y="31" width="38" height="31" rx="6"/><path d="M25 31V21a11 11 0 0 1 22 0v10m-11 11v10"/>',
    }
    drawings["Optimize"] = {"compress": drawings["Optimize"], "flatten": '<path d="m12 27 24-14 24 14-24 14-24-14zm0 14 24 14 24-14M12 53l24 14 24-14"/>', "clean": '<path d="M20 12h25l11 11v39H20zM44 12v14h12M28 38h20m-20 9h13m4 8 16-16"/>'}.get(tool.id, drawings["Optimize"])
    symbol = {"merge": "M18 37h36m-9-9 9 9-9 9", "extract": "M22 50l27-27m-14 0h14v14", "rotate": "M22 29a17 17 0 1 1-1 19m1-19v14H10", "split": "M36 53V32m0 0L18 14m18 18 18-18", "delete": "M20 36h32", "reorder": "M18 24h36m-8-8 8 8-8 8M54 48H18m8-8-8 8 8 8"}.get(tool.id)
    drawing = f'<path d="{symbol}"/>' if symbol else drawings[tool.group]
    formats = {"images_to_pdf": "PDF", "pdf_to_png": "PNG", "text": "TXT", "word": "DOC", "excel": "XLS", "powerpoint": "PPT", "office": "PDF", "ocr": "OCR"}
    if tool.id in formats:
        drawing = f'<path d="M19 8h25l12 12v44H19zM44 8v15h12"/><text x="37" y="47" fill="#bde2cd" stroke="none" text-anchor="middle" font-family="sans-serif" font-size="13">{formats[tool.id]}</text>'
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72" viewBox="0 0 72 72"><g fill="none" stroke="#bde2cd" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">{drawing}</g></svg>'
    pixmap = QPixmap(144, 144)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    return QIcon(pixmap)

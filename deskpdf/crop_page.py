import pymupdf as pdf
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget


class CropCanvas(QWidget):
    def __init__(self, page):
        super().__init__()
        scale = min(480 / page.rect.width, 580 / page.rect.height)
        pix = page.get_pixmap(matrix=pdf.Matrix(scale, scale), alpha=False)
        self.image = QPixmap.fromImage(QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy())
        self.setFixedSize(pix.width, pix.height)
        self.selection = QRectF(0, 0, pix.width, pix.height)
        self.edges = ""

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawPixmap(0, 0, self.image)
        p.setPen(QPen(QColor("#237c50"), 2))
        p.drawRect(self.selection)
        p.setBrush(QColor("#b6dfbd"))
        r = self.selection
        for x in (r.left(), r.center().x(), r.right()):
            for y in (r.top(), r.center().y(), r.bottom()):
                if x != r.center().x() or y != r.center().y():
                    p.drawRect(QRectF(x - 5, y - 5, 10, 10))

    def mousePressEvent(self, event):
        q = event.position()
        r = self.selection
        self.edges = ("l" if abs(q.x() - r.left()) < 14 else "r" if abs(q.x() - r.right()) < 14 else "") + ("t" if abs(q.y() - r.top()) < 14 else "b" if abs(q.y() - r.bottom()) < 14 else "")
        if not self.edges:
            self.anchor = q
            self.edges = "new"

    def mouseMoveEvent(self, event):
        q = QPointF(max(0, min(self.width(), event.position().x())), max(0, min(self.height(), event.position().y())))
        r = QRectF(self.selection)
        if self.edges == "new":
            r = QRectF(self.anchor, q).normalized()
        else:
            if "l" in self.edges: r.setLeft(min(q.x(), r.right() - 20))
            if "r" in self.edges: r.setRight(max(q.x(), r.left() + 20))
            if "t" in self.edges: r.setTop(min(q.y(), r.bottom() - 20))
            if "b" in self.edges: r.setBottom(max(q.y(), r.top() + 20))
        if r.width() >= 20 and r.height() >= 20:
            self.selection = r
            self.update()

    def mouseReleaseEvent(self, event):
        self.edges = ""


class CropPageDialog(QDialog):
    def __init__(self, page, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crop page")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Drag an edge or corner, or draw a new crop rectangle."))
        self.canvas = CropCanvas(page)
        layout.addWidget(self.canvas, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(QLabel("Cropping hides margins; it does not securely remove their contents."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Reset)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self.reset)
        layout.addWidget(buttons)
        self.page_rect = page.rect
        self.derotation = page.derotation_matrix
        self.origin = page.cropbox.tl

    def reset(self):
        self.canvas.selection = QRectF(self.canvas.rect())
        self.canvas.update()

    def cropbox(self):
        r = self.canvas.selection
        box = pdf.Rect(r.left() / self.canvas.width() * self.page_rect.width, r.top() / self.canvas.height() * self.page_rect.height, r.right() / self.canvas.width() * self.page_rect.width, r.bottom() / self.canvas.height() * self.page_rect.height) * self.derotation
        return tuple(box + (self.origin.x, self.origin.y, self.origin.x, self.origin.y))

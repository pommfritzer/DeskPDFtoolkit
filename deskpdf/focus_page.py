from pathlib import Path

import pymupdf as pdf
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import QCheckBox, QDialog, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from deskpdf.engine import open_document


class PageFocus(QDialog):
    def __init__(self, workspace, row, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDFtoolkit26 · Page focus")
        self.workspace = workspace
        self.row = row
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.caption = QLabel()
        top.addWidget(self.caption, 1)
        self.included = QCheckBox("Include page")
        self.included.toggled.connect(self.set_included)
        top.addWidget(self.included)
        close = QPushButton("Back to pages · Esc")
        close.clicked.connect(self.reject)
        top.addWidget(close)
        layout.addLayout(top)
        body = QHBoxLayout()
        self.previous = QPushButton("❮")
        self.previous.setAccessibleName("Previous page")
        self.previous.setFixedWidth(56)
        self.previous.clicked.connect(lambda: self.navigate(-1))
        self.next = QPushButton("❯")
        self.next.setAccessibleName("Next page")
        self.next.setFixedWidth(56)
        self.next.clicked.connect(lambda: self.navigate(1))
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        body.addWidget(self.previous)
        body.addWidget(self.view, 1)
        body.addWidget(self.next)
        layout.addLayout(body, 1)
        for key, action in (("Left", lambda: self.navigate(-1)), ("Right", lambda: self.navigate(1)), ("Ctrl++", lambda: self.view.scale(1.2, 1.2)), ("Ctrl+-", lambda: self.view.scale(1 / 1.2, 1 / 1.2))):
            QShortcut(QKeySequence(key), self, activated=action)
        self.render()

    def set_included(self, checked):
        self.workspace.pages.item(self.row).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def navigate(self, offset):
        self.row = max(0, min(self.workspace.pages.count() - 1, self.row + offset))
        self.render()

    def render(self):
        item = self.workspace.pages.item(self.row)
        path, number = item.data(Qt.ItemDataRole.UserRole)
        with open_document(Path(path), self.workspace.password) as document:
            page = document[number]
            crop = self.workspace.crops.get((path, number))
            if crop:
                page.set_cropbox(pdf.Rect(crop))
            pix = page.get_pixmap(matrix=pdf.Matrix(2, 2), alpha=False)
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
        self.scene.clear()
        self.scene.addPixmap(QPixmap.fromImage(image))
        self.scene.setSceneRect(0, 0, pix.width, pix.height)
        self.caption.setText(f"{Path(path).name} · Page {number + 1} · {self.row + 1}/{self.workspace.pages.count()}")
        self.included.blockSignals(True)
        self.included.setChecked(item.checkState() == Qt.CheckState.Checked)
        self.included.blockSignals(False)
        self.previous.setEnabled(self.row > 0)
        self.next.setEnabled(self.row + 1 < self.workspace.pages.count())
        QTimer.singleShot(0, self.fit)

    def fit(self):
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "view"):
            self.fit()

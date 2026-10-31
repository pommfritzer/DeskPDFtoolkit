from pathlib import Path

import pymupdf as pdf
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from deskpdf.engine import open_document


class MergeView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Click pages to include or remove them."))
        self.pages = QListWidget()
        self.pages.setViewMode(QListWidget.ViewMode.IconMode)
        self.pages.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.pages.setIconSize(QSize(80, 110))
        self.pages.setMinimumHeight(220)
        self.pages.itemClicked.connect(self.toggle)
        layout.addWidget(self.pages)
        layout.addWidget(QLabel("Output order — drag pages to rearrange"))
        self.output = QListWidget()
        self.output.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.output.setMinimumHeight(170)
        layout.addWidget(self.output)

    def selection(self):
        return [self.output.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.output.count())]

    def refresh(self, path, paths, password):
        for index in reversed(range(self.output.count())):
            if Path(self.output.item(index).data(Qt.ItemDataRole.UserRole)[0]) not in paths:
                self.output.takeItem(index)
        self.pages.clear()
        if not path:
            return
        selected = self.selection()
        with open_document(path, password) as document:
            for index, page in enumerate(document):
                pix = page.get_pixmap(matrix=pdf.Matrix(.2, .2), alpha=False)
                image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
                item = QListWidgetItem(QIcon(QPixmap.fromImage(image)), f"Page {index + 1}")
                key = (str(path), index)
                item.setData(Qt.ItemDataRole.UserRole, key)
                item.setCheckState(Qt.CheckState.Checked if key in selected else Qt.CheckState.Unchecked)
                self.pages.addItem(item)

    def toggle(self, item):
        key = item.data(Qt.ItemDataRole.UserRole)
        for index, existing in enumerate(self.selection()):
            if existing == key:
                self.output.takeItem(index)
                item.setCheckState(Qt.CheckState.Unchecked)
                return
        output = QListWidgetItem(item.icon(), f"{Path(key[0]).name} · Page {key[1] + 1}")
        output.setData(Qt.ItemDataRole.UserRole, key)
        self.output.addItem(output)
        item.setCheckState(Qt.CheckState.Checked)

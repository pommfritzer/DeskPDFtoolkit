from pathlib import Path

import pymupdf as pdf
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from deskpdf.engine import open_document


class PageGrid(QListWidget):
    def move_page(self, source, destination):
        if source >= 0 and source != destination:
            item = self.takeItem(source)
            self.insertItem(destination, item)
            self.setCurrentItem(item)
            self.doItemsLayout()

    def dropEvent(self, event):
        if event.source() is not self:
            event.ignore()
            return
        destination = self.indexAt(event.position().toPoint()).row()
        self.move_page(self.currentRow(), destination if destination >= 0 else self.count() - 1)
        event.acceptProposedAction()


class MergeView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Click to select pages. Drag thumbnails into output order."))
        self.pages = PageGrid()
        self.pages.setViewMode(QListWidget.ViewMode.IconMode)
        self.pages.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.pages.setIconSize(QSize(110, 145))
        self.pages.setMinimumHeight(220)
        self.pages.itemClicked.connect(self.toggle)
        self.pages.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.pages.setMovement(QListWidget.Movement.Snap)
        self.pages.setGridSize(QSize(155, 220))
        self.loaded = set()
        layout.addWidget(self.pages)
        controls = QHBoxLayout()
        for title, checked in (("Select all", True), ("Clear selection", False)):
            action = QPushButton(title)
            action.clicked.connect(lambda unused=False, value=checked: self.select_all(value))
            controls.addWidget(action)
        layout.addLayout(controls)

    def select_all(self, checked):
        for index in range(self.pages.count()):
            self.pages.item(index).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def selection(self):
        return [self.pages.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.pages.count()) if self.pages.item(i).checkState() == Qt.CheckState.Checked]

    def refresh(self, paths, password):
        active = {str(path) for path in paths}
        for index in reversed(range(self.pages.count())):
            if self.pages.item(index).data(Qt.ItemDataRole.UserRole)[0] not in active:
                self.pages.takeItem(index)
        self.loaded.intersection_update(active)
        errors = []
        for path in paths:
            if str(path) in self.loaded:
                continue
            items = []
            try:
                with open_document(path, password) as document:
                    for index, page in enumerate(document):
                        scale = min(110 / page.rect.width, 145 / page.rect.height)
                        pix = page.get_pixmap(matrix=pdf.Matrix(scale, scale), alpha=False)
                        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
                        painter = QPainter(image)
                        painter.setPen(QColor("#b9c3b6"))
                        painter.drawRect(0, 0, image.width() - 1, image.height() - 1)
                        painter.end()
                        item = QListWidgetItem(QIcon(QPixmap.fromImage(image)), f"Page {index + 1}\n{path.stem[:18]}")
                        item.setToolTip(f"{path.name} · Page {index + 1}")
                        item.setData(Qt.ItemDataRole.UserRole, (str(path), index))
                        item.setCheckState(Qt.CheckState.Unchecked)
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                        items.append(item)
            except Exception as error:
                errors.append(f"{path.name}: {error}")
                continue
            for item in items:
                self.pages.addItem(item)
            self.loaded.add(str(path))
        if errors:
            raise ValueError("\n".join(errors))

    def toggle(self, item):
        item.setCheckState(Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked)

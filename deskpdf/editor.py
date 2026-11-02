import copy
from dataclasses import dataclass
from html import escape
from pathlib import Path

import pymupdf as pdf
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import QComboBox, QDialog, QFileDialog, QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget, QMessageBox

from deskpdf.engine import open_document
from deskpdf.crop_page import CropPageDialog


from deskpdf.objects import Object, apply_objects, export_objects


class ObjectItem(QGraphicsRectItem):
    def __init__(self, obj, editor):
        super().__init__(QRectF(0, 0, obj.rect[2] - obj.rect[0], obj.rect[3] - obj.rect[1]))
        self.obj = obj
        self.editor = editor
        self.setPos(obj.rect[0], obj.rect[1])
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.resizing = False
        self.image = QPixmap(obj.image) if obj.kind == "Image" else None

    def paint(self, painter, option, widget=None):
        r = self.rect()
        painter.setPen(QPen(QColor(self.obj.color), 2))
        if self.obj.kind == "Image":
            painter.drawPixmap(r, self.image, QRectF(self.image.rect()))
        elif self.obj.kind == "Rectangle":
            painter.drawRect(r)
        elif self.obj.kind == "Ellipse":
            painter.drawEllipse(r)
        else:
            font = QFont({"Sans": "Arial", "Serif": "Georgia", "Mono": "Courier New"}[self.obj.family])
            font.setPixelSize(self.obj.size)
            font.setBold(self.obj.bold)
            font.setItalic(self.obj.italic)
            painter.setFont(font)
            painter.setClipRect(r)
            painter.drawText(r, Qt.TextFlag.TextWordWrap, self.obj.text)
        if self.isSelected():
            painter.setClipping(False)
            painter.setPen(QPen(QColor("#3baf70"), 1, Qt.PenStyle.DashLine))
            painter.drawRect(r)
            painter.fillRect(QRectF(r.right() - 9, r.bottom() - 9, 9, 9), QColor("#3baf70"))

    def mousePressEvent(self, event):
        self.editor.remember()
        self.resizing = event.pos().x() > self.rect().right() - 16 and event.pos().y() > self.rect().bottom() - 16
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            self.setRect(0, 0, max(24, event.pos().x()), max(24, event.pos().y()))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        bounds = self.editor.document[self.editor.page].rect
        self.setPos(max(0, min(self.pos().x(), bounds.width - self.rect().width())), max(0, min(self.pos().y(), bounds.height - self.rect().height())))
        self.editor.capture()
        super().mouseReleaseEvent(event)


class VisualEditor(QDialog):
    def __init__(self, path, password="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDFtoolkit26 · Editor")
        self.resize(1200, 850)
        self.path = Path(path)
        self.document = open_document(self.path, password)
        self.output_password = password if self.document.needs_pass else None
        self.objects = {}
        self.page = 0
        self.history = []
        self.future = []
        self.dirty = False
        self.loading = False
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        for title, action in (("←", lambda: self.navigate(-1)), ("→", lambda: self.navigate(1)), ("Text", lambda: self.add("Text")), ("Picture", self.add_image), ("Rectangle", lambda: self.add("Rectangle")), ("Ellipse", lambda: self.add("Ellipse")), ("Crop", self.crop), ("Undo", self.undo), ("Redo", self.redo), ("Delete", self.delete), ("Save a copy…", self.save)):
            button = QPushButton(title)
            button.clicked.connect(action)
            bar.addWidget(button)
        layout.addLayout(bar)
        self.page_label = QLabel()
        layout.addWidget(self.page_label)
        body = QHBoxLayout()
        self.scene = QGraphicsScene(self)
        self.scene.selectionChanged.connect(self.show_properties)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        body.addWidget(self.view, 1)
        props = QWidget()
        props.setFixedWidth(240)
        controls = QVBoxLayout(props)
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("Select a text box to edit its words")
        self.text.setMaximumHeight(200)
        self.family = QComboBox()
        self.family.addItems(["Sans", "Serif", "Mono"])
        self.size = QSpinBox()
        self.size.setRange(6, 144)
        self.size.setSuffix(" pt")
        self.bold = QPushButton("Bold")
        self.bold.setCheckable(True)
        self.italic = QPushButton("Italic")
        self.italic.setCheckable(True)
        self.color = QComboBox()
        self.color.addItems(["Forest", "Black", "Blue", "Red"])
        for caption, widget in (("Text", self.text), ("Font", self.family), ("Size", self.size), ("", self.bold), ("", self.italic), ("Color", self.color)):
            if caption: controls.addWidget(QLabel(caption))
            controls.addWidget(widget)
        controls.addStretch()
        body.addWidget(props)
        layout.addLayout(body, 1)
        self.text.textChanged.connect(self.apply_properties)
        self.family.currentTextChanged.connect(self.apply_properties)
        self.size.valueChanged.connect(self.apply_properties)
        self.bold.toggled.connect(self.apply_properties)
        self.italic.toggled.connect(self.apply_properties)
        self.color.currentIndexChanged.connect(self.apply_properties)
        QShortcut(QKeySequence("Ctrl++"), self, activated=lambda: self.view.scale(1.15, 1.15))
        QShortcut(QKeySequence("Ctrl+-"), self, activated=lambda: self.view.scale(1 / 1.15, 1 / 1.15))
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self.redo)
        self.render()

    def showEvent(self, event):
        super().showEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def capture(self):
        entries = []
        for item in reversed(self.scene.items()):
            if isinstance(item, ObjectItem):
                r = item.rect().translated(item.pos())
                item.obj.rect = (r.left(), r.top(), r.right(), r.bottom())
                entries.append(item.obj)
        self.objects[self.page] = entries

    def remember(self):
        self.capture()
        self.history.append((self.document.tobytes(), copy.deepcopy(self.objects), self.page))
        self.history = self.history[-30:]
        self.future.clear()
        self.dirty = True

    def restore(self, source, target):
        if not source: return
        self.capture()
        target.append((self.document.tobytes(), copy.deepcopy(self.objects), self.page))
        data, self.objects, self.page = source.pop()
        self.document.close()
        self.document = pdf.open(stream=data)
        self.dirty = True
        self.render()

    def undo(self): self.restore(self.history, self.future)
    def redo(self): self.restore(self.future, self.history)

    def render(self):
        self.loading = True
        self.scene.clear()
        page = self.document[self.page]
        pix = page.get_pixmap(matrix=pdf.Matrix(1.5, 1.5), alpha=False)
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
        background = self.scene.addPixmap(QPixmap.fromImage(image))
        background.setScale(1 / 1.5)
        background.setZValue(-100)
        self.scene.setSceneRect(0, 0, page.rect.width, page.rect.height)
        for obj in self.objects.get(self.page, []): self.scene.addItem(ObjectItem(obj, self))
        self.page_label.setText(f"{self.path.name} · Page {self.page + 1} / {len(self.document)}")
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.loading = False
        self.show_properties()

    def selected(self):
        return next((item for item in self.scene.selectedItems() if isinstance(item, ObjectItem)), None)

    def show_properties(self):
        if self.loading: return
        self.loading = True
        item = self.selected()
        is_text = bool(item and item.obj.kind == "Text")
        self.text.setEnabled(is_text)
        for control in (self.family, self.size, self.bold, self.italic):
            control.setEnabled(is_text)
        self.color.setEnabled(bool(item and item.obj.kind != "Image"))
        if item:
            obj = item.obj
            self.text.setPlainText(obj.text)
            self.family.setCurrentText(obj.family)
            self.size.setValue(obj.size)
            self.bold.setChecked(obj.bold)
            self.italic.setChecked(obj.italic)
            self.color.setCurrentIndex(["#204c37", "#111111", "#225fbc", "#bc3434"].index(obj.color))
        self.loading = False

    def apply_properties(self):
        item = self.selected()
        if self.loading or not item: return
        self.remember()
        obj = item.obj
        obj.text, obj.family, obj.size = self.text.toPlainText(), self.family.currentText(), self.size.value()
        obj.bold, obj.italic = self.bold.isChecked(), self.italic.isChecked()
        obj.color = ["#204c37", "#111111", "#225fbc", "#bc3434"][self.color.currentIndex()]
        item.update()

    def add(self, kind, image=""):
        self.remember()
        self.scene.clearSelection()
        item = ObjectItem(Object(kind, (40, 60, 260, 150), image=image), self)
        bounds = self.document[self.page].rect
        item.setPos((bounds.width - 220) / 2, (bounds.height - 90) / 2)
        self.scene.addItem(item)
        item.setSelected(True)
        self.capture()

    def add_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Insert picture", "", "Pictures (*.png *.jpg *.jpeg *.bmp)")
        if path: self.add("Image", path)

    def delete(self):
        if not self.selected(): return
        self.remember()
        for item in self.scene.selectedItems():
            if isinstance(item, ObjectItem): self.scene.removeItem(item)
        self.capture()

    def navigate(self, offset):
        self.capture()
        self.page = max(0, min(len(self.document) - 1, self.page + offset))
        self.render()

    def crop(self):
        page = self.document[self.page]
        dialog = CropPageDialog(page, self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        self.remember()
        old = page.cropbox
        box = pdf.Rect(dialog.cropbox())
        page.set_cropbox(box)
        delta = pdf.Point(old.x0 - box.x0, old.y0 - box.y0) * page.rotation_matrix - pdf.Point(0, 0) * page.rotation_matrix
        for obj in self.objects.get(self.page, []):
            r = pdf.Rect(obj.rect) + (delta.x, delta.y, delta.x, delta.y)
            obj.rect = tuple(r)
        self.render()

    def save(self):
        output, _ = QFileDialog.getSaveFileName(self, "Save edited PDF", str(self.path.with_name(self.path.stem + "-edited.pdf")), "PDF (*.pdf)")
        if not output: return
        if Path(output).resolve() == self.path.resolve():
            QMessageBox.information(self, "Save a copy", "Choose a new filename to preserve the original.")
            return
        self.capture()
        try:
            from tempfile import TemporaryDirectory
            destination = Path(output)
            with TemporaryDirectory(dir=destination.parent) as folder:
                staged = Path(folder) / "edited.pdf"
                with pdf.open(stream=self.document.tobytes()) as working:
                    export_objects(working, self.objects, staged, self.output_password)
                staged.replace(destination)
            self.dirty = False
            self.page_label.setText(f"Saved {destination.name}")
        except Exception as error:
            QMessageBox.warning(self, "Could not save", str(error))

    def closeEvent(self, event):
        if self.dirty and QMessageBox.question(self, "Unsaved edits", "Discard unsaved edits?", QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Discard:
            event.ignore()
            return
        self.dirty = False
        if not self.document.is_closed:
            self.document.close()
        event.accept()

    def reject(self):
        if self.dirty and QMessageBox.question(self, "Unsaved edits", "Discard unsaved edits?", QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Discard:
            return
        self.dirty = False
        if not self.document.is_closed:
            self.document.close()
        super().reject()

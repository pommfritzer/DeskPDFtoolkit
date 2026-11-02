import copy
from dataclasses import dataclass
from html import escape
from pathlib import Path

import pymupdf as pdf
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import QColorDialog, QComboBox, QDialog, QFileDialog, QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QDoubleSpinBox, QVBoxLayout, QWidget, QMessageBox

from deskpdf.engine import open_document
from deskpdf.crop_page import CropPageDialog


from deskpdf.objects import Object, apply_objects, export_objects, remove_originals


class ObjectItem(QGraphicsRectItem):
    def __init__(self, obj, editor):
        super().__init__(QRectF(0, 0, obj.rect[2] - obj.rect[0], obj.rect[3] - obj.rect[1]))
        self.obj = obj
        self.editor = editor
        self.setPos(obj.rect[0], obj.rect[1])
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(1 if obj.source_rect and obj.kind == "Image" else 2 if obj.source_rect else 3)
        self.setAcceptHoverEvents(True)
        self.resizing = False
        self.image = QPixmap() if obj.kind == "Image" else None
        if self.image is not None:
            self.image.loadFromData(obj.image_data) if obj.image_data else self.image.load(obj.image)

    def paint(self, painter, option, widget=None):
        r = self.rect()
        painter.setOpacity(self.obj.opacity)
        painter.setPen(QPen(QColor(self.obj.color), 2))
        if self.obj.source_rect and not self.obj.modified:
            pass
        elif self.obj.kind == "Image":
            painter.drawPixmap(r, self.image, QRectF(self.image.rect()))
        elif self.obj.kind == "Rectangle":
            painter.drawRect(r)
        elif self.obj.kind == "Ellipse":
            painter.drawEllipse(r)
        else:
            font = QFont({"Sans": "Arial", "Serif": "Georgia", "Mono": "Courier New"}[self.obj.family])
            font.setPixelSize(max(1, round(self.obj.size)))
            font.setBold(self.obj.bold)
            font.setItalic(self.obj.italic)
            painter.setFont(font)
            painter.setClipRect(r)
            painter.drawText(r, Qt.TextFlag.TextWordWrap, self.obj.text)
        if self.isSelected():
            painter.setOpacity(1)
            painter.setClipping(False)
            painter.setPen(QPen(QColor("#3baf70"), 1, Qt.PenStyle.DashLine))
            painter.drawRect(r)
            painter.fillRect(QRectF(r.right() - 9, r.bottom() - 9, 9, 9), QColor("#3baf70"))

    def mousePressEvent(self, event):
        self.before_edit = self.editor.snapshot()
        self.before_rect = (self.pos().x(), self.pos().y(), self.rect().width(), self.rect().height())
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
        after = (self.pos().x(), self.pos().y(), self.rect().width(), self.rect().height())
        if after != self.before_rect:
            self.editor.remember(self.before_edit)
            self.obj.modified = True
        self.editor.capture()
        if after != self.before_rect:
            self.editor.refresh_background()
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
        self.content_hint = QLabel("Select text or a picture on the page")
        self.content_hint.setWordWrap(True)
        self.content_hint.setToolTip("Some overlapping, rotated or flattened content cannot be edited separately.")
        controls.addWidget(self.content_hint)
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("Select a text box to edit its words")
        self.text.setMaximumHeight(200)
        self.family = QComboBox()
        self.family.addItems(["Sans", "Serif", "Mono"])
        self.size = QDoubleSpinBox()
        self.size.setRange(.1, 1000)
        self.size.setDecimals(2)
        self.size.setSuffix(" pt")
        self.bold = QPushButton("Bold")
        self.bold.setCheckable(True)
        self.italic = QPushButton("Italic")
        self.italic.setCheckable(True)
        self.color = QComboBox()
        for name, value in (("Forest", "#204c37"), ("Black", "#111111"), ("Blue", "#225fbc"), ("Red", "#bc3434")):
            self.color.addItem(name, value)
        self.custom_color = QPushButton("Choose color…")
        self.custom_color.clicked.connect(self.choose_color)
        for caption, widget in (("Text", self.text), ("Font", self.family), ("Size", self.size), ("", self.bold), ("", self.italic), ("Color", self.color), ("", self.custom_color)):
            if caption: controls.addWidget(QLabel(caption))
            controls.addWidget(widget)
        controls.addStretch()
        self.replace_image = QPushButton("Replace picture…")
        self.replace_image.clicked.connect(self.change_image)
        controls.insertWidget(0, self.replace_image)
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
                if not item.obj.source_rect or item.obj.modified:
                    entries.append(item.obj)
        entries.extend(obj for obj in self.objects.get(self.page, []) if obj.removed)
        self.objects[self.page] = entries

    def snapshot(self):
        self.capture()
        return self.document.tobytes(), copy.deepcopy(self.objects), self.page

    def remember(self, snapshot=None):
        self.history.append(snapshot if snapshot is not None else self.snapshot())
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
        self.content_hint.setText("Existing content on rotated pages cannot be edited yet." if page.rotation else "Select text or a picture on the page")
        self.background = self.scene.addPixmap(QPixmap())
        self.background.setScale(1 / 1.5)
        self.background.setZValue(-100)
        self.refresh_background()
        self.scene.setSceneRect(0, 0, page.rect.width, page.rect.height)
        entries = self.objects.get(self.page, [])
        changed = {obj.source_id for obj in entries if obj.source_id}
        for obj in self.existing_objects(page):
            if obj.source_id not in changed:
                self.scene.addItem(ObjectItem(obj, self))
        for obj in entries:
            if not obj.removed:
                self.scene.addItem(ObjectItem(obj, self))
        self.page_label.setText(f"{self.path.name} · Page {self.page + 1} / {len(self.document)}")
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.loading = False
        self.show_properties()

    def refresh_background(self):
        with pdf.open(stream=self.document.tobytes()) as preview:
            page = preview[self.page]
            remove_originals(page, self.objects.get(self.page, []))
            pix = page.get_pixmap(matrix=pdf.Matrix(1.5, 1.5), alpha=False)
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
            self.background.setPixmap(QPixmap.fromImage(image))

    def existing_objects(self, page):
        if page.rotation or any(annot.type[0] == pdf.PDF_ANNOT_REDACT for annot in page.annots() or []):
            return []
        objects = []
        blocks = page.get_text("dict")["blocks"]
        original_boxes = {"Text": [], "Image": []}
        for block in blocks:
            if block["type"] == 0:
                for line in block["lines"]:
                    original_boxes["Text"].extend(pdf.Rect(span["bbox"]) for span in line["spans"] if span["text"].strip())
            elif block["type"] == 1:
                original_boxes["Image"].append(pdf.Rect(block["bbox"]))
        for block_index, block in enumerate(blocks):
            if block["type"] == 0:
                for line_index, line in enumerate(block["lines"]):
                    if tuple(line["dir"]) != (1.0, 0.0):
                        continue
                    for span_index, span in enumerate(line["spans"]):
                        if not span["text"].strip():
                            continue
                        box = pdf.Rect(span["bbox"]) * page.rotation_matrix
                        flags = span["flags"]
                        font = span["font"].lower()
                        family = "Mono" if flags & 8 else "Serif" if flags & 4 else "Sans"
                        color = f"#{span['color']:06x}"
                        origin = span["origin"]
                        identity = f"{origin[0] + page.cropbox.x0:.1f}:{origin[1] + page.cropbox.y0:.1f}:{span['text']}"
                        objects.append(Object("Text", tuple(box), text=span["text"], family=family,
                                              size=span["size"], bold=bool(flags & 16) or "bold" in font,
                                              italic=bool(flags & 2), color=color, source_rect=tuple(box),
                                              baseline_ratio=(origin[1] - span["bbox"][1]) / span["size"],
                                              opacity=span.get("alpha", 255) / 255,
                                              source_id=f"t:{identity}", modified=False))
            elif block["type"] == 1 and block.get("image"):
                transform = block.get("transform", (1, 0, 0, 1, 0, 0))
                if abs(transform[1]) > .001 or abs(transform[2]) > .001 or transform[0] <= 0 or transform[3] <= 0:
                    continue
                box = pdf.Rect(block["bbox"]) * page.rotation_matrix
                image_data = block["image"]
                if block.get("mask"):
                    try:
                        image_data = pdf.Pixmap(pdf.Pixmap(image_data), pdf.Pixmap(block["mask"])).tobytes("png")
                    except (RuntimeError, ValueError):
                        continue
                identity = f"{box.x0 + page.cropbox.x0:.1f}:{box.y0 + page.cropbox.y0:.1f}:{box.width:.1f}:{box.height:.1f}"
                objects.append(Object("Image", tuple(box), image_data=image_data, source_rect=tuple(box),
                                      source_id=f"i:{identity}", modified=False))
        safe = []
        for obj in objects:
            box = pdf.Rect(obj.source_rect)
            if obj.kind == "Text":
                box.y0 += box.height * .15
                box.y1 -= box.height * .15
            if sum(box.intersects(other) for other in original_boxes[obj.kind]) != 1:
                continue
            safe.append(obj)
        return safe

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
        self.custom_color.setEnabled(bool(item and item.obj.kind != "Image"))
        self.replace_image.setVisible(bool(item and item.obj.kind == "Image"))
        if item:
            obj = item.obj
            self.text.setPlainText(obj.text)
            self.family.setCurrentText(obj.family)
            self.size.setValue(obj.size)
            self.bold.setChecked(obj.bold)
            self.italic.setChecked(obj.italic)
            self.set_color(obj.color)
        self.loading = False

    def set_color(self, color):
        index = self.color.findData(color)
        if index < 0:
            self.color.addItem(color.upper(), color)
            index = self.color.count() - 1
        self.color.setCurrentIndex(index)

    def choose_color(self):
        item = self.selected()
        if not item:
            return
        color = QColorDialog.getColor(QColor(item.obj.color), self, "Choose color")
        if color.isValid():
            self.set_color(color.name())

    def apply_properties(self):
        item = self.selected()
        if self.loading or not item: return
        self.remember()
        obj = item.obj
        obj.text, obj.family, obj.size = self.text.toPlainText(), self.family.currentText(), self.size.value()
        obj.bold, obj.italic = self.bold.isChecked(), self.italic.isChecked()
        obj.color = self.color.currentData()
        obj.modified = True
        self.capture()
        self.refresh_background()
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

    def change_image(self):
        item = self.selected()
        if not item or item.obj.kind != "Image": return
        path, _ = QFileDialog.getOpenFileName(self, "Replace picture", "", "Pictures (*.png *.jpg *.jpeg *.bmp)")
        if not path: return
        self.remember()
        item.obj.image = path
        item.obj.image_data = b""
        item.obj.modified = True
        item.image.load(path)
        self.capture()
        self.refresh_background()
        item.update()

    def delete(self):
        if not self.selected(): return
        self.remember()
        for item in self.scene.selectedItems():
            if isinstance(item, ObjectItem):
                if item.obj.source_rect:
                    item.obj.modified = True
                    item.obj.removed = True
                    entries = self.objects.setdefault(self.page, [])
                    if not any(obj is item.obj for obj in entries):
                        entries.append(item.obj)
                self.scene.removeItem(item)
        self.capture()
        self.refresh_background()

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
            if obj.source_rect:
                obj.source_rect = tuple(pdf.Rect(obj.source_rect) + (delta.x, delta.y, delta.x, delta.y))
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

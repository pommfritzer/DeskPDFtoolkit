import copy
import time
from dataclasses import dataclass
from html import escape
from pathlib import Path

import pymupdf as pdf
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog, QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QRadioButton, QDoubleSpinBox, QVBoxLayout, QWidget, QMessageBox

from deskpdf.engine import open_document
from deskpdf.crop_page import CropPageDialog


from deskpdf.objects import Object, apply_related_forms, apply_objects, decode_pdf_name, embedded_text_font, export_objects, rebase_objects_for_crop, remove_originals, selected_form_values


class FormFieldItem(QGraphicsRectItem):
    def __init__(self, obj, editor):
        super().__init__(QRectF(*obj.rect[:2], obj.rect[2] - obj.rect[0], obj.rect[3] - obj.rect[1]))
        self.obj = obj
        self.editor = editor
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(10)
        self.setToolTip(obj.form_name)

    def paint(self, painter, option, widget=None):
        if self.isSelected():
            painter.setPen(QPen(QColor("#3baf70"), 2, Qt.PenStyle.DashLine))
            painter.drawRect(self.rect())

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.obj.form_type == pdf.PDF_WIDGET_TYPE_CHECKBOX and self.rect().contains(event.pos()):
            self.editor.set_form_value("Off" if self.editor.form_checked(self.obj) else self.obj.form_on)
        elif self.obj.form_type == pdf.PDF_WIDGET_TYPE_RADIOBUTTON and self.rect().contains(event.pos()):
            self.editor.set_form_value(self.obj.form_on)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if self.obj.form_type == pdf.PDF_WIDGET_TYPE_TEXT:
            target = self.editor.form_multiline if not self.editor.form_multiline.isHidden() else self.editor.form_text
            target.setFocus()


class ObjectItem(QGraphicsRectItem):
    def __init__(self, obj, editor):
        super().__init__(QRectF(0, 0, obj.rect[2] - obj.rect[0], obj.rect[3] - obj.rect[1]))
        self.obj = obj
        self.editor = editor
        self.setPos(obj.rect[0], obj.rect[1])
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(4 if obj.kind == "Redaction" else 1 if obj.source_rect and obj.kind == "Image" else 2 if obj.source_rect else 3)
        self.setAcceptHoverEvents(True)
        self.resizing = False
        self.image = QPixmap() if obj.kind == "Image" else None
        if self.image is not None:
            self.image.loadFromData(obj.image_data) if obj.image_data else self.image.load(obj.image)

    def paint(self, painter, option, widget=None):
        r = self.rect()
        painter.save()
        if self.obj.rotation == 90:
            painter.translate(r.width(), 0)
            painter.rotate(90)
            r = QRectF(0, 0, r.height(), r.width())
        elif self.obj.rotation == 180:
            painter.translate(r.width(), r.height())
            painter.rotate(180)
        elif self.obj.rotation == 270:
            painter.translate(0, r.height())
            painter.rotate(270)
            r = QRectF(0, 0, r.height(), r.width())
        painter.setOpacity(self.obj.opacity)
        painter.setPen(QPen(QColor(self.obj.color), 2))
        if self.obj.source_rect and not self.obj.modified:
            pass
        elif self.obj.kind == "Image":
            painter.drawPixmap(r, self.image, QRectF(self.image.rect()))
        elif self.obj.kind == "Redaction":
            painter.fillRect(r, QColor("black"))
        elif self.obj.kind == "Rectangle":
            painter.drawRect(r)
        elif self.obj.kind == "Ellipse":
            painter.drawEllipse(r)
        else:
            baseline = (self.obj.baseline_ratio or 1.075) * self.obj.size
            use_embedded = embedded_text_font(self.obj, r.width(), baseline, r.height())
            family = self.editor.embedded_font_family(self.obj.source_font) if use_embedded else ""
            font = QFont(family or {"Sans": "Arial", "Serif": "Georgia", "Mono": "Courier New"}[self.obj.family])
            font.setPixelSize(max(1, round(self.obj.size)))
            font.setBold(self.obj.bold)
            font.setItalic(self.obj.italic)
            painter.setFont(font)
            painter.setClipRect(r)
            if family:
                painter.drawText(QPointF(0, baseline), self.obj.text)
            else:
                painter.drawText(r, Qt.TextFlag.TextWordWrap, self.obj.text)
        painter.restore()
        if self.isSelected():
            r = self.rect()
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
        self.password = password
        self.objects = {}
        self.page = 0
        self.history = []
        self.future = []
        self.dirty = False
        self.loading = False
        self.preview_fonts = {}
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        for title, action in (("←", lambda: self.navigate(-1)), ("→", lambda: self.navigate(1)), ("Text", lambda: self.add("Text")), ("Picture", self.add_image), ("Rectangle", lambda: self.add("Rectangle")), ("Ellipse", lambda: self.add("Ellipse")), ("Redact area", lambda: self.add("Redaction")), ("Crop", self.crop), ("Undo", self.undo), ("Redo", self.redo), ("Delete", self.delete), ("Save a copy…", self.save)):
            button = QPushButton(title)
            button.clicked.connect(action)
            if title == "Redact area":
                button.setToolTip("Drag and resize the black area. Saving removes covered page content. Flatten overlapping form fields or annotations first; review metadata separately.")
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
        properties = QVBoxLayout(props)
        properties.setContentsMargins(0, 0, 0, 0)
        self.form_panel = QWidget()
        form_controls = QVBoxLayout(self.form_panel)
        form_controls.setContentsMargins(0, 0, 0, 0)
        self.form_label = QLabel()
        self.form_label.setWordWrap(True)
        self.form_text = QLineEdit()
        self.form_multiline = QPlainTextEdit()
        self.form_multiline.setMaximumHeight(200)
        self.form_check = QCheckBox("Checked")
        self.form_radio = QRadioButton("Selected")
        self.form_radio.setAutoExclusive(False)
        self.form_choice = QComboBox()
        self.form_choice.setEditable(True)
        self.form_multi = QListWidget()
        self.form_multi.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.form_multi.setMaximumHeight(240)
        for widget in (self.form_label, self.form_text, self.form_multiline, self.form_check, self.form_radio, self.form_choice, self.form_multi):
            form_controls.addWidget(widget)
        form_controls.addStretch()
        properties.addWidget(self.form_panel)
        self.design_panel = QWidget()
        controls = QVBoxLayout(self.design_panel)
        controls.setContentsMargins(0, 0, 0, 0)
        properties.addWidget(self.design_panel)
        self.content_hint = QLabel("Select text, a picture or a form field on the page")
        self.content_hint.setWordWrap(True)
        self.content_hint.setToolTip("Some overlapping, individually rotated or flattened content cannot be edited separately.")
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
        self.form_text.textEdited.connect(self.set_form_value)
        self.form_multiline.textChanged.connect(lambda: self.set_form_value(self.form_multiline.toPlainText()))
        self.form_check.toggled.connect(self.set_form_checked)
        self.form_radio.toggled.connect(self.set_form_checked)
        self.form_choice.currentIndexChanged.connect(lambda: self.set_form_value(self.form_choice.currentData()))
        self.form_choice.lineEdit().textEdited.connect(self.set_form_value)
        self.form_multi.itemSelectionChanged.connect(self.set_multichoice)
        QShortcut(QKeySequence("Ctrl++"), self, activated=lambda: self.view.scale(1.15, 1.15))
        QShortcut(QKeySequence("Ctrl+-"), self, activated=lambda: self.view.scale(1 / 1.15, 1 / 1.15))
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self.redo)
        self.render()

    def embedded_font_family(self, data):
        if data not in self.preview_fonts:
            identifier = QFontDatabase.addApplicationFontFromData(data)
            families = QFontDatabase.applicationFontFamilies(identifier) if identifier >= 0 else []
            self.preview_fonts[data] = (identifier, families[0] if families else "")
        return self.preview_fonts[data][1]

    def release_preview_fonts(self):
        for identifier, _ in self.preview_fonts.values():
            if identifier >= 0:
                QFontDatabase.removeApplicationFont(identifier)
        self.preview_fonts.clear()

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
            elif isinstance(item, FormFieldItem) and item.obj.modified:
                entries.append(item.obj)
        entries.extend(obj for obj in self.objects.get(self.page, []) if obj.removed)
        self.objects[self.page] = entries

    def document_data(self):
        return self.document.tobytes(encryption=pdf.PDF_ENCRYPT_KEEP)

    def open_document_data(self, data):
        document = pdf.open(stream=data)
        if document.needs_pass and not document.authenticate(self.password):
            document.close()
            raise ValueError("Could not open the encrypted document copy.")
        return document

    def snapshot(self):
        self.capture()
        return self.document_data(), copy.deepcopy(self.objects), self.page

    def remember(self, snapshot=None):
        self.history.append(snapshot if snapshot is not None else self.snapshot())
        self.history = self.history[-30:]
        self.future.clear()
        self.dirty = True

    def restore(self, source, target):
        if not source: return
        self.capture()
        target.append((self.document_data(), copy.deepcopy(self.objects), self.page))
        data, self.objects, self.page = source.pop()
        self.document.close()
        self.document = self.open_document_data(data)
        self.dirty = True
        self.render()

    def undo(self): self.restore(self.history, self.future)
    def redo(self): self.restore(self.future, self.history)

    def render(self):
        self.loading = True
        self.scene.clear()
        page = self.document[self.page]
        self.content_hint.setText("Select text, a picture or a form field on the page")
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
            if obj.kind != "Form" and not obj.removed:
                self.scene.addItem(ObjectItem(obj, self))
        saved_fields = {obj.form_xref: obj for obj in entries if obj.kind == "Form"}
        latest_groups = {}
        for page_entries in self.objects.values():
            for obj in page_entries:
                if obj.kind == "Form":
                    latest_groups[obj.form_group] = max(latest_groups.get(obj.form_group, 0), obj.form_seq)
        for obj in self.preview_fields:
            saved = saved_fields.get(obj.form_xref)
            if saved and saved.form_seq >= latest_groups.get(saved.form_group, 0):
                obj = saved
            self.scene.addItem(FormFieldItem(obj, self))
        self.page_label.setText(f"{self.path.name} · Page {self.page + 1} / {len(self.document)}")
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.loading = False
        self.show_properties()

    def refresh_background(self):
        with self.open_document_data(self.document_data()) as preview:
            related = [(index, obj) for index, entries in self.objects.items() for obj in entries if obj.kind == "Form"]
            apply_related_forms(preview, related)
            page = preview[self.page]
            remove_originals(page, self.objects.get(self.page, []))
            pix = page.get_pixmap(matrix=pdf.Matrix(1.5, 1.5), alpha=False)
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
            self.background.setPixmap(QPixmap.fromImage(image))
            self.preview_fields = self.form_fields(page)

    def form_fields(self, page):
        supported = {pdf.PDF_WIDGET_TYPE_TEXT, pdf.PDF_WIDGET_TYPE_CHECKBOX, pdf.PDF_WIDGET_TYPE_RADIOBUTTON, pdf.PDF_WIDGET_TYPE_COMBOBOX, pdf.PDF_WIDGET_TYPE_LISTBOX}
        fields = []
        for widget in page.widgets() or []:
            if widget.field_type not in supported or widget.field_flags & pdf.PDF_FIELD_IS_READ_ONLY:
                continue
            if widget.field_type == pdf.PDF_WIDGET_TYPE_COMBOBOX and widget.field_flags & pdf.PDF_CH_FIELD_IS_MULTI_SELECT:
                continue
            on_state = widget.on_state()
            if widget.field_type == pdf.PDF_WIDGET_TYPE_RADIOBUTTON and on_state is None:
                continue
            if widget.field_type == pdf.PDF_WIDGET_TYPE_RADIOBUTTON and isinstance(on_state, str):
                on_state = decode_pdf_name(on_state)
            box = tuple(widget.rect * page.rotation_matrix)
            parent_type, parent_value = page.parent.xref_get_key(widget.xref, "Parent")
            if widget.field_type == pdf.PDF_WIDGET_TYPE_RADIOBUTTON and parent_type != "xref":
                continue
            parent = int(parent_value.split()[0]) if parent_type == "xref" else widget.xref
            fields.append(Object("Form", box, source_rect=box, source_id=f"form:{widget.xref}", modified=False,
                                 form_xref=widget.xref, form_name=widget.field_name, form_label=widget.field_label or widget.field_name,
                                 form_value=selected_form_values(widget) if widget.field_type == pdf.PDF_WIDGET_TYPE_LISTBOX and widget.field_flags & pdf.PDF_CH_FIELD_IS_MULTI_SELECT else widget.field_value,
                                 form_type=widget.field_type, form_flags=widget.field_flags,
                                 form_choices=tuple(widget.choice_values or ()), form_on=on_state,
                                 form_maxlen=widget.text_maxlen or 0, form_group=f"{parent}:{widget.field_name}"))
        return fields

    def existing_objects(self, page):
        if any(annot.type[0] == pdf.PDF_ANNOT_REDACT for annot in page.annots() or []):
            return []
        objects = []
        embedded_fonts = {}
        for xref, _, _, name, *_ in page.get_fonts(full=True):
            try:
                font_data = page.parent.extract_font(xref)[3]
                if font_data:
                    key = "".join(char.lower() for char in name.split("+")[-1] if char.isalnum())
                    embedded_fonts.setdefault(key, []).append(font_data)
            except (RuntimeError, ValueError):
                continue
        blocks = page.get_text("dict")["blocks"]
        form_rects = [widget.rect for widget in page.widgets() or []]
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
                        if any(pdf.Rect(span["bbox"]).intersects(rect) for rect in form_rects):
                            continue
                        flags = span["flags"]
                        font = span["font"].lower()
                        family = "Mono" if flags & 8 else "Serif" if flags & 4 else "Sans"
                        color = f"#{span['color']:06x}"
                        origin = span["origin"]
                        identity = f"{origin[0] + page.cropbox.x0:.1f}:{origin[1] + page.cropbox.y0:.1f}:{span['text']}"
                        bold, italic = bool(flags & 16) or "bold" in font, bool(flags & 2)
                        key = "".join(char.lower() for char in span["font"].split("+")[-1] if char.isalnum())
                        fonts = embedded_fonts.get(key, [])
                        objects.append(Object("Text", tuple(box), text=span["text"], family=family,
                                              size=span["size"], bold=bold, italic=italic, color=color, source_rect=tuple(box),
                                              source_font=fonts[0] if len(fonts) == 1 else b"", source_style=(family, bold, italic),
                                              baseline_ratio=(origin[1] - span["bbox"][1]) / span["size"],
                                              opacity=span.get("alpha", 255) / 255, rotation=page.rotation,
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
                unrotated = pdf.Rect(block["bbox"])
                identity = f"{unrotated.x0 + page.cropbox.x0:.1f}:{unrotated.y0 + page.cropbox.y0:.1f}:{unrotated.width:.1f}:{unrotated.height:.1f}"
                objects.append(Object("Image", tuple(box), image_data=image_data, source_rect=tuple(box),
                                      source_id=f"i:{identity}", modified=False, rotation=page.rotation))
        safe = []
        for obj in objects:
            box = pdf.Rect(obj.source_rect) * page.derotation_matrix
            if obj.kind == "Text":
                box.y0 += box.height * .15
                box.y1 -= box.height * .15
            if sum(box.intersects(other) for other in original_boxes[obj.kind]) != 1:
                continue
            safe.append(obj)
        return safe

    def selected(self):
        return next((item for item in self.scene.selectedItems() if isinstance(item, (ObjectItem, FormFieldItem))), None)

    def show_properties(self):
        if self.loading: return
        self.loading = True
        item = self.selected()
        is_form = isinstance(item, FormFieldItem)
        self.form_panel.setVisible(is_form)
        self.design_panel.setVisible(not is_form)
        if is_form:
            obj = item.obj
            self.form_label.setText(obj.form_label or "Form field")
            for control in (self.form_text, self.form_multiline, self.form_check, self.form_radio, self.form_choice, self.form_multi):
                control.setAccessibleName(obj.form_label or "Form field")
            is_text = obj.form_type == pdf.PDF_WIDGET_TYPE_TEXT
            multiline = is_text and bool(obj.form_flags & pdf.PDF_TX_FIELD_IS_MULTILINE) and not obj.form_flags & pdf.PDF_TX_FIELD_IS_PASSWORD
            self.form_text.setVisible(is_text and not multiline)
            self.form_multiline.setVisible(multiline)
            self.form_check.setVisible(obj.form_type == pdf.PDF_WIDGET_TYPE_CHECKBOX)
            self.form_radio.setVisible(obj.form_type == pdf.PDF_WIDGET_TYPE_RADIOBUTTON)
            multi = obj.form_type == pdf.PDF_WIDGET_TYPE_LISTBOX and bool(obj.form_flags & pdf.PDF_CH_FIELD_IS_MULTI_SELECT)
            self.form_multi.setVisible(multi)
            self.form_choice.setVisible(obj.form_type in (pdf.PDF_WIDGET_TYPE_COMBOBOX, pdf.PDF_WIDGET_TYPE_LISTBOX) and not multi)
            if is_text:
                self.form_text.setEchoMode(QLineEdit.EchoMode.Password if obj.form_flags & pdf.PDF_TX_FIELD_IS_PASSWORD else QLineEdit.EchoMode.Normal)
                self.form_text.setMaxLength(obj.form_maxlen or 32767)
                self.form_text.setText(str(obj.form_value or ""))
                self.form_multiline.setPlainText(str(obj.form_value or ""))
            elif obj.form_type == pdf.PDF_WIDGET_TYPE_CHECKBOX:
                self.form_check.setChecked(self.form_checked(obj))
            elif obj.form_type == pdf.PDF_WIDGET_TYPE_RADIOBUTTON:
                self.form_radio.setChecked(self.form_checked(obj))
            elif multi:
                self.form_multi.clear()
                for choice in obj.form_choices:
                    value, title = choice if isinstance(choice, (list, tuple)) and len(choice) == 2 else (choice, choice)
                    row = QListWidgetItem(str(title))
                    row.setData(Qt.ItemDataRole.UserRole, value)
                    self.form_multi.addItem(row)
                    row.setSelected(value in obj.form_value)
            else:
                self.form_choice.clear()
                editable = bool(obj.form_flags & pdf.PDF_CH_FIELD_IS_EDIT)
                self.form_choice.lineEdit().setReadOnly(not editable)
                self.form_choice.addItem("Choose…", "")
                for choice in obj.form_choices:
                    value, title = choice if isinstance(choice, (list, tuple)) and len(choice) == 2 else (choice, choice)
                    self.form_choice.addItem(str(title), value)
                index = self.form_choice.findData(obj.form_value)
                self.form_choice.setCurrentIndex(max(0, index))
                if index < 0 and editable and obj.form_value:
                    self.form_choice.setEditText(str(obj.form_value))
            self.loading = False
            return
        is_text = bool(item and item.obj.kind == "Text")
        self.text.setEnabled(is_text)
        for control in (self.family, self.size, self.bold, self.italic):
            control.setEnabled(is_text)
        self.color.setEnabled(bool(item and item.obj.kind not in ("Image", "Redaction")))
        self.custom_color.setEnabled(bool(item and item.obj.kind not in ("Image", "Redaction")))
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

    @staticmethod
    def form_checked(obj):
        if obj.form_type == pdf.PDF_WIDGET_TYPE_RADIOBUTTON:
            return obj.form_value == obj.form_on and obj.form_on not in (None, "Off")
        return obj.form_value not in (None, "", "Off", False)

    def set_form_checked(self, checked):
        if self.loading:
            return
        item = self.selected()
        if isinstance(item, FormFieldItem):
            if item.obj.form_type == pdf.PDF_WIDGET_TYPE_RADIOBUTTON and not checked:
                self.loading = True
                self.form_radio.setChecked(self.form_checked(item.obj))
                self.loading = False
                return
            self.set_form_value(item.obj.form_on if checked else "Off")

    def set_multichoice(self):
        self.set_form_value(tuple(self.form_multi.item(index).data(Qt.ItemDataRole.UserRole)
                                  for index in range(self.form_multi.count()) if self.form_multi.item(index).isSelected()))

    def set_form_value(self, value):
        item = self.selected()
        if self.loading or not isinstance(item, FormFieldItem) or value is None or value == item.obj.form_value:
            return
        if item.obj.form_type == pdf.PDF_WIDGET_TYPE_TEXT and item.obj.form_maxlen:
            value = value[:item.obj.form_maxlen]
            if not self.form_multiline.isHidden() and self.form_multiline.toPlainText() != value:
                self.loading = True
                self.form_multiline.setPlainText(value)
                cursor = self.form_multiline.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.form_multiline.setTextCursor(cursor)
                self.loading = False
        if value == item.obj.form_value:
            return
        self.remember()
        item.obj.form_value = value
        item.obj.modified = True
        item.obj.form_seq = time.monotonic_ns()
        for sibling in self.scene.items():
            if isinstance(sibling, FormFieldItem) and sibling is not item and sibling.obj.form_group == item.obj.form_group:
                sibling.obj.form_value = "Off" if item.obj.form_type == pdf.PDF_WIDGET_TYPE_RADIOBUTTON and sibling.obj.form_on != value else value
                sibling.obj.modified = False
        self.capture()
        self.refresh_background()
        if item.obj.form_type in (pdf.PDF_WIDGET_TYPE_CHECKBOX, pdf.PDF_WIDGET_TYPE_RADIOBUTTON):
            self.loading = True
            control = self.form_radio if item.obj.form_type == pdf.PDF_WIDGET_TYPE_RADIOBUTTON else self.form_check
            control.setChecked(self.form_checked(item.obj))
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
        if self.loading or not isinstance(item, ObjectItem): return
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
        if not any(isinstance(item, ObjectItem) for item in self.scene.selectedItems()): return
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
        old_derotation = page.derotation_matrix
        box = pdf.Rect(dialog.cropbox())
        page.set_cropbox(box)
        rebase_objects_for_crop(self.objects.get(self.page, []), old, old_derotation, page)
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
                with self.open_document_data(self.document_data()) as working:
                    export_objects(working, self.objects, staged)
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
        self.release_preview_fonts()
        if not self.document.is_closed:
            self.document.close()
        event.accept()

    def reject(self):
        if self.dirty and QMessageBox.question(self, "Unsaved edits", "Discard unsaved edits?", QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Discard:
            return
        self.dirty = False
        self.release_preview_fonts()
        if not self.document.is_closed:
            self.document.close()
        super().reject()

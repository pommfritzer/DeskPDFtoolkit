from pathlib import Path
import tempfile
import uuid

import pymupdf as pdf
from PySide6.QtCore import QSize, Qt, QTimer, Signal, QEvent
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QInputDialog, QStyleOptionViewItem, QStyledItemDelegate, QStyle, QDialog, QSlider, QHBoxLayout, QPushButton, QLabel, QListWidget, QListWidgetItem, QToolTip, QVBoxLayout, QWidget

from deskpdf.engine import open_document
from deskpdf.add_page import AddPageDialog
from deskpdf.crop_page import CropPageDialog
from deskpdf.objects import rebase_objects_for_crop


class PageActions(QStyledItemDelegate):
    def paint(self, painter, option, index):
        display = QStyleOptionViewItem(option)
        self.initStyleOption(display, index)
        display.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        display.state &= ~QStyle.StateFlag.State_Selected
        style = display.widget.style() if display.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, display, painter, display.widget)
        painter.save()
        if index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked.value:
            image_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemDecoration, display, display.widget)
            painter.fillRect(image_rect, QColor(46, 139, 86, 68))
            painter.setPen(QPen(QColor("#78d7a0"), 3))
            painter.drawRect(image_rect.adjusted(1, 1, -2, -2))
        color = index.data(Qt.ItemDataRole.UserRole + 4) or "#bde2cd"
        painter.setPen(QColor(color))
        painter.drawLine(option.rect.left() + 4, option.rect.top() + 4, option.rect.right() - 4, option.rect.top() + 4)
        for offset, text in ((8, "×"), (38, "⌗"), (68, "focus")):
            rect = option.rect.adjusted(option.rect.width() - 32, offset, -6, -(option.rect.height() - offset - 26))
            painter.fillRect(rect, QColor("#163f32"))
            painter.setPen(QPen(QColor(color), 1.5))
            x, y = rect.left(), rect.top()
            if text == "×":
                painter.drawLine(x + 8, y + 8, x + 18, y + 18)
                painter.drawLine(x + 18, y + 8, x + 8, y + 18)
            elif text == "focus":
                painter.drawRect(x + 6, y + 6, 14, 14)
                painter.drawLine(x + 9, y + 17, x + 18, y + 8)
            else:
                painter.drawLine(x + 8, y + 4, x + 8, y + 18)
                painter.drawLine(x + 8, y + 18, x + 22, y + 18)
                painter.drawLine(x + 4, y + 8, x + 18, y + 8)
                painter.drawLine(x + 18, y + 8, x + 18, y + 22)
        painter.drawText(option.rect.adjusted(8, 8, -40, -option.rect.height() + 34), str(index.data(Qt.ItemDataRole.UserRole + 5) or ""))
        painter.restore()


class PageGrid(QListWidget):
    order_changed = Signal()
    delete_page = Signal(int)
    crop_page = Signal(int)
    focus_page = Signal(int)
    set_action = Signal(int)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.currentItem():
            item = self.currentItem()
            item.setCheckState(Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked)
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.count():
            painter = QPainter(self.viewport())
            painter.setPen(QColor("#b5c9bf"))
            painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, "Add PDFs to get started")

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip:
            index = self.indexAt(event.pos())
            if index.isValid():
                rect = self.visualRect(index)
                x, y = event.pos().x() - rect.left(), event.pos().y() - rect.top()
                if x > rect.width() - 36 and 8 <= y < 95:
                    QToolTip.showText(event.globalPos(), "Delete page" if y < 36 else "Crop page" if y < 66 else "Focus and edit page", self)
                    return True
        return super().viewportEvent(event)

    def mouseReleaseEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if index.isValid():
            rect = self.visualRect(index)
            x = event.position().x() - rect.left()
            y = event.position().y() - rect.top()
            if x > rect.width() - 36 and 8 <= y < 95:
                row = index.row()
                self.blockSignals(True)
                super().mouseReleaseEvent(event)
                self.blockSignals(False)
                (self.delete_page if y < 36 else self.crop_page if y < 66 else self.focus_page).emit(row)
                return
            if x < 70 and y < 36 and index.data(Qt.ItemDataRole.UserRole + 5):
                row = index.row()
                self.blockSignals(True)
                super().mouseReleaseEvent(event)
                self.blockSignals(False)
                self.set_action.emit(row)
                return
        super().mouseReleaseEvent(event)

    def move_page(self, source, destination):
        if source >= 0 and source != destination:
            item = self.takeItem(source)
            self.insertItem(destination, item)
            self.setCurrentItem(item)
            self.doItemsLayout()
            self.order_changed.emit()

    def dropEvent(self, event):
        if event.source() is not self:
            event.ignore()
            return
        destination = self.indexAt(event.position().toPoint()).row()
        self.move_page(self.currentRow(), destination if destination >= 0 else self.count() - 1)
        event.acceptProposedAction()


class MergeView(QWidget):
    page_created = Signal(str)
    save_requested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.controls = QWidget()
        self.controls_layout = QVBoxLayout(self.controls)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        zoom = QHBoxLayout()
        zoom.addStretch()
        self.zoom = QSlider(Qt.Orientation.Horizontal)
        self.zoom.setRange(140, 650)
        self.zoom.setValue(260)
        self.zoom.hide()
        minus = QPushButton("−")
        plus = QPushButton("+")
        minus.setFixedWidth(36)
        plus.setFixedWidth(36)
        minus.clicked.connect(lambda: self.zoom.setValue(self.zoom.value() - 26))
        plus.clicked.connect(lambda: self.zoom.setValue(self.zoom.value() + 26))
        self.zoom_label = QLabel("100%")
        zoom.addWidget(minus)
        zoom.addWidget(self.zoom_label)
        zoom.addWidget(plus)
        self.controls_layout.addLayout(zoom)
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self.render_thumbnails)
        self.source_paths = []
        self.password = ""
        self.pages = PageGrid()
        self.pages.setItemDelegate(PageActions(self.pages))
        self.pages.order_changed.connect(self.update_sets)
        self.pages.delete_page.connect(self.delete_page)
        self.pages.crop_page.connect(self.crop_page)
        self.pages.focus_page.connect(self.focus_page)
        self.pages.set_action.connect(self.toggle_set)
        self.crops = {}
        self.edits = {}
        self.edits_dirty = False
        self.collapsed = set()
        self.pages.setViewMode(QListWidget.ViewMode.IconMode)
        self.pages.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.pages.setIconSize(QSize(260, 360))
        self.pages.setMinimumHeight(220)
        self.pages.itemClicked.connect(self.toggle)
        self.pages.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.pages.setMovement(QListWidget.Movement.Snap)
        self.pages.setGridSize(QSize(300, 425))
        self.loaded = set()
        self.generated_pages = tempfile.TemporaryDirectory(prefix="pdftoolkit26-pages-")
        self.zoom.valueChanged.connect(self.resize_thumbnails)
        layout.addWidget(self.pages)
        self.page_tools = QWidget()
        controls = QHBoxLayout(self.page_tools)
        controls.setContentsMargins(0, 0, 0, 0)
        add = QPushButton("+ Add page")
        add.clicked.connect(self.add_page)
        controls.addWidget(add)
        for title, checked in (("Select all", True), ("Clear selection", False)):
            action = QPushButton(title)
            action.clicked.connect(lambda unused=False, value=checked: self.select_all(value))
            controls.addWidget(action)
        move = QPushButton("Move page to…")
        move.clicked.connect(self.move_to_position)
        controls.addWidget(move)
        controls.addStretch()


    def update_sets(self):
        colors = ["#a5d6b1", "#acc8f0", "#e5c4a1", "#d0b5e8", "#a7dcd9"]
        for group, path in enumerate(self.source_paths):
            items = [self.pages.item(i) for i in range(self.pages.count()) if self.pages.item(i).data(Qt.ItemDataRole.UserRole)[0] == str(path)]
            for position, item in enumerate(items):
                item.setData(Qt.ItemDataRole.UserRole + 4, colors[group % len(colors)])
                marker = f"▶ {group + 1}" if position == 0 else f"{group + 1} ◀" if position == len(items) - 1 else ""
                item.setData(Qt.ItemDataRole.UserRole + 5, marker)
                item.setHidden(str(path) in self.collapsed and position != 0)
        self.pages.viewport().update()

    def toggle_set(self, row):
        item = self.pages.item(row)
        path = item.data(Qt.ItemDataRole.UserRole)[0]
        items = [self.pages.item(i) for i in range(self.pages.count()) if self.pages.item(i).data(Qt.ItemDataRole.UserRole)[0] == path]
        if path in self.collapsed or item is items[0]:
            self.collapsed.discard(path)
        else:
            self.collapsed.add(path)
        self.update_sets()

    def delete_page(self, row):
        self.pages.takeItem(row)
        self.update_sets()

    def focus_page(self, row):
        from deskpdf.focus_page import PageFocus
        dialog = PageFocus(self, row, self)
        dialog.showMaximized()
        dialog.exec()

    def crop_page(self, row):
        item = self.pages.item(row)
        key = item.data(Qt.ItemDataRole.UserRole)
        with open_document(Path(key[0]), self.password) as document:
            page = document[key[1]]
            if key in self.crops:
                page.set_cropbox(pdf.Rect(self.crops[key]))
            dialog = CropPageDialog(page, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            old_crop, old_derotation = page.cropbox, page.derotation_matrix
            box = pdf.Rect(dialog.cropbox())
            page.set_cropbox(box)
            rebase_objects_for_crop(self.edits.get(key, []), old_crop, old_derotation, page)
            self.crops[key] = tuple(box)
        self.edits_dirty = True
        self.render_thumbnails()

    def move_to_position(self):
        row = self.pages.currentRow()
        if row < 0:
            return
        position, accepted = QInputDialog.getInt(self, "Move page", "New document position", row + 1, 1, self.pages.count())
        if accepted:
            self.pages.move_page(row, position - 1)
            self.update_sets()

    def add_page(self):
        dialog = AddPageDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        path = Path(self.generated_pages.name) / f"Title page-{uuid.uuid4().hex[:6]}.pdf"
        with dialog.document() as document:
            document.save(path)
        self.page_created.emit(str(path))
        for index in range(self.pages.count()):
            item = self.pages.item(index)
            if item.data(Qt.ItemDataRole.UserRole)[0] == str(path):
                item.setCheckState(Qt.CheckState.Checked)
                self.pages.scrollToItem(item)

    def resize_thumbnails(self, width):
        self.pages.setIconSize(QSize(width, int(width * 1.4)))
        self.pages.setGridSize(QSize(width + 40, int(width * 1.4) + 65))
        self.zoom_label.setText(f"{round(width / 260 * 100)}%")
        self.pages.doItemsLayout()
        self.render_timer.start(180)

    def page_icon(self, page):
        width = self.zoom.value()
        scale = min(width / page.rect.width, width * 1.4 / page.rect.height)
        pix = page.get_pixmap(matrix=pdf.Matrix(scale, scale), alpha=False)
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
        painter = QPainter(image)
        painter.setPen(QColor("#b9c3b6"))
        painter.drawRect(0, 0, image.width() - 1, image.height() - 1)
        painter.end()
        return QIcon(QPixmap.fromImage(image))

    def render_thumbnails(self):
        for path in self.source_paths:
            items = [self.pages.item(i) for i in range(self.pages.count()) if self.pages.item(i).data(Qt.ItemDataRole.UserRole)[0] == str(path)]
            if not items:
                continue
            try:
                with open_document(path, self.password) as document:
                    from deskpdf.objects import apply_objects, apply_related_forms
                    related = [(page, obj) for (source, page), entries in self.edits.items() if source == str(path)
                               for obj in entries if obj.kind == "Form"]
                    apply_related_forms(document, related)
                    for item in items:
                        key = item.data(Qt.ItemDataRole.UserRole)
                        page = document[key[1]]
                        if key in self.crops:
                            page.set_cropbox(pdf.Rect(self.crops[key]))
                        apply_objects(document, {key[1]: [obj for obj in self.edits.get(key, []) if obj.kind != "Form"]})
                        item.setIcon(self.page_icon(document[key[1]]))
            except Exception as error:
                for item in items:
                    item.setToolTip(str(error))

    def select_all(self, checked):
        for index in range(self.pages.count()):
            self.pages.item(index).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def selection(self):
        return [self.pages.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.pages.count()) if self.pages.item(i).checkState() == Qt.CheckState.Checked]

    def refresh(self, paths, password):
        self.source_paths = list(paths)
        self.password = password
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
                        item = QListWidgetItem(self.page_icon(page), f"Page {index + 1}\n{path.stem[:18]}")
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
        self.update_sets()
        if errors:
            raise ValueError("\n".join(errors))

    def toggle(self, item):
        item.setCheckState(Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked)

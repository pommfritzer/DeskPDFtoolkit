import copy
from pathlib import Path

import pymupdf as pdf
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QCheckBox, QPushButton

from deskpdf.editor import VisualEditor
from deskpdf.engine import open_document
from deskpdf.objects import apply_related_forms


class PageFocus(VisualEditor):
    def __init__(self, workspace, row, parent=None):
        self.workspace = workspace
        self.row = row
        path, number = workspace.pages.item(row).data(Qt.ItemDataRole.UserRole)
        super().__init__(Path(path), workspace.password, parent)
        self.setWindowTitle("PDFtoolkit26 · Focus editor")
        self.previous = QPushButton("❮")
        self.next = QPushButton("❯")
        self.previous.setFixedWidth(48)
        self.next.setFixedWidth(48)
        self.previous.clicked.connect(lambda: self.navigate(-1))
        self.next.clicked.connect(lambda: self.navigate(1))
        body = self.layout().itemAt(2).layout()
        body.insertWidget(0, self.previous)
        body.addWidget(self.next)
        self.included = QCheckBox("Include page")
        self.included.toggled.connect(self.set_included)
        self.layout().itemAt(0).layout().addWidget(self.included)
        back = QPushButton("Back · Esc")
        back.clicked.connect(self.reject)
        self.layout().itemAt(0).layout().addWidget(back)
        toolbar = self.layout().itemAt(0).layout()
        for unused in range(2):
            toolbar.takeAt(0).widget().deleteLater()
        for key, offset in (("Left", -1), ("Right", 1)):
            shortcut = QShortcut(QKeySequence(key), self.view)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(lambda delta=offset: self.navigate(delta))
        self.load_page()

    def set_included(self, checked):
        self.workspace.pages.item(self.row).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def store(self):
        if self.document.is_closed:
            return
        self.capture()
        key = self.workspace.pages.item(self.row).data(Qt.ItemDataRole.UserRole)
        self.workspace.edits[key] = copy.deepcopy(self.objects.get(self.page, []))
        current_forms = [obj for obj in self.workspace.edits[key] if obj.kind == "Form"]
        for other_key, entries in self.workspace.edits.items():
            if other_key == key or other_key[0] != key[0]:
                continue
            self.workspace.edits[other_key] = [obj for obj in entries if obj.kind != "Form" or not any(
                latest.form_group == obj.form_group and latest.form_seq > obj.form_seq for latest in current_forms)]
        self.workspace.crops[key] = tuple(self.document[self.page].cropbox)
        if self.dirty:
            self.workspace.edits_dirty = True
            self.set_included(True)
        self.dirty = False

    def load_page(self):
        path, number = self.workspace.pages.item(self.row).data(Qt.ItemDataRole.UserRole)
        if not self.document.is_closed:
            self.document.close()
        self.document = open_document(Path(path), self.workspace.password)
        related = [(page, obj) for (source, page), entries in self.workspace.edits.items() if source == path
                   for obj in entries if obj.kind == "Form"]
        apply_related_forms(self.document, related)
        self.path = Path(path)
        self.page = number
        key = (path, number)
        if key in self.workspace.crops:
            self.document[number].set_cropbox(pdf.Rect(self.workspace.crops[key]))
        self.objects = {number: copy.deepcopy(self.workspace.edits.get(key, []))}
        self.history.clear()
        self.future.clear()
        self.dirty = False
        self.render()
        self.previous.setEnabled(self.row > 0)
        self.next.setEnabled(self.row + 1 < self.workspace.pages.count())
        self.included.blockSignals(True)
        self.included.setChecked(self.workspace.pages.item(self.row).checkState() == Qt.CheckState.Checked)
        self.included.blockSignals(False)

    def navigate(self, offset):
        self.store()
        self.row = max(0, min(self.workspace.pages.count() - 1, self.row + offset))
        self.load_page()

    def save(self):
        self.store()
        self.workspace.save_requested.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "view"):
            QTimer.singleShot(0, self.fit)

    def fit(self):
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def finish(self):
        self.store()
        self.workspace.render_thumbnails()
        if not self.document.is_closed:
            self.document.close()

    def reject(self):
        self.finish()
        super().reject()

    def closeEvent(self, event):
        self.finish()
        event.accept()

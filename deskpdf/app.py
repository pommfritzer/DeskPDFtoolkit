import argparse
import sys
from pathlib import Path

import pymupdf as pdf

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QSize
from PySide6.QtGui import QDesktopServices, QIcon, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QComboBox, QMenu, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QStackedWidget, QVBoxLayout, QWidget,
)

from deskpdf.catalog import TOOLS, TOOL_BY_ID
from deskpdf.engine import open_document, run_tool
from deskpdf.theme import STYLE
from deskpdf.design import AmbientBackground, tool_icon
from deskpdf.merge_view import MergeView

ASSETS = Path(__file__).parent / "assets"
MERGE_PAGES_ROLE = Qt.ItemDataRole.UserRole + 1
FIELDS = {
    "pages": ("Pages", "all", "Examples: 1, 3-5 or 5-1. Page order is preserved."),
    "rotation": ("Turn clockwise", "90", "Degrees"),
    "dpi": ("Resolution", "144", "72–300 DPI. Higher values use more memory."),
    "text": ("Text", "", "Standard PDF fonts support Latin text. Use a signature image for other scripts."),
    "size": ("Text size", "18", "PDF points"),
    "x": ("Left position", "48", "PDF points from the visible page’s left edge."),
    "y": ("Top position", "72", "PDF points from the visible page’s top edge; text uses its baseline."),
    "width": ("Signature width", "140", "PDF points"),
    "margin": ("Trim each edge", "18", "PDF points. 72 points = 1 inch."),
    "language": ("OCR language", "eng", "Installed Tesseract language code, such as eng or deu."),
    "new_password": ("New opening password", "", "Keep this password somewhere safe."),
    "form_values": ("Field values", "", "One per line: field name=value. Checkboxes use their export value (often Yes)."),
    "signature": ("Signature image", "", "Choose a PNG with a transparent background."),
}


def label(text, name=None):
    widget = QLabel(text)
    widget.setWordWrap(True)
    if name:
        widget.setObjectName(name)
    return widget


def button(text, callback, name=None):
    widget = QPushButton(text)
    if name:
        widget.setObjectName(name)
    widget.clicked.connect(callback)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


class Worker(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, tool, paths, output, options):
        super().__init__()
        self.arguments = tool, paths, output, options

    def run(self):
        try:
            result = run_tool(*self.arguments)
            self.completed.emit(str(result))
        except Exception as error:
            self.failed.emit(str(error) or type(error).__name__)


class Preview(QLabel):
    positioned = Signal(float, float)

    def __init__(self):
        super().__init__("Your document preview\nwill appear here")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(250, 200)
        self.setWordWrap(True)
        self.page_size = None
        self.source_pixmap = None

    def set_image(self, pixmap):
        self.source_pixmap = pixmap
        self.fit_image()

    def fit_image(self):
        if self.source_pixmap:
            self.setPixmap(self.source_pixmap.scaled(min(360, self.width()), min(420, self.height()), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_image()

    def clear(self):
        self.source_pixmap = None
        super().clear()

    def mousePressEvent(self, event):
        pixmap = self.pixmap()
        if pixmap and self.page_size:
            left = (self.width() - pixmap.width()) / 2
            top = (self.height() - pixmap.height()) / 2
            x, y = event.position().x() - left, event.position().y() - top
            if 0 <= x <= pixmap.width() and 0 <= y <= pixmap.height():
                self.positioned.emit(x / pixmap.width() * self.page_size[0], y / pixmap.height() * self.page_size[1])


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDFtoolkit26 — Your PDFs, at hand")
        self.setWindowIcon(QIcon(str(ASSETS / "icon.ico")))
        self.resize(1210, 830)
        self.setMinimumSize(960, 680)
        self.paths = []
        self.current_tool = None
        self.page_index = 0
        self.fields = {}
        self.worker = None
        self.last_output = None
        self.setAcceptDrops(True)
        root = AmbientBackground()
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        self.topbar = QFrame(objectName="topbar")
        navigation = QVBoxLayout(self.topbar)
        navigation.setContentsMargins(30, 10, 30, 10)
        top = QHBoxLayout()
        top.addWidget(button("PDFtoolkit26", lambda: self.show_catalog(), "brand"))
        top.addWidget(label("LOCAL PDF STUDIO", "eyebrow"))
        self.active_title = label("Choose a tool", "muted")
        top.addWidget(self.active_title)
        top.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find a tool…  Ctrl+K")
        self.search.setFixedWidth(260)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.search_tools)
        top.addWidget(self.search)
        settings = button("Settings", self.show_settings)
        self.add_page_action = button("+ Add page", self.add_editor_page)
        self.add_page_action.hide()
        top.addWidget(self.add_page_action)
        top.addWidget(settings)
        navigation.addLayout(top)
        shell.addWidget(self.topbar)
        self.stack = QStackedWidget()
        self.stack.setContentsMargins(24, 0, 24, 12)
        shell.addWidget(self.stack, 1)
        self.build_catalog()
        self.build_workbench()
        self.show_catalog()
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.choose_files)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.focus_search)

    def add_editor_page(self):
        if self.worker and self.worker.isRunning():
            return
        if not self.current_tool or self.current_tool.id != "merge":
            self.select_tool(TOOL_BY_ID["merge"])
            self.visual_merge.select_all(True)
        self.visual_merge.add_page()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "topbar"):
            self.topbar.setFixedHeight(round(self.height() * (.40 if hasattr(self, "stack") and self.stack.currentIndex() == 1 else .22)))

    def search_tools(self):
        if hasattr(self, "cards"):
            if self.stack.currentIndex() != 0:
                self.show_catalog()
            self.filter_catalog()

    def show_settings(self):
        menu = QMenu(self)
        motion = menu.addAction("Animated background")
        motion.setCheckable(True)
        motion.setChecked(self.centralWidget().timer.isActive())
        motion.triggered.connect(lambda checked: self.centralWidget().timer.start() if checked else self.centralWidget().timer.stop())
        menu.addAction("About PDFtoolkit26", self.about)
        menu.exec(self.cursor().pos())

    def build_catalog(self):
        page = QWidget(objectName="catalog")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 24, 14, 8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.catalog = QWidget(objectName="catalog")
        self.cards = QGridLayout(self.catalog)
        self.cards.setContentsMargins(0, 0, 10, 0)
        self.cards.setSpacing(12)
        scroll.setWidget(self.catalog)
        layout.addWidget(scroll, 1)
        layout.addWidget(label("Drop files anywhere to start  ·  Originals stay untouched  ·  Ctrl+O to open", "muted"))
        self.stack.addWidget(page)

    def show_catalog(self, group="All tools"):
        if self.worker and self.worker.isRunning():
            return
        self.add_page_action.hide()
        self.editor_controls.hide()
        self.description.hide()
        self.topbar.setFixedHeight(round(self.height() * .22))
        self.group = group
        self.active_title.setText("Choose a tool")
        self.stack.setCurrentIndex(0)
        self.filter_catalog()

    def filter_catalog(self):
        for row in range(self.cards.rowCount()):
            self.cards.setRowStretch(row, 0)
        while self.cards.count():
            item = self.cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        query = self.search.text().casefold()
        tools = [tool for tool in TOOLS if (self.group == "All tools" or tool.group == self.group) and query in f"{tool.title} {tool.description} {tool.group}".casefold()]
        for index, tool in enumerate(tools):
            card = button(f"{tool.title}", lambda checked=False, value=tool: self.select_tool(value), "card")
            card.setIcon(tool_icon(tool))
            card.setIconSize(QSize(72, 72))
            card.setMinimumHeight(138)
            card.setAccessibleName(tool.title + ": " + tool.description)
            card.setToolTip(tool.description)
            self.cards.addWidget(card, index // 3, index % 3)
        if not tools:
            self.cards.addWidget(label("No tools found. Try pages, text or convert.", "muted"), 0, 0, 1, 3)
        self.cards.setRowStretch((len(tools) + 2) // 3, 1)
        for column in range(3):
            self.cards.setColumnStretch(column, 1)

    def focus_search(self):
        self.show_catalog()
        self.search.setFocus()
        self.search.selectAll()

    def build_workbench(self):
        self.workbench = QWidget()
        layout = QVBoxLayout(self.workbench)
        layout.setContentsMargins(20, 18, 20, 16)
        # The top navigation provides the return path for every workbench.
        self.title = label("", "section")
        self.description = label("", "muted")
        self.title.hide()
        self.topbar.layout().addWidget(self.description)
        self.description.hide()
        layout.addSpacing(16)
        columns = QHBoxLayout()
        layout.addLayout(columns, 1)
        settings_scroll = QScrollArea()
        self.settings_scroll = settings_scroll
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setMinimumWidth(310)
        settings = QWidget(objectName="catalog")
        left = QVBoxLayout(settings)
        left.setContentsMargins(0, 0, 16, 0)
        left.addWidget(label("1   YOUR FILES", "eyebrow"))
        self.file_list = QListWidget()
        self.file_list.setFixedHeight(65)
        self.file_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.file_list.currentRowChanged.connect(self.file_selected)
        self.file_list.model().rowsMoved.connect(self.sync_paths)
        left.addWidget(self.file_list)
        actions = QHBoxLayout()
        actions.addWidget(button("+ Add files", self.choose_files))
        actions.addWidget(button("Remove", self.remove_file))
        left.addLayout(actions)
        self.order_hint = label("Drag files to change their order.", "muted")
        left.addWidget(self.order_hint)
        self.password = QLineEdit()
        self.password.setPlaceholderText("Opening password, if needed")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setAccessibleName("Document opening password")
        self.password.editingFinished.connect(self.refresh_preview)
        left.addWidget(self.password)
        left.addSpacing(4)
        self.settings_title = label("2   MAKE IT YOURS", "eyebrow")
        left.addWidget(self.settings_title)
        self.form_widget = QWidget()
        self.form = QFormLayout(self.form_widget)
        self.form.setContentsMargins(0, 10, 0, 0)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        left.addWidget(self.form_widget)
        self.visual_merge = MergeView()
        self.visual_merge.page_created.connect(lambda path: self.add_paths([path]))
        self.no_options = label("Ready when you are. This tool needs no extra settings.", "muted")
        left.addWidget(self.no_options)
        left.addStretch()
        settings_scroll.setWidget(settings)
        self.editor_controls = QWidget()
        editor_layout = QHBoxLayout(self.editor_controls)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.addWidget(settings_scroll, 1)
        editor_layout.addWidget(self.visual_merge.controls, 2)
        self.topbar.layout().addWidget(self.editor_controls)
        self.editor_controls.hide()
        preview_frame = QFrame(objectName="preview")
        right = QVBoxLayout(preview_frame)
        right.setContentsMargins(16, 16, 16, 16)
        preview_header = QHBoxLayout()
        preview_header.addWidget(label("DOCUMENT PREVIEW", "eyebrow"))
        preview_header.addStretch()
        preview_header.addWidget(button("↗ Open original", self.open_original))
        right.addLayout(preview_header)
        self.preview = Preview()
        self.preview.positioned.connect(self.set_position)
        right.addWidget(self.preview, 1)
        paging = QHBoxLayout()
        paging.addWidget(button("←", lambda: self.change_page(-1)))
        self.page_label = label("No document", "muted")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        paging.addWidget(self.page_label, 1)
        paging.addWidget(button("→", lambda: self.change_page(1)))
        right.addLayout(paging)
        self.preview_hint = label("Preview shows your original. Open the saved file to review changes.", "muted")
        right.addWidget(self.preview_hint)
        self.preview_frame = preview_frame
        columns.addWidget(preview_frame, 6)
        columns.addWidget(self.visual_merge, 9)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        self.topbar.layout().addWidget(self.progress)
        self.status = label("", "status")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.topbar.layout().addWidget(self.status)
        footer = QHBoxLayout()
        footer.addWidget(label("Saved as a new file. Your original stays yours.", "muted"), 1)
        self.open_result = button("Open result ↗", self.open_output)
        self.open_result.hide()
        self.topbar.layout().addWidget(self.open_result)
        self.save = button("Save a copy…", self.start_job, "primary")
        footer.addWidget(self.save)
        layout.addLayout(footer)
        self.stack.addWidget(self.workbench)

    def select_tool(self, tool):
        self.add_page_action.show()
        self.editor_controls.show()
        self.description.show()
        self.topbar.setFixedHeight(round(self.height() * .40))
        self.visual_merge.controls.setVisible(tool.id == "merge")
        self.current_tool = tool
        self.title.setText(tool.title)
        self.active_title.setText(tool.title)
        self.settings_scroll.setMaximumWidth(280 if tool.id == "merge" else 500)
        self.settings_scroll.setMinimumWidth(240)
        self.description.setText(tool.description)
        self.fields.clear()
        while self.form.rowCount():
            self.form.removeRow(0)
        for name in tool.fields:
            title, default, hint = FIELDS[name]
            if name in {"rotation", "dpi"}:
                widget = QComboBox()
                widget.addItems(["90", "180", "270"] if name == "rotation" else ["72", "144", "200", "300"])
                widget.setCurrentText(default)
            elif name == "form_values":
                widget = QPlainTextEdit()
                widget.setMaximumHeight(130)
                widget.setPlaceholderText("Full name=Alex Example\nAccepted=Yes")
            else:
                widget = QLineEdit(default)
                if name == "new_password":
                    widget.setEchoMode(QLineEdit.EchoMode.Password)
            widget.setAccessibleName(title)
            widget.setToolTip(hint)
            self.fields[name] = widget
            if name == "signature":
                row = QWidget()
                line = QHBoxLayout(row)
                line.setContentsMargins(0, 0, 0, 0)
                line.addWidget(widget)
                line.addWidget(button("Browse…", self.choose_signature))
                self.form.addRow(title, row)
            else:
                self.form.addRow(title, widget)
        self.visual_merge.setVisible(tool.id == "merge")
        self.settings_title.setVisible(tool.id != "merge")
        self.order_hint.setText("Arrange pages directly in the thumbnail grid." if tool.id == "merge" else "Drag files to change their order.")
        self.preview_frame.setVisible(tool.id != "merge")
        self.no_options.setVisible(not tool.fields and tool.id != "merge")
        self.order_hint.setVisible(tool.multiple and tool.id != "merge")
        self.file_list.setDragDropMode(QListWidget.DragDropMode.InternalMove if tool.multiple else QListWidget.DragDropMode.NoDragDrop)
        self.status.clear()
        self.open_result.hide()
        self.stack.setCurrentIndex(1)
        self.refresh_preview()

    def choose_signature(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose signature image", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.fields["signature"].setText(path)

    def choose_files(self):
        if self.worker and self.worker.isRunning():
            return
        if not self.current_tool or self.stack.currentIndex() == 0:
            self.select_tool(TOOL_BY_ID["merge"])
        tool = self.current_tool.id
        filters = "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp)" if tool == "images_to_pdf" else "Office documents (*.doc *.docx *.odt *.xls *.xlsx *.ods *.ppt *.pptx *.odp *.rtf *.txt *.html)" if tool == "office" else "PDF documents (*.pdf)"
        paths, _ = QFileDialog.getOpenFileNames(self, "Add files", "", filters)
        if paths:
            self.add_paths(paths)

    def add_paths(self, paths):
        for value in paths:
            path = Path(value)
            if path.is_file() and path not in self.paths:
                self.paths.append(path)
                item = QListWidgetItem(path.name)
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                item.setData(MERGE_PAGES_ROLE, "all")
                item.setToolTip(str(path))
                self.file_list.addItem(item)
        if self.file_list.currentRow() < 0:
            self.file_list.setCurrentRow(0)
        self.status.clear()
        self.refresh_preview()

    def sync_paths(self, *args):
        self.paths = [Path(self.file_list.item(index).data(Qt.ItemDataRole.UserRole)) for index in range(self.file_list.count())]

    def remove_file(self):
        row = self.file_list.currentRow()
        if row >= 0:
            self.file_list.takeItem(row)
            self.sync_paths()
            self.page_index = 0
            self.refresh_preview()

    def file_selected(self, row):
        self.page_index = 0
        self.refresh_preview()

    def selected_path(self):
        item = self.file_list.currentItem()
        return Path(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def change_page(self, delta):
        self.page_index = max(0, self.page_index + delta)
        self.refresh_preview()

    def refresh_preview(self):
        if self.current_tool and self.current_tool.id == "merge":
            try:
                self.visual_merge.refresh(self.paths, self.password.text())
            except Exception as error:
                self.status.setText(str(error))
        self.preview.clear()
        self.preview.page_size = None
        path = self.selected_path()
        if not path:
            self.preview.setText("Your document preview\nwill appear here")
            self.page_label.setText("No document")
            return
        try:
            if self.current_tool and self.current_tool.id in {"office", "images_to_pdf"}:
                if self.current_tool.id == "images_to_pdf":
                    image = QPixmap(str(path))
                    self.preview.set_image(image)
                else:
                    self.preview.setText("Office document ready\n\nLibreOffice will convert this file locally.")
                self.page_label.setText(path.suffix.upper().lstrip("."))
                return
            with open_document(path, self.password.text()) as document:
                self.page_index = min(self.page_index, len(document) - 1)
                page = document[self.page_index]
                scale = min(360 / page.rect.width, 420 / page.rect.height) * 1.6
                pix = page.get_pixmap(matrix=pdf.Matrix(scale, scale), alpha=False)
                image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
                self.preview.set_image(QPixmap.fromImage(image))
                self.preview.page_size = page.rect.width, page.rect.height
                self.page_label.setText(f"Page {self.page_index + 1} of {len(document)}")
                if self.current_tool and self.current_tool.id == "forms":
                    names = [widget.field_name for widget in page.widgets()]
                    self.status.setText("Fields on this page: " + (", ".join(names) or "none"))
        except Exception as error:
            self.preview.setText(str(error))
            self.page_label.setText("Preview unavailable")

    def set_position(self, x, y):
        for name, value in (("x", x), ("y", y)):
            if name in self.fields:
                self.fields[name].setText(str(round(value, 1)))

    def start_job(self):
        if not self.paths:
            self.choose_files()
            return
        if not self.current_tool.multiple and len(self.paths) != 1:
            self.status.setText("This tool works on one file at a time. Remove the other files first.")
            return
        extension = self.current_tool.extension
        default = self.paths[0].with_name(f"{self.paths[0].stem}-{self.current_tool.id}.{extension}")
        temporary_pages = Path(self.visual_merge.generated_pages.name).resolve()
        if default.resolve().is_relative_to(temporary_pages):
            default = Path.home() / "Documents" / f"New document.{extension}"
        output, _ = QFileDialog.getSaveFileName(self, "Save a new file", str(default), f"{extension.upper()} file (*.{extension})")
        if not output:
            return
        if Path(output).resolve().is_relative_to(temporary_pages):
            self.status.setText("Choose a permanent folder, such as Documents, for your saved file.")
            return
        if Path(output).resolve() in [path.resolve() for path in self.paths]:
            self.status.setText("Save to a new file to keep every original safe.")
            return
        options = {"password": self.password.text()}
        for name, widget in self.fields.items():
            options[name] = widget.toPlainText() if isinstance(widget, QPlainTextEdit) else widget.currentText() if isinstance(widget, QComboBox) else widget.text()
        job_paths = list(self.paths)
        if self.current_tool.id == "merge":
            selected = self.visual_merge.selection()
            if not selected:
                self.status.setText("Click page thumbnails to include them first.")
                return
            job_paths = [Path(path) for path, page in selected]
            options["merge_pages"] = [str(page + 1) for path, page in selected]
            options["merge_crops"] = [self.visual_merge.crops.get((path, page)) for path, page in selected]
        self.worker = Worker(self.current_tool.id, job_paths, Path(output), options)
        self.worker.completed.connect(self.job_done)
        self.worker.failed.connect(self.job_failed)
        self.worker.finished.connect(self.job_finished)
        self.workbench.setEnabled(False)
        self.progress.show()
        self.status.setText("Working on your document…")
        self.worker.start()

    def job_done(self, output):
        self.last_output = Path(output)
        self.status.setText(f"Saved {self.last_output.name}  ·  {self.last_output.stat().st_size / 1024:,.0f} KB")
        self.open_result.show()

    def job_failed(self, message):
        self.status.setText(message)

    def job_finished(self):
        self.workbench.setEnabled(True)
        self.progress.hide()

    def open_original(self):
        if self.selected_path():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.selected_path())))

    def open_output(self):
        if self.last_output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output)))

    def about(self):
        QMessageBox.about(self, "About PDFtoolkit26", "PDFtoolkit26 0.4.0\n\nA local-first, open-source PDF workbench.\nAGPL-3.0-or-later · Built with Qt and MuPDF.\n\nNo telemetry, accounts or document uploads.\nOCR needs Tesseract; Office input needs LibreOffice.\nVisual signatures are not certificate signatures.\n\nWindows 11: Explorer commands appear under Show more options.")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and not (self.worker and self.worker.isRunning()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if self.stack.currentIndex() == 0:
            self.select_tool(TOOL_BY_ID["merge"])
        self.add_paths([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.status.setText("Please wait for the current operation to finish before closing.")
            event.ignore()
        else:
            event.accept()


def main():
    parser = argparse.ArgumentParser(description="PDFtoolkit26 local PDF workbench")
    parser.add_argument("--tool", choices=list(TOOL_BY_ID), default=None)
    parser.add_argument("files", nargs="*")
    arguments = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("PDFtoolkit26")
    app.setOrganizationName("PDFtoolkit26")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = Window()
    if arguments.tool or arguments.files:
        window.select_tool(TOOL_BY_ID[arguments.tool or "merge"])
        window.add_paths(arguments.files)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

import pymupdf as pdf
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from deskpdf.objects import validate_text_characters
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPlainTextEdit, QSpinBox, QToolButton, QVBoxLayout


def create_title_page(text, family="Sans", size=32, bold=False, italic=False):
    if len(text) > 1000 or len(text.splitlines()) > 20:
        raise ValueError("Keep your page title within 1,000 characters and 20 lines.")
    validate_text_characters(text)
    document = pdf.open()
    page = document.new_page(width=595, height=842)
    if text.strip():
        names = {"Sans": ("helv", "hebo", "heit", "hebi"), "Serif": ("tiro", "tibo", "tiit", "tibi"), "Mono": ("cour", "cobo", "coit", "cobi")}
        font = pdf.Font(names[family][int(bold) + 2 * int(italic)])
        lines = []
        for paragraph in text.split("\n"):
            line = ""
            for character in paragraph:
                if font.text_length(line + character, fontsize=size) > 499 and line:
                    lines.append(line)
                    line = ""
                line += character
            lines.append(line)
        line_height = size * 1.35
        block_height = (len(lines) - 1) * line_height + (font.ascender - font.descender) * size
        if block_height > 746:
            document.close()
            return create_title_page(text, family, max(1, size * .8), bold, italic)
        baseline = (842 - block_height) / 2 + font.ascender * size
        writer = pdf.TextWriter(page.rect)
        for index, line in enumerate(lines):
            x = (595 - font.text_length(line, fontsize=size)) / 2
            writer.append((x, baseline + index * line_height), line, font=font, fontsize=size)
        writer.write_text(page, color=(.125, .235, .188))
    return document


class AddPageDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add page · PDFtoolkit26")
        self.resize(620, 760)
        layout = QVBoxLayout(self)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.preview, 1)
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("Type the words for the middle of your page…")
        self.text.setMaximumHeight(100)
        self.text.setAccessibleName("Centered page text")
        layout.addWidget(self.text)
        controls = QHBoxLayout()
        self.family = QComboBox()
        self.family.addItems(["Sans", "Serif", "Mono"])
        self.family.setAccessibleName("Font family")
        self.size = QSpinBox()
        self.size.setRange(8, 96)
        self.size.setValue(32)
        self.size.setSuffix(" pt")
        self.size.setAccessibleName("Font size")
        controls.addWidget(self.family)
        controls.addWidget(self.size)
        self.bold = QToolButton()
        self.italic = QToolButton()
        for widget, title in ((self.bold, "Bold"), (self.italic, "Italic")):
            widget.setText(title)
            widget.setCheckable(True)
            controls.addWidget(widget)
            widget.toggled.connect(self.update_preview)
        layout.addLayout(controls)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        self.confirm = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.confirm.setText("Add page")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.text.textChanged.connect(self.update_preview)
        self.family.currentTextChanged.connect(self.update_preview)
        self.size.valueChanged.connect(self.update_preview)
        self.update_preview()

    def document(self):
        return create_title_page(self.text.toPlainText(), self.family.currentText(), self.size.value(), self.bold.isChecked(), self.italic.isChecked())

    def update_preview(self):
        try:
            with self.document() as document:
                pix = document[0].get_pixmap(matrix=pdf.Matrix(.55, .55), alpha=False)
                image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
                self.preview.setPixmap(QPixmap.fromImage(image))
            self.confirm.setEnabled(True)
        except ValueError as error:
            self.preview.setText(str(error))
            self.confirm.setEnabled(False)

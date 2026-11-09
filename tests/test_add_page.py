import pytest
from deskpdf.add_page import create_title_page


@pytest.mark.parametrize("family", ["Sans", "Serif", "Mono"])
@pytest.mark.parametrize("bold,italic", [(False, False), (True, False), (False, True), (True, True)])
def test_centered_title_page(family, bold, italic):
    with create_title_page("Chapter One", family, 32, bold, italic) as document:
        page = document[0]
        block = page.get_text("blocks")[0]
        assert abs((block[0] + block[2]) / 2 - page.rect.width / 2) < 1
        assert abs((block[1] + block[3]) / 2 - page.rect.height / 2) < 1
        assert "Chapter One" in page.get_text()


def test_blank_page():
    with create_title_page("") as document:
        assert len(document) == 1
        assert not document[0].get_text().strip()


def test_add_page_dialog_exports_to_merge(tmp_path):
    from unittest.mock import patch
    from PySide6.QtWidgets import QApplication, QDialog
    from deskpdf.app import Window
    from deskpdf.catalog import TOOL_BY_ID
    from deskpdf.add_page import AddPageDialog
    from pathlib import Path
    import pymupdf as pdf
    app = QApplication.instance() or QApplication([])
    window = Window()
    window.select_tool(TOOL_BY_ID["merge"])
    def accept(dialog):
        dialog.text.setPlainText("A new chapter")
        dialog.family.setCurrentText("Serif")
        dialog.bold.setChecked(True)
        return QDialog.DialogCode.Accepted
    with patch.object(AddPageDialog, "exec", accept):
        window.visual_merge.add_page()
    selected = window.visual_merge.selection()
    assert len(selected) == 1
    with pdf.open(Path(selected[0][0])) as document:
        assert "A new chapter" in document[0].get_text()
    from PySide6.QtWidgets import QFileDialog
    with patch.object(QFileDialog, "getSaveFileName", return_value=("", "")) as save_dialog:
        window.start_job()
    assert Path(save_dialog.call_args.args[2]).parent == Path.home() / "Documents"
    output = tmp_path / "title.pdf"
    with patch.object(QFileDialog, "getSaveFileName", return_value=(str(output), "")):
        window.start_job()
    assert window.worker.wait(10000)
    app.processEvents()
    with pdf.open(output) as saved:
        assert "A new chapter" in saved[0].get_text()
    window.close()
    app.processEvents()


def test_title_page_rejects_unsupported_characters():
    with pytest.raises(ValueError, match="cannot be saved reliably"):
        create_title_page("Hello \U0001f600")

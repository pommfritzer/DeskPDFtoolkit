import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from deskpdf.app import Window
from deskpdf.catalog import TOOLS


def test_all_tool_forms_and_search():
    app = QApplication.instance() or QApplication([])
    window = Window()
    for tool in TOOLS:
        window.select_tool(tool)
        assert window.title.text() == tool.title
        assert set(window.fields) == set(tool.fields)
    window.show_catalog("Security")
    window.search.setText("protect")
    assert window.cards.itemAtPosition(0, 0).widget().text().find("Protect PDF") >= 0
    window.search.setText("no such tool")
    assert "No tools" in window.cards.itemAtPosition(0, 0).widget().text()
    window.close()
    app.processEvents()


def test_merge_page_choices_follow_files(tmp_path):
    import pymupdf as pdf
    from PySide6.QtWidgets import QFileDialog
    from unittest.mock import patch
    from deskpdf.app import MERGE_PAGES_ROLE
    from deskpdf.catalog import TOOL_BY_ID

    app = QApplication.instance() or QApplication([])
    paths = [tmp_path / "first.pdf", tmp_path / "second.pdf"]
    for path in paths:
        with pdf.open() as document:
            for index in range(3):
                document.new_page()
            document.save(path)
    window = Window()
    window.select_tool(TOOL_BY_ID["merge"])
    window.add_paths(paths)
    window.merge_pages.setText("3,1")
    window.file_list.setCurrentRow(1)
    assert window.merge_pages.text() == "all"
    window.change_page(1)
    window.merge_current_page()
    assert window.merge_pages.text() == "2"
    window.file_list.setCurrentRow(0)
    assert window.merge_pages.text() == "3,1"
    window.select_tool(TOOL_BY_ID["extract"])
    window.select_tool(TOOL_BY_ID["merge"])
    assert window.merge_pages.text() == "3,1"
    item = window.file_list.takeItem(1)
    window.file_list.insertItem(0, item)
    window.sync_paths()
    assert window.file_list.item(0).data(MERGE_PAGES_ROLE) == "2"
    assert window.paths == paths[::-1]
    output = tmp_path / "merged.pdf"
    with patch.object(QFileDialog, "getSaveFileName", return_value=(str(output), "")):
        window.start_job()
    assert window.worker.arguments[3]["merge_pages"] == ["2", "3,1"]
    assert window.worker.wait(10000)
    app.processEvents()
    with pdf.open(output) as document:
        assert len(document) == 3
    window.file_list.setCurrentRow(0)
    window.remove_file()
    assert window.paths == [paths[0]]
    assert window.merge_pages.text() == "3,1"
    window.close()

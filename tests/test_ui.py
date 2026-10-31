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

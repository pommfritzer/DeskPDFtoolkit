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


def test_combined_merge_grid(tmp_path):
    import pymupdf as pdf
    from unittest.mock import patch
    from PySide6.QtWidgets import QFileDialog
    from deskpdf.catalog import TOOL_BY_ID
    app = QApplication.instance() or QApplication([])
    paths = [tmp_path / "first.pdf", tmp_path / "second.pdf"]
    for path in paths:
        with pdf.open() as document:
            for number in range(3):
                document.new_page().insert_text((40, 60), f"{path.stem} {number + 1}")
            document.save(path)
    window = Window()
    window.select_tool(TOOL_BY_ID["merge"])
    window.add_paths(paths)
    grid = window.visual_merge.pages
    assert grid.count() == 6
    for index in (0, 2, 4):
        window.visual_merge.toggle(grid.item(index))
    grid.move_page(4, 0)
    window.file_list.setCurrentRow(1)
    assert grid.count() == 6
    assert window.visual_merge.selection() == [(str(paths[1]), 1), (str(paths[0]), 0), (str(paths[0]), 2)]
    before_zoom = window.visual_merge.selection()
    window.visual_merge.zoom.setValue(500)
    window.visual_merge.render_thumbnails()
    assert grid.iconSize().width() == 500
    assert grid.item(0).icon().availableSizes()[0].width() > 300
    assert window.visual_merge.selection() == before_zoom
    output = tmp_path / "merged.pdf"
    with patch.object(QFileDialog, "getSaveFileName", return_value=(str(output), "")):
        window.start_job()
    assert window.worker.wait(10000)
    app.processEvents()
    with pdf.open(output) as document:
        assert [page.get_text().strip() for page in document] == ["second 2", "first 1", "first 3"]
    window.file_list.setCurrentRow(0)
    window.remove_file()
    assert grid.count() == 3
    window.visual_merge.select_all(True)
    assert len(window.visual_merge.selection()) == 3
    window.visual_merge.select_all(False)
    assert not window.visual_merge.selection()
    window.close()


def test_top_navigation_and_motion_control():
    app = QApplication.instance() or QApplication([])
    window = Window()
    window.show()
    app.processEvents()
    assert abs(window.topbar.height() - window.height() / 6) < 2
    background = window.centralWidget()
    phase = background.phase
    background.advance()
    assert background.phase > phase
    background.timer.stop()
    assert not background.timer.isActive()
    window.close()

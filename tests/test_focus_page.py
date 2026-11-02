from pathlib import Path
import pymupdf as pdf
from PySide6.QtCore import Qt
from deskpdf.focus_page import PageFocus
from deskpdf.merge_view import MergeView
from deskpdf.app import Window


def test_focus_navigation_crop_and_selection(tmp_path, application_session):
    source = tmp_path / "pages.pdf"
    with pdf.open() as document:
        document.new_page(width=400, height=600)
        document.new_page(width=400, height=600)
        document.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    workspace.crops[(str(source), 1)] = (20, 20, 380, 580)
    focus = PageFocus(workspace, 0)
    assert not focus.previous.isEnabled()
    assert focus.next.isEnabled()
    focus.included.setChecked(True)
    assert workspace.selection() == [(str(source), 0)]
    focus.navigate(1)
    assert focus.row == 1
    assert not focus.next.isEnabled()
    assert focus.scene.sceneRect().width() == 720
    focus.navigate(1)
    assert focus.row == 1
    focus.navigate(-1)
    assert focus.included.isChecked()
    focus.close()
    workspace.close()


def test_toolbar_height_survives_window_resize(application_session):
    window = Window()
    window.show()
    application_session.processEvents()
    window.partition.setSizes([130, 650])
    window.partition.splitterMoved.emit(130, 1)
    before = window.partition.sizes()[0]
    window.resize(1300, 950)
    application_session.processEvents()
    assert window.toolbar_manual
    window.set_partition_default(.4)
    assert window.partition.sizes()[0] < window.height() * .25
    window.close()

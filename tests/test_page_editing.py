import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pymupdf as pdf
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF
from deskpdf.crop_page import CropPageDialog
from deskpdf.engine import run_tool
from deskpdf.merge_view import MergeView


def test_per_page_crop_survives_export(tmp_path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "source.pdf"
    with pdf.open() as doc:
        doc.new_page(width=400, height=600)
        doc.new_page(width=400, height=600)
        doc.save(source)
    with pdf.open(source) as doc:
        dialog = CropPageDialog(doc[1])
        canvas = dialog.canvas
        canvas.selection = QRectF(canvas.width() * .1, canvas.height() * .1, canvas.width() * .8, canvas.height() * .8)
        crop = dialog.cropbox()
        dialog.close()
    output = tmp_path / "cropped.pdf"
    run_tool("merge", [source, source], output, {"merge_pages": ["1", "2"], "merge_crops": [None, crop]})
    with pdf.open(output) as doc:
        assert doc[0].rect.width == 400
        assert abs(doc[1].rect.width - 320) < 1
        assert abs(doc[1].rect.height - 480) < 1
    with pdf.open(source) as doc:
        assert doc[1].rect.width == 400


def test_sets_collapse_without_losing_selection_and_delete(tmp_path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "set.pdf"
    with pdf.open() as doc:
        for i in range(3): doc.new_page()
        doc.save(source)
    view = MergeView()
    view.refresh([source], "")
    view.select_all(True)
    chosen = view.selection()
    view.toggle_set(2)
    assert view.pages.item(1).isHidden()
    assert view.selection() == chosen
    view.toggle_set(0)
    assert not view.pages.item(1).isHidden()
    view.delete_page(1)
    assert len(view.selection()) == 2
    view.refresh([source], "")
    assert view.pages.count() == 2
    view.close()

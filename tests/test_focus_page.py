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
    assert focus.scene.sceneRect().width() == 360
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


def test_focus_edits_survive_navigation_and_merge_export(tmp_path, application_session):
    from deskpdf.engine import run_tool
    from PIL import Image
    source = tmp_path / "source.pdf"
    with pdf.open() as doc:
        doc.new_page(width=400, height=600).insert_text((30, 40), "Original")
        doc.new_page(width=400, height=600)
        doc.save(source)
    picture = tmp_path / "picture.png"
    Image.new("RGB", (80, 40), "green").save(picture)
    workspace = MergeView()
    workspace.refresh([source], "")
    workspace.select_all(True)
    focus = PageFocus(workspace, 0)
    focus.add("Text")
    focus.text.setPlainText("Edited in focus")
    focus.selected().setPos(40, 120)
    focus.capture()
    focus.add("Image", str(picture))
    focus.selected().setPos(40, 240)
    from unittest.mock import patch
    from PySide6.QtWidgets import QDialog
    from PySide6.QtCore import QRectF
    from deskpdf.crop_page import CropPageDialog
    def crop_edges(dialog):
        canvas = dialog.canvas
        canvas.selection = QRectF(canvas.width() / 40, canvas.height() / 60, canvas.width() * .95, canvas.height() * (58 / 60))
        return QDialog.DialogCode.Accepted
    with patch.object(CropPageDialog, "exec", crop_edges):
        focus.crop()
    focus.navigate(1)
    focus.add("Rectangle")
    focus.navigate(-1)
    assert focus.objects[0][0].text == "Edited in focus"
    focus.close()
    selected = workspace.selection()
    output = tmp_path / "result.pdf"
    run_tool("merge", [Path(path) for path, number in selected], output, {
        "merge_pages": [str(number + 1) for path, number in selected],
        "merge_crops": [workspace.crops.get(key) for key in selected],
        "merge_edits": [workspace.edits.get(key, []) for key in selected],
    })
    with pdf.open(output) as doc:
        assert "Original" in doc[0].get_text()
        assert "Edited in focus" in doc[0].get_text()
        assert doc[0].get_images()
        assert abs(doc[0].rect.width - 380) < 1
        assert abs(doc[0].rect.height - 580) < 1
        assert doc[1].get_drawings()
    with pdf.open(source) as doc:
        assert "Edited in focus" not in doc[0].get_text()
    workspace.close()

def test_focus_edits_existing_text_and_image(tmp_path, application_session):
    from deskpdf.editor import ObjectItem
    from deskpdf.engine import run_tool
    from PIL import Image
    source = tmp_path / "existing.pdf"
    picture = tmp_path / "original.png"
    replacement = tmp_path / "replacement.png"
    Image.new("RGB", (60, 40), "red").save(picture)
    Image.new("RGB", (60, 40), "blue").save(replacement)
    with pdf.open() as doc:
        page = doc.new_page(width=400, height=500)
        page.insert_text((40, 80), "Original words", fontsize=18)
        page.insert_text((40, 130), "Keep this line", fontsize=14)
        page.insert_image(pdf.Rect(40, 200, 160, 280), filename=str(picture))
        doc.new_page(width=400, height=500)
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    workspace.select_all(True)
    focus = PageFocus(workspace, 0)
    items = [item for item in focus.scene.items() if isinstance(item, ObjectItem)]
    text_item = next(item for item in items if item.obj.kind == "Text" and item.obj.text == "Original words")
    text_item.setSelected(True)
    focus.text.setPlainText("Changed words")
    image_item = next(item for item in items if item.obj.kind == "Image")
    focus.scene.clearSelection()
    image_item.setSelected(True)
    from unittest.mock import patch
    from PySide6.QtWidgets import QFileDialog
    with patch.object(QFileDialog, "getOpenFileName", return_value=(str(replacement), "")):
        focus.change_image()
    image_item.setPos(200, 200)
    focus.capture()
    focus.navigate(1)
    focus.navigate(-1)
    assert any(obj.text == "Changed words" for obj in focus.objects[0])
    focus.close()
    selected = workspace.selection()
    output = tmp_path / "edited.pdf"
    run_tool("merge", [Path(path) for path, number in selected], output, {
        "merge_pages": [str(number + 1) for path, number in selected],
        "merge_crops": [workspace.crops.get(key) for key in selected],
        "merge_edits": [workspace.edits.get(key, []) for key in selected],
    })
    with pdf.open(output) as doc:
        text = doc[0].get_text()
        assert "Changed words" in text
        assert "Original words" not in text
        assert "Keep this line" in text
        pix = doc[0].get_pixmap(alpha=False)
        assert pix.pixel(220, 220)[2] > 200
        assert pix.pixel(80, 220) == (255, 255, 255)
    with pdf.open(source) as doc:
        assert "Original words" in doc[0].get_text()
    workspace.close()

def test_existing_content_selection_undo_and_delete(tmp_path, application_session):
    from deskpdf.editor import ObjectItem
    source = tmp_path / "input.pdf"
    with pdf.open() as doc:
        doc.new_page().insert_text((50, 70), "Original text")
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    item = next(item for item in focus.scene.items() if isinstance(item, ObjectItem) and item.obj.source_rect)
    item.setSelected(True)
    focus.capture()
    assert not focus.objects[0]
    focus.text.setPlainText("New text")
    focus.undo()
    assert not focus.objects[0]
    item = next(item for item in focus.scene.items() if isinstance(item, ObjectItem) and item.obj.source_rect)
    item.setSelected(True)
    focus.delete()
    assert len(focus.objects[0]) == 1 and focus.objects[0][0].removed
    focus.undo()
    assert not focus.objects[0]
    focus.close()
    workspace.close()

def test_cropping_after_edit_keeps_existing_text_identity(tmp_path, application_session):
    from deskpdf.editor import ObjectItem
    from deskpdf.crop_page import CropPageDialog
    from PySide6.QtCore import QRectF
    from PySide6.QtWidgets import QDialog
    from unittest.mock import patch
    source = tmp_path / "crop.pdf"
    with pdf.open() as doc:
        doc.new_page(width=400, height=600).insert_text((60, 80), "Original")
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    item = next(item for item in focus.scene.items() if isinstance(item, ObjectItem) and item.obj.source_rect)
    item.setSelected(True)
    focus.text.setPlainText("Changed")
    def crop_edges(dialog):
        canvas = dialog.canvas
        canvas.selection = QRectF(canvas.width() * .05, canvas.height() * .05, canvas.width() * .9, canvas.height() * .9)
        return QDialog.DialogCode.Accepted
    with patch.object(CropPageDialog, "exec", crop_edges):
        focus.crop()
    items = [item for item in focus.scene.items() if isinstance(item, ObjectItem)]
    assert len(items) == 1
    focus.close()
    workspace.close()

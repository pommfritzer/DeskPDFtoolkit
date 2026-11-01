from pathlib import Path
import pymupdf as pdf
from PIL import Image
from deskpdf.editor import VisualEditor, Object, export_objects


def test_editor_export_preserves_original_and_adds_content(tmp_path):
    source = tmp_path / "source.pdf"
    with pdf.open() as doc:
        doc.new_page().insert_text((40, 40), "Original text")
        doc.save(source)
    image = tmp_path / "picture.png"
    Image.new("RGB", (80, 40), "green").save(image)
    output = tmp_path / "result.pdf"
    with pdf.open(source) as doc:
        export_objects(doc, {0: [Object("Text", (40, 100, 300, 180), text="Added words"), Object("Image", (40, 220, 240, 320), image=str(image)), Object("Rectangle", (300, 220, 400, 300)), Object("Ellipse", (300, 330, 400, 400))]}, output)
    with pdf.open(output) as doc:
        assert "Original text" in doc[0].get_text()
        assert "Added words" in doc[0].get_text()
        assert doc[0].get_images()
        assert len(doc[0].get_drawings()) >= 2
    with pdf.open(source) as doc:
        assert "Added words" not in doc[0].get_text()


def test_editor_move_resize_undo_and_page_switch(tmp_path, application_session):
    source = tmp_path / "source.pdf"
    with pdf.open() as doc:
        doc.new_page()
        doc.new_page()
        doc.save(source)
    editor = VisualEditor(source)
    editor.add("Text")
    item = editor.selected()
    editor.capture()
    original_rect = editor.objects[0][0].rect
    editor.remember()
    item.setPos(100, 200)
    item.setRect(0, 0, 240, 120)
    editor.capture()
    assert editor.objects[0][0].rect == (100, 200, 340, 320)
    editor.undo()
    assert editor.objects[0][0].rect == original_rect
    editor.redo()
    assert editor.objects[0][0].rect == (100, 200, 340, 320)
    editor.navigate(1)
    editor.add("Rectangle")
    editor.navigate(-1)
    assert editor.objects[0][0].kind == "Text"
    editor.dirty = False
    editor.close()


def test_escape_respects_unsaved_changes(tmp_path, application_session):
    from unittest.mock import patch
    from PySide6.QtWidgets import QMessageBox
    source = tmp_path / "source.pdf"
    with pdf.open() as doc:
        doc.new_page()
        doc.save(source)
    editor = VisualEditor(source)
    editor.add("Text")
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
        editor.reject()
    assert not editor.document.is_closed
    assert editor.dirty
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard):
        editor.reject()
    assert editor.document.is_closed
    assert not editor.dirty

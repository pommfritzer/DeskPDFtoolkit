import pytest
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


def test_unsupported_text_does_not_replace_existing_output(tmp_path):
    from deskpdf.engine import run_tool
    from deskpdf.objects import Object

    source = tmp_path / "source.pdf"
    output = tmp_path / "output.pdf"
    with pdf.open() as document:
        document.new_page()
        document.save(source)
    output.write_bytes(b"existing file")
    obj = Object("Text", (40, 40, 200, 100), text="Hello \U0001f600")
    with pytest.raises(ValueError, match="cannot be saved reliably"):
        run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_edits": [[obj]]})
    assert output.read_bytes() == b"existing file"


def test_editor_preserves_distinct_passwords_and_permissions_through_undo(tmp_path, application_session):
    from unittest.mock import patch
    from PySide6.QtWidgets import QFileDialog

    source = tmp_path / "encrypted.pdf"
    output = tmp_path / "edited.pdf"
    permissions = pdf.PDF_PERM_MODIFY | pdf.PDF_PERM_PRINT
    with pdf.open() as document:
        document.new_page()
        document.save(source, encryption=pdf.PDF_ENCRYPT_AES_256,
                      owner_pw="owner-password", user_pw="user-password", permissions=permissions)
    expected_permissions = {}
    for password in ("user-password", "owner-password"):
        with pdf.open(source) as document:
            assert document.authenticate(password)
            expected_permissions[password] = document.permissions
            expected_encryption = document.metadata["encryption"]
    editor = VisualEditor(source, "user-password")
    editor.add("Text")
    editor.undo()
    editor.redo()
    with patch.object(QFileDialog, "getSaveFileName", return_value=(str(output), "PDF (*.pdf)")):
        editor.save()
    assert output.exists()
    for password, expected_role in (("user-password", 2), ("owner-password", 4)):
        with pdf.open(output) as document:
            assert document.needs_pass
            assert document.authenticate(password) == expected_role
            assert document.permissions == expected_permissions[password]
            assert document.metadata["encryption"] == expected_encryption
            assert "Text" in document[0].get_text()
    editor.close()


@pytest.mark.parametrize("reader_password", ["reader-password", ""])
def test_owner_password_allows_editing_restricted_pdf_without_changing_permissions(tmp_path, application_session, reader_password):
    from unittest.mock import patch
    from PySide6.QtWidgets import QFileDialog
    from deskpdf.engine import ToolError

    source = tmp_path / "restricted.pdf"
    output = tmp_path / "edited.pdf"
    with pdf.open() as document:
        document.new_page()
        document.save(source, encryption=pdf.PDF_ENCRYPT_AES_256, owner_pw="owner-password",
                      user_pw=reader_password, permissions=pdf.PDF_PERM_PRINT)
    with pytest.raises(ToolError, match="owner password"):
        VisualEditor(source, reader_password)
    editor = VisualEditor(source, "owner-password")
    editor.add("Text")
    editor.undo()
    editor.redo()
    with patch.object(QFileDialog, "getSaveFileName", return_value=(str(output), "PDF (*.pdf)")):
        editor.save()
    with pdf.open(output) as document:
        assert document.authenticate(reader_password) == 2
        assert not document.permissions & pdf.PDF_PERM_MODIFY
        assert "Text" in document[0].get_text()
    with pdf.open(output) as document:
        assert document.authenticate("owner-password") == 4
    editor.close()

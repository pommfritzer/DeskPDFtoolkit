from pathlib import Path
import pymupdf as pdf
import pytest
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

def test_existing_text_keeps_color_and_size_when_edited(tmp_path, application_session):
    from deskpdf.editor import ObjectItem
    source = tmp_path / "colored.pdf"
    with pdf.open() as doc:
        doc.new_page(width=400, height=400).insert_text((40, 70), "Colored", fontsize=11.25, color=(.12, .56, .78), fill_opacity=.4)
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    item = next(item for item in focus.scene.items() if isinstance(item, ObjectItem) and item.obj.kind == "Text")
    original_color = item.obj.color
    item.setSelected(True)
    assert focus.color.currentData() == original_color
    assert focus.size.value() == 11.25
    focus.text.setPlainText("Edit")
    assert item.obj.color == original_color
    assert item.obj.size == 11.25
    with pdf.open(stream=focus.document.tobytes()) as doc:
        from deskpdf.objects import apply_objects
        apply_objects(doc, {0: focus.objects[0]})
        span = next(span for block in doc[0].get_text("dict")["blocks"] if block["type"] == 0 for line in block["lines"] for span in line["spans"] if "Edit" in span["text"])
        assert span["color"] == int(original_color[1:], 16)
        assert abs(span["size"] - 11.25) < .01
        assert abs(span["origin"][1] - 70) < .01
        assert abs(span["alpha"] - 102) <= 1
    focus.close()
    workspace.close()


def test_clicking_existing_content_does_not_create_an_edit(tmp_path, application_session):
    from deskpdf.editor import ObjectItem
    from PySide6.QtTest import QTest
    source = tmp_path / "click.pdf"
    with pdf.open() as doc:
        doc.new_page().insert_text((50, 70), "Click me")
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    focus.show()
    application_session.processEvents()
    item = next(item for item in focus.scene.items() if isinstance(item, ObjectItem))
    point = focus.view.mapFromScene(item.mapToScene(item.rect().center()))
    QTest.mouseClick(focus.view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert focus.selected() is item
    assert not focus.dirty
    assert not focus.history
    focus.close()
    assert not workspace.edits_dirty
    assert not workspace.selection()
    workspace.close()

def test_drag_existing_text_can_be_undone(tmp_path, application_session):
    from deskpdf.editor import ObjectItem
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    source = tmp_path / "move.pdf"
    with pdf.open() as doc:
        doc.new_page(width=400, height=400).insert_text((50, 70), "Move me", fontsize=18)
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    focus.show()
    application_session.processEvents()
    item = next(item for item in focus.scene.items() if isinstance(item, ObjectItem))
    original = item.obj.rect
    point = focus.view.mapFromScene(item.mapToScene(item.rect().center()))
    viewport = focus.view.viewport()
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=point)
    QTest.mouseMove(viewport, point + QPoint(80, 80), delay=20)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=point + QPoint(80, 80))
    assert focus.dirty and len(focus.history) == 1
    assert focus.objects[0][0].rect != original
    focus.undo()
    assert not focus.objects[0]
    focus.redo()
    assert focus.objects[0][0].rect != original
    focus.close()
    workspace.close()

def test_fill_form_fields_in_focus_and_save(tmp_path, application_session):
    from deskpdf.editor import FormFieldItem
    from deskpdf.engine import run_tool
    from PySide6.QtTest import QTest
    source = tmp_path / "form.pdf"
    with pdf.open() as doc:
        page = doc.new_page(width=400, height=500)
        for field_type, name, top in ((pdf.PDF_WIDGET_TYPE_TEXT, "Name", 50), (pdf.PDF_WIDGET_TYPE_CHECKBOX, "Agree", 100), (pdf.PDF_WIDGET_TYPE_COMBOBOX, "Choice", 150)):
            widget = pdf.Widget()
            widget.field_type = field_type
            widget.field_name = name
            widget.rect = pdf.Rect(40, top, 220, top + 30)
            if field_type == pdf.PDF_WIDGET_TYPE_COMBOBOX:
                widget.choice_values = ["Red", "Green", "Blue"]
            page.add_widget(widget)
        doc.new_page(width=400, height=500)
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    focus.show()
    application_session.processEvents()
    fields = {item.obj.form_name: item for item in focus.scene.items() if isinstance(item, FormFieldItem)}
    assert set(fields) == {"Name", "Agree", "Choice"}
    fields["Name"].setSelected(True)
    focus.form_text.setFocus()
    QTest.keyClicks(focus.form_text, "Alex")
    focus.scene.clearSelection()
    fields["Agree"].setSelected(True)
    focus.form_check.setChecked(True)
    focus.scene.clearSelection()
    fields["Choice"].setSelected(True)
    focus.form_choice.setCurrentIndex(focus.form_choice.findData("Green"))
    focus.undo()
    assert all(obj.form_name != "Choice" for obj in focus.objects[0] if obj.kind == "Form")
    focus.redo()
    focus.navigate(1)
    focus.navigate(-1)
    assert {obj.form_name: obj.form_value for obj in focus.objects[0] if obj.kind == "Form"} == {"Name": "Alex", "Agree": "Yes", "Choice": "Green"}
    focus.close()
    selected = workspace.selection()
    assert selected == [(str(source), 0)]
    output = tmp_path / "filled.pdf"
    run_tool("merge", [Path(path) for path, number in selected], output, {
        "merge_pages": [str(number + 1) for path, number in selected],
        "merge_crops": [workspace.crops.get(key) for key in selected],
        "merge_edits": [workspace.edits.get(key, []) for key in selected],
    })
    with pdf.open(output) as doc:
        values = {widget.field_name: widget.field_value for widget in doc[0].widgets()}
        assert values == {"Name": "Alex", "Agree": "Yes", "Choice": "Green"}
        assert "Alex" in doc[0].get_text()
    with pdf.open(source) as doc:
        assert next(doc[0].widgets()).field_value == ""
    workspace.close()

def test_form_checkbox_click_and_unicode_text_with_cropped_rotated_page(tmp_path, application_session):
    from deskpdf.editor import FormFieldItem
    from deskpdf.engine import run_tool
    from PySide6.QtTest import QTest
    source = tmp_path / "form.pdf"
    with pdf.open() as doc:
        page = doc.new_page(width=400, height=500)
        for field_type, name, top in ((pdf.PDF_WIDGET_TYPE_TEXT, "Name", 80), (pdf.PDF_WIDGET_TYPE_CHECKBOX, "Accept", 140)):
            widget = pdf.Widget()
            widget.field_type = field_type
            widget.field_name = name
            widget.rect = pdf.Rect(60, top, 240, top + 30)
            page.add_widget(widget)
        page.set_cropbox(pdf.Rect(20, 20, 380, 480))
        page.set_rotation(90)
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    before_thumbnail = workspace.pages.item(0).icon().pixmap(workspace.pages.iconSize()).toImage()
    focus = PageFocus(workspace, 0)
    focus.show()
    application_session.processEvents()
    fields = {item.obj.form_name: item for item in focus.scene.items() if isinstance(item, FormFieldItem)}
    fields["Name"].setSelected(True)
    focus.form_text.setFocus()
    focus.form_text.insert("M\u00fcller Z\u00fcrich")
    assert fields["Name"].obj.form_value == "M\u00fcller Z\u00fcrich"
    point = focus.view.mapFromScene(fields["Accept"].rect().center())
    QTest.mouseClick(focus.view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert focus.form_checked(fields["Accept"].obj)
    focus.close()
    key = (str(source), 0)
    assert workspace.pages.item(0).toolTip() == f"{source.name} · Page 1"
    assert workspace.pages.item(0).icon().pixmap(workspace.pages.iconSize()).toImage() != before_thumbnail
    output = tmp_path / "output.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        assert doc[0].rotation == 90
        values = {widget.field_name: widget.field_value for widget in doc[0].widgets()}
        assert values == {"Name": "M\u00fcller Z\u00fcrich", "Accept": "Yes"}
    workspace.close()

def test_editable_form_choice_in_focus(tmp_path, application_session):
    from deskpdf.editor import FormFieldItem
    from deskpdf.engine import run_tool
    from PySide6.QtTest import QTest
    source = tmp_path / "choice.pdf"
    with pdf.open() as doc:
        page = doc.new_page()
        widget = pdf.Widget()
        widget.field_type = pdf.PDF_WIDGET_TYPE_COMBOBOX
        widget.field_flags = pdf.PDF_CH_FIELD_IS_EDIT
        widget.field_name = "City"
        widget.choice_values = ["Paris", "Bern"]
        widget.rect = pdf.Rect(40, 60, 200, 90)
        page.add_widget(widget)
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    item = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem))
    item.setSelected(True)
    assert focus.form_choice.isEditable()
    focus.form_choice.lineEdit().selectAll()
    QTest.keyClicks(focus.form_choice.lineEdit(), "Basel")
    assert item.obj.form_value == "Basel"
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "output.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        assert next(doc[0].widgets()).field_value == "Basel"
    workspace.close()

def test_form_choice_uses_display_name_and_saves_export_value(tmp_path, application_session):
    from deskpdf.editor import FormFieldItem
    from deskpdf.engine import run_tool
    source = tmp_path / "choice-pairs.pdf"
    with pdf.open() as doc:
        page = doc.new_page()
        widget = pdf.Widget()
        widget.field_type = pdf.PDF_WIDGET_TYPE_COMBOBOX
        widget.field_name = "Language"
        widget.choice_values = ["de", "fr"]
        widget.rect = pdf.Rect(40, 60, 200, 90)
        xref = page.add_widget(widget).xref
        doc.xref_set_key(xref, "Opt", "[[(de)(German)] [(fr)(French)]]")
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    item = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem))
    item.setSelected(True)
    index = focus.form_choice.findText("German")
    assert focus.form_choice.itemData(index) == "de"
    focus.form_choice.setCurrentIndex(index)
    assert item.obj.form_value == "de"
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "output.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        page = doc[0]
        assert next(page.widgets()).field_value == "de"
        assert "German" in page.get_text()
    workspace.close()

def test_form_multiline_limit_and_readonly_fields(tmp_path, application_session):
    from deskpdf.editor import FormFieldItem
    source = tmp_path / "limited.pdf"
    with pdf.open() as doc:
        page = doc.new_page()
        for name, flags, top in (("Notes", pdf.PDF_TX_FIELD_IS_MULTILINE, 50), ("Locked", pdf.PDF_FIELD_IS_READ_ONLY, 120)):
            widget = pdf.Widget()
            widget.field_type = pdf.PDF_WIDGET_TYPE_TEXT
            widget.field_name = name
            widget.field_flags = flags
            widget.text_maxlen = 5
            widget.rect = pdf.Rect(40, top, 200, top + 50)
            page.add_widget(widget)
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    fields = {item.obj.form_name: item for item in focus.scene.items() if isinstance(item, FormFieldItem)}
    assert set(fields) == {"Notes"}
    fields["Notes"].setSelected(True)
    focus.form_multiline.setPlainText("abcdef")
    assert fields["Notes"].obj.form_value == "abcde"
    assert focus.form_multiline.toPlainText() == "abcde"
    focus.close()
    workspace.close()

def test_linked_fields_stay_in_sync_across_focus_and_merge(tmp_path, application_session):
    from deskpdf.editor import FormFieldItem
    from deskpdf.engine import run_tool
    from PySide6.QtTest import QTest
    source = tmp_path / "linked.pdf"
    make_linked_form(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    workspace.select_all(True)
    focus = PageFocus(workspace, 0)
    first = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem))
    first.setSelected(True)
    focus.form_text.selectAll()
    QTest.keyClicks(focus.form_text, "Alice")
    focus.navigate(1)
    second = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem))
    assert second.obj.form_value == "Alice"
    second.setSelected(True)
    focus.form_text.selectAll()
    QTest.keyClicks(focus.form_text, "Bob")
    focus.navigate(-1)
    first = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem))
    assert first.obj.form_value == "Bob"
    focus.close()
    selected = workspace.selection()
    related = [(path, page, obj) for (path, page), entries in workspace.edits.items() for obj in entries if obj.kind == "Form"]
    assert len(related) == 1
    output = tmp_path / "merged.pdf"
    run_tool("merge", [Path(path) for path, number in selected], output, {
        "merge_pages": [str(number + 1) for path, number in selected],
        "merge_crops": [workspace.crops.get(key) for key in selected],
        "merge_edits": [workspace.edits.get(key, []) for key in selected],
        "merge_form_edits": related,
    })
    with pdf.open(output) as doc:
        assert [next(page.widgets()).field_value for page in doc] == ["Bob", "Bob"]
        assert all("Bob" in page.get_text() for page in doc)
        page = doc[0]
        field = next(page.widgets())
        field.field_value = "Charlie"
        field.update()
        updated = tmp_path / "merged-updated.pdf"
        doc.save(updated)
    with pdf.open(updated) as doc:
        assert [next(page.widgets()).field_value for page in doc] == ["Charlie", "Charlie"]
    only_first = tmp_path / "first.pdf"
    run_tool("merge", [source], only_first, {"merge_pages": ["1"], "merge_form_edits": related})
    with pdf.open(only_first) as doc:
        assert next(doc[0].widgets()).field_value == "Bob"
    with pdf.open(source) as doc:
        assert [next(page.widgets()).field_value for page in doc] == ["Old", "Old"]
    workspace.close()


def make_linked_form(source):
    with pdf.open() as doc:
        kids = []
        for index in range(2):
            page = doc.new_page(width=400, height=500)
            widget = pdf.Widget()
            widget.field_name = f"temporary{index}"
            widget.field_type = pdf.PDF_WIDGET_TYPE_TEXT
            widget.field_value = "Old"
            widget.rect = pdf.Rect(40, 60, 200, 90)
            kids.append(page.add_widget(widget).xref)
        parent = doc.get_new_xref()
        doc.update_object(parent, f"<</FT /Tx /T (Shared) /Kids [{kids[0]} 0 R {kids[1]} 0 R] /V (Old)>>")
        for child in kids:
            doc.xref_set_key(child, "Parent", f"{parent} 0 R")
            for key in ("T", "FT", "V"):
                pdf.mupdf.pdf_dict_dels(pdf.mupdf.pdf_load_object(pdf._as_pdf_document(doc), child), key)
        doc.xref_set_key(doc.pdf_catalog(), "AcroForm/Fields", f"[{parent} 0 R]")
        doc.save(source)

def test_standalone_editor_keeps_linked_form_fields_in_sync(tmp_path, application_session):
    from deskpdf.editor import FormFieldItem, VisualEditor
    from PySide6.QtTest import QTest
    source = tmp_path / "linked.pdf"
    make_linked_form(source)
    editor = VisualEditor(source)
    first = next(item for item in editor.scene.items() if isinstance(item, FormFieldItem))
    first.setSelected(True)
    editor.form_text.selectAll()
    QTest.keyClicks(editor.form_text, "Alice")
    editor.navigate(1)
    second = next(item for item in editor.scene.items() if isinstance(item, FormFieldItem))
    assert second.obj.form_value == "Alice"
    second.setSelected(True)
    editor.form_text.selectAll()
    QTest.keyClicks(editor.form_text, "Bob")
    editor.navigate(-1)
    first = next(item for item in editor.scene.items() if isinstance(item, FormFieldItem))
    assert first.obj.form_value == "Bob"
    editor.capture()
    output = tmp_path / "filled.pdf"
    from deskpdf.objects import export_objects
    with pdf.open(stream=editor.document.tobytes()) as doc:
        export_objects(doc, editor.objects, output)
    with pdf.open(output) as doc:
        assert [next(page.widgets()).field_value for page in doc] == ["Bob", "Bob"]
    editor.dirty = False
    editor.close()

def test_window_saves_linked_field_when_edited_page_is_not_included(tmp_path, application_session):
    from deskpdf.catalog import TOOL_BY_ID
    from deskpdf.editor import FormFieldItem
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QFileDialog
    from unittest.mock import patch
    source = tmp_path / "linked.pdf"
    make_linked_form(source)
    window = Window()
    window.select_tool(TOOL_BY_ID["merge"])
    window.add_paths([source])
    window.visual_merge.toggle(window.visual_merge.pages.item(0))
    focus = PageFocus(window.visual_merge, 1)
    item = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem))
    item.setSelected(True)
    focus.form_text.selectAll()
    QTest.keyClicks(focus.form_text, "New")
    focus.close()
    window.visual_merge.toggle(window.visual_merge.pages.item(1))
    assert window.visual_merge.selection() == [(str(source), 0)]
    output = tmp_path / "output.pdf"
    with patch.object(QFileDialog, "getSaveFileName", return_value=(str(output), "")):
        window.start_job()
    assert window.worker.wait(10000)
    application_session.processEvents()
    with pdf.open(output) as doc:
        assert next(doc[0].widgets()).field_value == "New"
    window.close()

def test_merge_keeps_form_widgets_when_importing_multiple_pages(tmp_path):
    from deskpdf.engine import run_tool
    linked = tmp_path / "linked.pdf"
    make_linked_form(linked)
    cover = tmp_path / "cover.pdf"
    with pdf.open() as doc:
        doc.new_page()
        doc.save(cover)
    output = tmp_path / "output.pdf"
    run_tool("merge", [cover, linked], output, {"merge_pages": ["1", "1-2"]})
    with pdf.open(output) as doc:
        assert [next(doc[index].widgets()).field_value for index in (1, 2)] == ["Old", "Old"]

def test_merge_preserves_linked_fields_without_linking_different_documents(tmp_path):
    from deskpdf.engine import run_tool
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    make_linked_form(first)
    make_linked_form(second)
    output = tmp_path / "merged.pdf"
    run_tool("merge", [first, second, first, second], output, {"merge_pages": ["2", "1", "1", "2"]})
    updated = tmp_path / "updated.pdf"
    with pdf.open(output) as doc:
        assert len(doc) == 4
        assert [next(page.widgets()).field_value for page in doc] == ["Old"] * 4
        page = doc[0]
        widget = next(page.widgets())
        widget.field_value = "Changed first document"
        widget.update()
        doc.save(updated)
    with pdf.open(updated) as doc:
        assert [next(page.widgets()).field_value for page in doc] == ["Changed first document", "Old", "Changed first document", "Old"]
    with pdf.open(first) as doc:
        assert [next(page.widgets()).field_value for page in doc] == ["Old", "Old"]


def test_merge_keeps_distinct_crops_for_repeated_page(tmp_path):
    from deskpdf.engine import run_tool
    source = tmp_path / "single.pdf"
    with pdf.open() as doc:
        doc.new_page(width=400, height=500)
        doc.save(source)
    output = tmp_path / "merged.pdf"
    run_tool("merge", [source, source], output, {
        "merge_pages": ["1", "1"],
        "merge_crops": [(0, 0, 300, 500), (0, 0, 200, 500)],
    })
    with pdf.open(output) as doc:
        assert [page.rect.width for page in doc] == [300, 200]

def test_merge_retains_internal_links_after_interleaving_sources(tmp_path):
    from deskpdf.engine import run_tool
    paths = [tmp_path / "a.pdf", tmp_path / "b.pdf"]
    for path in paths:
        with pdf.open() as doc:
            doc.new_page(width=300, height=300).insert_text((40, 50), f"{path.stem}1")
            doc.new_page(width=300, height=300).insert_text((40, 50), f"{path.stem}2")
            doc[0].insert_link({"kind": pdf.LINK_GOTO, "from": pdf.Rect(10, 10, 100, 30), "page": 1, "to": pdf.Point(0, 0)})
            doc.save(path)
    output = tmp_path / "merged.pdf"
    run_tool("merge", [paths[0], paths[1], paths[0], paths[1]], output, {"merge_pages": ["1", "1", "2", "2"]})
    with pdf.open(output) as doc:
        assert [page.get_text().strip() for page in doc] == ["a1", "b1", "a2", "b2"]
        assert doc[0].get_links()[0]["page"] == 2
        assert doc[1].get_links()[0]["page"] == 3


def test_merge_keeps_first_document_password(tmp_path):
    from deskpdf.engine import run_tool
    protected = tmp_path / "protected.pdf"
    cover = tmp_path / "cover.pdf"
    with pdf.open() as doc:
        doc.new_page().insert_text((40, 60), "Protected")
        doc.save(protected, encryption=pdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="secret")
    with pdf.open() as doc:
        doc.new_page().insert_text((40, 60), "Cover")
        doc.save(cover)
    output = tmp_path / "merged.pdf"
    run_tool("merge", [protected, cover], output, {"password": "secret"})
    with pdf.open(output) as doc:
        assert doc.needs_pass
        assert doc.authenticate("secret")
        assert [page.get_text().strip() for page in doc] == ["Protected", "Cover"]

def test_merge_copies_only_selected_pages_from_unconnected_source(tmp_path, monkeypatch):
    from deskpdf.engine import run_tool
    cover = tmp_path / "cover.pdf"
    source = tmp_path / "long.pdf"
    with pdf.open() as doc:
        doc.new_page()
        doc.save(cover)
    with pdf.open() as doc:
        for index in range(12):
            doc.new_page().insert_text((40, 60), f"Page {index + 1}")
        doc.save(source)
    copied = []
    original = pdf.Document.insert_pdf
    def track(target, source_doc, **kwargs):
        copied.append((kwargs.get("from_page"), kwargs.get("to_page")))
        return original(target, source_doc, **kwargs)
    monkeypatch.setattr(pdf.Document, "insert_pdf", track)
    output = tmp_path / "merged.pdf"
    run_tool("merge", [cover, source], output, {"merge_pages": ["1", "1,12"]})
    assert copied == [(0, 0), (11, 11)]
    with pdf.open(output) as doc:
        assert [page.get_text().strip() for page in doc][1:] == ["Page 1", "Page 12"]

def make_radio_form(source, across_pages=False):
    with pdf.open() as doc:
        page = doc.new_page(width=400, height=500)
        kids = []
        for index, name in enumerate(("Alpha", "Beta")):
            if index and across_pages:
                page = doc.new_page(width=400, height=500)
            widget = pdf.Widget()
            widget.field_type = pdf.PDF_WIDGET_TYPE_CHECKBOX
            widget.field_name = f"temporary{index}"
            widget.rect = pdf.Rect(40 + (0 if across_pages else index * 50), 60, 60 + (0 if across_pages else index * 50), 80)
            widget.field_value = False
            xref = page.add_widget(widget).xref
            kids.append(xref)
            on = doc.xref_get_key(xref, "AP/N/Yes")[1]
            off = doc.xref_get_key(xref, "AP/N/Off")[1]
            doc.xref_set_key(xref, "AP/N", f"<</Off {off} /{name} {on}>>")
            doc.xref_set_key(xref, "AS", f"/{name}" if index == 0 else "/Off")
        parent = doc.get_new_xref()
        doc.update_object(parent, f"<</FT /Btn /Ff {pdf.PDF_BTN_FIELD_IS_RADIO} /T (Group) /V /Alpha /Kids [{kids[0]} 0 R {kids[1]} 0 R]>>")
        for child in kids:
            doc.xref_set_key(child, "Parent", f"{parent} 0 R")
            for key in ("T", "FT", "V", "Ff"):
                pdf.mupdf.pdf_dict_dels(pdf.mupdf.pdf_load_object(pdf._as_pdf_document(doc), child), key)
        doc.xref_set_key(doc.pdf_catalog(), "AcroForm/Fields", f"[{parent} 0 R]")
        doc.save(source)


def test_radio_group_selection_undo_and_save_in_focus(tmp_path, application_session):
    from deskpdf.editor import FormFieldItem
    from deskpdf.engine import run_tool
    from PySide6.QtTest import QTest
    source = tmp_path / "radio.pdf"
    make_radio_form(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    focus.show()
    application_session.processEvents()
    fields = {item.obj.form_on: item for item in focus.scene.items() if isinstance(item, FormFieldItem)}
    assert focus.form_checked(fields["Alpha"].obj)
    assert not focus.form_checked(fields["Beta"].obj)
    fields["Alpha"].setSelected(True)
    assert focus.form_radio.isChecked()
    focus.scene.clearSelection()
    fields["Beta"].setSelected(True)
    assert not focus.form_radio.isChecked()
    assert not focus.dirty
    point = focus.view.mapFromScene(fields["Beta"].rect().center())
    QTest.mouseClick(focus.view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert focus.form_checked(fields["Beta"].obj)
    assert not focus.form_checked(fields["Alpha"].obj)
    assert focus.form_radio.isChecked()
    focus.undo()
    states = {item.obj.form_on: focus.form_checked(item.obj) for item in focus.scene.items() if isinstance(item, FormFieldItem)}
    assert states == {"Alpha": True, "Beta": False}
    focus.redo()
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "radio-filled.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        page = doc[0]
        widgets = list(page.widgets())
        assert [(w.on_state(), w.field_value) for w in widgets] == [("Alpha", "Off"), ("Beta", "Beta")]
        assert [doc.xref_get_key(w.xref, "AS")[1] for w in widgets] == ["/Off", "/Beta"]
        parent = int(doc.xref_get_key(widgets[0].xref, "Parent")[1].split()[0])
        assert doc.xref_get_key(parent, "V") == ("name", "/Beta")
    with pdf.open(source) as doc:
        assert [(w.on_state(), w.field_value) for w in doc[0].widgets()] == [("Alpha", "Alpha"), ("Beta", "Off")]
    workspace.close()

def test_radio_group_remains_linked_across_merged_pages(tmp_path, application_session):
    from deskpdf.editor import FormFieldItem
    from deskpdf.engine import run_tool
    source = tmp_path / "radios.pdf"
    make_radio_form(source, across_pages=True)
    workspace = MergeView()
    workspace.refresh([source], "")
    workspace.select_all(True)
    focus = PageFocus(workspace, 1)
    item = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem))
    item.setSelected(True)
    focus.form_radio.setChecked(True)
    focus.navigate(-1)
    first = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem))
    assert not focus.form_checked(first.obj)
    focus.close()
    selected = workspace.selection()
    related = [(path, page, obj) for (path, page), entries in workspace.edits.items() for obj in entries if obj.kind == "Form"]
    output = tmp_path / "output.pdf"
    run_tool("merge", [Path(path) for path, number in selected], output, {
        "merge_pages": [str(number + 1) for path, number in selected],
        "merge_crops": [workspace.crops.get(key) for key in selected],
        "merge_edits": [workspace.edits.get(key, []) for key in selected],
        "merge_form_edits": related,
    })
    with pdf.open(output) as doc:
        assert [next(page.widgets()).field_value for page in doc] == ["Off", "Beta"]
        first_page = doc[0]
        first = next(first_page.widgets())
        first.field_value = first.on_state()
        first.update()
        updated = tmp_path / "updated.pdf"
        doc.save(updated)
    with pdf.open(updated) as doc:
        assert [next(page.widgets()).field_value for page in doc] == ["Alpha", "Off"]
    workspace.close()

def test_page_tools_preserve_acroform_catalog_and_radio_hierarchy(tmp_path):
    from deskpdf.engine import run_tool
    source = tmp_path / "radios.pdf"
    make_radio_form(source, across_pages=True)
    with pdf.open(source) as doc:
        doc.xref_set_key(doc.pdf_catalog(), "AcroForm/NeedAppearances", "true")
        updated = tmp_path / "with-options.pdf"
        doc.save(updated)
    for tool, options in (("extract", {"pages": "2,1"}), ("reorder", {"pages": "2,1"}), ("delete", {"pages": "1"}), ("merge", {"merge_pages": ["2,1"]})):
        output = tmp_path / f"{tool}.pdf"
        run_tool(tool, [updated], output, options)
        with pdf.open(output) as doc:
            assert doc.xref_get_key(doc.pdf_catalog(), "AcroForm/Fields")[0] == "array"
            assert doc.xref_get_key(doc.pdf_catalog(), "AcroForm/NeedAppearances") == ("bool", "true")
            widgets = [(page.number, widget.xref) for page in doc for widget in page.widgets()]
            assert len(widgets) == len(doc)
            parent = int(doc.xref_get_key(widgets[0][1], "Parent")[1].split()[0])
            parent_kids = doc.xref_get_key(parent, "Kids")[1]
            for _, xref in widgets:
                assert f"{xref} 0 R" in parent_kids
            assert len(parent_kids.split("R")) - 1 == len(widgets)

def make_multiselect_form(source):
    with pdf.open() as doc:
        page = doc.new_page(width=400, height=500)
        widget = pdf.Widget()
        widget.field_type = pdf.PDF_WIDGET_TYPE_LISTBOX
        widget.field_flags = pdf.PDF_CH_FIELD_IS_MULTI_SELECT
        widget.field_name = "Colors"
        widget.choice_values = ["Red", "Green", "Blue"]
        widget.rect = pdf.Rect(40, 60, 200, 140)
        xref = page.add_widget(widget).xref
        doc.xref_set_key(xref, "V", "[(Green)]")
        doc.xref_set_key(xref, "I", "[1]")
        doc.save(source)


def test_multiselect_list_in_focus_preserves_values_and_appearance(tmp_path, application_session):
    from deskpdf.editor import FormFieldItem
    from deskpdf.engine import run_tool
    from deskpdf.objects import selected_form_values
    source = tmp_path / "multi.pdf"
    make_multiselect_form(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    field = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem))
    assert field.obj.form_value == ("Green",)
    field.setSelected(True)
    assert [item.text() for item in focus.form_multi.selectedItems()] == ["Green"]
    focus.form_multi.item(1).setSelected(False)
    focus.form_multi.item(0).setSelected(True)
    focus.form_multi.item(2).setSelected(True)
    assert field.obj.form_value == ("Red", "Blue")
    focus.undo()
    assert next(item.obj.form_value for item in focus.scene.items() if isinstance(item, FormFieldItem)) == ("Red",)
    focus.redo()
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "output.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        page = doc[0]
        widget = next(page.widgets())
        assert selected_form_values(widget) == ("Red", "Blue")
        assert doc.xref_get_key(widget.xref, "I") == ("array", "[0 2]")
        appearance = int(doc.xref_get_key(widget.xref, "AP/N")[1].split()[0])
        stream = doc.xref_stream(appearance)
        assert b"/DeskPDFSelection gs" in stream
        assert stream.count(b" re f") == 2
        assert {"Red", "Green", "Blue"} <= set(page.get_text().split())
    with pdf.open(source) as doc:
        assert selected_form_values(next(doc[0].widgets())) == ("Green",)
    workspace.close()

def test_multiselect_export_values_and_clear(tmp_path, application_session):
    from deskpdf.editor import FormFieldItem
    from deskpdf.engine import run_tool
    from deskpdf.objects import selected_form_values
    source = tmp_path / "languages.pdf"
    with pdf.open() as doc:
        page = doc.new_page()
        widget = pdf.Widget()
        widget.field_type = pdf.PDF_WIDGET_TYPE_LISTBOX
        widget.field_flags = pdf.PDF_CH_FIELD_IS_MULTI_SELECT
        widget.field_name = "Languages"
        widget.choice_values = ["de", "fr", "it"]
        widget.rect = pdf.Rect(40, 60, 220, 140)
        xref = page.add_widget(widget).xref
        doc.xref_set_key(xref, "Opt", "[[(de)(German)] [(fr)(French)] [(it)(Italian)]]")
        doc.xref_set_key(xref, "V", "[(fr)]")
        doc.xref_set_key(xref, "I", "[1]")
        doc.new_page()
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    field = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem))
    field.setSelected(True)
    assert [item.text() for item in focus.form_multi.selectedItems()] == ["French"]
    focus.form_multi.item(0).setSelected(True)
    assert field.obj.form_value == ("de", "fr")
    focus.navigate(1)
    focus.navigate(-1)
    field = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem))
    field.setSelected(True)
    assert {item.text() for item in focus.form_multi.selectedItems()} == {"German", "French"}
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "selected.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        page = doc[0]
        widget = next(page.widgets())
        assert selected_form_values(widget) == ("de", "fr")
        appearance = int(doc.xref_get_key(widget.xref, "AP/N")[1].split()[0])
        assert doc.xref_stream(appearance).count(b" re f") == 2
    focus = PageFocus(workspace, 0)
    field = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem))
    field.setSelected(True)
    for item in list(focus.form_multi.selectedItems()):
        item.setSelected(False)
    focus.close()
    cleared = tmp_path / "cleared.pdf"
    run_tool("merge", [source], cleared, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(cleared) as doc:
        page = doc[0]
        widget = next(page.widgets())
        assert selected_form_values(widget) == ()
        assert doc.xref_get_key(widget.xref, "V")[0] == "null"
        assert doc.xref_get_key(widget.xref, "I")[0] == "null"
    workspace.close()

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_multiselect_on_rotated_cropped_page(tmp_path, application_session, rotation):
    from deskpdf.editor import FormFieldItem
    from deskpdf.engine import run_tool
    from deskpdf.objects import selected_form_values
    original = tmp_path / "original.pdf"
    make_multiselect_form(original)
    source = tmp_path / "cropped.pdf"
    with pdf.open(original) as doc:
        doc[0].set_cropbox(pdf.Rect(20, 20, 380, 480))
        doc[0].set_rotation(rotation)
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    item = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem))
    item.setSelected(True)
    focus.form_multi.item(0).setSelected(True)
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "output.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        page = doc[0]
        assert page.rotation == rotation
        widget = next(page.widgets())
        assert selected_form_values(widget) == ("Red", "Green")
        appearance = int(doc.xref_get_key(widget.xref, "AP/N")[1].split()[0])
        assert doc.xref_stream(appearance).count(b" re f") == 2
    workspace.close()

def test_page_selection_preserves_indirect_acroform_resources(tmp_path):
    from deskpdf.engine import run_tool
    source = tmp_path / "form.pdf"
    make_linked_form(source)
    indirect = tmp_path / "indirect.pdf"
    with pdf.open(source) as doc:
        kind, value = doc.xref_get_key(doc.pdf_catalog(), "AcroForm")
        assert kind == "dict"
        xref = doc.get_new_xref()
        doc.update_object(xref, value)
        doc.xref_set_key(xref, "NeedAppearances", "true")
        doc.xref_set_key(doc.pdf_catalog(), "AcroForm", f"{xref} 0 R")
        doc.save(indirect)
    output = tmp_path / "extracted.pdf"
    run_tool("extract", [indirect], output, {"pages": "2,1"})
    with pdf.open(output) as doc:
        assert doc.xref_get_key(doc.pdf_catalog(), "AcroForm")[0] == "xref"
        assert doc.xref_get_key(doc.pdf_catalog(), "AcroForm/NeedAppearances") == ("bool", "true")
        assert doc.xref_get_key(doc.pdf_catalog(), "AcroForm/Fields")[0] == "array"
        page = doc[0]
        widget = next(page.widgets())
        widget.field_value = "Linked"
        widget.update()
        changed = tmp_path / "changed.pdf"
        doc.save(changed)
    with pdf.open(changed) as doc:
        assert [next(page.widgets()).field_value for page in doc] == ["Linked", "Linked"]

def test_multiselect_preserves_other_fields_in_parent_hierarchy(tmp_path, application_session):
    from deskpdf.editor import FormFieldItem
    from deskpdf.engine import run_tool
    from deskpdf.objects import selected_form_values
    source = tmp_path / "nested.pdf"
    with pdf.open() as doc:
        page = doc.new_page()
        kids = []
        for kind, name, top in ((pdf.PDF_WIDGET_TYPE_LISTBOX, "Languages", 60), (pdf.PDF_WIDGET_TYPE_TEXT, "City", 180)):
            widget = pdf.Widget()
            widget.field_type = kind
            widget.field_name = name
            widget.rect = pdf.Rect(40, top, 200, top + 80)
            if kind == pdf.PDF_WIDGET_TYPE_LISTBOX:
                widget.field_flags = pdf.PDF_CH_FIELD_IS_MULTI_SELECT
                widget.choice_values = ["German", "French"]
            else:
                widget.field_value = "Zurich"
            kids.append(page.add_widget(widget).xref)
        parent = doc.get_new_xref()
        doc.update_object(parent, f"<</T (Person) /Kids [{kids[0]} 0 R {kids[1]} 0 R]>>")
        for kid in kids:
            doc.xref_set_key(kid, "Parent", f"{parent} 0 R")
        doc.xref_set_key(doc.pdf_catalog(), "AcroForm/Fields", f"[{parent} 0 R]")
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    field = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem) and item.obj.form_type == pdf.PDF_WIDGET_TYPE_LISTBOX)
    field.setSelected(True)
    focus.form_multi.item(0).setSelected(True)
    focus.form_multi.item(1).setSelected(True)
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "output.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        page = doc[0]
        fields = {widget.field_type: widget for widget in page.widgets()}
        assert selected_form_values(fields[pdf.PDF_WIDGET_TYPE_LISTBOX]) == ("German", "French")
        assert fields[pdf.PDF_WIDGET_TYPE_TEXT].field_value == "Zurich"
        parent_type, parent_ref = doc.xref_get_key(fields[pdf.PDF_WIDGET_TYPE_LISTBOX].xref, "Parent")
        assert parent_type == "xref"
        assert doc.xref_get_key(int(parent_ref.split()[0]), "V")[0] == "null"
    workspace.close()

def test_page_selection_preserves_hidden_form_values(tmp_path):
    from deskpdf.engine import run_tool
    source = tmp_path / "form.pdf"
    make_linked_form(source)
    hidden = tmp_path / "hidden.pdf"
    with pdf.open(source) as doc:
        existing = doc.xref_get_key(doc.pdf_catalog(), "AcroForm/Fields")[1].strip("[]")
        parent = doc.get_new_xref()
        child = doc.get_new_xref()
        doc.update_object(parent, f"<</T (Metadata) /Kids [{child} 0 R]>>")
        doc.update_object(child, f"<</FT /Tx /T (Reference) /V (KEEP-42) /Parent {parent} 0 R>>")
        doc.xref_set_key(doc.pdf_catalog(), "AcroForm/Fields", f"[{existing} {parent} 0 R]")
        doc.save(hidden)
    output = tmp_path / "output.pdf"
    run_tool("extract", [hidden], output, {"pages": "2"})
    with pdf.open(output) as doc:
        catalog_fields = doc.xref_get_key(doc.pdf_catalog(), "AcroForm/Fields")[1]
        roots = [int(token) for token in catalog_fields.replace("0 R", "").strip("[]").split()]
        metadata = next(xref for xref in roots if doc.xref_get_key(xref, "T") == ("string", "Metadata"))
        kids = doc.xref_get_key(metadata, "Kids")[1]
        field = int(kids.strip("[]").split()[0])
        assert doc.xref_get_key(field, "V") == ("string", "KEEP-42")

def test_radio_option_with_escaped_pdf_name(tmp_path, application_session):
    from deskpdf.editor import FormFieldItem
    from deskpdf.engine import run_tool
    original = tmp_path / "original.pdf"
    source = tmp_path / "special.pdf"
    make_radio_form(original)
    with pdf.open(original) as doc:
        page = doc[0]
        widget = list(page.widgets())[1]
        on = doc.xref_get_key(widget.xref, "AP/N/Beta")[1]
        off = doc.xref_get_key(widget.xref, "AP/N/Off")[1]
        doc.xref_set_key(widget.xref, "AP/N", f"<</Off {off} /Beta#20Choice {on}>>")
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    item = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem) and item.obj.form_on == "Beta Choice")
    item.setSelected(True)
    focus.form_radio.setChecked(True)
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "output.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        page = doc[0]
        widget = list(page.widgets())[1]
        assert widget.field_value == "Beta Choice"
        assert doc.xref_get_key(widget.xref, "AS") == ("name", "/Beta Choice")
        parent = int(doc.xref_get_key(widget.xref, "Parent")[1].split()[0])
        assert doc.xref_get_key(parent, "V") == ("name", "/Beta Choice")
    reopened = MergeView()
    reopened.refresh([output], "")
    focus = PageFocus(reopened, 0)
    item = next(item for item in focus.scene.items() if isinstance(item, FormFieldItem) and item.obj.form_on == "Beta Choice")
    assert focus.form_checked(item.obj)
    focus.close()
    reopened.close()
    workspace.close()

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_edit_existing_content_on_rotated_cropped_page(tmp_path, application_session, rotation):
    from deskpdf.editor import ObjectItem
    from deskpdf.engine import run_tool
    from PIL import Image, ImageDraw
    from unittest.mock import patch
    from PySide6.QtWidgets import QFileDialog
    source_image = tmp_path / "original.png"
    replacement = tmp_path / "replacement.png"
    Image.new("RGB", (80, 40), "red").save(source_image)
    picture = Image.new("RGB", (80, 40), "green")
    ImageDraw.Draw(picture).rectangle((40, 0, 79, 39), fill="blue")
    picture.save(replacement)
    source = tmp_path / "source.pdf"
    with pdf.open() as doc:
        page = doc.new_page(width=400, height=500)
        page.insert_text((60, 90), "Original words", fontsize=18)
        page.insert_text((60, 145), "Keep this line", fontsize=14)
        page.insert_image(pdf.Rect(70, 200, 230, 280), filename=str(source_image))
        page.set_cropbox(pdf.Rect(20, 20, 380, 480))
        page.set_rotation(rotation)
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    items = [item for item in focus.scene.items() if isinstance(item, ObjectItem)]
    text_item = next(item for item in items if item.obj.kind == "Text" and item.obj.text == "Original words")
    text_item.setSelected(True)
    focus.text.setPlainText("Edited")
    image_item = next(item for item in items if item.obj.kind == "Image")
    focus.scene.clearSelection()
    image_item.setSelected(True)
    with patch.object(QFileDialog, "getOpenFileName", return_value=(str(replacement), "")):
        focus.change_image()
    visible_rect = pdf.Rect(image_item.obj.rect)
    assert text_item.obj.rotation == rotation
    assert image_item.obj.rotation == rotation
    from PySide6.QtGui import QImage, QPainter
    scene_rect = focus.scene.sceneRect()
    preview = QImage(round(scene_rect.width()), round(scene_rect.height()), QImage.Format.Format_RGB32)
    preview.fill(Qt.GlobalColor.white)
    focus.scene.clearSelection()
    painter = QPainter(preview)
    focus.scene.render(painter)
    painter.end()
    page = focus.document[0]
    original_space = visible_rect * page.derotation_matrix
    for fraction, expected in ((.25, "green"), (.75, "blue")):
        point = pdf.Point(original_space.x0 + original_space.width * fraction, (original_space.y0 + original_space.y1) / 2) * page.rotation_matrix
        color = preview.pixelColor(round(point.x), round(point.y))
        if expected == "green":
            assert color.green() > color.red() and color.green() > color.blue()
        else:
            assert color.blue() > color.red() and color.blue() > color.green()
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "output.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        page = doc[0]
        assert page.rotation == rotation
        text = page.get_text()
        assert "Original words" not in text
        assert "Edited" in text and "Keep this line" in text
        original_space = visible_rect * page.derotation_matrix
        pix = page.get_pixmap(alpha=False)
        for fraction, expected in ((.25, "green"), (.75, "blue")):
            point = pdf.Point(original_space.x0 + original_space.width * fraction, (original_space.y0 + original_space.y1) / 2) * page.rotation_matrix
            red, green, blue = pix.pixel(round(point.x), round(point.y))
            if expected == "green":
                assert green > red and green > blue
            else:
                assert blue > red and blue > green
    with pdf.open(source) as doc:
        assert "Original words" in doc[0].get_text()
    workspace.close()

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_crop_preserves_edited_content_position_on_rotated_page(tmp_path, application_session, rotation):
    from deskpdf.editor import ObjectItem
    from deskpdf.crop_page import CropPageDialog
    from deskpdf.engine import run_tool
    from unittest.mock import patch
    from PySide6.QtWidgets import QDialog
    source = tmp_path / "source.pdf"
    with pdf.open() as doc:
        page = doc.new_page(width=400, height=500)
        page.insert_text((100, 140), "Original words", fontsize=18)
        page.set_rotation(rotation)
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    item = next(item for item in focus.scene.items() if isinstance(item, ObjectItem) and item.obj.kind == "Text")
    item.setSelected(True)
    focus.text.setPlainText("Edited")
    page = focus.document[0]
    before = (pdf.Rect(item.obj.rect) * page.derotation_matrix) + (page.cropbox.x0, page.cropbox.y0, page.cropbox.x0, page.cropbox.y0)
    with patch.object(CropPageDialog, "exec", return_value=QDialog.DialogCode.Accepted), patch.object(CropPageDialog, "cropbox", return_value=(20, 30, 370, 460)):
        focus.crop()
    page = focus.document[0]
    edited = next(obj for obj in focus.objects[0] if obj.kind == "Text")
    after = (pdf.Rect(edited.rect) * page.derotation_matrix) + (page.cropbox.x0, page.cropbox.y0, page.cropbox.x0, page.cropbox.y0)
    assert all(abs(a - b) < .01 for a, b in zip(before, after))
    assert len([item for item in focus.scene.items() if isinstance(item, ObjectItem) and item.obj.kind == "Text"]) == 1
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "output.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        assert "Edited" in doc[0].get_text()
        assert "Original words" not in doc[0].get_text()
    workspace.close()

@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_move_and_resize_existing_text_on_rotated_page(tmp_path, application_session, rotation):
    from deskpdf.editor import ObjectItem
    from deskpdf.engine import run_tool
    from PySide6.QtCore import QPointF
    from PySide6.QtTest import QTest
    source = tmp_path / "source.pdf"
    with pdf.open() as doc:
        page = doc.new_page(width=400, height=500)
        page.insert_text((100, 140), "Move existing text", fontsize=18)
        page.set_rotation(rotation)
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    focus.show()
    application_session.processEvents()
    item = next(item for item in focus.scene.items() if isinstance(item, ObjectItem) and item.obj.kind == "Text")
    initial = pdf.Rect(item.obj.rect)
    viewport = focus.view.viewport()
    start = focus.view.mapFromScene(item.mapToScene(item.rect().center()))
    end = focus.view.mapFromScene(item.mapToScene(item.rect().center()) + QPointF(30, 30))
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(viewport, end, delay=20)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
    moved = pdf.Rect(item.obj.rect)
    assert moved.x0 > initial.x0 + 20 and moved.y0 > initial.y0 + 20
    handle = item.mapToScene(item.rect().bottomRight() - QPointF(3, 3))
    start = focus.view.mapFromScene(handle)
    end = focus.view.mapFromScene(handle + QPointF(30, 30))
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(viewport, end, delay=20)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
    resized = pdf.Rect(item.obj.rect)
    assert resized.width > moved.width + 15 and resized.height > moved.height + 15
    focus.undo()
    assert pdf.Rect(focus.objects[0][0].rect) == moved
    focus.redo()
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "output.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        page = doc[0]
        assert page.get_text().count("Move existing text") == 1
        box = page.search_for("Move existing text")[0] * page.rotation_matrix
        assert box.intersects(resized)
        assert not box.intersects(initial)
    workspace.close()

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_added_picture_stays_upright_on_rotated_page(tmp_path, application_session, rotation):
    from deskpdf.engine import run_tool
    from PIL import Image, ImageDraw
    picture = Image.new("RGB", (80, 40), "green")
    ImageDraw.Draw(picture).rectangle((40, 0, 79, 39), fill="blue")
    image = tmp_path / "picture.png"
    picture.save(image)
    source = tmp_path / "source.pdf"
    with pdf.open() as doc:
        page = doc.new_page(width=400, height=500)
        page.set_rotation(rotation)
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    focus.add("Image", str(image))
    item = focus.selected()
    item.setPos(80, 100)
    item.setRect(0, 0, 160, 80)
    focus.capture()
    rect = pdf.Rect(item.obj.rect)
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "output.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        pix = doc[0].get_pixmap(alpha=False)
        left = pix.pixel(round(rect.x0 + rect.width * .25), round((rect.y0 + rect.y1) / 2))
        right = pix.pixel(round(rect.x0 + rect.width * .75), round((rect.y0 + rect.y1) / 2))
        assert left[1] > left[0] and left[1] > left[2]
        assert right[2] > right[0] and right[2] > right[1]
    workspace.close()

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_crop_keeps_existing_picture_edit_and_identity(tmp_path, application_session, rotation):
    from deskpdf.editor import ObjectItem
    from deskpdf.crop_page import CropPageDialog
    from deskpdf.engine import run_tool
    from PIL import Image
    from unittest.mock import patch
    from PySide6.QtWidgets import QFileDialog, QDialog
    first = tmp_path / "first.png"
    replacement = tmp_path / "replacement.png"
    Image.new("RGB", (80, 40), "red").save(first)
    Image.new("RGB", (80, 40), "blue").save(replacement)
    source = tmp_path / "source.pdf"
    with pdf.open() as doc:
        page = doc.new_page(width=400, height=500)
        page.insert_image(pdf.Rect(100, 150, 260, 230), filename=str(first))
        page.set_rotation(rotation)
        doc.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    item = next(item for item in focus.scene.items() if isinstance(item, ObjectItem) and item.obj.kind == "Image")
    item.setSelected(True)
    with patch.object(QFileDialog, "getOpenFileName", return_value=(str(replacement), "")):
        focus.change_image()
    with patch.object(CropPageDialog, "exec", return_value=QDialog.DialogCode.Accepted), patch.object(CropPageDialog, "cropbox", return_value=(20, 30, 370, 460)):
        focus.crop()
    items = [item for item in focus.scene.items() if isinstance(item, ObjectItem) and item.obj.kind == "Image"]
    assert len(items) == 1 and items[0].obj.modified
    box = pdf.Rect(items[0].obj.rect)
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "output.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_crops": [workspace.crops[key]], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as doc:
        page = doc[0]
        blocks = [block for block in page.get_text("dict")["blocks"] if block["type"] == 1]
        assert len(blocks) == 1
        placed = pdf.Rect(blocks[0]["bbox"]) * page.rotation_matrix
        assert all(abs(a - b) < .1 for a, b in zip(placed, box))
        pix = page.get_pixmap(alpha=False)
        red, green, blue = pix.pixel(round((box.x0 + box.x1) / 2), round((box.y0 + box.y1) / 2))
        assert blue > red and blue > green
        assert not any(red > 240 and green < 15 and blue < 15 for red, green, blue in zip(pix.samples[0::3], pix.samples[1::3], pix.samples[2::3]))
    workspace.close()

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_existing_text_reuses_embedded_font(tmp_path, application_session, rotation):
    from deskpdf.editor import ObjectItem
    from deskpdf.engine import run_tool

    source = tmp_path / "font.pdf"
    font = pdf.Font("helv")
    with pdf.open() as document:
        page = document.new_page(width=400, height=500)
        page.insert_font(fontname="OriginalFont", fontbuffer=font.buffer)
        page.insert_text((50, 90), "Original long text", fontname="OriginalFont", fontsize=18)
        page.set_rotation(rotation)
        document.save(source)

    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    item = next(item for item in focus.scene.items() if isinstance(item, ObjectItem) and item.obj.kind == "Text")
    assert item.obj.source_font
    item.setSelected(True)
    focus.text.setPlainText("Grüße")
    focus.close()
    key = (str(source), 0)
    output = tmp_path / "edited.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_edits": [workspace.edits[key]]})
    with pdf.open(output) as document:
        spans = [span for block in document[0].get_text("dict")["blocks"] if block["type"] == 0
                 for line in block["lines"] for span in line["spans"]]
        assert [span["text"] for span in spans] == ["Grüße"]
        assert spans[0]["font"] == "NimbusSans-Regular"
        assert abs(spans[0]["size"] - 18) < .1
    workspace.close()


def test_existing_embedded_font_respects_style_change(tmp_path, application_session):
    from deskpdf.editor import ObjectItem
    from deskpdf.engine import run_tool

    source = tmp_path / "font.pdf"
    with pdf.open() as document:
        page = document.new_page()
        page.insert_font(fontname="OriginalFont", fontbuffer=pdf.Font("helv").buffer)
        page.insert_text((50, 90), "Original long text", fontname="OriginalFont", fontsize=18)
        document.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    item = next(item for item in focus.scene.items() if isinstance(item, ObjectItem) and item.obj.kind == "Text")
    item.setSelected(True)
    focus.text.setPlainText("Bold")
    focus.bold.setChecked(True)
    focus.close()
    output = tmp_path / "edited.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_edits": [workspace.edits[(str(source), 0)]]})
    with pdf.open(output) as document:
        spans = [span for block in document[0].get_text("dict")["blocks"] if block["type"] == 0
                 for line in block["lines"] for span in line["spans"]]
        assert [span["text"] for span in spans] == ["Bold"]
        assert spans[0]["flags"] & 16
    workspace.close()

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_embedded_font_preview_tracks_saved_text(tmp_path, application_session, rotation):
    from PySide6.QtGui import QImage, QPainter
    from deskpdf.editor import ObjectItem
    from deskpdf.engine import run_tool

    source = tmp_path / "font-preview.pdf"
    with pdf.open() as document:
        page = document.new_page(width=250, height=300)
        page.insert_font(fontname="OriginalFont", fontbuffer=pdf.Font("cjk").buffer)
        page.insert_text((40, 90), "Original words", fontname="OriginalFont", fontsize=18)
        page.set_rotation(rotation)
        document.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    item = next(item for item in focus.scene.items() if isinstance(item, ObjectItem) and item.obj.kind == "Text")
    assert focus.embedded_font_family(item.obj.source_font)
    item.setSelected(True)
    focus.text.setPlainText("Changed")
    focus.scene.clearSelection()
    bounds = focus.scene.sceneRect()
    preview = QImage(round(bounds.width()), round(bounds.height()), QImage.Format.Format_RGB32)
    preview.fill(Qt.GlobalColor.white)
    painter = QPainter(preview)
    focus.scene.render(painter)
    painter.end()
    focus.close()
    output = tmp_path / "output.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_edits": [workspace.edits[(str(source), 0)]]})
    with pdf.open(output) as document:
        rendered = document[0].get_pixmap(alpha=False)
        def dark_bounds(pixel):
            points = [(x, y) for y in range(rendered.height) for x in range(rendered.width)
                      if max(pixel(x, y)) < 180]
            assert points
            return (min(p[0] for p in points), min(p[1] for p in points),
                    max(p[0] for p in points), max(p[1] for p in points))
        on_screen = dark_bounds(lambda x, y: preview.pixelColor(x, y).getRgb()[:3])
        on_pdf = dark_bounds(rendered.pixel)
        assert all(abs(a - b) <= 4 for a, b in zip(on_screen, on_pdf)), (on_screen, on_pdf)
    workspace.close()

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_focus_redacts_text_and_picture_on_rotated_page(tmp_path, application_session, rotation):
    from PySide6.QtCore import QRectF
    from PIL import Image
    from deskpdf.editor import ObjectItem
    from deskpdf.engine import run_tool

    picture = tmp_path / "secret.png"
    Image.new("RGB", (100, 50), "red").save(picture)
    source = tmp_path / "source.pdf"
    with pdf.open() as document:
        page = document.new_page(width=300, height=300)
        page.insert_text((40, 90), "SECRET", fontsize=18)
        page.insert_image(pdf.Rect(40, 110, 140, 160), filename=str(picture))
        page.insert_text((40, 230), "KEEP", fontsize=18)
        page.set_rotation(rotation)
        document.save(source)
    workspace = MergeView()
    workspace.refresh([source], "")
    focus = PageFocus(workspace, 0)
    focus.add("Redaction")
    item = next(item for item in focus.scene.items() if isinstance(item, ObjectItem) and item.obj.kind == "Redaction")
    area = pdf.Rect(30, 65, 160, 170) * focus.document[0].rotation_matrix
    item.setPos(area.x0, area.y0)
    item.setRect(QRectF(0, 0, area.width, area.height))
    focus.capture()
    focus.close()
    output = tmp_path / "redacted.pdf"
    run_tool("merge", [source], output, {"merge_pages": ["1"], "merge_edits": [workspace.edits[(str(source), 0)]]})
    with pdf.open(output) as document:
        page = document[0]
        assert "SECRET" not in page.get_text()
        assert "KEEP" in page.get_text()
        pixmap = page.get_pixmap(alpha=False)
        point = pdf.Point(90, 135) * page.rotation_matrix
        assert max(pixmap.pixel(round(point.x), round(point.y))) < 20
        for image in page.get_images():
            extracted = document.extract_image(image[0])["image"]
            from io import BytesIO
            with Image.open(BytesIO(extracted)).convert("RGB") as pixels:
                assert all(not (red > 200 and green < 30 and blue < 30) for red, green, blue in pixels.getdata())
    workspace.close()


def test_redaction_area_does_not_apply_existing_annotations(tmp_path):
    from deskpdf.objects import Object, apply_objects
    with pdf.open() as document:
        page = document.new_page()
        page.insert_text((40, 90), "KEEP EXISTING", fontsize=18)
        annotation = page.add_redact_annot(pdf.Rect(35, 65, 200, 95))
        original_xref = annotation.xref
        with pytest.raises(ValueError, match="already has redaction annotations"):
            apply_objects(document, {0: [Object("Redaction", (250, 100, 300, 150))]})
        assert "KEEP EXISTING" in document[0].get_text()
        assert document[0].load_annot(original_xref) is not None


def test_redaction_area_refuses_overlapping_form_field():
    from deskpdf.objects import Object, apply_objects
    with pdf.open() as document:
        page = document.new_page()
        widget = pdf.Widget()
        widget.field_name = "private"
        widget.field_type = pdf.PDF_WIDGET_TYPE_TEXT
        widget.field_value = "sensitive"
        widget.rect = pdf.Rect(40, 40, 160, 80)
        page.add_widget(widget)
        with pytest.raises(ValueError, match="overlaps a form field"):
            apply_objects(document, {0: [Object("Redaction", (30, 30, 170, 90))]})
        assert next(document[0].widgets()).field_value == "sensitive"

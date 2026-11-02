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
                doc.xref_set_key(child, key, "null")
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

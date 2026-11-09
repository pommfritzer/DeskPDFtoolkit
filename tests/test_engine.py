import zipfile
from pathlib import Path

import pymupdf as pdf
import pytest
from PIL import Image

from deskpdf.engine import ToolError, parse_pages, run_tool


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.pdf"
    with pdf.open() as document:
        for index in range(3):
            page = document.new_page(width=400, height=500)
            page.insert_text((40, 60), f"Page {index + 1}: secret document")
        document.set_metadata({"author": "Private author"})
        document.save(path)
    return path


def execute(source, tmp_path, tool, options=None, suffix="pdf"):
    output = tmp_path / f"result-{tool}.{suffix}"
    run_tool(tool, [source], output, options or {})
    return output


def test_page_sequences():
    assert parse_pages("3-1,2", 3) == [2, 1, 0, 1]
    assert parse_pages("all", 3) == [0, 1, 2]
    for expression in ("0", "4", "-1", "abc", "1-2-3", "1,"):
        with pytest.raises(ToolError):
            parse_pages(expression, 3)


@pytest.mark.parametrize("tool,expression,expected", [("extract", "3,1", [3, 1]), ("reorder", "2,2,1", [2, 2, 1]), ("delete", "2", [1, 3])])
def test_page_content_order(source, tmp_path, tool, expression, expected):
    with pdf.open(execute(source, tmp_path, tool, {"pages": expression})) as result:
        assert len(result) == len(expected)
        assert [page.get_text().split(":")[0] for page in result] == [f"Page {number}" for number in expected]


def test_merge(source, tmp_path):
    output = tmp_path / "merged.pdf"
    run_tool("merge", [source, source], output, {})
    with pdf.open(output) as result:
        assert len(result) == 6


def test_merge_selected_pages_from_each_file(source, tmp_path):
    second = tmp_path / "second.pdf"
    with pdf.open() as document:
        for number in range(1, 4):
            document.new_page().insert_text((40, 60), f"Second {number}")
        document.save(second)
    output = tmp_path / "selected-merge.pdf"
    run_tool("merge", [source, second], output, {"merge_pages": ["3,1,1", "2-1"]})
    with pdf.open(output) as result:
        assert [page.get_text().strip() for page in result] == [
            "Page 3: secret document", "Page 1: secret document", "Page 1: secret document",
            "Second 2", "Second 1",
        ]


def test_invalid_merge_selection_preserves_destination(source, tmp_path):
    output = tmp_path / "merged.pdf"
    output.write_bytes(b"existing destination")
    with pytest.raises(ToolError, match="source.pdf: Page numbers"):
        run_tool("merge", [source, source], output, {"merge_pages": ["1", "4"]})
    assert output.read_bytes() == b"existing destination"
    with pytest.raises(ToolError, match="each input PDF"):
        run_tool("merge", [source, source], output, {"merge_pages": ["1"]})


def test_original_and_failure_are_safe(source, tmp_path):
    original = source.read_bytes()
    with pytest.raises(ToolError):
        run_tool("rotate", [source], source, {})
    output = tmp_path / "keep.pdf"
    output.write_bytes(b"existing output")
    with pytest.raises(ToolError):
        run_tool("delete", [source], output, {"pages": "all"})
    assert source.read_bytes() == original
    assert output.read_bytes() == b"existing output"
    assert not list(tmp_path.glob(".deskpdf-*"))


def test_rotation_and_crop(source, tmp_path):
    with pdf.open(execute(source, tmp_path, "rotate", {"pages": "2", "rotation": "90"})) as result:
        assert [page.rotation for page in result] == [0, 90, 0]
    with pdf.open(execute(source, tmp_path, "crop", {"margin": "20"})) as result:
        assert result[0].rect.width == 360


def test_redaction_removes_content(source, tmp_path):
    output = execute(source, tmp_path, "redact", {"text": "secret"})
    with pdf.open(output) as result:
        assert all("secret" not in page.get_text() for page in result)
        assert all("document" in page.get_text() for page in result)


@pytest.mark.parametrize("tool", ["compress", "flatten", "clean", "highlight", "text_overlay", "watermark", "number"])
def test_edit_tools(source, tmp_path, tool):
    with pdf.open(execute(source, tmp_path, tool, {"text": "document"})) as result:
        assert len(result) == 3
        if tool == "clean":
            assert not result.metadata.get("author")
        if tool == "highlight":
            assert len(list(result[0].annots())) == 1
        if tool == "text_overlay":
            assert result[0].get_text().count("document") == 2


def test_password_lifecycle(source, tmp_path):
    protected = execute(source, tmp_path, "protect", {"new_password": "password-123"})
    with pdf.open(protected) as result:
        assert result.needs_pass
        assert result.authenticate("password-123")
    with pytest.raises(ToolError):
        execute(protected, tmp_path, "unlock", {"password": "wrong"})
    compressed = execute(protected, tmp_path, "compress", {"password": "password-123"})
    with pdf.open(compressed) as result:
        assert result.needs_pass
    unlocked = execute(protected, tmp_path, "unlock", {"password": "password-123"})
    with pdf.open(unlocked) as result:
        assert not result.needs_pass
        assert len(result) == 3


@pytest.mark.parametrize("tool,extension", [("split", "pdf"), ("pdf_to_png", "png")])
def test_archive(source, tmp_path, tool, extension):
    output = execute(source, tmp_path, tool, {"pages": "3,1"}, "zip")
    with zipfile.ZipFile(output) as archive:
        assert len(archive.namelist()) == 2
        assert archive.namelist()[0].endswith(f"page-3.{extension}")
        if extension == "pdf":
            with pdf.open(stream=archive.read(archive.namelist()[0])) as page:
                assert "Page 3" in page[0].get_text()


@pytest.mark.parametrize("tool,suffix", [("text", "txt"), ("word", "docx"), ("powerpoint", "pptx")])
def test_exports(source, tmp_path, tool, suffix):
    output = execute(source, tmp_path, tool, {"pages": "2"}, suffix)
    if tool == "text":
        assert "Page 2" in output.read_text()
        assert "Page 1" not in output.read_text()
    elif tool == "word":
        from docx import Document
        assert "Page 2" in Document(output).paragraphs[0].text
    else:
        from pptx import Presentation
        assert len(Presentation(output).slides) == 1


def test_images_and_signature(source, tmp_path):
    image = tmp_path / "signature.png"
    Image.new("RGB", (200, 60), "green").save(image)
    output = tmp_path / "images.pdf"
    run_tool("images_to_pdf", [image, image], output, {})
    with pdf.open(output) as result:
        assert len(result) == 2
        assert result[0].get_images()
    with pdf.open(execute(source, tmp_path, "sign", {"signature": str(image)})) as result:
        assert result[0].get_images()


def test_fill_and_flatten(source, tmp_path):
    form = tmp_path / "form.pdf"
    with pdf.open(source) as document:
        field = pdf.Widget()
        field.field_name = "Name"
        field.field_type = pdf.PDF_WIDGET_TYPE_TEXT
        field.rect = pdf.Rect(40, 100, 200, 130)
        document[0].add_widget(field)
        document.save(form)
    filled = execute(form, tmp_path, "forms", {"form_values": "Name=Alex Example"})
    with pdf.open(filled) as result:
        assert list(result[0].widgets())[0].field_value == "Alex Example"
    with pdf.open(execute(filled, tmp_path, "flatten")) as result:
        assert not list(result[0].widgets())
        assert "Alex Example" in result[0].get_text()


def test_excel_table(tmp_path):
    source = tmp_path / "table.pdf"
    with pdf.open() as document:
        page = document.new_page()
        for x in (40, 180, 320):
            page.draw_line((x, 40), (x, 130))
        for y in (40, 70, 100, 130):
            page.draw_line((40, y), (320, y))
        for row in range(3):
            page.insert_text((50, 60 + row * 30), "=SUM(A1:A2)" if row == 1 else f"Item {row}")
            page.insert_text((190, 60 + row * 30), str(row))
        document.save(source)
    from openpyxl import load_workbook
    output = execute(source, tmp_path, "excel", suffix="xlsx")
    workbook = load_workbook(output)
    assert workbook.active["A2"].data_type == "s"
    assert workbook.active["A2"].value.startswith("=SUM")


@pytest.mark.parametrize("tool,options", [("rotate", {"rotation": "91"}), ("crop", {"margin": "999"}), ("redact", {"text": "missing"}), ("text_overlay", {"x": "nan", "text": "test"}), ("protect", {}), ("forms", {"form_values": "Missing=value"})])
def test_invalid_options(source, tmp_path, tool, options):
    with pytest.raises(ToolError):
        execute(source, tmp_path, tool, options)

def test_ocr_preserves_original_pdf_and_avoids_duplicate_text(tmp_path, monkeypatch):
    from types import SimpleNamespace
    source = tmp_path / "input.pdf"
    scan = Image.new("RGB", (300, 120), "white")
    from PIL import ImageDraw
    ImageDraw.Draw(scan).rectangle((30, 30, 100, 75), fill="black")
    image = tmp_path / "scan.png"
    scan.save(image)
    with pdf.open() as doc:
        for rotation in (0, 90, 180, 270):
            page = doc.new_page(width=400, height=400)
            page.insert_text((45, 50), "Native", fontsize=16)
            page.insert_image(pdf.Rect(40, 90, 340, 210), filename=str(image))
            page.insert_link({"kind": pdf.LINK_URI, "from": pdf.Rect(40, 250, 180, 275), "uri": "https://example.com"})
            page.add_text_annot((250, 250), "Keep this note")
            widget = pdf.Widget()
            widget.field_name = f"field{rotation}"
            widget.field_type = pdf.PDF_WIDGET_TYPE_TEXT
            widget.rect = pdf.Rect(40, 300, 180, 325)
            widget.field_value = "Keep value"
            page.add_widget(widget)
            page.set_cropbox(pdf.Rect(20, 20, 380, 380))
            page.set_rotation(rotation)
        doc.set_metadata({"author": "Test author"})
        doc.save(source)
    calls = []
    def fake_tesseract(command, **kwargs):
        calls.append(command)
        assert command[-3:] == ["-c", "textonly_pdf=1", "pdf"]
        with Image.open(command[1]) as image:
            assert image.getpixel((70, 45)) == (255, 255, 255)
            width, height = image.size
        with pdf.open() as recognized:
            page = recognized.new_page(width=width, height=height)
            page.insert_text((100, 250), "SCANNED", fontsize=28, render_mode=3)
            recognized.save(command[2] + ".pdf")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr("deskpdf.engine.executable", lambda *args: "tesseract")
    monkeypatch.setattr("deskpdf.engine.subprocess.run", fake_tesseract)
    output = tmp_path / "recognized.pdf"
    run_tool("ocr", [source], output, {"dpi": 144})
    assert len(calls) == 4
    with pdf.open(source) as original, pdf.open(output) as result:
        assert result.metadata["author"] == "Test author"
        for rotation, before, after in zip((0, 90, 180, 270), original, result):
            assert after.rotation == rotation
            assert after.cropbox == before.cropbox
            assert after.get_pixmap(annots=False).samples == before.get_pixmap(annots=False).samples
            assert after.get_text().count("Native") == 1
            assert "SCANNED" in after.get_text()
            scanned = next(word for word in after.get_text("words") if word[4] == "SCANNED")
            assert 20 <= scanned[0] < 320 and 70 <= scanned[1] < 190
            assert len(after.get_links()) == 1
            assert [widget.field_value for widget in after.widgets()] == ["Keep value"]
            assert [annotation.info["content"] for annotation in after.annots()] == ["Keep this note"]


def test_ocr_failure_does_not_overwrite_existing_destination(source, tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr("deskpdf.engine.executable", lambda *args: "tesseract")
    monkeypatch.setattr("deskpdf.engine.subprocess.run", lambda *args, **kwargs: SimpleNamespace(returncode=1))
    output = tmp_path / "existing.pdf"
    output.write_bytes(b"keep me")
    with pytest.raises(ToolError, match="Tesseract failed"):
        run_tool("ocr", [source], output, {})
    assert output.read_bytes() == b"keep me"
    assert not list(tmp_path.glob(".deskpdf-*"))

def test_ocr_keeps_input_encryption(tmp_path, monkeypatch):
    from types import SimpleNamespace
    source = tmp_path / "protected.pdf"
    with pdf.open() as doc:
        doc.new_page().insert_text((40, 60), "Readable")
        doc.save(source, encryption=pdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="secret")
    def fake_tesseract(command, **kwargs):
        with pdf.open() as recognized:
            page = recognized.new_page()
            page.insert_text((40, 100), "OCR", render_mode=3)
            recognized.save(command[2] + ".pdf")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr("deskpdf.engine.executable", lambda *args: "tesseract")
    monkeypatch.setattr("deskpdf.engine.subprocess.run", fake_tesseract)
    output = tmp_path / "output.pdf"
    run_tool("ocr", [source], output, {"password": "secret"})
    with pdf.open(output) as doc:
        assert doc.needs_pass
        assert doc.authenticate("secret")
        assert "Readable" in doc[0].get_text()
        assert "OCR" in doc[0].get_text()


def test_ocr_with_real_tesseract(tmp_path, monkeypatch):
    import os
    from PIL import ImageDraw, ImageFont
    executable = os.environ.get("PDFTOOLKIT26_TEST_TESSERACT")
    if not executable:
        pytest.skip("Set PDFTOOLKIT26_TEST_TESSERACT to test the real OCR engine")
    image = Image.new("RGB", (900, 350), "white")
    candidates = [Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/System/Library/Fonts/Supplemental/Arial.ttf")]
    font_path = next((path for path in candidates if path.is_file()), None)
    font = ImageFont.truetype(str(font_path), 72) if font_path else ImageFont.load_default(size=72)
    ImageDraw.Draw(image).text((65, 100), "SCAN SAMPLE 2026", font=font, fill="black")
    image_path = tmp_path / "scan.png"
    image.save(image_path)
    source = tmp_path / "scan.pdf"
    with pdf.open() as doc:
        page = doc.new_page(width=600, height=500)
        page.insert_image(pdf.Rect(40, 100, 490, 275), filename=str(image_path))
        page.set_cropbox(pdf.Rect(20, 20, 570, 470))
        page.set_rotation(90)
        doc.save(source)
    monkeypatch.setattr("deskpdf.engine.executable", lambda *args: executable)
    output = tmp_path / "recognized.pdf"
    run_tool("ocr", [source], output, {"dpi": 144})
    with pdf.open(source) as original, pdf.open(output) as result:
        assert result[0].rotation == 90
        assert "SCAN SAMPLE 2026" in result[0].get_text()
        assert result[0].get_pixmap().samples == original[0].get_pixmap().samples

def test_ocr_only_recognizes_selected_pages(source, tmp_path, monkeypatch):
    from types import SimpleNamespace
    calls = []
    def fake_tesseract(command, **kwargs):
        calls.append(command)
        with pdf.open() as recognized:
            recognized.new_page(width=400, height=500).insert_text((40, 100), "SCANNED", render_mode=3)
            recognized.save(command[2] + ".pdf")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr("deskpdf.engine.executable", lambda *args: "tesseract")
    monkeypatch.setattr("deskpdf.engine.subprocess.run", fake_tesseract)
    output = tmp_path / "selected.pdf"
    run_tool("ocr", [source], output, {"pages": "2"})
    assert len(calls) == 1
    with pdf.open(output) as doc:
        assert ["SCANNED" in page.get_text() for page in doc] == [False, True, False]

def test_optional_tool_locations_cover_supported_platforms(monkeypatch):
    from deskpdf.engine import executable_candidates
    monkeypatch.setenv("LOCALAPPDATA", "C:/Users/example/AppData/Local")
    assert any("Tesseract-OCR" in path for path in executable_candidates("tesseract", "win32"))
    assert "/opt/homebrew/bin/tesseract" in executable_candidates("tesseract", "darwin")
    assert "/Applications/LibreOffice.app/Contents/MacOS/soffice" in executable_candidates("soffice", "darwin")
    assert "/usr/bin/tesseract" in executable_candidates("tesseract", "linux")
    assert "/usr/bin/soffice" in executable_candidates("soffice", "linux")

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_text_overlay_fits_and_rejects_overflow_in_visible_coordinates(tmp_path, rotation):
    source = tmp_path / "rotated.pdf"
    with pdf.open() as document:
        page = document.new_page(width=300, height=400)
        page.set_cropbox(pdf.Rect(20, 30, 280, 370))
        page.set_rotation(rotation)
        document.save(source)
    output = tmp_path / "output.pdf"
    run_tool("text_overlay", [source], output, {"text": "Hello", "size": "20", "x": "40", "y": "80"})
    with pdf.open(output) as document:
        page = document[0]
        box = page.search_for("Hello")[0] * page.rotation_matrix
        assert abs(box.x0 - 40) < .1
        assert abs(box.y0 - 58.5) < .2
        width = page.rect.width
    with pytest.raises(ToolError, match="extends beyond"):
        run_tool("text_overlay", [source], tmp_path / "overflow.pdf", {"text": "Hello", "size": "20", "x": str(width - 10), "y": "80"})
    assert not (tmp_path / "overflow.pdf").exists()

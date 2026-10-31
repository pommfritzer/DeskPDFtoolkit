import zipfile

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

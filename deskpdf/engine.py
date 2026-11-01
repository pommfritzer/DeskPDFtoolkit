import io
import os
import shutil
import subprocess
import tempfile
import zipfile
from contextlib import ExitStack
from pathlib import Path

import pymupdf as pdf
from PIL import Image, ImageOps, ImageSequence


class ToolError(ValueError):
    pass


def parse_pages(expression: str, count: int) -> list[int]:
    if not expression.strip() or expression.strip().lower() == "all":
        return list(range(count))
    result = []
    try:
        for part in expression.split(","):
            bounds = [int(value.strip()) for value in part.split("-")]
            if len(bounds) == 1:
                result.append(bounds[0] - 1)
            elif len(bounds) == 2:
                start, end = bounds
                result.extend(range(start - 1, end if end >= start else end - 2, 1 if end >= start else -1))
            else:
                raise ValueError
    except ValueError:
        raise ToolError("Use page numbers such as 1, 3-5, 8. Use all for every page.") from None
    if not result or any(index < 0 or index >= count for index in result):
        raise ToolError(f"Page numbers must be between 1 and {count}.")
    return result


def open_document(path: Path, password: str = ""):
    document = pdf.open(path)
    if document.needs_pass and not document.authenticate(password):
        document.close()
        raise ToolError(f"Enter the correct opening password for {path.name}.")
    if document.is_pdf and not document.permissions & pdf.PDF_PERM_MODIFY:
        document.close()
        raise ToolError("This document restricts editing. Open an authorized, unrestricted copy.")
    return document


def executable(name: str, candidates: list[str]) -> str:
    found = shutil.which(name)
    if found:
        return found
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    raise ToolError(f"Install {name} locally and restart PDFtoolkit26 to use this tool.")


def numeric(options, name, default, minimum, maximum):
    try:
        value = float(options.get(name, default))
        if not minimum <= value <= maximum:
            raise ValueError
        return value
    except (TypeError, ValueError):
        raise ToolError(f"{name.capitalize()} must be between {minimum:g} and {maximum:g}.") from None


def run_tool(tool: str, paths: list[Path], destination: Path, options: dict) -> Path:
    if not paths:
        raise ToolError("Choose at least one file first.")
    paths = [Path(path).resolve() for path in paths]
    destination = Path(destination).resolve()
    if destination in paths:
        raise ToolError("Save to a new file to keep your original safe.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Stage beside the destination so the final replacement stays atomic on the same volume.
    with tempfile.TemporaryDirectory(prefix=".deskpdf-", dir=destination.parent) as folder:
        staged = Path(folder) / destination.name
        _process(tool, paths, staged, options)
        if not staged.is_file():
            raise ToolError("No output was produced.")
        os.replace(staged, destination)
    return destination


def _process(tool, paths, target, options):
    password = options.get("password", "")
    with ExitStack() as stack:
        if tool == "office":
            converter = executable("soffice", [r"C:\Program Files\LibreOffice\program\soffice.exe"])
            profile = target.parent / "libreoffice-profile"
            result = subprocess.run([converter, f"-env:UserInstallation={profile.as_uri()}", "--headless", "--convert-to", "pdf", "--outdir", str(target.parent), str(paths[0])], capture_output=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            converted = target.parent / (paths[0].stem + ".pdf")
            if result.returncode or not converted.exists():
                raise ToolError("LibreOffice could not convert this file. Check that its format is supported.")
            if converted != target:
                converted.replace(target)
            return
        if tool == "images_to_pdf":
            output = stack.enter_context(pdf.open())
            for path in paths:
                with Image.open(path) as image:
                    for frame in ImageSequence.Iterator(image):
                        upright = ImageOps.exif_transpose(frame).convert("RGB")
                        data = io.BytesIO()
                        upright.save(data, format="PNG")
                        width, height = upright.size
                        page = output.new_page(width=width * .75, height=height * .75)
                        page.insert_image(page.rect, stream=data.getvalue())
            output.save(target, garbage=4, deflate=True)
            return
        document = stack.enter_context(open_document(paths[0], password))
        if not document.is_pdf:
            raise ToolError("Choose a PDF document for this tool.")
        pages = parse_pages(options.get("pages", "all"), len(document))
        unique_pages = list(dict.fromkeys(pages))
        if tool == "merge":
            selections = options.get("merge_pages", ["all"] * len(paths))
            if not isinstance(selections, list) or len(selections) != len(paths):
                raise ToolError("Choose a page selection for each input PDF.")

            def select_source_pages(source, expression, path):
                try:
                    source.select(parse_pages(expression, len(source)))
                except ToolError as error:
                    raise ToolError(f"{path.name}: {error}") from None

            select_source_pages(document, selections[0], paths[0])
            for path, expression in zip(paths[1:], selections[1:]):
                with open_document(path, password) as source:
                    select_source_pages(source, expression, path)
                    document.insert_pdf(source)
        elif tool in {"extract", "reorder"}:
            document.select(pages)
        elif tool == "delete":
            keep = [index for index in range(len(document)) if index not in pages]
            if not keep:
                raise ToolError("Keep at least one page in the document.")
            document.select(keep)
        elif tool in {"split", "pdf_to_png"}:
            dpi = numeric(options, "dpi", 144, 72, 300)
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                for sequence, index in enumerate(pages, 1):
                    name = f"{paths[0].stem}-{sequence:03d}-page-{index + 1}"
                    if tool == "split":
                        with pdf.open() as single:
                            single.insert_pdf(document, from_page=index, to_page=index)
                            archive.writestr(name + ".pdf", single.tobytes(garbage=4, deflate=True))
                    else:
                        archive.writestr(name + ".png", document[index].get_pixmap(dpi=int(dpi)).tobytes("png"))
            return
        elif tool in {"text", "word", "excel", "powerpoint"}:
            _export(document, pages, tool, target)
            return
        elif tool == "ocr":
            tesseract = executable("tesseract", [r"C:\Program Files\Tesseract-OCR\tesseract.exe"])
            dpi = int(numeric(options, "dpi", 144, 72, 300))
            output = stack.enter_context(pdf.open())
            for index, page in enumerate(document):
                base = target.parent / f"ocr-{index}"
                page.get_pixmap(dpi=dpi).save(str(base) + ".png")
                result = subprocess.run([tesseract, str(base) + ".png", str(base), "-l", options.get("language", "eng"), "pdf"], capture_output=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if result.returncode:
                    raise ToolError("Tesseract failed. Check that the requested language data is installed.")
                with pdf.open(str(base) + ".pdf") as recognized:
                    output.insert_pdf(recognized)
            output.save(target, garbage=4, deflate=True)
            return
        elif tool == "flatten":
            document.bake()
        elif tool == "clean":
            document.set_metadata({})
            document.del_xml_metadata()
            for name in document.embfile_names():
                document.embfile_del(name)
        elif tool == "forms":
            values = {}
            for line in options.get("form_values", "").splitlines():
                if line.strip():
                    if "=" not in line:
                        raise ToolError("Enter one field per line: field name=value")
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip()
            available = {widget.field_name for page in document for widget in page.widgets()}
            if not values or values.keys() - available:
                raise ToolError("Use existing field names. Available: " + (", ".join(sorted(available)) or "no fillable fields"))
            for page in document:
                for widget in page.widgets():
                    if widget.field_name in values:
                        widget.field_value = values[widget.field_name]
                        widget.update()
        elif tool in {"rotate", "crop", "text_overlay", "watermark", "number", "redact", "highlight", "sign"}:
            matches = 0
            for index in unique_pages:
                page = document[index]
                rect = page.rect
                if tool == "rotate":
                    rotation = int(numeric(options, "rotation", 90, 90, 270))
                    if rotation not in (90, 180, 270):
                        raise ToolError("Choose 90, 180 or 270 degrees.")
                    page.set_rotation((page.rotation + rotation) % 360)
                elif tool == "crop":
                    margin = numeric(options, "margin", 18, 0, 1000)
                    box = page.cropbox + (margin, margin, -margin, -margin)
                    if box.is_empty:
                        raise ToolError("That margin would remove the whole page.")
                    page.set_cropbox(box)
                elif tool in {"redact", "highlight"}:
                    text_value = options.get("text", "").strip()
                    if not text_value:
                        raise ToolError("Enter the text to find.")
                    hits = page.search_for(text_value)
                    matches += len(hits)
                    for hit in hits:
                        if tool == "redact":
                            page.add_redact_annot(hit, fill=(0, 0, 0))
                        else:
                            page.add_highlight_annot(hit)
                    if tool == "redact":
                        page.apply_redactions()
                elif tool == "number":
                    page.insert_text((rect.width / 2, rect.height - 22), str(index + 1), fontsize=10, color=(.35, .38, .42))
                elif tool == "sign":
                    signature = Path(options.get("signature", ""))
                    if not signature.is_file():
                        raise ToolError("Choose a signature image first.")
                    x = numeric(options, "x", 48, 0, rect.width)
                    y = numeric(options, "y", 72, 0, rect.height)
                    width = numeric(options, "width", 140, 10, rect.width)
                    with Image.open(signature) as image:
                        height = width * image.height / image.width
                    box = pdf.Rect(x, y, x + width, y + height)
                    if not rect.contains(box):
                        raise ToolError("The signature extends beyond this page. Move it or reduce its width.")
                    page.insert_image(box * page.derotation_matrix, filename=str(signature))
                else:
                    text_value = options.get("text", "").strip()
                    if not text_value:
                        raise ToolError("Enter some text first.")
                    size = numeric(options, "size", 24 if tool == "watermark" else 12, 6, 144)
                    point = pdf.Point(rect.width / 4, rect.height / 2) if tool == "watermark" else pdf.Point(numeric(options, "x", 48, 0, rect.width), numeric(options, "y", 72, size, rect.height))
                    point = point * page.derotation_matrix
                    if tool == "text_overlay" and point.x + pdf.get_text_length(text_value, fontsize=size) > page.cropbox.width:
                        raise ToolError("The text extends beyond this page. Reduce its size or move it left.")
                    page.insert_text(point, text_value, fontsize=size, color=(.15, .19, .25), fill_opacity=.18 if tool == "watermark" else 1, rotate=page.rotation)
            if tool in {"redact", "highlight"} and not matches:
                raise ToolError("No matching text found. Scanned documents may need text recognition first.")
        elif tool not in {"compress", "protect", "unlock"}:
            raise ToolError("Unknown tool.")
        save_options = dict(garbage=4, deflate=True, use_objstms=1, encryption=pdf.PDF_ENCRYPT_NONE if tool == "unlock" else pdf.PDF_ENCRYPT_KEEP)
        if tool == "protect":
            new_password = options.get("new_password", "")
            if not new_password:
                raise ToolError("Enter a new opening password.")
            save_options.update(encryption=pdf.PDF_ENCRYPT_AES_256, owner_pw=new_password, user_pw=new_password)
        document.save(target, **save_options)


def _export(document, pages, tool, target):
    if tool == "text":
        target.write_text("\n\f\n".join(document[index].get_text(sort=True) for index in pages), encoding="utf-8")
    elif tool == "word":
        from docx import Document
        output = Document()
        for sequence, index in enumerate(pages):
            if sequence:
                output.add_page_break()
            output.add_paragraph(document[index].get_text(sort=True))
        output.save(target)
    elif tool == "excel":
        from openpyxl import Workbook
        output = Workbook()
        output.remove(output.active)
        for index in pages:
            for number, table in enumerate(document[index].find_tables().tables, 1):
                sheet = output.create_sheet(f"Page {index + 1} table {number}")
                for row in table.extract():
                    sheet.append(row)
                    for cell in sheet[sheet.max_row]:
                        if isinstance(cell.value, str):
                            cell.data_type = "s"
        if not output.worksheets:
            raise ToolError("No tables detected. Scanned pages may need text recognition first.")
        output.save(target)
    else:
        from pptx import Presentation
        from pptx.util import Inches
        output = Presentation()
        first = document[pages[0]].rect
        output.slide_width = Inches(10)
        output.slide_height = Inches(10 * first.height / first.width)
        for index in pages:
            page = document[index]
            slide = output.slides.add_slide(output.slide_layouts[6])
            scale = min(output.slide_width / page.rect.width, output.slide_height / page.rect.height)
            width, height = int(page.rect.width * scale), int(page.rect.height * scale)
            slide.shapes.add_picture(io.BytesIO(page.get_pixmap(dpi=144).tobytes("png")), (output.slide_width - width) // 2, (output.slide_height - height) // 2, width, height)
        output.save(target)

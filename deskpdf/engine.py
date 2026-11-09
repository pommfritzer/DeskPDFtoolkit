import io
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from contextlib import ExitStack
from functools import lru_cache
from pathlib import Path

import pymupdf as pdf
from PIL import Image, ImageDraw, ImageOps, ImageSequence


class ToolError(ValueError):
    pass


@lru_cache(maxsize=1)
def unicode_overlay_font():
    return pdf.Font("cjk")


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
    # Rechecking needs_pass after authentication can reset MuPDF's encryption state.
    needs_password = document.needs_pass
    authenticated = document.authenticate(password) if needs_password or (password and document.is_pdf) else 0
    if needs_password and not authenticated:
        document.close()
        raise ToolError(f"Enter the correct opening password for {path.name}.")
    if document.is_pdf and not document.permissions & pdf.PDF_PERM_MODIFY and not authenticated & 4:
        document.close()
        raise ToolError("This document restricts editing. Open it with the owner password.")
    return document


def executable(name: str, candidates: list[str]) -> str:
    found = shutil.which(name)
    if found:
        return found
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    raise ToolError(f"Install {name} locally and restart PDFtoolkit26 to use this tool.")


def executable_candidates(name: str, platform: str | None = None) -> list[str]:
    platform = platform or sys.platform
    if platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"
        return {
            "tesseract": [str(local / "Tesseract-OCR" / "tesseract.exe"), r"C:\Program Files\Tesseract-OCR\tesseract.exe"],
            "soffice": [r"C:\Program Files\LibreOffice\program\soffice.exe"],
        }.get(name, [])
    if platform == "darwin":
        return {
            "tesseract": ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"],
            "soffice": ["/Applications/LibreOffice.app/Contents/MacOS/soffice"],
        }.get(name, [])
    return {"tesseract": ["/usr/bin/tesseract", "/usr/local/bin/tesseract"],
            "soffice": ["/usr/bin/soffice", "/usr/local/bin/soffice"]}.get(name, [])


def numeric(options, name, default, minimum, maximum):
    try:
        value = float(options.get(name, default))
        if not minimum <= value <= maximum:
            raise ValueError
        return value
    except (TypeError, ValueError):
        raise ToolError(f"{name.capitalize()} must be between {minimum:g} and {maximum:g}.") from None


def hidden_form_paths(document):
    mupdf = pdf.mupdf
    catalog = mupdf.pdf_load_object(pdf._as_pdf_document(document), document.pdf_catalog())
    form = mupdf.pdf_dict_gets(catalog, "AcroForm")
    roots = mupdf.pdf_dict_gets(form, "Fields")
    paths = []

    def visit(field, ancestors):
        xref = mupdf.pdf_to_num(field)
        if not xref:
            raise ToolError("This PDF contains a direct form-field dictionary that cannot be safely rearranged.")
        if xref in ancestors:
            raise ToolError("This PDF contains a circular form-field hierarchy.")
        path = (*ancestors, xref)
        kids = mupdf.pdf_dict_gets(field, "Kids")
        if mupdf.pdf_array_len(kids):
            for index in range(mupdf.pdf_array_len(kids)):
                visit(mupdf.pdf_array_get(kids, index), path)
        elif mupdf.pdf_to_name(mupdf.pdf_dict_gets(field, "Subtype")) != "Widget":
            paths.append(path)

    for index in range(mupdf.pdf_array_len(roots)):
        visit(mupdf.pdf_array_get(roots, index), ())
    return paths


def select_pages(document, pages):
    catalog = document.pdf_catalog()
    acroform_type, acroform = document.xref_get_key(catalog, "AcroForm")
    hidden_paths = hidden_form_paths(document)
    document.select(pages)
    roots = set()
    children = {}
    for page in document:
        for widget in page.widgets() or []:
            child = widget.xref
            visited = set()
            while True:
                if child in visited:
                    raise ToolError("This PDF contains a circular form-field hierarchy.")
                visited.add(child)
                kind, value = document.xref_get_key(child, "Parent")
                if kind != "xref":
                    roots.add(child)
                    break
                parent = int(value.split()[0])
                children.setdefault(parent, set()).add(child)
                child = parent
    for path in hidden_paths:
        roots.add(path[0])
        for parent, child in zip(path, path[1:]):
            children.setdefault(parent, set()).add(child)
    if acroform_type == "null" and not roots:
        return
    document.xref_set_key(catalog, "AcroForm", acroform if acroform_type in ("dict", "xref") else "<<>>")
    for parent, kids in children.items():
        document.xref_set_key(parent, "Kids", "[" + " ".join(f"{kid} 0 R" for kid in sorted(kids)) + "]")
    fields = "[" + " ".join(f"{root} 0 R" for root in sorted(roots)) + "]"
    if acroform_type == "xref":
        document.xref_set_key(int(acroform.split()[0]), "Fields", fields)
    else:
        document.xref_set_key(catalog, "AcroForm/Fields", fields)


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


def merge_grouped(document, paths, selections, crops, edits, options, password):
    from deskpdf.objects import apply_objects, apply_related_forms

    sizes = {paths[0]: len(document)}
    for path in dict.fromkeys(paths[1:]):
        if path not in sizes:
            with open_document(path, password) as source:
                sizes[path] = len(source)
    pages = []
    actions = {path: {} for path in sizes}
    for path, expression, crop, page_edits in zip(paths, selections, crops, edits):
        try:
            indexes = parse_pages(expression, sizes[path])
        except ToolError as error:
            raise ToolError(f"{path.name}: {error}") from None
        for position, index in enumerate(indexes):
            action = (crop if position == 0 else None,
                      [obj for obj in page_edits if obj.kind != "Form"] if position == 0 else [])
            previous = actions[path].get(index)
            if previous is not None and previous != action:
                return False
            actions[path][index] = action
            pages.append((path, index))

    all_forms = options.get("merge_form_edits")
    if all_forms is None:
        all_forms = [(str(path), parse_pages(expression, sizes[path])[0], obj)
                     for path, expression, entries in zip(paths, selections, edits)
                     for obj in entries if obj.kind == "Form"]

    def prepare(source, path):
        related = [(page, obj) for source_path, page, obj in all_forms if Path(source_path).resolve() == path]
        apply_related_forms(source, related)
        for index, (crop, objects) in actions[path].items():
            if crop is not None:
                source[index].set_cropbox(pdf.Rect(crop))
            if objects:
                apply_objects(source, {index: objects})

    prepare(document, paths[0])
    page_map = {(paths[0], index): index for index in actions[paths[0]]}
    for path in dict.fromkeys(paths[1:]):
        if path == paths[0]:
            continue
        with open_document(path, password) as source:
            prepare(source, path)
            indexes = sorted(actions[path])
            connected = any(source[index].first_widget or any(link["kind"] == pdf.LINK_GOTO for link in source[index].get_links()) for index in indexes)
            ranges = []
            for index in indexes:
                if ranges and (connected or index == ranges[-1][1] + 1):
                    ranges[-1] = (ranges[-1][0], index)
                else:
                    ranges.append((index, index))
            for sequence, (first, last) in enumerate(ranges):
                offset = len(document)
                document.insert_pdf(source, from_page=first, to_page=last, final=int(sequence == len(ranges) - 1))
                for index in indexes:
                    if first <= index <= last:
                        page_map[(path, index)] = offset + index - first
    select_pages(document, [page_map[(path, index)] for path, index in pages])
    return True


def _process(tool, paths, target, options):
    password = options.get("password", "")
    with ExitStack() as stack:
        if tool == "office":
            converter = executable("soffice", executable_candidates("soffice"))
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
                    select_pages(source, parse_pages(expression, len(source)))
                except ToolError as error:
                    raise ToolError(f"{path.name}: {error}") from None

            def selected_indexes(source, expression, path):
                try:
                    return parse_pages(expression, len(source))
                except ToolError as error:
                    raise ToolError(f"{path.name}: {error}") from None

            crops = options.get("merge_crops", [None] * len(paths))
            edits = options.get("merge_edits", [[] for _ in paths])
            if not isinstance(edits, list) or len(edits) != len(paths):
                raise ToolError("Page edits do not match the selected input pages.")
            if not isinstance(crops, list) or len(crops) != len(paths):
                raise ToolError("Page crops do not match the selected input pages.")
            if merge_grouped(document, paths, selections, crops, edits, options, password):
                document.save(target, garbage=4, deflate=True, use_objstms=1, encryption=pdf.PDF_ENCRYPT_KEEP)
                return
            from deskpdf.objects import apply_objects, apply_related_forms

            def apply_source_forms(source, path):
                all_forms = options.get("merge_form_edits")
                if all_forms is None:
                    related = [(parse_pages(expression, len(source))[0], obj)
                               for source_path, expression, entries in zip(paths, selections, edits) if source_path == path
                               for obj in entries if obj.kind == "Form"]
                else:
                    related = [(page, obj) for source_path, page, obj in all_forms if Path(source_path).resolve() == path]
                apply_related_forms(source, related)

            apply_source_forms(document, paths[0])
            if crops[0] is not None:
                document[parse_pages(selections[0], len(document))[0]].set_cropbox(pdf.Rect(crops[0]))
            if edits[0]:
                apply_objects(document, {parse_pages(selections[0], len(document))[0]: [obj for obj in edits[0] if obj.kind != "Form"]})
            select_source_pages(document, selections[0], paths[0])
            for source_index, (path, expression) in enumerate(zip(paths[1:], selections[1:]), 1):
                with open_document(path, password) as source:
                    apply_source_forms(source, path)
                    if crops[source_index] is not None:
                        source[parse_pages(expression, len(source))[0]].set_cropbox(pdf.Rect(crops[source_index]))
                    if edits[source_index]:
                        apply_objects(source, {parse_pages(expression, len(source))[0]: [obj for obj in edits[source_index] if obj.kind != "Form"]})
                    indexes = selected_indexes(source, expression, path)
                    if len(indexes) == 1 or any(source[index].first_widget for index in indexes):
                        for index in indexes:
                            document.insert_pdf(source, from_page=index, to_page=index)
                    else:
                        select_source_pages(source, expression, path)
                        document.insert_pdf(source)
        elif tool in {"extract", "reorder"}:
            select_pages(document, pages)
        elif tool == "delete":
            keep = [index for index in range(len(document)) if index not in pages]
            if not keep:
                raise ToolError("Keep at least one page in the document.")
            select_pages(document, keep)
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
            tesseract = executable("tesseract", executable_candidates("tesseract"))
            dpi = int(numeric(options, "dpi", 144, 72, 300))
            for index in unique_pages:
                page = document[index]
                base = target.parent / f"ocr-{index}"
                rotation = page.rotation
                try:
                    page.set_rotation(0)
                    pix = page.get_pixmap(dpi=dpi, alpha=False, annots=False)
                    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    mask = ImageDraw.Draw(image)
                    xscale, yscale = pix.width / page.rect.width, pix.height / page.rect.height
                    for x0, y0, x1, y1, *_ in page.get_text("words"):
                        mask.rectangle((x0 * xscale - 1, y0 * yscale - 1, x1 * xscale + 1, y1 * yscale + 1), fill="white")
                    image.save(str(base) + ".png", dpi=(dpi, dpi))
                    result = subprocess.run([tesseract, str(base) + ".png", str(base), "-l", options.get("language", "eng"), "-c", "textonly_pdf=1", "pdf"], capture_output=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    if result.returncode:
                        raise ToolError("Tesseract failed. Check that the requested language data is installed.")
                    with pdf.open(str(base) + ".pdf") as recognized:
                        if recognized[0].get_contents():
                            page.show_pdf_page(page.rect, recognized, 0, keep_proportion=False)
                finally:
                    page.set_rotation(rotation)
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
                    if not text_value.isprintable():
                        raise ToolError("Enter a single line of printable text.")
                    from deskpdf.objects import validate_text_characters
                    try:
                        validate_text_characters(text_value)
                    except ValueError as error:
                        raise ToolError(str(error)) from None
                    use_unicode = any(ord(char) > 255 for char in text_value)
                    font = unicode_overlay_font() if use_unicode else None
                    if font and any(not font.has_glyph(ord(char)) or unicodedata.bidirectional(char) in {"R", "AL", "AN"}
                                    or unicodedata.category(char).startswith("M") for char in text_value):
                        raise ToolError("Some characters cannot be used in this tool. Try a text box in the visual editor.")
                    width = font.text_length(text_value, fontsize=size) if font else pdf.get_text_length(text_value, fontsize=size)
                    if tool == "text_overlay" and point.x + width > rect.width:
                        raise ToolError("The text extends beyond this page. Reduce its size or move it left.")
                    fontname = "helv"
                    if font:
                        names = {entry[4] for entry in page.get_fonts()}
                        fontname = "DPUnicode"
                        while fontname in names:
                            fontname += "X"
                        page.insert_font(fontname=fontname, fontbuffer=font.buffer)
                    point = point * page.derotation_matrix
                    page.insert_text(point, text_value, fontname=fontname, fontsize=size, color=(.15, .19, .25), fill_opacity=.18 if tool == "watermark" else 1, rotate=page.rotation)
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

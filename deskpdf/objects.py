from dataclasses import dataclass
from html import escape
from functools import lru_cache
from hashlib import sha256
import pymupdf as pdf

@dataclass
class Object:
    kind: str
    rect: tuple
    text: str = "Text"
    image: str = ""
    family: str = "Sans"
    size: int = 20
    bold: bool = False
    italic: bool = False
    color: str = "#204c37"
    image_data: bytes = b""
    source_rect: tuple | None = None
    source_id: str = ""
    baseline_ratio: float | None = None
    source_font: bytes = b""
    source_style: tuple = ()
    opacity: float = 1.0
    rotation: int = 0
    form_xref: int = 0
    form_name: str = ""
    form_label: str = ""
    form_value: object = ""
    form_type: int = 0
    form_flags: int = 0
    form_choices: tuple = ()
    form_on: object = None
    form_maxlen: int = 0
    form_seq: int = 0
    form_group: str = ""
    modified: bool = True
    removed: bool = False


def decode_pdf_name(value):
    data = bytearray()
    index = 0
    while index < len(value):
        if value[index] == "#" and index + 2 < len(value):
            try:
                data.append(int(value[index + 1:index + 3], 16))
                index += 3
                continue
            except ValueError:
                pass
        data.extend(value[index].encode("utf-8"))
        index += 1
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def remove_originals(page, entries):
    rotation, derotation = page.rotation, page.derotation_matrix
    page.set_rotation(0)
    try:
        for kind in ("Text", "Image"):
            originals = [obj for obj in entries if obj.kind == kind and obj.source_rect and obj.modified]
            if not originals:
                continue
            for obj in originals:
                box = pdf.Rect(obj.source_rect) * derotation
                if kind == "Text":
                    box.y0 += box.height * .15
                    box.y1 -= box.height * .15
                page.add_redact_annot(box, fill=False, cross_out=False)
            page.apply_redactions(images=pdf.PDF_REDACT_IMAGE_PIXELS if kind == "Image" else pdf.PDF_REDACT_IMAGE_NONE,
                                  graphics=pdf.PDF_REDACT_LINE_ART_NONE,
                                  text=pdf.PDF_REDACT_TEXT_REMOVE if kind == "Text" else pdf.PDF_REDACT_TEXT_NONE)
    finally:
        page.set_rotation(rotation)


def selected_form_values(widget):
    document = widget.parent.parent
    mupdf = pdf.mupdf
    # PyMuPDF's Widget.field_value does not expose multi-select PDF arrays.
    field = mupdf.pdf_load_object(pdf._as_pdf_document(document), widget.xref)
    value = mupdf.pdf_dict_get_inheritable(field, mupdf.pdf_new_name("V"))
    if mupdf.pdf_is_array(value):
        values = [mupdf.pdf_array_get(value, index) for index in range(mupdf.pdf_array_len(value))]
        return tuple(mupdf.pdf_to_name(item) if mupdf.pdf_is_name(item) else mupdf.pdf_to_text_string(item) for item in values)
    return (widget.field_value,) if widget.field_value else ()


def field_value_owner(document, xref):
    owner = xref
    while document.xref_get_key(owner, "V")[0] == "null":
        if document.xref_get_key(owner, "T")[0] != "null":
            break
        kind, parent = document.xref_get_key(owner, "Parent")
        if kind != "xref":
            break
        owner = int(parent.split()[0])
    return owner


def apply_multichoice(document, index, widget, obj):
    choices = [(choice[0], choice[1]) if isinstance(choice, (list, tuple)) and len(choice) == 2 else (choice, choice)
               for choice in obj.form_choices]
    selected = set(obj.form_value)
    indexes = [number for number, (value, _) in enumerate(choices) if value in selected]
    widget.field_value = ""
    widget.update()
    owner = field_value_owner(document, widget.xref)
    document.xref_set_key(owner, "V", "[" + " ".join(pdf.get_pdf_str(str(choices[number][0])) for number in indexes) + "]" if indexes else "null")
    document.xref_set_key(owner, "I", "[" + " ".join(str(number) for number in indexes) + "]" if indexes else "null")
    if not indexes:
        return
    kind, appearance = document.xref_get_key(widget.xref, "AP/N")
    if kind != "xref":
        return
    appearance_xref = int(appearance.split()[0])
    labels = {str(choices[number][1]) for number in indexes}
    with pdf.open() as isolated:
        isolated.insert_pdf(document, from_page=index, to_page=index, links=False)
        page = isolated[0]
        blank = isolated.get_new_xref()
        isolated.update_object(blank, "<<>>")
        isolated.update_stream(blank, b"")
        page.set_contents(blank)
        lines = [line for block in page.get_text("dict", clip=widget.rect)["blocks"] if block["type"] == 0
                 for line in block["lines"] if "".join(span["text"] for span in line["spans"]).strip() in labels]
    if not lines:
        return
    state = document.get_new_xref()
    document.update_object(state, "<</Type /ExtGState /ca 0.2 /CA 0.2>>")
    if document.xref_get_key(appearance_xref, "Resources/ExtGState")[0] == "null":
        document.xref_set_key(appearance_xref, "Resources/ExtGState", "<<>>")
    document.xref_set_key(appearance_xref, "Resources/ExtGState/DeskPDFSelection", f"{state} 0 R")
    overlay = ["q /DeskPDFSelection gs 0.18 0.55 0.33 rg"]
    for line in lines:
        box = pdf.Rect(line["bbox"]) & widget.rect
        # Widget appearance streams use a bottom-left origin inside the field.
        overlay.append(f"0 {widget.rect.y1 - box.y1:.4f} {widget.rect.width:.4f} {box.height:.4f} re f")
    overlay.append("Q")
    document.update_stream(appearance_xref, document.xref_stream(appearance_xref) + ("\n" + "\n".join(overlay) + "\n").encode("ascii"))


def apply_form_values(document, index, entries):
    page = document[index]
    for obj in entries:
        if obj.kind != "Form":
            continue
        widget = page.load_widget(obj.form_xref)
        if widget is None or widget.field_name != obj.form_name:
            raise ValueError(f"Could not find form field {obj.form_name!r} on page {index + 1}.")
        if obj.form_type == pdf.PDF_WIDGET_TYPE_LISTBOX and obj.form_flags & pdf.PDF_CH_FIELD_IS_MULTI_SELECT:
            apply_multichoice(document, index, widget, obj)
            continue
        display = next((choice[1] for choice in obj.form_choices if isinstance(choice, (list, tuple)) and len(choice) == 2 and choice[0] == obj.form_value), None)
        widget.field_value = display if display is not None else obj.form_value
        widget.update()
        if obj.form_type == pdf.PDF_WIDGET_TYPE_RADIOBUTTON:
            owner = field_value_owner(document, widget.xref)
            field = pdf.mupdf.pdf_load_object(pdf._as_pdf_document(document), owner)
            pdf.mupdf.pdf_dict_puts(field, "V", pdf.mupdf.pdf_new_name(str(obj.form_value)))
        if display is not None:
            # The widget appearance uses the label; the stored PDF value must remain the export value.
            owner = field_value_owner(document, widget.xref)
            document.xref_set_key(owner, "V", pdf.get_pdf_str(str(obj.form_value)))
    return document[index] if any(obj.kind == "Form" for obj in entries) else page


def apply_related_forms(document, entries):
    for index, obj in sorted(entries, key=lambda entry: entry[1].form_seq):
        apply_form_values(document, index, [obj])


@lru_cache(maxsize=8)
def load_embedded_font(data):
    return pdf.Font(fontbuffer=data)


def embedded_text_font(obj, width, baseline, bottom):
    if not (obj.source_font and obj.source_style == (obj.family, obj.bold, obj.italic)
            and obj.baseline_ratio is not None and baseline <= bottom
            and all(char.isprintable() for char in obj.text)):
        return None
    try:
        font = load_embedded_font(obj.source_font)
        if (all(font.has_glyph(ord(char)) for char in obj.text)
                and font.text_length(obj.text, fontsize=obj.size) <= width):
            return font
    except (RuntimeError, ValueError):
        pass
    return None


def apply_objects(document, objects):
    apply_related_forms(document, [(index, obj) for index, entries in objects.items() for obj in entries if obj.kind == "Form"])
    for index, entries in objects.items():
        page = document[index]
        redactions = [obj for obj in entries if obj.kind == "Redaction" and not obj.removed]
        if redactions:
            annotations = list(page.annots() or [])
            if any(annot.type[0] == pdf.PDF_ANNOT_REDACT for annot in annotations):
                raise ValueError("This page already has redaction annotations. Apply or remove them before adding a redaction area.")
            areas = [pdf.Rect(obj.rect) * page.derotation_matrix for obj in redactions]
            widgets = list(page.widgets() or [])
            if any(area.intersects(widget.rect) for area in areas for widget in widgets):
                raise ValueError("A redaction area overlaps a form field. Flatten or remove the field first.")
            if any(area.intersects(annot.rect) for area in areas for annot in annotations):
                raise ValueError("A redaction area overlaps an annotation. Flatten or remove the annotation first.")
        remove_originals(page, entries)
        rotation, derotation = page.rotation, page.derotation_matrix
        page.set_rotation(0)
        try:
            for obj in entries:
                if obj.kind in ("Form", "Redaction") or obj.removed or (obj.source_rect and not obj.modified):
                    continue
                visible = pdf.Rect(obj.rect)
                box = visible * derotation
                color = tuple(int(obj.color[i:i + 2], 16) / 255 for i in (1, 3, 5))
                if obj.kind == "Text":
                    fonts = {
                        "Sans": ("helv", "hebo", "heit", "hebi"),
                        "Serif": ("tiro", "tibo", "tiit", "tibi"),
                        "Mono": ("cour", "cobo", "coit", "cobi"),
                    }
                    font = fonts[obj.family][int(obj.bold) + 2 * int(obj.italic)]
                    baseline = box.y0 + (obj.baseline_ratio or 1.075) * obj.size
                    if embedded_text_font(obj, box.width, baseline, box.y1):
                        try:
                            resource = "DP" + sha256(obj.source_font).hexdigest()[:16]
                            page.insert_font(fontname=resource, fontbuffer=obj.source_font)
                            page.insert_text((box.x0, baseline), obj.text, fontname=resource,
                                             fontsize=obj.size, color=color, fill_opacity=obj.opacity)
                            continue
                        except (RuntimeError, ValueError):
                            pass
                    single_line = (obj.source_rect and obj.baseline_ratio is not None and obj.text.isascii()
                                   and all(32 <= ord(char) < 127 for char in obj.text)
                                   and baseline <= box.y1
                                   and pdf.get_text_length(obj.text, fontname=font, fontsize=obj.size) <= box.width)
                    if single_line:
                        page.insert_text((box.x0, baseline), obj.text, fontname=font, fontsize=obj.size, color=color, fill_opacity=obj.opacity)
                        continue
                    family = {"Sans": "sans-serif", "Serif": "serif", "Mono": "monospace"}[obj.family]
                    content = escape(obj.text).replace("\n", "<br>")
                    html = f'<div style="font-family:{family};font-size:{obj.size}pt;color:{obj.color};font-weight:{"bold" if obj.bold else "normal"};font-style:{"italic" if obj.italic else "normal"}">{content}</div>'
                    remaining, _ = page.insert_htmlbox(box, html, rotate=0 if obj.source_rect else rotation, opacity=obj.opacity)
                    if remaining < 0:
                        raise ValueError("Text could not fit in its box. Enlarge the box and try again.")
                elif obj.kind == "Image":
                    source = {"stream": obj.image_data} if obj.image_data else {"filename": obj.image}
                    page.insert_image(box, rotate=0 if obj.source_rect else rotation, keep_proportion=False, **source)
                elif obj.kind == "Rectangle":
                    page.draw_rect(box, color=color, width=2)
                elif obj.kind == "Ellipse":
                    page.draw_oval(box, color=color, width=2)
            for obj in redactions:
                page.add_redact_annot(pdf.Rect(obj.rect) * derotation, fill=(0, 0, 0), cross_out=False)
            if redactions:
                page.apply_redactions(images=pdf.PDF_REDACT_IMAGE_PIXELS,
                                      graphics=pdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
                                      text=pdf.PDF_REDACT_TEXT_REMOVE)
        finally:
            page.set_rotation(rotation)


def export_objects(document, objects, output, password=None):
    apply_objects(document, objects)
    options = dict(encryption=pdf.PDF_ENCRYPT_KEEP) if password is None else dict(encryption=pdf.PDF_ENCRYPT_AES_256, user_pw=password, owner_pw=password)
    document.save(output, garbage=4, deflate=True, **options)



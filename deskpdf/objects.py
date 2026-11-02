from dataclasses import dataclass
from html import escape
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
    opacity: float = 1.0
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


def remove_originals(page, entries):
    for kind in ("Text", "Image"):
        originals = [obj for obj in entries if obj.kind == kind and obj.source_rect and obj.modified]
        if not originals:
            continue
        for obj in originals:
            box = pdf.Rect(obj.source_rect) * page.derotation_matrix
            if kind == "Text":
                box.y0 += box.height * .15
                box.y1 -= box.height * .15
            page.add_redact_annot(box, fill=False, cross_out=False)
        page.apply_redactions(images=pdf.PDF_REDACT_IMAGE_PIXELS if kind == "Image" else pdf.PDF_REDACT_IMAGE_NONE,
                              graphics=pdf.PDF_REDACT_LINE_ART_NONE,
                              text=pdf.PDF_REDACT_TEXT_REMOVE if kind == "Text" else pdf.PDF_REDACT_TEXT_NONE)


def apply_form_values(document, index, entries):
    page = document[index]
    for obj in entries:
        if obj.kind != "Form":
            continue
        widget = page.load_widget(obj.form_xref)
        if widget is None or widget.field_name != obj.form_name:
            raise ValueError(f"Could not find form field {obj.form_name!r} on page {index + 1}.")
        display = next((choice[1] for choice in obj.form_choices if isinstance(choice, (list, tuple)) and len(choice) == 2 and choice[0] == obj.form_value), None)
        widget.field_value = display if display is not None else obj.form_value
        widget.update()
        if display is not None:
            # The widget appearance uses the label; the stored PDF value must remain the export value.
            owner = widget.xref
            while document.xref_get_key(owner, "V")[0] == "null":
                kind, parent = document.xref_get_key(owner, "Parent")
                if kind != "xref":
                    break
                owner = int(parent.split()[0])
            document.xref_set_key(owner, "V", pdf.get_pdf_str(str(obj.form_value)))
    return document[index] if any(obj.kind == "Form" for obj in entries) else page


def apply_related_forms(document, entries):
    for index, obj in sorted(entries, key=lambda entry: entry[1].form_seq):
        apply_form_values(document, index, [obj])


def apply_objects(document, objects):
    apply_related_forms(document, [(index, obj) for index, entries in objects.items() for obj in entries if obj.kind == "Form"])
    for index, entries in objects.items():
        page = document[index]
        remove_originals(page, entries)
        for obj in entries:
            if obj.kind == "Form" or obj.removed or (obj.source_rect and not obj.modified):
                continue
            visible = pdf.Rect(obj.rect)
            box = visible * page.derotation_matrix
            color = tuple(int(obj.color[i:i + 2], 16) / 255 for i in (1, 3, 5))
            if obj.kind == "Text":
                fonts = {
                    "Sans": ("helv", "hebo", "heit", "hebi"),
                    "Serif": ("tiro", "tibo", "tiit", "tibi"),
                    "Mono": ("cour", "cobo", "coit", "cobi"),
                }
                font = fonts[obj.family][int(obj.bold) + 2 * int(obj.italic)]
                baseline = box.y0 + (obj.baseline_ratio or 1.075) * obj.size
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
                remaining, _ = page.insert_htmlbox(box, html, rotate=page.rotation, opacity=obj.opacity)
                if remaining < 0:
                    raise ValueError("Text could not fit in its box. Enlarge the box and try again.")
            elif obj.kind == "Image":
                source = {"stream": obj.image_data} if obj.image_data else {"filename": obj.image}
                page.insert_image(box, rotate=page.rotation, keep_proportion=False, **source)
            elif obj.kind == "Rectangle":
                page.draw_rect(box, color=color, width=2)
            elif obj.kind == "Ellipse":
                page.draw_oval(box, color=color, width=2)

def export_objects(document, objects, output, password=None):
    apply_objects(document, objects)
    options = dict(encryption=pdf.PDF_ENCRYPT_KEEP) if password is None else dict(encryption=pdf.PDF_ENCRYPT_AES_256, user_pw=password, owner_pw=password)
    document.save(output, garbage=4, deflate=True, **options)



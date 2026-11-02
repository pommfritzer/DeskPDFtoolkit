from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    id: str
    title: str
    description: str
    group: str
    symbol: str
    fields: tuple[str, ...] = ()
    extension: str = "pdf"
    multiple: bool = False


TOOLS = [
    Tool("merge", "Merge PDF", "Choose pages from each PDF, then bring them together in your order.", "Organize", "⊕", multiple=True),
    Tool("extract", "Extract pages", "Keep just the pages you need.", "Organize", "↗", ("pages",)),
    Tool("split", "Split PDF", "Save each selected page as its own PDF in a ZIP.", "Organize", "⋈", ("pages",), "zip"),
    Tool("delete", "Delete pages", "Remove pages from a document.", "Organize", "−", ("pages",)),
    Tool("reorder", "Reorder pages", "Build a new page sequence, including duplicates.", "Organize", "⇄", ("pages",)),
    Tool("rotate", "Rotate pages", "Turn selected pages by 90, 180 or 270 degrees.", "Organize", "↻", ("pages", "rotation")),
    Tool("compress", "Compress PDF", "Optimize structure and remove duplicate objects, losslessly.", "Optimize", "↙"),
    Tool("flatten", "Flatten PDF", "Make annotations and completed form fields permanent.", "Optimize", "▱"),
    Tool("clean", "Remove metadata", "Clear document properties, XML metadata and attachments.", "Optimize", "◇"),
    Tool("images_to_pdf", "Images to PDF", "One page per image. Supports PNG, JPEG, TIFF and more.", "Convert", "▧", multiple=True),
    Tool("pdf_to_png", "PDF to images", "Export selected pages as crisp PNG images in a ZIP.", "Convert", "▦", ("pages", "dpi"), "zip"),
    Tool("text", "PDF to text", "Extract readable text in page order.", "Convert", "≡", ("pages",), "txt"),
    Tool("word", "PDF to Word", "Export editable text and page breaks; original layout is not preserved.", "Convert", "W", ("pages",), "docx"),
    Tool("excel", "PDF to Excel", "Detect tables and export each table to a worksheet.", "Convert", "X", ("pages",), "xlsx"),
    Tool("powerpoint", "PDF to PowerPoint", "Create a slide image for each page; slide contents are not individually editable.", "Convert", "P", ("pages",), "pptx"),
    Tool("office", "Office to PDF", "Convert with a locally installed LibreOffice. No uploads.", "Convert", "↘"),
    Tool("ocr", "Recognize text", "Make scanned text searchable while keeping the original pages, links and forms. Requires Tesseract.", "Convert", "⌕", ("pages", "language", "dpi")),
    Tool("text_overlay", "Add text", "Place text on selected pages. Click the preview to position it.", "Edit & sign", "T", ("pages", "text", "size", "x", "y")),
    Tool("watermark", "Watermark", "Add a subtle text watermark to selected pages.", "Edit & sign", "◈", ("pages", "text", "size")),
    Tool("number", "Number pages", "Add page numbers at the bottom of selected pages.", "Edit & sign", "#", ("pages",)),
    Tool("crop", "Crop pages", "Hide equal margins; cropped content remains in the PDF.", "Edit & sign", "⌗", ("pages", "margin")),
    Tool("redact", "Redact text", "Permanently remove every exact text match on selected pages.", "Edit & sign", "▰", ("pages", "text")),
    Tool("highlight", "Highlight text", "Highlight every exact text match on selected pages.", "Edit & sign", "▰", ("pages", "text")),
    Tool("sign", "Place signature", "Place your PNG signature. This is a visual, not certificate signature.", "Edit & sign", "∿", ("pages", "signature", "x", "y", "width")),
    Tool("forms", "Fill form", "Fill existing text fields, checkboxes and choices by field name.", "Edit & sign", "☑", ("form_values",)),
    Tool("protect", "Protect PDF", "Encrypt a document with an AES-256 opening password.", "Security", "□", ("new_password",)),
    Tool("unlock", "Unlock PDF", "Remove encryption using the password you provide.", "Security", "⌑"),
]

TOOL_BY_ID = {tool.id: tool for tool in TOOLS}

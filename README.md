# PDFtoolkit26

Click a page thumbnail to include it in the output; its translucent green highlight shows selection. Click it again to exclude it. Hover over its corner controls for their names. The toolbar divider can be dragged to give pages more space.

Focus mode now edits pages directly: text boxes, pictures, shapes, crop, drag/resize, font controls and undo/redo are available without leaving focus. Changes stay with their page across navigation and return to the main workspace for Save a copy. Added or changed pages are included automatically. The workspace warns before discarding unsaved focus edits on app close. Selectable original text spans and embedded pictures can also be edited in focus mode.

Compact page tools live at the bottom left; the input-unlock control sits beside Save. Thumbnail zoom uses a percentage and minus/plus buttons at the top right instead of a slider.

The editor toolbar is resizable: drag the green divider between its controls and the page workspace. Each page thumbnail has a focus button below crop. Focus mode opens maximized, with previous/next arrows on the screen sides, Left/Right keyboard navigation, Ctrl++/Ctrl+- zoom, and Escape to return. It follows the current page order across PDFs, respects crops, and lets you include/exclude the focused page without losing the selection.

Modern Windows 11 menu integration is implemented as a native command and a signed sparse package. See [shell integration](shell/README.md) for building, signing and registration. The local development installation uses an explicitly approved signing-certificate trust configuration; unsigned public installers retain the classic menu unless a signed shell package is supplied.

Select one or more PDFs in Explorer and choose **Open with PDFtoolkit26**. The entry uses the application icon. Separate Explorer launch requests are forwarded to one running window, with paths containing spaces and Unicode preserved. On Windows 11 this classic menu entry appears under **Show more options**. The installer’s Explorer integration option controls installation and cleanup of the entry.

## Visual editor (0.5)

Choose **Editor** in the top bar to edit the selected PDF, or choose a file if none is selected. The page canvas supports added text boxes, pictures, rectangles and ellipses. Select an object and drag it to move; drag its bottom-right handle to resize. The property panel edits text, font family, size, bold, italic and colour. Crop edits page margins. Undo/redo, page navigation, canvas zoom with Ctrl++/Ctrl+-, and save-a-copy are available. Closing or pressing Escape asks before discarding unsaved work.

Added objects leave the original content intact. Select supported existing text spans and embedded pictures to edit, move, resize or delete them; select a picture and choose Replace picture to swap it. Existing form widgets remain in the PDF. Edited original text is reconstructed using an approximate font and styling, and text is fitted within its box; check the saved result. Overlapping content, rotated pages and some complex or flattened content cannot be edited separately. Scanned text is part of a picture unless OCR has added a text layer. This is an initial visual editor, not complete Acrobat feature parity. PDF form filling and redaction remain available through their dedicated tools.

**Your PDFs, at hand.** A quiet, local-first PDF workbench for Windows.

Version 0.2 introduces a full-width single-row toolbar without category buttons, an animated green ambient background with a grey dot grid, and a gallery led by large vector tool icons. The current background is a static green gradient with layered dot grids. In Merge PDF, the Page size slider enlarges thumbnails from 140 to 650 pixels and re-renders pages sharply without changing your selection or order.

![PDFtoolkit26 tool library](docs/screenshots/library.png)

PDFtoolkit26 brings common PDF jobs into one native desktop app: choose a tool, add a file, save a copy. Documents are processed on your computer. No account, telemetry, server, or upload service.

## Install

Download the installer from [GitHub Releases](https://github.com/pommfritzer/DeskPDFtoolkit/releases), or run `PDFtoolkit26-0.6.3-Setup.exe` from the local `releases` folder. The installer includes Python, Qt and the PDF engine; users do not install Python. Installation is per user and needs no administrator privileges.

The optional Explorer integration adds **Open in PDFtoolkit26**, **Compress with PDFtoolkit26**, and **Extract pages with PDFtoolkit26** to PDF right-click menus. On Windows 11, use **Show more options**. Your default PDF reader is unchanged. Uninstall from Windows Settings to remove the app and its menu entries.

Target: Windows 10/11, x64. The initial build is unsigned; Windows may show an unknown-publisher notice. Signing is a release-maintainer task.

## Tools

| Area | Available tools |
| --- | --- |
| Organize | Merge, extract, split, delete, reorder, rotate |
| Optimize | Lossless compression, flatten forms/annotations, remove metadata and embedded attachments |
| Convert | Images → PDF, PDF → PNG, text, Word, Excel, PowerPoint; Office → PDF; OCR |
| Edit & sign | Add text, watermark, page numbers, crop, redact text, highlight text, place a signature image, fill existing forms |
| Security | AES-256 password protection; password-authorized unlocking |

Page selections accept `all`, `1,3-5`, descending ranges such as `5-1`, and duplicates for extraction/reordering. Drag input files to set merge order. Click a document preview to position text or a signature. Coordinates and dimensions use PDF points (72 points per inch).

For merging, all pages from every added PDF appear together in one thumbnail grid. Click thumbnails to include or exclude pages; drag the thumbnails directly into output order. Select all and Clear selection apply across the whole grid. Each thumbnail identifies its source PDF and page number.

![PDFtoolkit26 workbench](docs/screenshots/workbench.png)

### Honest boundaries

- Compression is lossless structural optimization. Already optimized files may stay the same size or grow slightly.
- Word export produces editable text and page breaks, without reconstructing the original layout. Scans need OCR first.
- Excel export detects tables, rather than inferring an entire spreadsheet. Exported strings remain strings, including text beginning with `=`.
- PowerPoint export produces one page image per slide; slide contents are not individually editable.
- Office input requires a separate local [LibreOffice](https://www.libreoffice.org/) installation. Supported formats depend on that installation.
- OCR requires [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html) and its requested language data. It rasterizes pages and replaces them with searchable page images; existing forms, links and annotations are not retained.
- Text overlays add content. The visual editor can also edit supported existing text spans; complex layouts may not be editable. Standard-font overlays support Latin text. Use a signature image for other scripts.
- Signatures are placed images, not cryptographic certificate signatures or a remote signing service.
- Redaction removes exact searchable text matches and overlapping image content. It does not detect sensitive information, redact scans by appearance, or sanitize every hidden data source. Inspect the saved file. Metadata removal clears standard/XML metadata and embedded files; it is not a complete forensic sanitizer.
- Cropping hides margins rather than deleting the content outside them.
- Form filling supports existing AcroForm widgets, not XFA forms. Checkbox values must match their export values.
- Editing preserves source encryption unless you explicitly choose Unlock. Modifications can invalidate existing digital signatures.
- Cloud collaboration, remote signature requests, AI chat/translation, PDF/A certification, scanner hardware acquisition, and editing arbitrary original text are outside this initial release.
- Preview displays the original document. Open the saved result to inspect your changes.

## Develop

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python run.py
.\.venv\Scripts\python -m pytest -q
```

Python 3.11+ is supported; the release workflow uses 3.13. `requirements-lock.txt` records the exact packages used for the initial Windows build (Python 3.14). To recreate that build environment, install that file before installing the project with `--no-deps`.

```powershell
.\.venv\Scripts\python run.py --tool extract "C:\Documents\example.pdf"
```

## Build an installer

Install [Inno Setup 6](https://jrsoftware.org/isinfo.php), then:

```powershell
.\scripts\build.ps1
```

To upgrade the local installation and open Merge PDF, run `./scripts/install.ps1` from the project folder. It uses the project version's installer, retains installer task preferences, closes the previous app through the installer, and launches once afterward. Installation stays in `%LOCALAPPDATA%\Programs\PDFtoolkit26`; reinstalling updates the same Windows uninstall entry. Disabling Explorer integration or the desktop shortcut during setup removes those entries.

The script regenerates the icon, runs tests, collects dependency licenses, bundles a standalone application with PyInstaller, checks bundled startup, and compiles `releases/PDFtoolkit26-0.6.3-Setup.exe`. Dependency discovery uses an isolated PATH to avoid picking up incompatible DLLs from unrelated installed software. The portable app is in `dist/PDFtoolkit26`. The Windows GitHub Actions workflow builds and uploads the installer on pushes and pull requests. Pushing a version tag such as `v0.6.3` also publishes the installer and SHA-256 checksum to a preview release. Update the version in `pyproject.toml`, `deskpdf/__init__.py`, the About dialog, installer definition and release workflow before tagging a new version.

## Architecture

- `deskpdf/catalog.py`: declarative tool definitions and UI options.
- `deskpdf/engine.py`: PDF operations, validation and atomic output saving; no GUI dependencies.
- `deskpdf/app.py`: Qt widgets, file selection, preview and background jobs.
- `deskpdf/theme.py`: centralized visual styling.
- `installer/PDFtoolkit26.iss`: per-user installer and removable Explorer commands.
- `tests/`: generated documents verify content, page order, redaction, encryption, form values, exports, and failure behavior.

The app uses Python and PySide6 for legible, direct native UI code; MuPDF handles PDF rendering and manipulation. Work runs on a background thread while controls are locked against competing edits. Files are staged beside the destination, then atomically replaced only after successful processing. Input paths cannot be output paths.

See [design decisions](docs/DESIGN.md), [contributing](CONTRIBUTING.md), and [third-party notices](THIRD_PARTY_NOTICES.md).

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE). PDFtoolkit26 has its own branding and implementation; it is not affiliated with Smallpdf.

Use **Add page** in the editor to create an A4 title or divider page. The live composer centers your text and offers Sans, Serif, Mono, size, bold and italic. New pages are included automatically and can be dragged into place. Generated pages stay in a temporary workspace until the app closes; save your finished PDF before quitting.

### Page editing in 0.4

Editor controls are grouped in the expanded top partition. Each PDF set uses a numbered colour accent. The first-page arrow expands the set; the last-page arrow collapses it without excluding pages from export. Drag thumbnails across sets, or use **Move page to…** for an exact document position. Each thumbnail has delete above crop at the top right. The crop overlay supports dragging edges, corners or drawing a new rectangle; Reset restores the current crop boundary. Cropping hides margins and is not secure redaction. Page deletion affects this editing sequence, not your original files.

### 0.6.1 interface controls

Ctrl++ (or Ctrl+=) enlarges the interface, Ctrl+- reduces it, and Ctrl+0 resets it. Thumbnail size remains independently adjustable. Background dots use 6 px marks on a 136 px grid and 2 px marks on a 51 px grid. Swirls and continuous background repainting are removed. The lock-and-key control reveals a masked **input PDF password** field with a green arrow confirmation; it does not set output encryption. Use Protect PDF for that.

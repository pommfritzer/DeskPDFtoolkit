# Initial release validation

Validated on Windows 11 x64, 31 October 2026, with Python 3.14.6, Qt/PySide6 6.12.0, MuPDF/PyMuPDF 1.26.7, PyInstaller 6.22.3 and Inno Setup 6.7.4.

- 31 automated tests pass, including all tool forms and search, exact page sequencing, duplicate pages, merge, delete, rotation, crop, irreversible text redaction, annotations, text overlays, watermarking, numbering, lossless save, metadata removal, password protection/preservation/unlocking, image input, signature placement, ZIP output, text/Word/PowerPoint export, Excel tables and formula-safe string cells, form filling and flattening, validation failures, and preservation of existing destinations after failure.
- A generated DOCX file converted through the installed LibreOffice to a readable PDF with the expected text.
- The missing-Tesseract path returns a useful installation message. OCR output has not been validated against a real Tesseract installation.
- Rendered application views were inspected at 1210 × 830 and 960 × 680. The preview scales to available space. Offscreen screenshot generation loads Windows fonts explicitly because the offscreen Qt platform does not discover system fonts.
- The standalone application and installer compile successfully. Dependency licenses are included.
- The installer was exercised through installation, an upgrade over the earlier diagnostic bundle, all three registered Explorer commands, bundled startup with a PDF and preselected tool, and uninstallation. The installed executable and Explorer keys were removed successfully. The installer clears obsolete files in its managed `_internal` runtime directory on upgrade.
- A packaging failure caused by an unrelated ICU DLL on the development environment's PATH was corrected by isolating dependency discovery. Bundled startup is now a required build step before installer compilation.

These checks are not a substitute for testing on clean Windows 10 and Windows 11 machines, different DPI settings, screen readers, complex real-world documents, or a corpus of malformed PDFs. The initial release is unsigned and should be treated as a preview.

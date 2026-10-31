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

## 0.1.1: merge page selection

All 34 tests pass. New checks verify different selections for each source, page order and duplicates, file-specific invalid-range errors, destination preservation on failure, and selection persistence through file changes, reordering, tool switching and removal. The UI test also saves an actual merged PDF through the workbench and verifies the submitted per-file choices.

The merge view was rendered and inspected. The Windows bundle passed its startup checks, the 0.1.1 installer upgraded the installed application successfully, and the updated app reopened on Merge PDF.

## 0.1.2: combined thumbnail workspace and installation cleanup

All 34 tests pass. The merge UI test loads both PDFs together, clicks pages from both sources, uses the same move operation as thumbnail dropping, switches source selection without resetting the grid, exports the actual PDF, and checks its text order. Removing an input prunes its thumbnails; select-all and clear apply across remaining pages.

The combined view was rendered and inspected. The installer upgrades one fixed per-user installation, cleans obsolete runtime files, disables automatic duplicate relaunches, and removes deselected integration entries. Reinstall checks verified Explorer integration both disabled and enabled, and one Windows uninstall entry for DeskPDF 0.1.2.

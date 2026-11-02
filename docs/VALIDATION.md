# Initial release validation

## 0.6.0 integrated focus editing

All 59 tests pass. The new end-to-end focus test adds and moves text and a picture, crops edges through the crop overlay, navigates between pages, preserves objects on return, and exports the main merged PDF with text, image, crop and vector shapes intact. The original PDF is checked for unchanged content. Updated workspace and focus views were rendered and inspected against the user's layout markup. PDF object application/export is shared by standalone editing, focus previews and merged output.

## 0.5.3 resizable toolbar and page focus

All 58 tests pass. New tests verify manual toolbar sizing survives window resizing, focus navigation boundaries, cropped focus rendering, and selection synchronisation with the thumbnail workspace. The compact toolbar and focused page view were rendered and visually inspected.

## 0.5.2 Windows 11 modern menu

Built an x64 native IExplorerCommand DLL and sparse MSIX registration. Windows rejected unsigned executable activation and current-user-only signing trust. With the user's explicit approval, the local PDFtoolkit26 certificate was installed into Local Machine Trusted People; the signed package then registered with status OK. Native COM activation verified the exact menu title, executable icon path, enabled PDF state, and invocation handoff. No global menu preference or system security setting was disabled.

## 0.5.1 Explorer open integration

The menu label is Open with PDFtoolkit26, with a quoted executable icon path and Player multi-selection model. A process-level test forwards multiple requests, spaces and Unicode filenames to a single primary local server. A per-user instance lock handles simultaneous launches; the local server restricts access to the current user. Packaged smoke tests use an isolated instance scope to avoid interacting with a running user window.

All 56 tests pass. After installation, the registered label, icon path and command were checked. Repeated shell-open requests against the installed executable completed successfully with only one application process remaining. Windows extracted the executable's icon resource successfully.

## 0.5.0 visual object editor

All 55 tests pass. New tests verify exported text, embedded pictures, vector rectangle/ellipse objects, preservation of original PDF content, movement/resizing state, undo/redo, edits across pages and cancellation/discard behaviour for Escape. A rendered editor view was inspected. The editor works with newly added objects; it does not reconstruct arbitrary original document text into editable paragraphs.

## 0.2.1 compact toolbar

All 35 tests pass. The navigation test checks the 30% height reduction, full window width, zero horizontal offset, and removal of category buttons. Updated gallery and workbench renders were inspected before packaging.

## 0.2.0 interface overhaul

All 35 tests pass, including preservation of selected page order across thumbnail enlargement, sharper re-rendered icons, top navigation height, and background animation control. The gallery and workbenches were rendered and inspected at normal and minimum window sizes. The build checks the packaged application's imports and workbench startup before compiling the installer.

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

## PDFtoolkit26 0.3.0

All 49 tests pass. Twelve combinations verify exact horizontal and vertical centering across Sans, Serif, Mono, bold and italic. Additional tests cover blank pages and adding a generated title page into the selected editor sequence. The composer was rendered and visually inspected. Product executables, installer, shortcuts and Explorer menu entries use PDFtoolkit26; the installer removes the legacy DeskPDF installation before migration.

## 0.4.0 page editor

All 51 tests pass. New tests verify source-preserving per-page crop export, set collapse/expand without selection loss, and deletion surviving grid refresh. The expanded control partition and page buttons were rendered and inspected.

## 0.4.1 static dots and compact input unlock

All 52 tests pass, including UI scale changes/reset, input-password disclosure, and the inactive background timer. Offscreen UI tests now explicitly delete their windows before QApplication teardown. This removes an intermittent teardown failure that previously occurred after the tests themselves had passed.

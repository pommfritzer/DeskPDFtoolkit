# Third-party notices

PDFtoolkit26 is distributed under AGPL-3.0-or-later. Its source is available at https://github.com/pommfritzer/DeskPDFtoolkit. No Smallpdf code, branding, or artwork is included.

The application bundles the following open-source components. Original package license and notice files are copied to `licenses/` in application distributions by `scripts/collect_licenses.py`.

| Component | License | Source |
| --- | --- | --- |
| Python | PSF License | https://www.python.org/ |
| PySide6 / Shiboken / Qt | LGPL-3.0 / GPL / Qt component licenses | https://code.qt.io/ |
| PyMuPDF / MuPDF | AGPL-3.0-or-later | https://github.com/pymupdf/PyMuPDF / https://mupdf.com/ |
| Pillow | MIT-CMU | https://github.com/python-pillow/Pillow |
| python-docx | MIT | https://github.com/python-openxml/python-docx |
| openpyxl | MIT | https://foss.heptapod.net/openpyxl/openpyxl |
| python-pptx | MIT | https://github.com/scanny/python-pptx |
| lxml | BSD and included library licenses | https://github.com/lxml/lxml |
| XlsxWriter | BSD-2-Clause | https://github.com/jmcnamara/XlsxWriter |
| et-xmlfile | MIT | https://foss.heptapod.net/openpyxl/et_xmlfile |
| typing-extensions | PSF-2.0 | https://github.com/python/typing_extensions |

PyInstaller is a build-time tool with a GPL exception for bundled applications. Inno Setup is a build-time tool governed by its own license. Tesseract and LibreOffice are optional, separately installed software and are not bundled.

Qt libraries remain separate shared libraries in the application bundle. Users may replace compatible Qt libraries under the applicable license; do not remove this capability when redistributing. Refer to upstream sources for corresponding library source and build instructions.

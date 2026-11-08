from pathlib import Path
import sys

root = Path(SPECPATH)
a = Analysis(
    [str(root / "run.py")],
    pathex=[str(root)],
    datas=[(str(root / "deskpdf" / "assets"), "deskpdf/assets"), (str(root / "build/licenses"), "licenses")],
    hiddenimports=["docx", "openpyxl", "pptx"],
    excludes=["PySide6.QtQml", "PySide6.QtQuick", "tkinter"],
)
pyz = PYZ(a.pure)
icon = str(root / "deskpdf/assets/icon.ico") if sys.platform == "win32" else None
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PDFtoolkit26", console=False,
          icon=icon, argv_emulation=sys.platform == "darwin")
coll = COLLECT(exe, a.binaries, a.datas, name="PDFtoolkit26")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="PDFtoolkit26.app", icon=str(root / "deskpdf/assets/icon.icns"),
                 bundle_identifier="org.pdftoolkit26.app", info_plist={
                     "NSHighResolutionCapable": True,
                     "CFBundleDocumentTypes": [{"CFBundleTypeName": "PDF document", "CFBundleTypeRole": "Viewer",
                                                "LSHandlerRank": "Alternate", "LSItemContentTypes": ["com.adobe.pdf"]}],
                 })

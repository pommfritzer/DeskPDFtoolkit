from pathlib import Path

root = Path(SPECPATH)
a = Analysis(
    [str(root / "run.py")],
    pathex=[str(root)],
    datas=[(str(root / "deskpdf" / "assets"), "deskpdf/assets"), (str(root / "build/licenses"), "licenses")],
    hiddenimports=["docx", "openpyxl", "pptx"],
    excludes=["PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtNetwork", "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PDFtoolkit26", console=False, icon=str(root / "deskpdf/assets/icon.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="PDFtoolkit26")

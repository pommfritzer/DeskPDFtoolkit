import importlib.metadata
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root / "build" / "licenses"
destination.mkdir(parents=True, exist_ok=True)
packages = ["PySide6-Essentials", "shiboken6", "PyMuPDF", "Pillow", "python-docx", "openpyxl", "python-pptx", "lxml", "XlsxWriter", "et-xmlfile", "typing-extensions"]
for name in packages:
    distribution = importlib.metadata.distribution(name)
    for entry in distribution.files or []:
        if any(token in entry.name.lower() for token in ("license", "licence", "copying", "notice", "copyright")):
            source = Path(distribution.locate_file(entry))
            if source.is_file():
                output = destination / name / str(entry).replace("../", "").replace("..\\", "")
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, output)
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.exists():
    shutil.copy2(python_license, destination / "Python-LICENSE.txt")
for source in (root / "third_party_licenses").iterdir():
    if source.is_file():
        shutil.copy2(source, destination / source.name)

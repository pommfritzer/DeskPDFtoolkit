import os
import subprocess
import sys
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
default_application = (root / "dist" / "PDFtoolkit26.app" / "Contents" / "MacOS" / "PDFtoolkit26" if sys.platform == "darwin"
                       else root / "dist" / "PDFtoolkit26" / ("PDFtoolkit26.exe" if os.name == "nt" else "PDFtoolkit26"))
application = Path(os.environ.get("PDFTOOLKIT26_CHECK_EXECUTABLE", default_application))
subprocess.run([str(application), "--help"], timeout=20, check=True)
environment = os.environ.copy()
environment.setdefault("QT_QPA_PLATFORM", "offscreen")
environment["PDFTOOLKIT26_INSTANCE_SCOPE"] = "bundle-check-" + uuid.uuid4().hex
process = subprocess.Popen([str(application), "--tool", "compress"], env=environment)
try:
    try:
        result = process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        print("Packaged application imports and initializes its workbench.")
    else:
        raise RuntimeError(f"Packaged application exited during startup: {result}")
finally:
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=10)

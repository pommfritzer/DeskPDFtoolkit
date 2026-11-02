import os
import subprocess
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
application = root / "dist" / "PDFtoolkit26" / "PDFtoolkit26.exe"
subprocess.run([str(application), "--help"], timeout=20, check=True)
environment = os.environ.copy()
environment["QT_QPA_PLATFORM"] = "offscreen"
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

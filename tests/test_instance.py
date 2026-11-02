import time
import uuid
from deskpdf.instance import InstanceBroker


def test_multiple_shell_requests_reach_one_instance(application_session, monkeypatch):
    monkeypatch.setenv("PDFTOOLKIT26_INSTANCE_SCOPE", uuid.uuid4().hex)
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.setApplicationName("PDFtoolkit26")
    primary = InstanceBroker()
    assert primary.start_or_forward({"files": []})
    received = []
    primary.requested.connect(received.append)
    import subprocess, sys, os
    script = "from PySide6.QtCore import QCoreApplication; from deskpdf.instance import InstanceBroker; app=QCoreApplication([]); app.setApplicationName('PDFtoolkit26'); b=InstanceBroker(); assert not b.start_or_forward({'files': ['C:/PDFs/one file.pdf']}); assert not b.start_or_forward({'files': ['C:/PDFs/two.pdf', 'C:/PDFs/\\u00dcnicode.pdf']})"
    child = subprocess.Popen([sys.executable, "-c", script], env=os.environ.copy())
    deadline = time.monotonic() + 15
    while (child.poll() is None or len(received) < 2) and time.monotonic() < deadline:
        application_session.processEvents()
    assert child.wait(timeout=2) == 0
    assert received == [{"files": ["C:/PDFs/one file.pdf"]}, {"files": ["C:/PDFs/two.pdf", "C:/PDFs/Ünicode.pdf"]}]
    primary.server.close()
    primary.lock.unlock()

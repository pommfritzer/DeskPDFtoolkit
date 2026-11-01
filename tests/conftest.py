import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import gc
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def application_session():
    application = QApplication.instance() or QApplication([])
    yield application
    gc.collect()
    application.processEvents()

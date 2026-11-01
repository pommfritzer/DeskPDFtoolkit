import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import gc
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent


@pytest.fixture(scope="session", autouse=True)
def application_session():
    application = QApplication.instance() or QApplication([])
    yield application
    gc.collect()
    application.processEvents()


@pytest.fixture(autouse=True)
def close_test_windows(application_session):
    yield
    for window in QApplication.topLevelWidgets():
        window.close()
        window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()

import hashlib
import json
import os
import time
from pathlib import Path

from PySide6.QtCore import QObject, QLockFile, QStandardPaths, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class InstanceBroker(QObject):
    requested = Signal(dict)

    def __init__(self):
        super().__init__()
        folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        folder.mkdir(parents=True, exist_ok=True)
        scope = os.environ.get("PDFTOOLKIT26_INSTANCE_SCOPE", "desktop")
        token = hashlib.sha256((str(folder) + scope).encode()).hexdigest()[:20]
        self.name = "PDFtoolkit26-" + token
        self.lock = QLockFile(str(folder / ("instance-" + token + ".lock")))
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self.accept)
        self.connections = set()

    def start_or_forward(self, request):
        if self.lock.tryLock(100):
            QLocalServer.removeServer(self.name)
            if not self.server.listen(self.name):
                self.lock.unlock()
                raise RuntimeError(self.server.errorString())
            return True
        socket = QLocalSocket()
        connected = False
        for attempt in range(50):
            socket.abort()
            socket.connectToServer(self.name)
            if socket.waitForConnected(100):
                connected = True
                break
            time.sleep(.05)
        if not connected:
            raise RuntimeError("PDFtoolkit26 is starting or closing. Please try opening the files again.")
        socket.write(json.dumps(request).encode() + b"\n")
        if socket.bytesToWrite() and not socket.waitForBytesWritten(3000):
            raise RuntimeError("Could not deliver files to the running PDFtoolkit26 window.")
        socket.disconnectFromServer()
        return False

    def accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self.connections.add(socket)
            socket.setProperty("buffer", b"")
            socket.readyRead.connect(lambda connection=socket: self.read(connection))
            socket.disconnected.connect(lambda connection=socket: self.release(connection))
            self.read(socket)

    def read(self, socket):
        data = bytes(socket.property("buffer") or b"") + bytes(socket.readAll())
        while b"\n" in data:
            message, data = data.split(b"\n", 1)
            try:
                request = json.loads(message)
                if isinstance(request, dict) and isinstance(request.get("files", []), list):
                    self.requested.emit(request)
            except (ValueError, UnicodeDecodeError):
                pass
        socket.setProperty("buffer", data)

    def release(self, socket):
        from shiboken6 import isValid
        if not isValid(socket):
            return
        self.read(socket)
        self.connections.discard(socket)
        socket.deleteLater()

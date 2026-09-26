"""pil-modu komut satırını arka planda çalıştırır; arayüz donmaz.

Arayüz donanıma kendisi dokunmaz: tüm işi CLI yapar. Böylece arayüz ile
terminalden çalıştırma birebir aynı davranır.
"""
import sys

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from .. import paths


class ModeRunner(QObject):
    output = Signal(str)
    finished = Signal(bool)  # başarılı mı

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", str(paths.SOURCE_DIR))
        env.insert("PYTHONUNBUFFERED", "1")
        self.process.setProcessEnvironment(env)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)

    def is_running(self):
        return self.process.state() != QProcess.NotRunning

    def start(self, args):
        self.process.start(sys.executable, ["-m", "pil_modu", *args])

    def _read(self):
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data.strip():
            self.output.emit(data.rstrip())

    def _finished(self, code, exit_status):
        self._read()
        self.finished.emit(code == 0 and exit_status == QProcess.NormalExit)

    def _error(self, error):
        if error == QProcess.FailedToStart:
            self.output.emit(self.process.errorString())
            self.finished.emit(False)

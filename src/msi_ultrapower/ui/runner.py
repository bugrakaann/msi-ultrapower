"""Runs the msi-ultrapower command line in the background so the window does not freeze.

The window never touches hardware itself; the CLI does all the work, so the window and
the terminal behave exactly the same.
"""
import sys

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from .. import i18n, paths


class ModeRunner(QObject):
    output = Signal(str)
    finished = Signal(bool)  # succeeded

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", str(paths.SOURCE_DIR))
        env.insert("PYTHONUNBUFFERED", "1")
        self._env = env
        self.process.setProcessEnvironment(env)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)

    def is_running(self):
        return self.process.state() != QProcess.NotRunning

    def start(self, args):
        # The language may change while the window is open; pass it on every run.
        for key, value in i18n.child_environment().items():
            self._env.insert(key, value)
        self.process.setProcessEnvironment(self._env)
        self.process.start(sys.executable, ["-m", "msi_ultrapower", *args])

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

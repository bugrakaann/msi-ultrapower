"""Runs the helper that needs root through pkexec."""
import json
import os
import select
import subprocess
import sys

from . import paths
from .i18n import _

PYTHON = "/usr/bin/python3"
# pkexec exit codes: password dialog dismissed / not authorized.
PKEXEC_DISMISSED = 126
PKEXEC_NOT_AUTHORIZED = 127


def hardware(*args):
    """The installed helper (with its polkit action), or the same entry point from the source in development."""
    if paths.INSTALLED_HELPER.exists():
        return ["pkexec", str(paths.INSTALLED_HELPER), *args]
    code = (f"import sys; sys.path.insert(0, {str(paths.SOURCE_DIR)!r}); "
            "from msi_ultrapower.privileged.hardware import entry; entry()")
    return ["pkexec", PYTHON, "-P", "-c", code, *args]  # make run


def auth_error(returncode):
    """A clear reason if pkexec stopped at the password step, otherwise None."""
    if returncode == PKEXEC_DISMISSED:
        return _("The password prompt was cancelled; nothing was changed.")
    if returncode == PKEXEC_NOT_AUTHORIZED:
        return _("Authorization failed; nothing was changed.")
    return None


class HardwareHelper:
    """Runs the READY → COMMIT/ROLLBACK exchange with privileged/hardware.py.

    The helper applies the settings at once but waits for COMMIT to keep them, so the hardware
    goes back too if the KDE side fails. The NVIDIA boot setting is done by the same helper after
    COMMIT, so a mode switch asks for the password only once.
    The helper's stderr is merged into stdout (so initramfs output cannot fill a pipe).
    """

    def __init__(self, target):
        self.process = subprocess.Popen(
            hardware(json.dumps(target)),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.output = []      # output other than the marker lines (reason for a failure)
        self._buffer = b""

    def _lines(self, timeout):
        """Yields the output line by line. We own the buffer, so this is safe with select().

        timeout: longest wait for new output in seconds; None waits forever.
        """
        fd = self.process.stdout.fileno()
        while True:
            if b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                yield line.decode("utf-8", "replace")
                continue
            if timeout is not None and not select.select([fd], [], [], timeout)[0]:
                return
            chunk = os.read(fd, 4096)
            if not chunk:
                if self._buffer:
                    yield self._buffer.decode("utf-8", "replace")
                    self._buffer = b""
                return
            self._buffer += chunk

    def _read_until(self, marker, timeout):
        """True when the marker line arrives; False on timeout or when the helper exits."""
        for line in self._lines(timeout):
            if line.strip() == marker:
                return True
            self.output.append(line)
        return False

    def _stop(self):
        """Lets the helper go. pkexec runs as root, so it may not accept our signal; once stdin
        is closed the helper cannot get COMMIT after READY and rolls back by itself."""
        try:
            self.process.terminate()
        except OSError:
            pass
        try:
            return self.process.communicate(timeout=10)[0] or b""
        except subprocess.TimeoutExpired:
            self.process.stdin.close()
            return b""

    def _failure(self, title):
        rest = self._buffer + (self._stop() if self.process.poll() is None
                               else self.process.communicate()[0] or b"")
        self.output += rest.decode("utf-8", "replace").splitlines()
        reason = auth_error(self.process.returncode)
        return RuntimeError(reason or title + " " + "\n".join(self.output).strip())

    def wait_ready(self, timeout=120):
        """Waits until the password is entered and the settings are applied."""
        if not self._read_until("READY", timeout):
            raise self._failure(_("Hardware authorization or apply failed:"))

    def commit(self, gpu_mode=None, save=True):
        """Keeps the settings. With gpu_mode, the NVIDIA boot setting starts afterwards (see finish())."""
        words = ["COMMIT"] + ([f"gpu={gpu_mode}"] if gpu_mode else []) + ([] if save else ["save=no"])
        self.process.stdin.write((" ".join(words) + "\n").encode())
        self.process.stdin.flush()
        if not self._read_until("COMMITTED", 30):
            raise self._failure(_("Hardware settings could not be saved:"))

    def finish(self):
        """Passes on the output after COMMIT (the NVIDIA step); True if the helper succeeded."""
        for line in self._lines(None):
            print(line, flush=True)
        self.process.stdin.close()
        self.process.stdout.close()
        return self.process.wait() == 0

    def rollback(self):
        if self.process.poll() is None:
            try:
                self.process.communicate(input=b"ROLLBACK\n", timeout=15)
            except (OSError, subprocess.TimeoutExpired) as exc:
                print(_("Rollback error:"), exc, file=sys.stderr)


def set_charge_limit(value):
    """Sets the battery charge limit. Returns the reason on failure, None on success."""
    return _run(hardware("--charge", value))


def set_passwordless(enabled):
    """Turns the password-free rule on or off. Returns the reason on failure, None on success."""
    return _run(hardware("--passwordless", "1" if enabled else "0"))


def _run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        return None
    return auth_error(result.returncode) or (result.stderr or result.stdout).strip() or "?"

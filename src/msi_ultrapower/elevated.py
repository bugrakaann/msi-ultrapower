"""Root yetkisi gereken yardımcıyı pkexec ile çalıştırır."""
import json
import os
import select
import subprocess
import sys

from . import paths
from .i18n import _

PYTHON = "/usr/bin/python3"
# pkexec'in çıkış kodları: parola penceresi kapatıldı / yetki verilmedi.
PKEXEC_DISMISSED = 126
PKEXEC_NOT_AUTHORIZED = 127


def hardware(*args):
    """Kurulu yardımcı (kendi polkit eylemiyle) ya da geliştirmede kaynak koddaki aynı giriş noktası."""
    if paths.INSTALLED_HELPER.exists():
        return ["pkexec", str(paths.INSTALLED_HELPER), *args]
    code = (f"import sys; sys.path.insert(0, {str(paths.SOURCE_DIR)!r}); "
            "from msi_ultrapower.privileged.hardware import entry; entry()")
    return ["pkexec", PYTHON, "-P", "-c", code, *args]  # make run


def auth_error(returncode):
    """pkexec parola aşamasında durduysa kullanıcıya anlaşılır neden; değilse None."""
    if returncode == PKEXEC_DISMISSED:
        return _("The password prompt was cancelled; nothing was changed.")
    if returncode == PKEXEC_NOT_AUTHORIZED:
        return _("Authorization failed; nothing was changed.")
    return None


class HardwareHelper:
    """privileged/hardware.py ile READY → COMMIT/ROLLBACK konuşmasını yönetir.

    Yardımcı ayarları hemen uygular ama kalıcı yapmak için COMMIT bekler. Böylece KDE tarafı
    başarısız olursa donanım da eski haline döner. NVIDIA açılış ayarı da COMMIT ile aynı
    yardımcıda yapılır; bir mod geçişi yalnızca bir kez parola ister.
    Yardımcının hata çıktısı da stdout'a katılır (initramfs çıktısı boru tıkamasın).
    """

    def __init__(self, target):
        self.process = subprocess.Popen(
            hardware(json.dumps(target)),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.output = []      # işaret satırları dışındaki çıktı (hata nedeni)
        self._buffer = b""

    def _lines(self, timeout):
        """Çıktıyı satır satır verir. Arabellek kendi elimizde: select() ile birlikte güvenli.

        timeout: yeni çıktı için en fazla beklenecek süre (sn); None sınırsız.
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
        """marker satırı gelirse True; süre dolar ya da yardımcı biterse False."""
        for line in self._lines(timeout):
            if line.strip() == marker:
                return True
            self.output.append(line)
        return False

    def _stop(self):
        """Yardımcıyı bırakır. pkexec root olarak çalıştığı için sinyal gönderilemeyebilir;
        stdin kapanınca yardımcı READY'den sonra COMMIT alamaz ve kendisi geri alır."""
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
        """Parola girilip ayarlar uygulanana kadar bekler."""
        if not self._read_until("READY", timeout):
            raise self._failure(_("Hardware authorization or apply failed:"))

    def commit(self, gpu_mode=None, save=True):
        """Ayarları kalıcı yapar. gpu_mode verilirse NVIDIA açılış ayarı ardından başlar (finish())."""
        words = ["COMMIT"] + ([f"gpu={gpu_mode}"] if gpu_mode else []) + ([] if save else ["save=no"])
        self.process.stdin.write((" ".join(words) + "\n").encode())
        self.process.stdin.flush()
        if not self._read_until("COMMITTED", 30):
            raise self._failure(_("Hardware settings could not be saved:"))

    def finish(self):
        """COMMIT sonrası çıktıyı (NVIDIA adımı) aktarır; yardımcı başarıyla bittiyse True."""
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
    """Pilin şarj sınırını ayarlar. Başarısızsa nedeni, başarılıysa None."""
    return _run(hardware("--sarj", value))


def set_passwordless(enabled):
    """Parolasız geçiş kuralını açar/kapatır. Başarısızsa nedeni, başarılıysa None."""
    return _run(hardware("--parolasiz", "1" if enabled else "0"))


def _run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        return None
    return auth_error(result.returncode) or (result.stderr or result.stdout).strip() or "?"

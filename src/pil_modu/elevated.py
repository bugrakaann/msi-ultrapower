"""Root yetkisi gereken yardımcıları pkexec ile çalıştırır."""
import json
import select
import subprocess

from . import paths

PYTHON = "/usr/bin/python3"


class HardwareHelper:
    """privileged/hardware.py ile READY → COMMIT/ROLLBACK konuşmasını yönetir.

    Yardımcı ayarları hemen uygular ama kalıcı yapmak için COMMIT bekler.
    Böylece KDE tarafı başarısız olursa donanım da eski haline döner.
    """

    def __init__(self, target):
        self.process = subprocess.Popen(
            ["pkexec", PYTHON, str(paths.HARDWARE_HELPER), json.dumps(target)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def wait_ready(self, timeout=120):
        """Parola girilip ayarlar uygulanana kadar bekler."""
        readable, _, _ = select.select([self.process.stdout], [], [], timeout)
        if not readable or self.process.stdout.readline().strip() != "READY":
            if self.process.poll() is None:
                self.process.terminate()
            error = self.process.communicate(timeout=10)[1]
            raise RuntimeError("Donanım yetkilendirmesi/uygulaması başarısız: " + error)

    def commit(self):
        self.process.stdin.write("COMMIT\n")
        self.process.stdin.flush()
        _, error = self.process.communicate(timeout=10)
        if self.process.returncode:
            raise RuntimeError(error)

    def rollback(self):
        if self.process.poll() is None:
            self.process.communicate(input="ROLLBACK\n", timeout=15)


def configure_gpu_boot(mode):
    """Sonraki açılışın GPU modunu hazırlar. Başarılıysa True."""
    result = subprocess.run(["pkexec", PYTHON, str(paths.GPU_BOOT_HELPER), mode])
    return result.returncode == 0

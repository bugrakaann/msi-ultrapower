"""Sistemin anlık durumunu okur (pil, NVIDIA, EC). Hiçbir şey yazmaz."""
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .privileged import gpu_boot
from .privileged import hardware as hw

NVIDIA_DEVICE = Path(hw.GPU + "0")


def read(path, default="—"):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


@dataclass
class Battery:
    status: str          # Charging, Discharging, Full, Not charging…
    capacity: int | None
    watts: float | None  # pilden ölçülen güç; okunamazsa None

    @property
    def discharging(self):
        return self.status == "Discharging"


def battery():
    folder = next(iter(sorted(paths.POWER_SUPPLY_DIR.glob("BAT*"))), None)
    if folder is None:
        return None
    capacity = read(folder / "capacity")
    try:
        if (folder / "power_now").exists():
            watts = abs(int(read(folder / "power_now"))) / 1e6
        else:
            watts = abs(int(read(folder / "voltage_now")) * int(read(folder / "current_now"))) / 1e12
    except ValueError:
        watts = None
    return Battery(read(folder / "status"), int(capacity) if capacity.isdigit() else None, watts)


@dataclass
class Gpu:
    present: bool            # NVIDIA PCI aygıtı şu an var mı
    runtime: str             # suspended / active / …
    blocked_next_boot: bool  # sonraki açılışta devre dışı olacak mı

    @property
    def reboot_pending(self):
        """Seçilen GPU modu ancak yeniden başlatınca geçerli olacaksa True."""
        return self.blocked_next_boot == self.present


def gpu():
    return Gpu(NVIDIA_DEVICE.exists(),
               read(NVIDIA_DEVICE / "power/runtime_status", "yok"),
               gpu_boot.MOD.exists())


def ec_shift_mode():
    return read(hw.EC + "shift_mode")


def turbo_enabled():
    value = read(hw.CPU + "no_turbo")
    return None if value not in ("0", "1") else value == "0"

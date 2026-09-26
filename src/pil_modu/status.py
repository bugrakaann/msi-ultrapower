"""Sistemin anlık durumunu okur (pil, NVIDIA, EC). Hiçbir şey yazmaz."""
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .privileged import gpu_boot
from .privileged import hardware as hw

NVIDIA_DEVICE = Path(hw.NVIDIA_GPU) if hw.NVIDIA_GPU else None


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
    present = NVIDIA_DEVICE is not None and NVIDIA_DEVICE.exists()
    return Gpu(present,
               read(NVIDIA_DEVICE / "power/runtime_status", "yok") if present else "yok",
               gpu_boot.MOD.exists())


def ec_shift_mode():
    return read(hw.EC + "shift_mode")


def turbo_enabled():
    value = read(hw.CPU + "no_turbo")
    if value in ("0", "1"):
        return value == "0"
    value = read(hw.BOOST)
    return None if value not in ("0", "1") else value == "1"


def charge_limits():
    """(başlangıç, bitiş) şarj eşikleri; desteklenmiyorsa bitiş None."""
    start, end = read(hw.CHARGE_START), read(hw.CHARGE_LIMIT)
    return (int(start) if start.isdigit() else None, int(end) if end.isdigit() else None)


@dataclass
class Sensors:
    cpu_temp: int | None     # °C
    gpu_temp: int | None
    cpu_fan: int | None      # msi-ec: yüzde
    gpu_fan: int | None


def _int(path):
    value = read(path, "")
    return int(value) if value.lstrip("-").isdigit() else None


def _hwmon_temp(names):
    """msi-ec yoksa işlemci sıcaklığı için coretemp/k10temp (millidereceden dereceye)."""
    for folder in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
        if read(folder / "name", "") in names:
            value = _int(folder / "temp1_input")
            return round(value / 1000) if value is not None else None
    return None


def sensors():
    return Sensors(
        cpu_temp=_int(hw.EC + "cpu/realtime_temperature") or _hwmon_temp(("coretemp", "k10temp")),
        gpu_temp=_int(hw.EC + "gpu/realtime_temperature"),
        cpu_fan=_int(hw.EC + "cpu/realtime_fan_speed"),
        gpu_fan=_int(hw.EC + "gpu/realtime_fan_speed"),
    )

"""Bu bilgisayarda hangi ayarların yapılabildiğini bulur. Hiçbir şey yazmaz.

MSI modelleri arasında EC modları, fan modları, ekran Hz'leri ve NVIDIA'nın
varlığı değişir. Modlar buradaki bilgiyle makineye uyarlanır.
"""
from dataclasses import dataclass
from pathlib import Path

from . import display
from .privileged import gpu_boot
from .privileged import hardware as hw


def read(path, default=""):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def shift_modes():
    """EC'nin kabul ettiği shift modları; msi-ec yoksa boş."""
    if not Path(hw.EC + "shift_mode").exists():
        return ()
    listed = read(hw.EC + "available_shift_modes").split()
    return tuple(m for m in hw.SHIFT_MODES if m in listed) if listed else hw.SHIFT_MODES


def fan_modes():
    if not Path(hw.EC + "fan_mode").exists():
        return ()
    listed = read(hw.EC + "available_fan_modes").split()
    return tuple(m for m in hw.FAN_MODES if m in listed) if listed else hw.FAN_MODES


def nearest_shift(wanted, available):
    """İstenen mod yoksa ona en yakın olanı (eşitlikte daha tasarruflu olanı) seçer."""
    if not available or wanted in available:
        return wanted if available else None
    order = hw.SHIFT_MODES
    return min(available, key=lambda m: (abs(order.index(m) - order.index(wanted)), order.index(m)))


@dataclass(frozen=True)
class Capabilities:
    model: str
    shift_modes: tuple
    fan_modes: tuple
    cooler_boost: bool
    turbo: bool
    keyboard_light: bool
    nvidia: bool           # NVIDIA var mı (şu an çalışıyor ya da açılışta engellenmiş)
    charge_limit: bool
    panel_rates: tuple     # dahili ekranın Hz'leri; bilinmiyorsa boş
    runtime_pm: int        # güç yönetimi yapılabilen PCI aygıtı sayısı
    sound_power_save: bool
    bluetooth: bool

    @property
    def ec(self):
        return bool(self.shift_modes)


def detect(outputs=None):
    """outputs: kscreen-doctor çıktısı (Hz'leri bulmak için); verilmezse Hz bilinmez."""
    vendor = read("/sys/class/dmi/id/sys_vendor")
    product = read("/sys/class/dmi/id/product_name")
    return Capabilities(
        model=" ".join(x for x in ("MSI" if "Micro-Star" in vendor else vendor, product) if x),
        shift_modes=shift_modes(),
        fan_modes=fan_modes(),
        cooler_boost=Path(hw.EC + "cooler_boost").exists(),
        turbo=Path(hw.CPU + "no_turbo").exists() or Path(hw.BOOST).exists(),
        keyboard_light=Path(hw.LED).exists(),
        nvidia=hw.NVIDIA_GPU is not None or gpu_boot.MOD.exists(),
        charge_limit=Path(hw.CHARGE_LIMIT).exists(),
        panel_rates=tuple(display.panel_rates(outputs or [])),
        runtime_pm=len(hw.RUNTIME_PM),
        sound_power_save=Path(hw.SOUND_POWER_SAVE).exists(),
        bluetooth=bool(hw.BLUETOOTH),
    )


def unsupported_reason(preset, caps):
    """Mod bu bilgisayarda uygulanamıyorsa nedeni, uygulanabiliyorsa None."""
    if preset.fan != "auto" and caps.ec and preset.fan not in caps.fan_modes:
        return f"EC “{preset.fan}” fan modunu desteklemiyor"
    if preset.fan == "advanced" and not caps.ec:
        return "Manuel fan için msi-ec sürücüsü gerekli"
    if preset.panel == "min" and len(caps.panel_rates) == 1:
        return f"Dahili ekran yalnızca {caps.panel_rates[0]} Hz destekliyor"
    return None

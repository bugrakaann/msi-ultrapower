"""Bu bilgisayarda hangi ayarların yapılabildiğini bulur. Hiçbir şey yazmaz.

MSI modelleri arasında EC modları, fan modları, ekran Hz'leri ve NVIDIA'nın
varlığı değişir. Modlar buradaki bilgiyle makineye uyarlanır.
"""
import glob
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import display
from .i18n import _
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


# ppd ile aynı işi yapan ve onunla çakışan güç yöneticileri.
CONFLICTING_SERVICES = ("tlp", "auto-cpufreq", "tuned", "system76-power", "powertop")


def conflicts():
    """Çalışan çakışan servislerin adları."""
    if not shutil.which("systemctl"):
        return ()
    found = []
    for name in CONFLICTING_SERVICES:
        result = subprocess.run(["systemctl", "is-active", "--quiet", name + ".service"])
        if result.returncode == 0:
            found.append(name)
    return tuple(found)


def nvidia_outputs():
    """NVIDIA'ya bağlı ekran çıkışlarının adları (kscreen adlarıyla aynı: HDMI-A-1 gibi)."""
    names = []
    for connector in glob.glob("/sys/class/drm/card*-*"):
        if read(Path(connector, "device", "device", "vendor")) == "0x10de":
            names.append(Path(connector).name.split("-", 1)[1])
    return tuple(sorted(names))


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
    screen: bool = True           # kscreen-doctor ile ekran ayarlanabiliyor mu (KDE Plasma)
    brightness: bool = True       # parlaklık ayarlanabiliyor mu (Plasma 6.1+)
    nvidia_outputs: tuple = ()    # NVIDIA'ya bağlı çıkışlar; batarya modunda kapanır
    conflicts: tuple = ()         # ppd ile çakışan çalışan servisler
    ec_firmware: str = ""

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
        screen=bool(outputs),
        brightness=any("brightness" in o for o in outputs or []),
        nvidia_outputs=nvidia_outputs(),
        conflicts=conflicts(),
        ec_firmware=read(hw.EC + "fw_version"),
    )


def unsupported_reason(preset, caps):
    """Mod bu bilgisayarda uygulanamıyorsa nedeni, uygulanabiliyorsa None."""
    if preset.fan != "auto" and caps.ec and preset.fan not in caps.fan_modes:
        return _("the EC does not support the “{fan}” fan mode").format(fan=preset.fan)
    if preset.fan == "advanced" and not caps.ec:
        return _("manual fan needs the msi-ec driver")
    if preset.panel == "min" and len(caps.panel_rates) == 1:
        return _("the built-in display only supports {hz} Hz").format(hz=caps.panel_rates[0])
    return None

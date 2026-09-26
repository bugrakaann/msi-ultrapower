"""Bir mod geçişinde neyin değişeceğini hesaplar (hiçbir şeyi uygulamaz)."""
from dataclasses import dataclass
from pathlib import Path

from . import display
from .presets import PRESETS
from .privileged import hardware as hw


@dataclass
class Plan:
    mode: str
    restoring: bool
    profile: str         # hedef powerprofilesctl profili
    screen_args: list    # kscreen-doctor argümanları
    rollback_args: list  # hata olursa ekranı eski haline döndüren argümanlar
    hardware: dict       # sysfs yolu -> değer
    gpu_boot: str        # "integrated" ya da "hybrid"


def hardware_plan(original, preset):
    result = dict(original)
    result.update({
        hw.EC + "shift_mode": preset.shift,
        hw.EC + "fan_mode": preset.fan,
        hw.EC + "cooler_boost": preset.boost,
        hw.CPU + "no_turbo": preset.turbo,
    })
    for i in range(4):
        path = hw.GPU + str(i) + "/power/control"
        if Path(path).exists():
            result[path] = preset.gpu if i == 0 else "auto"
        else:
            result.pop(path, None)
    if preset.is_battery and hw.LED in result:
        result[hw.LED] = "0"
    return result


def build(mode, external, before, original):
    """before: şu anki anlık görüntü, original: ilk moddan önce kaydedilen görüntü."""
    preset = PRESETS.get(mode)
    restoring = preset is None
    if restoring:
        hardware = hw.writable(original["hardware"])
    else:
        hardware = hardware_plan(original["hardware"], preset)
    # NVIDIA devre dışıyken GPU dosyaları yoktur; onları atla.
    hardware = {k: v for k, v in hardware.items() if not k.startswith(hw.GPU) or Path(k).exists()}
    hw.validate(hardware)

    return Plan(
        mode=mode,
        restoring=restoring,
        profile=original["profile"] if restoring else preset.profile,
        screen_args=display.screen_plan(before["outputs"], original["outputs"], preset, external),
        rollback_args=display.screen_plan(before["outputs"], before["outputs"]),
        hardware=hardware,
        gpu_boot="integrated" if preset and preset.is_battery else "hybrid",
    )


def verify_hardware(plan, actual):
    for path, value in plan.hardware.items():
        if actual.get(path) != value:
            raise RuntimeError("Donanım ayarı değişti: " + path)

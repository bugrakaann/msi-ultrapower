"""Bir mod geçişinde neyin değişeceğini hesaplar (hiçbir şeyi uygulamaz)."""
from dataclasses import dataclass
from pathlib import Path

from . import capabilities, display
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


def mode_settings(preset):
    """Modun bu bilgisayarda yazılacak değerleri; olmayan ayarlar atlanır."""
    wanted = {
        hw.EC + "shift_mode": capabilities.nearest_shift(preset.shift, capabilities.shift_modes()),
        hw.EC + "fan_mode": preset.fan,
        hw.EC + "cooler_boost": preset.boost,
        hw.CPU + "no_turbo": preset.turbo,
        hw.BOOST: "1" if preset.turbo == "0" else "0",
        **{path: "auto" for path in hw.GPU_PM},
    }
    if hw.NVIDIA_GPU:
        wanted[hw.NVIDIA_GPU + "/power/control"] = preset.gpu
    return {path: value for path, value in wanted.items() if value and Path(path).exists()}


def hardware_plan(original, preset):
    result = dict(original)
    result.update(mode_settings(preset))
    if preset.is_battery:
        result.update(battery_savings(result))
    return result


def battery_savings(current):
    """TLP'nin pilde yaptığı aygıt tasarrufları; yalnızca bu sistemde bulunan ayarlar."""
    wanted = {
        hw.LED: "0",
        hw.SOUND_POWER_SAVE: "1",   # 1 sn sessizlikten sonra ses kartı uyur
        hw.DIRTY_WRITEBACK: "6000", # diske 60 sn'de bir yaz; disk daha uzun uyur
        **{path: "auto" for path in hw.RUNTIME_PM},
        **{path: "1" for path in hw.BLUETOOTH},
    }
    return {path: value for path, value in wanted.items() if path in current}


def build(mode, external, before, original):
    """before: şu anki anlık görüntü, original: ilk moddan önce kaydedilen görüntü."""
    preset = PRESETS.get(mode)
    restoring = preset is None
    if preset:
        reason = capabilities.unsupported_reason(preset, capabilities.detect(before["outputs"]))
        if reason:
            raise RuntimeError(f"{preset.title} bu bilgisayarda kullanılamıyor: {reason}")
    if restoring:
        hardware = hw.writable(original["hardware"])
    else:
        hardware = hardware_plan(original["hardware"], preset)
    # NVIDIA devre dışıyken GPU dosyaları yoktur; çıkarılan aygıtlar da. Onları atla.
    hardware = {k: v for k, v in hardware.items() if Path(k).exists()}
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

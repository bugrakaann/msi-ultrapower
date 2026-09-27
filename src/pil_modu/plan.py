"""Bir mod geçişinde neyin değişeceğini hesaplar (hiçbir şeyi uygulamaz)."""
from dataclasses import dataclass
from pathlib import Path

from . import capabilities, display, settings
from .i18n import _
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


def hardware_plan(original, preset, options=None):
    """options: settings.load() sözlüğü; verilmezse varsayılanlar."""
    options = {**settings.DEFAULTS, **(options or {})}
    result = dict(original)
    result.update(mode_settings(preset))
    if preset.is_battery:
        result.update(battery_savings(result, options))
    return result


def battery_savings(current, options=settings.DEFAULTS):
    """TLP'nin pilde yaptığı aygıt tasarrufları; yalnızca bu sistemde bulunan ayarlar."""
    wanted = {hw.LED: "0"}
    if options["device_savings"]:
        wanted.update({
            hw.SOUND_POWER_SAVE: "1",    # 1 sn sessizlikten sonra ses kartı uyur
            hw.DIRTY_WRITEBACK: "6000",  # diske 60 sn'de bir yaz; disk daha uzun uyur
            **{path: "auto" for path in hw.RUNTIME_PM},
        })
    if options["bluetooth_off_on_battery"]:
        wanted.update({path: "1" for path in hw.BLUETOOTH})
    return {path: value for path, value in wanted.items() if path in current}


def build(mode, external, before, original, options=None, caps=None, layouts=None):
    """before: şu anki anlık görüntü, original: ilk moddan önce kaydedilen görüntü."""
    preset = PRESETS.get(mode)
    restoring = preset is None
    caps = caps or capabilities.detect(before["outputs"])
    if preset:
        reason = capabilities.unsupported_reason(preset, caps)
        if reason:
            raise RuntimeError(_("{mode} is not available on this computer: {reason}").format(
                mode=preset.title, reason=reason))
    if restoring:
        hardware = hw.writable(original["hardware"])
    else:
        hardware = hardware_plan(original["hardware"], preset, options)
    # NVIDIA devre dışıyken GPU dosyaları yoktur; çıkarılan aygıtlar da. Onları atla.
    hardware = {k: v for k, v in hardware.items() if Path(k).exists()}
    hw.validate(hardware)

    return Plan(
        mode=mode,
        restoring=restoring,
        profile=original["profile"] if restoring else preset.profile,
        screen_args=display.screen_plan(before["outputs"], original["outputs"], preset, external,
                                        caps.nvidia_outputs, layouts),
        rollback_args=display.screen_plan(before["outputs"], before["outputs"]),
        hardware=hardware,
        gpu_boot="integrated" if preset and preset.is_battery else "hybrid",
    )


def verify_hardware(plan, actual):
    for path, value in plan.hardware.items():
        if actual.get(path) != value:
            raise RuntimeError(_("A hardware setting did not stick: {path}").format(path=path))

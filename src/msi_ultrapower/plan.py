"""Works out what a mode switch will change (applies nothing)."""
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
    profile: str         # target powerprofilesctl profile
    screen_args: list    # kscreen-doctor arguments
    rollback_args: list  # arguments that put the displays back on failure
    hardware: dict       # sysfs path -> value
    gpu_boot: str        # "integrated" or "hybrid"


def mode_settings(preset):
    """Values the mode writes on this laptop; missing settings are skipped."""
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
    """options: the settings.load() dictionary; defaults if not given."""
    options = {**settings.DEFAULTS, **(options or {})}
    result = dict(original)
    result.update(mode_settings(preset))
    if preset.is_battery:
        result.update(battery_savings(result, options))
    if not options["bluetooth_off_on_battery"]:
        # With the option off, Bluetooth belongs to the user; it is not reset to the first snapshot either.
        for path in hw.BLUETOOTH:
            result.pop(path, None)
    return result


def battery_savings(current, options=settings.DEFAULTS):
    """Device power savings TLP makes on battery; only settings present on this system."""
    wanted = {hw.LED: "0"}
    if options["device_savings"]:
        wanted.update({
            hw.SOUND_POWER_SAVE: "1",    # the sound card sleeps after 1 s of silence
            hw.DIRTY_WRITEBACK: "6000",  # write to disk every 60 s so the disk sleeps longer
            **{path: "auto" for path in hw.RUNTIME_PM},
        })
    if options["bluetooth_off_on_battery"]:
        wanted.update({path: "1" for path in hw.BLUETOOTH})
    return {path: value for path, value in wanted.items() if path in current}


def build(mode, external, before, original, options=None, caps=None, layouts=None):
    """before: the current snapshot; original: the snapshot saved before the first mode."""
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
    # With NVIDIA disabled its files do not exist, nor do removed devices. Skip them.
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

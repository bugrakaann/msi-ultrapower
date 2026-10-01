"""Turns what a mode changes on this laptop into readable text.

Feeds the details panel and the card tooltips. The text follows the same rules as
what plan.py actually does.
"""
from html import escape

from . import capabilities, settings
from .i18n import _, ngettext, percent
from .privileged import hardware as hw


def profile_name(profile):
    return {"performance": _("Performance"), "balanced": _("Balanced"),
            "power-saver": _("Power saver")}.get(profile, profile)


def fan_name(fan):
    return {"auto": _("Automatic"), "silent": _("Silent"), "basic": _("Basic"),
            "advanced": _("Custom curve (MControlCenter)")}.get(fan, fan)


def on_off(value):
    return _("On") if value else _("Off")


def _panel_hz(preset, caps):
    if not caps.panel_rates:
        return _("Highest refresh rate") if preset.panel == "max" else _("Lowest refresh rate")
    if preset.panel == "max":
        return _("{hz} Hz (highest)").format(hz=max(caps.panel_rates))
    return _("{hz} Hz (lowest)").format(hz=min(caps.panel_rates))


def _external(preset, caps):
    if preset.is_battery and caps.nvidia_outputs:
        return _("Outputs wired to NVIDIA ({outputs}) turn off · others follow your choice").format(
            outputs=", ".join(caps.nvidia_outputs))
    return _("Follows your choice below · refresh rate unchanged")


def describe(preset, caps, options=None):
    """[(section, [(setting, value), ...]), ...]"""
    options = {**settings.DEFAULTS, **(options or {})}
    if caps.screen:
        screen = [(_("Built-in display"), _panel_hz(preset, caps)),
                  (_("Brightness"), percent(preset.brightness) if caps.brightness
                   else _("Unchanged (needs Plasma 6.1+)")),
                  (_("External displays"), _external(preset, caps))]
    else:
        screen = [(_("Displays"), _("Unchanged (needs KDE Plasma 6)"))]

    cpu = [(_("Power profile"), profile_name(preset.profile)),
           (_("CPU turbo"), on_off(preset.turbo == "0") if caps.turbo
            else _("Not adjustable on this system"))]

    if caps.ec:
        shift = capabilities.nearest_shift(preset.shift, caps.shift_modes)
        ec = [(_("EC mode"), shift if shift == preset.shift
               else _("{mode} ({wanted} not available)").format(mode=shift, wanted=preset.shift)),
              (_("Fan"), fan_name(preset.fan))]
        if caps.cooler_boost:
            ec.append(("Cooler Boost", on_off(preset.boost == "on")))
    else:
        ec = [("MSI EC", _("No msi-ec driver · fan and EC mode are skipped"))]

    if caps.nvidia:
        gpu = [(_("NVIDIA now"), _("Always awake") if preset.gpu == "on" else _("Sleeps when idle")),
               (_("NVIDIA at boot"), _("Fully off · needs a restart") if preset.is_battery
                else _("Available"))]
    else:
        gpu = [("NVIDIA", _("No NVIDIA GPU"))]

    if preset.is_battery:
        devices = []
        if caps.keyboard_light:
            devices.append((_("Keyboard backlight"), _("Off")))
        if options["device_savings"]:
            if caps.runtime_pm:
                devices.append((_("PCI devices"), ngettext(
                    "{count} device sleeps when idle", "{count} devices sleep when idle",
                    caps.runtime_pm).format(count=caps.runtime_pm)))
            if caps.sound_power_save:
                devices.append((_("Sound card"), _("Sleeps after 1 s of silence")))
            devices.append((_("Disk writes"), _("Every 60 s (the disk sleeps longer)")))
        else:
            devices.append((_("Device power saving"), _("Off (can be enabled in settings)")))
        if caps.bluetooth:
            devices.append(("Bluetooth", _("Off") if options["bluetooth_off_on_battery"]
                            else _("Unchanged")))
    else:
        devices = [(_("Keyboard backlight"), _("Back to how it was before the first mode")),
                   (_("PCI, sound, Bluetooth, disk"), _("Back to how it was before the first mode"))]

    return [(_("Display"), screen), (_("Processor"), cpu), (_("Fan and EC"), ec),
            (_("Graphics"), gpu), (_("Devices"), devices)]


def restore_sections():
    return [(_("Restored"), [
        (_("Power profile"), _("The profile before the first mode")),
        (_("Displays"), _("Previous layout, refresh rate, scale and brightness")),
        (_("Processor and EC"), _("Previous turbo, EC mode, fan and Cooler Boost")),
        (_("Devices"), _("Previous keyboard backlight, PCI, sound, Bluetooth and disk settings")),
        ("NVIDIA", _("Available after a restart")),
        (_("Charge limit"), _("Unchanged (separate setting)")),
    ])]


def _hardware_changes(target, current):
    """Turns sysfs differences into readable rows; PCI devices are grouped into one row."""
    rows = []
    changed = {p: v for p, v in target.items() if current.get(p) != v}
    labels = {
        hw.EC + "shift_mode": (_("EC mode"), str),
        hw.EC + "fan_mode": (_("Fan"), fan_name),
        hw.EC + "cooler_boost": ("Cooler Boost", lambda v: on_off(v == "on")),
        hw.CPU + "no_turbo": (_("CPU turbo"), lambda v: on_off(v == "0")),
        hw.BOOST: (_("CPU turbo"), lambda v: on_off(v == "1")),
        hw.LED: (_("Keyboard backlight"), lambda v: _("Off") if v == "0"
                 else _("Level {level}").format(level=v)),
        hw.SOUND_POWER_SAVE: (_("Sound card power saving"), lambda v: on_off(v != "0")),
        hw.DIRTY_WRITEBACK: (_("Disk writes"), lambda v: _("Every {seconds} s").format(
            seconds=int(v) // 100) if v.isdigit() else v),
    }
    if hw.NVIDIA_GPU:
        labels[hw.NVIDIA_GPU + "/power/control"] = (
            _("NVIDIA now"), lambda v: _("Always awake") if v == "on" else _("Sleeps when idle"))
    for path, (label, show) in labels.items():
        if path in changed:
            rows.append((label, show(current[path]) if path in current else "—", show(changed[path])))

    pci = [p for p in changed if p in hw.RUNTIME_PM]
    if pci:
        sleeping = sum(changed[p] == "auto" for p in pci)
        count = ngettext("{count} device", "{count} devices", len(pci)).format(count=len(pci))
        old, new = (_("Off"), _("On")) if sleeping * 2 >= len(pci) else (_("On"), _("Off"))
        rows.append((_("PCI power saving"), old, f"{new} · {count}"))
    if any(p in hw.BLUETOOTH for p in changed):
        blocked = next(changed[p] for p in changed if p in hw.BLUETOOTH) == "1"
        rows.append(("Bluetooth", on_off(blocked), on_off(not blocked)))
    return rows


def _screen_changes(args, outputs):
    rows = []
    by_name = {o["name"]: o for o in outputs}
    for arg in args:
        _prefix, name, setting, *value = arg.split(".")
        value = ".".join(value)
        output = by_name.get(name)
        if output is None:
            continue
        if setting in ("enable", "disable") and output["enabled"] != (setting == "enable"):
            rows.append((name, on_off(output["enabled"]), on_off(setting == "enable")))
        elif setting == "mode" and value != output["currentModeId"]:
            modes = {m["id"]: m for m in output["modes"]}
            old, new = modes.get(output["currentModeId"]), modes.get(value)
            if old and new and round(old["refreshRate"]) != round(new["refreshRate"]):
                rows.append((_("{output} refresh rate").format(output=name),
                             f"{round(old['refreshRate'])} Hz", f"{round(new['refreshRate'])} Hz"))
        elif setting == "brightness" and "brightness" in output:
            old = round(output["brightness"] * 100)
            if abs(old - int(value)) > 1:
                rows.append((_("{output} brightness").format(output=name), percent(old), percent(value)))
    return rows


def changes(plan, before, nvidia_blocked_next_boot=False):
    """Settings the plan changes compared with now: [(setting, old, new), ...]"""
    rows = []
    if plan.profile != before["profile"]:
        rows.append((_("Power profile"), profile_name(before["profile"]), profile_name(plan.profile)))
    rows += _screen_changes(plan.screen_args, before["outputs"])
    rows += _hardware_changes(plan.hardware, before["hardware"])
    if (plan.gpu_boot == "integrated") != nvidia_blocked_next_boot and (hw.NVIDIA_GPU or nvidia_blocked_next_boot):
        rows.append((_("NVIDIA at boot"),
                     _("Off") if nvidia_blocked_next_boot else _("Available"),
                     _("Off (after a restart)") if plan.gpu_boot == "integrated" else _("Available")))
    return rows


def to_html(title, sections, note=None):
    """Rich text for a card tooltip."""
    rows = []
    for section, items in sections:
        rows.append(f"<tr><td colspan=2 style='padding-top:6px'><b>{escape(section)}</b></td></tr>")
        rows += [f"<tr><td style='padding-right:12px'>{escape(k)}</td><td>{escape(v)}</td></tr>"
                 for k, v in items]
    note_html = f"<p style='color:#da4453'>{escape(note)}</p>" if note else ""
    return f"<p><b>{escape(title)}</b></p>{note_html}<table cellspacing=0>{''.join(rows)}</table>"

"""Bir modun bu bilgisayarda neyi değiştireceğini okunur metne çevirir.

Arayüzdeki ayrıntı paneli ve kartların ipucu (hover) buradan beslenir. Metinler
plan.py'nin gerçekte yaptığıyla aynı kuralları izler.
"""
from html import escape

from . import capabilities, settings
from .i18n import _, ngettext


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
    """[(bölüm, [(ayar, değer), ...]), ...]"""
    options = {**settings.DEFAULTS, **(options or {})}
    if caps.screen:
        screen = [(_("Built-in display"), _panel_hz(preset, caps)),
                  (_("Brightness"), f"{preset.brightness}%" if caps.brightness
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


def to_html(title, sections, note=None):
    """Kart ipucu için zengin metin."""
    rows = []
    for section, items in sections:
        rows.append(f"<tr><td colspan=2 style='padding-top:6px'><b>{escape(section)}</b></td></tr>")
        rows += [f"<tr><td style='padding-right:12px'>{escape(k)}</td><td>{escape(v)}</td></tr>"
                 for k, v in items]
    note_html = f"<p style='color:#da4453'>{escape(note)}</p>" if note else ""
    return f"<p><b>{escape(title)}</b></p>{note_html}<table cellspacing=0>{''.join(rows)}</table>"

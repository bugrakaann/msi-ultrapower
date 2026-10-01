"""Komut satırı arayüzü:  msi-ultrapower <mod> [--harici ...] [--dene]  ·  msi-ultrapower sarj [60|80|100]

Türkçe ve İngilizce komut adları birlikte çalışır (presets.ALIASES).
"""
import argparse
import fcntl
import sys

from . import __version__, capabilities, controller, paths, state, status, system
from .i18n import _, ngettext, percent
from .presets import ALIASES, EXTERNAL_ALIASES, EXTERNAL_CHOICES, PRESETS, RESTORE_COMMANDS
from .privileged import hardware as hw

COMMANDS = [*PRESETS, *RESTORE_COMMANDS, "durum", "sarj", "doctor", "passwordless"]


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="msi-ultrapower", description=_("Power modes for MSI laptops on KDE Plasma."))
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("mod", metavar="command", choices=[*COMMANDS, *ALIASES],
                        help=_("mode, restore, status, charge or doctor") + ": "
                        + ", ".join(sorted({*COMMANDS, *ALIASES})))
    parser.add_argument("sinir", metavar="value", nargs="?",
                        help=_("charge: 60, 80 or 100 · passwordless: on or off"))
    parser.add_argument("--harici", "--external", dest="harici", default="otomatik",
                        choices=[*EXTERNAL_CHOICES, *EXTERNAL_ALIASES],
                        help=_("external displays: auto, keep or off"))
    parser.add_argument("--dene", "--dry-run", dest="dene", action="store_true",
                        help=_("show the plan without changing anything"))
    parser.add_argument("--gpu-koru", "--keep-gpu", dest="gpu_koru", action="store_true",
                        help=_("do not change the NVIDIA boot setting (used by automatic mode)"))
    opt = parser.parse_args(argv)
    opt.mod = ALIASES.get(opt.mod, opt.mod)
    opt.harici = EXTERNAL_ALIASES.get(opt.harici, opt.harici)
    return opt


def print_status():
    snapshot = system.capture()
    active = state.load_active()
    print(_("Selected mode:"), active["mod"] if active else _("none yet"))
    print(_("Power profile:"), snapshot["profile"])
    for output in snapshot["outputs"]:
        if output["connected"]:
            mode = next((m for m in output["modes"] if m["id"] == output["currentModeId"]), {})
            print(output["name"], _("on") if output["enabled"] else _("off"), mode.get("name", ""),
                  _("brightness"), output.get("brightness"))
    for path, value in snapshot["hardware"].items():
        print(path.removeprefix("/sys/"), "=", value)

    gpu = status.gpu()
    print(_("NVIDIA now:"), gpu.runtime if gpu.present else _("no PCI device / disabled"))
    print(_("NVIDIA next boot:"), _("disabled") if gpu.blocked_next_boot else _("available"))

    bat = status.battery()
    if bat:
        print(_("Battery:"), bat.status, percent(bat.capacity))
        start, end = status.charge_limits()
        if end is not None:
            print(_("Charge limit:"), percent(end),
                  _("(charging resumes below {start}%)").format(start=start) if start else "")
        if bat.watts is not None:
            label = _("Battery discharge power:") if bat.discharging \
                else _("Battery charge current power (not system usage):")
            print(label, round(bat.watts, 2), "W")


def print_doctor():
    """Uyumluluk raporu: hangi özellik var, hangisi neden yok. Hata bildirimine eklenir."""
    caps = capabilities.detect(system.get_outputs())
    plasma = system.plasma_version()
    yes = {True: _("yes"), False: _("NO")}
    rows = [
        (_("Model"), caps.model or "?"),
        ("KDE Plasma", plasma or _("NO (display settings are skipped)")),
        (_("Display control (kscreen-doctor)"), yes[caps.screen]),
        (_("Brightness control"), yes[caps.brightness]),
        (_("Panel refresh rates"), ", ".join(f"{hz} Hz" for hz in caps.panel_rates) or "?"),
        ("msi-ec", _("yes · firmware {version}").format(version=caps.ec_firmware or "?") if caps.ec
         else _("NO (fan/EC settings are skipped; AUR: msi-ec-dkms-git)")),
        (_("EC modes"), ", ".join(caps.shift_modes) or "—"),
        (_("Fan modes"), ", ".join(caps.fan_modes) or "—"),
        ("Cooler Boost", yes[caps.cooler_boost]),
        (_("CPU turbo control"), yes[caps.turbo]),
        (_("Keyboard backlight"), yes[caps.keyboard_light]),
        (_("Charge limit"), yes[caps.charge_limit]),
        ("NVIDIA", yes[caps.nvidia]),
        (_("Outputs wired to NVIDIA"), ", ".join(caps.nvidia_outputs) or "—"),
        (_("PCI power management"), ngettext("{count} device", "{count} devices",
                                             caps.runtime_pm).format(count=caps.runtime_pm)),
        (_("Audio power saving"), yes[caps.sound_power_save]),
        ("Bluetooth", yes[caps.bluetooth]),
        (_("Conflicting services"), ", ".join(caps.conflicts) or _("none")),
    ]
    width = max(len(k) for k, _v in rows)
    for key, value in rows:
        print(f"{key:<{width}}  {value}")
    for preset in PRESETS.values():
        reason = capabilities.unsupported_reason(preset, caps)
        if reason:
            print(_("Unavailable mode: {mode} ({reason})").format(mode=preset.key, reason=reason))


def main(argv=None):
    try:
        opt = parse_args(argv)
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with paths.LOCK_FILE.open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError(_("Another msi-ultrapower process is already running.")) from None
            if opt.sinir and opt.mod not in ("sarj", "passwordless"):
                raise RuntimeError(_("A value can only be used with the charge or passwordless command."))
            if opt.mod == "sarj" and opt.sinir and opt.sinir not in hw.CHARGE_LIMITS:
                raise RuntimeError(_("The charge limit must be one of: {values}").format(
                    values=", ".join(hw.CHARGE_LIMITS)))
            if opt.mod == "durum":
                print_status()
            elif opt.mod == "doctor":
                print_doctor()
            elif opt.mod == "passwordless":
                if opt.sinir not in ("on", "off"):
                    raise RuntimeError(_("Use: msi-ultrapower passwordless on|off"))
                controller.set_passwordless(opt.sinir == "on")
            elif opt.mod == "sarj":
                if opt.sinir:
                    controller.set_charge_limit(opt.sinir)
                else:
                    limit = status.charge_limits()[1]
                    print(_("Charge limit:"), percent(limit) if limit else _("not supported on this device"))
            else:
                controller.change_mode(opt.mod, opt.harici, opt.dene, keep_gpu=opt.gpu_koru)
    except Exception as exc:
        print(_("ERROR:"), exc, file=sys.stderr)
        return 1
    return 0

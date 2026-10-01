#!/usr/bin/python3
"""Prepares integrated-only or hybrid GPU mode for the next boot.

The hardware helper (hardware.py) calls configure() in the same privileged session while
applying a mode, so a mode switch asks for one password. On its own it is only for recovery.

It never removes the running GPU and never restarts the computer. It only manages the files
it created (marked with HEADER). Standard library only; imports nothing else from the package.

Recovery (TTY):  sudo /usr/lib/msi-ultrapower/msi-ultrapower-gpu-boot hybrid
"""
import gettext
import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Standard library gettext; pkexec keeps LANGUAGE/LANG, so the language matches the user's.
_ = gettext.translation("msi-ultrapower", fallback=True).gettext

HEADER = "# Managed by msi-ultrapower gpu_boot.py\n"
MOD = Path("/etc/modprobe.d/90-msi-ultrapower-nvidia.conf")
RULE = Path("/etc/udev/rules.d/50-msi-ultrapower-nvidia.rules")
INIT = Path("/etc/mkinitcpio.conf.d/99-msi-ultrapower-gpu.conf")
DRACUT = Path("/etc/dracut.conf.d/99-msi-ultrapower-gpu.conf")
BACKUP_DIR = Path("/var/lib/msi-ultrapower")
IGPU_VENDORS = ("0x8086", "0x1002")  # Intel, AMD
MODES = ("integrated", "hybrid")

MODULES = ("nvidia", "nvidia_drm", "nvidia_modeset", "nvidia_uvm",
           "nouveau", "nova_core", "nova_drm", "i2c_nvidia_gpu")

MODPROBE_TEXT = HEADER + "".join(
    f"blacklist {m}\ninstall {m} /usr/bin/false\n" for m in MODULES)

# PCI addresses differ between models, so every NVIDIA function (GPU, audio, USB-C) is removed by vendor.
UDEV_TEXT = HEADER + ('ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", '
                      'ATTR{power/control}="auto", ATTR{remove}="1"\n')

MKINITCPIO_TEXT = HEADER + '''msi_ultrapower_modules=()
for msi_ultrapower_module in "${MODULES[@]}"; do
    case "$msi_ultrapower_module" in
        nvidia*|nouveau|nova_core|nova_drm|i2c_nvidia_gpu) ;;
        *) msi_ultrapower_modules+=("$msi_ultrapower_module") ;;
    esac
done
MODULES=("${msi_ultrapower_modules[@]}")
unset msi_ultrapower_modules msi_ultrapower_module
'''

DRACUT_TEXT = HEADER + 'omit_drivers+=" ' + " ".join(MODULES) + ' "\n'

MANAGED = (MOD, RULE, INIT, DRACUT)  # every file this tool may own
NVIDIA_VENDOR = "0x10de"
INTERNAL_CONNECTORS = ("eDP", "LVDS", "DSI")


def integrated_config():
    """Files needed in "integrated" mode; in "hybrid" mode all of them are removed."""
    config = {MOD: MODPROBE_TEXT, RULE: UDEV_TEXT}
    if shutil.which("mkinitcpio"):
        config[INIT] = MKINITCPIO_TEXT
    if shutil.which("dracut"):
        config[DRACUT] = DRACUT_TEXT
    return config


def desired(mode):
    """Wanted content of every managed file in this mode (None: the file must not exist)."""
    wanted = integrated_config() if mode == "integrated" else {}
    return {p: wanted.get(p) for p in MANAGED}


def current():
    return {p: p.read_text() if p.exists() else None for p in MANAGED}


def is_configured(mode):
    """Whether the boot setting is already in this mode. The files are world-readable.

    Returns False if they cannot be read; the privileged helper decides then.
    """
    try:
        return current() == desired(mode)
    except OSError:
        return False


def write(path, content):
    """Removes the file if content is None, otherwise writes it atomically."""
    if content is None:
        path.unlink(missing_ok=True)
        return
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content)
    temp.chmod(0o644)
    temp.replace(path)


def rebuild_initramfs():
    if shutil.which("mkinitcpio"):
        subprocess.run(["mkinitcpio", "-P"], check=True)
    elif shutil.which("dracut"):
        subprocess.run(["dracut", "--regenerate-all", "--force"], check=True)
    else:
        print(_("mkinitcpio/dracut not found; boot images were not rebuilt."), flush=True)


def has_integrated_gpu():
    """Whether an Intel/AMD integrated GPU can drive the display once NVIDIA is off."""
    for device in glob.glob("/sys/bus/pci/devices/*"):
        try:
            vendor = Path(device, "vendor").read_text().strip()
            display_class = Path(device, "class").read_text().startswith("0x03")
        except OSError:
            continue
        if display_class and vendor in IGPU_VENDORS:
            return True
    return False


def internal_panel_on_nvidia():
    """On MUX models in BIOS "Discrete" mode NVIDIA drives the built-in display and cannot be turned off."""
    for connector in glob.glob("/sys/class/drm/card*-*"):
        name = Path(connector).name.split("-", 1)[1]
        if not name.startswith(INTERNAL_CONNECTORS):
            continue
        try:
            connected = Path(connector, "status").read_text().strip() == "connected"
            vendor = Path(connector, "device", "device", "vendor").read_text().strip()
        except OSError:
            continue
        if connected and vendor == NVIDIA_VENDOR:
            return True
    return False


def check_preconditions(mode):
    if mode not in MODES:
        raise ValueError(_("Invalid GPU mode"))
    if os.geteuid() != 0:
        raise RuntimeError(_("Administrator rights are required"))
    if mode == "integrated" and not has_integrated_gpu():
        raise RuntimeError(_("No integrated GPU found; turning NVIDIA off would leave no display"))
    if mode == "integrated" and internal_panel_on_nvidia():
        raise RuntimeError(_("NVIDIA drives the built-in display (GPU mode 'Discrete'/MUX in the BIOS). "
                             "Turning NVIDIA off would black out the screen; choose 'MSHybrid'/"
                             "'Optimus' in the BIOS."))


def configure(mode):
    check_preconditions(mode)
    before = current()
    if any(v is not None and not v.startswith(HEADER) for v in before.values()):
        raise RuntimeError(_("Unexpected configuration; existing files were not touched"))

    target = desired(mode)
    if before == target:
        print(_("GPU boot setting is already:"), mode, flush=True)
        return

    # Only files owned by this tool are backed up; distribution settings are never touched.
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "gpu-before.json").write_text(
        json.dumps({str(p): v for p, v in before.items()}, indent=2))
    try:
        for path, content in target.items():
            if content is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
            write(path, content)
        print(_("Rebuilding boot images; this can take a few minutes..."), flush=True)
        rebuild_initramfs()
    except BaseException:
        for path, content in before.items():
            write(path, content)
        print(_("GPU configuration rolled back; rebuilding the previous boot images."), flush=True)
        rebuild_initramfs()
        raise
    print(_("GPU boot setting saved:"), mode, flush=True)
    print(_("The change takes effect after a restart. Your session was not closed."), flush=True)


def entry():
    """Entry point of /usr/lib/msi-ultrapower/msi-ultrapower-gpu-boot (recovery, with sudo)."""
    try:
        configure(sys.argv[1])
    except Exception as exc:
        print(_("GPU configuration error:"), exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    entry()

#!/usr/bin/python3
"""Sonraki açılış için yalnızca tümleşik GPU / hibrit modunu hazırlar.

pkexec ile çalıştırılır:  gpu_boot.py integrated|hybrid

Canlı GPU'yu asla sökmez ve bilgisayarı yeniden başlatmaz. Yalnızca kendi
oluşturduğu üç dosyayı (HEADER ile işaretli) yönetir. Yalnızca standart
kütüphaneyi kullanır; paketin geri kalanından import yapmaz.

Kurtarma (TTY):  sudo python3 -P -m msi_ultrapower.privileged.gpu_boot hybrid
"""
import gettext
import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Standart kütüphane gettext; pkexec LANGUAGE/LANG'ı korur, dil kullanıcınınkiyle aynı olur.
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

# Adres modelden modele değiştiği için NVIDIA'nın tüm işlevleri (GPU, ses, USB-C) üreticiye göre kaldırılır.
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

MANAGED = (MOD, RULE, INIT, DRACUT)  # bu aracın sahip olabileceği tüm dosyalar
NVIDIA_VENDOR = "0x10de"
INTERNAL_CONNECTORS = ("eDP", "LVDS", "DSI")


def integrated_config():
    """"integrated" modunda olması gereken dosyalar; "hybrid" modunda hepsi silinir."""
    config = {MOD: MODPROBE_TEXT, RULE: UDEV_TEXT}
    if shutil.which("mkinitcpio"):
        config[INIT] = MKINITCPIO_TEXT
    if shutil.which("dracut"):
        config[DRACUT] = DRACUT_TEXT
    return config


def write(path, content):
    """content None ise dosyayı siler, değilse atomik olarak yazar."""
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
    """NVIDIA kapanınca ekranı sürecek Intel/AMD tümleşik GPU var mı."""
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
    """MUX'lu modellerde BIOS "Discrete" ise dahili ekranı NVIDIA sürer; o zaman kapatılamaz."""
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
    before = {p: p.read_text() if p.exists() else None for p in MANAGED}
    if any(v is not None and not v.startswith(HEADER) for v in before.values()):
        raise RuntimeError(_("Unexpected configuration; existing files were not touched"))

    wanted = integrated_config() if mode == "integrated" else {}
    desired = {p: wanted.get(p) for p in MANAGED}
    if before == desired:
        print(_("GPU boot setting is already:"), mode, flush=True)
        return

    # Yalnızca bu aracın sahip olduğu dosyalar yedeklenir; dağıtımın ayarlarına dokunulmaz.
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "gpu-before.json").write_text(
        json.dumps({str(p): v for p, v in before.items()}, indent=2))
    try:
        for path, content in desired.items():
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
    """/usr/lib/msi-ultrapower/msi-ultrapower-gpu-boot buradan başlar."""
    try:
        configure(sys.argv[1])
    except Exception as exc:
        print(_("GPU configuration error:"), exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    entry()

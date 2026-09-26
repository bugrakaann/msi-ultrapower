#!/usr/bin/python3
"""Sonraki açılış için yalnızca tümleşik GPU / hibrit modunu hazırlar.

pkexec ile çalıştırılır:  gpu_boot.py integrated|hybrid

Canlı GPU'yu asla sökmez ve bilgisayarı yeniden başlatmaz. Yalnızca kendi
oluşturduğu üç dosyayı (HEADER ile işaretli) yönetir. Yalnızca standart
kütüphaneyi kullanır; paketin geri kalanından import yapmaz.

Kurtarma (TTY):  sudo python3 -P -m pil_modu.privileged.gpu_boot hybrid
"""
import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HEADER = "# Managed by pil-modu gpu_boot.py\n"
MOD = Path("/etc/modprobe.d/90-pil-modu-nvidia.conf")
RULE = Path("/etc/udev/rules.d/50-pil-modu-nvidia.rules")
INIT = Path("/etc/mkinitcpio.conf.d/99-pil-modu-gpu.conf")
BACKUP_DIR = Path("/var/lib/pil-modu")
IGPU_VENDORS = ("0x8086", "0x1002")  # Intel, AMD
MODES = ("integrated", "hybrid")

MODULES = ("nvidia", "nvidia_drm", "nvidia_modeset", "nvidia_uvm",
           "nouveau", "nova_core", "nova_drm", "i2c_nvidia_gpu")

MODPROBE_TEXT = HEADER + "".join(
    f"blacklist {m}\ninstall {m} /usr/bin/false\n" for m in MODULES)

# Adres modelden modele değiştiği için NVIDIA'nın tüm işlevleri (GPU, ses, USB-C) üreticiye göre kaldırılır.
UDEV_TEXT = HEADER + ('ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", '
                      'ATTR{power/control}="auto", ATTR{remove}="1"\n')

MKINITCPIO_TEXT = HEADER + '''pil_modu_modules=()
for pil_modu_module in "${MODULES[@]}"; do
    case "$pil_modu_module" in
        nvidia*|nouveau|nova_core|nova_drm|i2c_nvidia_gpu) ;;
        *) pil_modu_modules+=("$pil_modu_module") ;;
    esac
done
MODULES=("${pil_modu_modules[@]}")
unset pil_modu_modules pil_modu_module
'''

# "integrated" modunda olması gereken dosyalar; "hybrid" modunda hepsi silinir.
CONFIG = {MOD: MODPROBE_TEXT, RULE: UDEV_TEXT, INIT: MKINITCPIO_TEXT}


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
        print("mkinitcpio/dracut bulunamadı; açılış imajı yenilenmedi.", flush=True)


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


def check_preconditions(mode):
    if mode not in MODES:
        raise ValueError("Geçersiz GPU modu")
    if os.geteuid() != 0:
        raise RuntimeError("Yönetici yetkisi gerekiyor")
    if mode == "integrated" and not has_integrated_gpu():
        raise RuntimeError("Tümleşik GPU bulunamadı; NVIDIA kapatılırsa ekran gider")


def configure(mode):
    check_preconditions(mode)
    before = {p: p.read_text() if p.exists() else None for p in CONFIG}
    if any(v is not None and not v.startswith(HEADER) for v in before.values()):
        raise RuntimeError("Beklenmeyen yapılandırma; mevcut dosyalara dokunulmadı")

    desired = CONFIG if mode == "integrated" else {p: None for p in CONFIG}
    if before == desired:
        print("GPU açılış tercihi zaten:", mode, flush=True)
        return

    # Yalnızca bu aracın sahip olduğu dosyalar yedeklenir; dağıtımın ayarlarına dokunulmaz.
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "gpu-before.json").write_text(
        json.dumps({str(p): v for p, v in before.items()}, indent=2))
    try:
        for path, content in desired.items():
            write(path, content)
        print("Açılış imajları hazırlanıyor; bu işlem birkaç dakika sürebilir...", flush=True)
        rebuild_initramfs()
    except BaseException:
        for path, content in before.items():
            write(path, content)
        print("GPU yapılandırması geri alındı; eski açılış imajları yeniden oluşturuluyor.", flush=True)
        rebuild_initramfs()
        raise
    print("GPU açılış tercihi kaydedildi:", mode, flush=True)
    print("Değişiklik yeniden başlatınca geçerli olacak. Oturum kapatılmadı.", flush=True)


if __name__ == "__main__":
    try:
        configure(sys.argv[1])
    except Exception as exc:
        print("GPU yapılandırma hatası:", exc, file=sys.stderr)
        sys.exit(1)

#!/usr/bin/python3
"""Sonraki açılış için Yalnızca Intel / hibrit GPU modunu hazırlar.

pkexec ile çalıştırılır:  gpu_boot.py integrated|hybrid

Canlı GPU'yu asla sökmez ve bilgisayarı yeniden başlatmaz. Yalnızca kendi
oluşturduğu üç dosyayı (HEADER ile işaretli) yönetir. Yalnızca standart
kütüphaneyi kullanır; paketin geri kalanından import yapmaz.

Kurtarma (TTY):  sudo /usr/bin/python3 <bu dosya> hybrid
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HEADER = "# Managed by pil-modu gpu_boot.py\n"
MOD = Path("/etc/modprobe.d/90-pil-modu-nvidia.conf")
RULE = Path("/etc/udev/rules.d/50-pil-modu-nvidia.rules")
INIT = Path("/etc/mkinitcpio.conf.d/99-pil-modu-gpu.conf")
BACKUP_DIR = Path("/var/lib/pil-modu")
INTEL_GPU = Path("/sys/bus/pci/devices/0000:00:02.0")
MODES = ("integrated", "hybrid")

MODULES = ("nvidia", "nvidia_drm", "nvidia_modeset", "nvidia_uvm",
           "nouveau", "nova_core", "nova_drm", "i2c_nvidia_gpu")

MODPROBE_TEXT = HEADER + "".join(
    f"blacklist {m}\ninstall {m} /usr/bin/false\n" for m in MODULES)

UDEV_TEXT = HEADER + "".join(
    'ACTION=="add", SUBSYSTEM=="pci", KERNEL=="0000:01:00.' + str(i)
    + '", ATTR{vendor}=="0x10de", ATTR{power/control}="auto", ATTR{remove}="1"\n'
    for i in (1, 2, 3, 0))

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
    subprocess.run(["/usr/bin/mkinitcpio", "-P"], check=True)


def check_preconditions(mode):
    if mode not in MODES:
        raise ValueError("Geçersiz GPU modu")
    if os.geteuid() != 0:
        raise RuntimeError("Yönetici yetkisi gerekiyor")
    if not INTEL_GPU.exists() or (INTEL_GPU / "vendor").read_text().strip() != "0x8086":
        raise RuntimeError("Intel GPU doğrulanamadı")


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

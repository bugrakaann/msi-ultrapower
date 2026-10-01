"""Programın kullandığı dosya yolları tek yerde."""
import json
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = PACKAGE_DIR.parent  # PYTHONPATH'e eklenen "src" klasörü
HARDWARE_HELPER = PACKAGE_DIR / "privileged" / "hardware.py"
GPU_BOOT_HELPER = PACKAGE_DIR / "privileged" / "gpu_boot.py"
# Paketle kurulan yardımcılar; polkit eylemleri bu yollara bağlıdır (parola hatırlama).
INSTALLED_HELPERS = Path("/usr/lib/msi-ultrapower")

# Kullanıcıya ait durum dosyaları (kod değil, yalnızca veri).
DATA_DIR = Path.home() / ".local/share/msi-ultrapower"
ORIGINAL_STATE = DATA_DIR / "original-v2.json"  # ilk moddan önceki ayarlar
ACTIVE_STATE = DATA_DIR / "active.json"         # son seçilen mod
LAYOUTS = DATA_DIR / "layouts.json"             # ekran kombinasyonu başına kullanıcı düzeni
HISTORY_LOG = DATA_DIR / "history.log"
LOCK_FILE = DATA_DIR / "lock"

POWER_SUPPLY_DIR = Path("/sys/class/power_supply")

CONFIG_DIR = Path.home() / ".config/msi-ultrapower"
SETTINGS = CONFIG_DIR / "settings.json"          # kullanıcının tercihleri (dil, otomatik mod…)

# Program eskiden "pil-modu" adını taşıyordu; o sürümün kullanıcı verileri bir kez taşınır.
LEGACY_NAME = "pil-modu"


def migrate_legacy():
    """Eski ayarları, ilk moddan önceki kaydı ve geçmişi yeni klasörlere taşır; otomatik başlatmayı yeniler.

    Ayarlar taşındıysa True döner (dil yeniden okunmalı).
    """
    home = Path.home()
    moved = False
    for old, new in ((home / ".local/share" / LEGACY_NAME, DATA_DIR),
                     (home / ".config" / LEGACY_NAME, CONFIG_DIR)):
        if old.is_dir() and not new.exists():
            new.parent.mkdir(parents=True, exist_ok=True)
            old.rename(new)
            moved = True
    if moved and SETTINGS.exists():
        # Eski paket kaldırılırken kendi polkit kuralını da sildi; ayar bunu yansıtsın.
        values = json.loads(SETTINGS.read_text())
        if values.get("passwordless"):
            values["passwordless"] = False
            SETTINGS.write_text(json.dumps(values, indent=2))
    old_autostart = home / ".config/autostart" / f"{LEGACY_NAME}.desktop"
    if old_autostart.exists():
        new_autostart = old_autostart.with_name("msi-ultrapower.desktop")
        if not new_autostart.exists():
            new_autostart.write_text(old_autostart.read_text().replace(LEGACY_NAME, "msi-ultrapower"))
        old_autostart.unlink()
    return moved

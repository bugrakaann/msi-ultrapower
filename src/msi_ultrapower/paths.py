"""Programın kullandığı dosya yolları tek yerde."""
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

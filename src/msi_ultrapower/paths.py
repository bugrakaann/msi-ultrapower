"""All file paths the program uses, in one place."""
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = PACKAGE_DIR.parent  # the "src" folder added to PYTHONPATH
# Root helper installed by the package; the polkit action is bound to this path.
INSTALLED_HELPER = Path("/usr/lib/msi-ultrapower/msi-ultrapower-hardware")

# The user's state files (data only, no code).
DATA_DIR = Path.home() / ".local/share/msi-ultrapower"
ORIGINAL_STATE = DATA_DIR / "original-v2.json"  # settings before the first mode
ACTIVE_STATE = DATA_DIR / "active.json"         # last selected mode
LAYOUTS = DATA_DIR / "layouts.json"             # the user's layout per display combination
HISTORY_LOG = DATA_DIR / "history.log"
LOCK_FILE = DATA_DIR / "lock"

POWER_SUPPLY_DIR = Path("/sys/class/power_supply")

CONFIG_DIR = Path.home() / ".config/msi-ultrapower"
SETTINGS = CONFIG_DIR / "settings.json"          # the user's preferences (language, automatic mode…)

"""User preferences: ~/.config/msi-ultrapower/settings.json

Missing keys get their defaults, so older files keep working with newer versions.
"""
from . import paths, state

DEFAULTS = {
    "language": "",                  # empty: system language
    "device_savings": True,          # PCI/sound/disk power saving in battery modes
    "bluetooth_off_on_battery": False,
    "auto_mode": False,              # switch modes when the charger is plugged in or out
    "auto_ac": "balanced",
    "auto_battery": "battery",
    "passwordless": False,           # apply modes without a password (polkit rule)
    "tray_autostart": False,         # start in the tray at login
}


def load():
    saved = state.read_json(paths.SETTINGS, {})
    return {**DEFAULTS, **{k: v for k, v in saved.items() if k in DEFAULTS}}


def save(values):
    paths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    state.write_json(paths.SETTINGS, {**load(), **values})

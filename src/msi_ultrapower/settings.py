"""Kullanıcı tercihleri: ~/.config/msi-ultrapower/settings.json

Eksik anahtarlar varsayılanla tamamlanır; böylece eski dosyalar yeni sürümde de çalışır.
"""
from . import paths, state

DEFAULTS = {
    "language": "",                  # boş: sistem dili
    "device_savings": True,          # batarya modunda PCI/ses/disk tasarrufu
    "bluetooth_off_on_battery": False,
    "auto_mode": False,              # prize takınca/çekince mod değiştir
    "auto_ac": "dengeli",
    "auto_battery": "batarya",
    "passwordless": False,           # modlar parola sormadan uygulansın (polkit kuralı)
    "tray_autostart": False,         # oturum açılınca tepside başla
}


def load():
    saved = state.read_json(paths.SETTINGS, {})
    return {**DEFAULTS, **{k: v for k, v in saved.items() if k in DEFAULTS}}


def save(values):
    paths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    state.write_json(paths.SETTINGS, {**load(), **values})

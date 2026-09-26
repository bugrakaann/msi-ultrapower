"""Ayarlar: dil, batarya modunun aygıt tasarrufları, otomatik mod ve sistem tepsisi."""
from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QVBoxLayout)

from .. import settings
from ..i18n import LANGUAGES, _
from ..presets import PRESETS
from .widgets import muted, section_label

AUTOSTART = Path.home() / ".config/autostart/pil-modu.desktop"
AUTOSTART_TEXT = """[Desktop Entry]
Type=Application
Name=pil-modu
Exec=pil-modu-ui --tray
Icon=battery-profile-balanced
X-KDE-autostart-phase=2
"""


def set_autostart(enabled):
    """Oturum açılınca tepsi simgesiyle başla (kullanıcıya ait dosya; yetki gerekmez)."""
    if enabled:
        AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART.write_text(AUTOSTART_TEXT)
    else:
        AUTOSTART.unlink(missing_ok=True)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Settings"))
        self.setMinimumWidth(460)
        values = settings.load()
        layout = QVBoxLayout(self)

        self.language = QComboBox()
        self.language.addItem(_("System default"), "")
        for code, name in LANGUAGES.items():
            self.language.addItem(name, code)
        self.language.setCurrentIndex(max(0, self.language.findData(values["language"])))

        self.device_savings = QCheckBox(_("Let PCI devices, the sound card and the disk sleep"))
        self.device_savings.setChecked(values["device_savings"])
        self.bluetooth = QCheckBox(_("Turn Bluetooth off"))
        self.bluetooth.setChecked(values["bluetooth_off_on_battery"])

        self.auto = QCheckBox(_("Switch modes when the charger is plugged in or out"))
        self.auto.setChecked(values["auto_mode"])
        self.auto_ac = self._mode_combo(values["auto_ac"])
        self.auto_battery = self._mode_combo(values["auto_battery"])
        self.passwordless = QCheckBox(_("Switch without asking for a password"))
        self.passwordless.setChecked(values["passwordless"])
        self.passwordless.setToolTip(_("Adds a polkit rule so local administrators of this session "
                                       "can apply modes without a password. Only the pil-modu "
                                       "hardware helper is allowed, and only whitelisted settings."))
        self.auto.toggled.connect(self._update_enabled)

        self.tray_autostart = QCheckBox(_("Start in the system tray when I log in"))
        self.tray_autostart.setChecked(values["tray_autostart"])

        form = QFormLayout()
        form.addRow(_("Language"), self.language)
        layout.addLayout(form)
        layout.addWidget(muted(_("A new language is used after the app restarts.")))

        layout.addWidget(section_label(_("Battery modes")))
        layout.addWidget(self.device_savings)
        layout.addWidget(self.bluetooth)

        layout.addWidget(section_label(_("Automatic mode")))
        layout.addWidget(self.auto)
        auto_form = QFormLayout()
        auto_form.addRow(_("Plugged in"), self.auto_ac)
        auto_form.addRow(_("On battery"), self.auto_battery)
        layout.addLayout(auto_form)
        layout.addWidget(self.passwordless)
        layout.addWidget(muted(_("Automatic switches do not change the NVIDIA boot setting, so the "
                                 "boot image is not rebuilt each time. Apply a battery mode by hand "
                                 "to turn NVIDIA fully off. The app must be running (tray is enough).")))

        layout.addWidget(section_label(_("System tray")))
        layout.addWidget(self.tray_autostart)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addStretch()
        layout.addWidget(buttons)
        self._update_enabled()

    def _mode_combo(self, selected):
        combo = QComboBox()
        for key, preset in PRESETS.items():
            combo.addItem(preset.title, key)
        combo.setCurrentIndex(max(0, combo.findData(selected)))
        return combo

    def _update_enabled(self):
        for widget in (self.auto_ac, self.auto_battery, self.passwordless):
            widget.setEnabled(self.auto.isChecked())

    def values(self):
        return {
            "language": self.language.currentData(),
            "device_savings": self.device_savings.isChecked(),
            "bluetooth_off_on_battery": self.bluetooth.isChecked(),
            "auto_mode": self.auto.isChecked(),
            "auto_ac": self.auto_ac.currentData(),
            "auto_battery": self.auto_battery.currentData(),
            "passwordless": self.auto.isChecked() and self.passwordless.isChecked(),
            "tray_autostart": self.tray_autostart.isChecked(),
        }

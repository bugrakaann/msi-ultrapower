"""Ayarlar: dil, batarya modunun aygıt tasarrufları, otomatik mod, parola ve sistem tepsisi."""
from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
                               QVBoxLayout)

from .. import settings
from ..i18n import LANGUAGES, _
from ..presets import PRESETS
from .widgets import muted, section_label

AUTOSTART = Path.home() / ".config/autostart/msi-ultrapower.desktop"
AUTOSTART_TEXT = """[Desktop Entry]
Type=Application
Name=msi-ultrapower
Exec=msi-ultrapower-ui --tray
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


DIALOG_WIDTH = 520


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Settings"))
        self.setFixedWidth(DIALOG_WIDTH)
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
        self.passwordless = QCheckBox(_("Do not ask for the administrator password"))
        self.passwordless.setChecked(values["passwordless"])
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
        layout.addWidget(muted(_("Automatic switches do not change the NVIDIA boot setting, so the "
                                 "boot image is not rebuilt each time. Apply a battery mode by hand "
                                 "to turn NVIDIA fully off. The app must be running (tray is enough).")))

        layout.addWidget(section_label(_("Administrator password")))
        layout.addWidget(self.passwordless)
        layout.addWidget(muted(_("Applies to switching modes, the charge limit and automatic mode. "
                                 "Adds a polkit rule for local administrators (wheel) of an active "
                                 "session; only the msi-ultrapower helper is allowed, and it only "
                                 "writes whitelisted settings. You are asked for the password once "
                                 "to turn this on or off.")))

        layout.addWidget(section_label(_("System tray")))
        layout.addWidget(self.tray_autostart)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addStretch()
        layout.addWidget(buttons)
        self._update_enabled()
        self._fit_wrapped_labels(layout)

    def _fit_wrapped_labels(self, layout):
        """Qt üst düzey pencerede kaydırmalı metnin yüksekliğini hesaplamaz; metin kesilmesin."""
        margins = layout.contentsMargins()
        width = DIALOG_WIDTH - margins.left() - margins.right()
        for label in self.findChildren(QLabel):
            if label.wordWrap():
                label.setMinimumHeight(label.heightForWidth(width))

    def _mode_combo(self, selected):
        combo = QComboBox()
        for key, preset in PRESETS.items():
            combo.addItem(preset.title, key)
        combo.setCurrentIndex(max(0, combo.findData(selected)))
        return combo

    def _update_enabled(self):
        for widget in (self.auto_ac, self.auto_battery):
            widget.setEnabled(self.auto.isChecked())

    def values(self):
        return {
            "language": self.language.currentData(),
            "device_savings": self.device_savings.isChecked(),
            "bluetooth_off_on_battery": self.bluetooth.isChecked(),
            "auto_mode": self.auto.isChecked(),
            "auto_ac": self.auto_ac.currentData(),
            "auto_battery": self.auto_battery.currentData(),
            "passwordless": self.passwordless.isChecked(),
            "tray_autostart": self.tray_autostart.isChecked(),
        }

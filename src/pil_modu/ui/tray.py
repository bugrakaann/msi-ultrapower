"""Sistem tepsisi: pencereyi açmadan mod ve şarj sınırı değiştirme, pil/sıcaklık ipucu."""
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .. import status
from ..i18n import _, percent
from ..presets import PRESETS
from ..privileged.hardware import CHARGE_LIMITS
from .status_strip import battery_text, power_text, sensor_text


class Tray(QSystemTrayIcon):
    def __init__(self, window, app):
        super().__init__(QIcon.fromTheme("battery-profile-balanced"), window)
        self.window = window
        self.app = app
        self.menu = QMenu()
        self.header = self.menu.addAction("")
        self.header.setEnabled(False)
        self.menu.addSeparator()

        self.modes = {}
        group = QActionGroup(self.menu)
        for key, preset in PRESETS.items():
            action = QAction(QIcon.fromTheme(preset.icon), preset.title, self.menu, checkable=True)
            action.setEnabled(window.cards[key].unsupported is None)
            action.triggered.connect(lambda _checked=False, k=key: self._apply(k))
            group.addAction(action)
            self.menu.addAction(action)
            self.modes[key] = action

        self.charge_menu = self.menu.addMenu(QIcon.fromTheme("battery"), _("Charge limit"))
        self.limits = {}
        limit_group = QActionGroup(self.charge_menu)
        for limit in CHARGE_LIMITS:
            action = QAction(percent(limit), self.charge_menu, checkable=True)
            action.triggered.connect(lambda _checked=False, value=limit: self.window.apply_charge(value))
            limit_group.addAction(action)
            self.charge_menu.addAction(action)
            self.limits[limit] = action

        self.menu.addSeparator()
        self.menu.addAction(QIcon.fromTheme("window"), _("Open Power Modes"), self.show_window)
        self.menu.addAction(QIcon.fromTheme("application-exit"), _("Quit"), app.quit)
        self.setContextMenu(self.menu)
        self.activated.connect(self._activated)
        window.timer.timeout.connect(self.refresh)
        window.finished.connect(self._notify)
        self.refresh()

    def _apply(self, key):
        if not self.window.apply_mode(key):
            self.showMessage(_("Power Modes"), _("Another change is still being applied."),
                             QSystemTrayIcon.Information, 4000)
        self.refresh()

    def _activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # sol tık: pencereyi aç/kapat
            if self.window.isVisible():
                self.window.hide()
            else:
                self.show_window()

    def show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def refresh(self):
        active = self.window.active_mode()
        busy = self.window.busy
        for key, action in self.modes.items():
            action.setChecked(key == active)
            action.setEnabled(not busy and self.window.cards[key].unsupported is None)
        preset = PRESETS.get(active)
        self.setIcon(QIcon.fromTheme(preset.icon if preset else "battery-profile-balanced"))

        limit = status.charge_limits()[1]
        self.charge_menu.setEnabled(limit is not None and not busy)
        for value, action in self.limits.items():
            action.setChecked(str(limit) == value)

        meter = self.window.power_meter
        battery = battery_text(status.battery())
        power = power_text(meter)
        title = preset.title if preset else _("Power Modes")
        self.header.setText(f"{battery} · {power}")
        lines = [title, battery, power]
        if meter.average is not None:
            lines.append(_("Average over {minutes} min on battery").format(minutes=meter.minutes))
        self.setToolTip("\n".join(lines + sensor_text(status.sensors())))

    def _notify(self, name, ok):
        if self.window.isVisible():
            return
        if ok:
            self.showMessage(_("Power Modes"), _("{name} applied.").format(name=name),
                             QSystemTrayIcon.Information, 4000)
        else:
            self.showMessage(_("Power Modes"), _("{name} could not be applied. Open the window "
                                                 "for the log.").format(name=name),
                             QSystemTrayIcon.Warning, 8000)

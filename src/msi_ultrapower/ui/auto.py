"""Switches to the mode chosen in Settings when the charger is plugged in or out
(settings: auto_mode, auto_ac, auto_battery).

Works while the app runs (the tray is enough). It does not disable NVIDIA at boot (--keep-gpu);
otherwise the boot image would be rebuilt on every unplug.

At startup (login) it also switches if the mode does not match the power source: shutting down
on AC and booting on battery counts as unplugging. It only does this with password-free
switching on; otherwise a password would be asked right after login.
"""
from PySide6.QtCore import QObject, Signal

from .. import settings, status
from ..presets import PRESETS


class AutoSwitcher(QObject):
    switching = Signal(str, bool)  # (mode key, on AC)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.last = status.on_ac()
        self.waiting = None  # target mode waiting while busy
        options = settings.load()
        if self.last is not None and options["auto_mode"] and options["passwordless"]:
            self.waiting = self._target(options, self.last)
        window.timer.timeout.connect(self.check)

    def check(self):
        plugged = status.on_ac()
        if plugged is None:
            return
        if plugged != self.last:
            self.last = plugged
            options = settings.load()
            if options["auto_mode"]:
                self.waiting = self._target(options, plugged)
        if self.waiting and not self.window.busy:
            target, self.waiting = self.waiting, None
            if target in PRESETS and self.window.active_mode() != target:
                if self.window.apply_mode(target, keep_gpu=True):
                    self.switching.emit(target, plugged)

    @staticmethod
    def _target(options, plugged):
        return options["auto_ac"] if plugged else options["auto_battery"]

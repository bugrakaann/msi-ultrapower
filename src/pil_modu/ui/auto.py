"""Prize takınca/çekince ayarlardaki moda geçer (settings: auto_mode, auto_ac, auto_battery).

Uygulama açıkken (tepside bile) çalışır. NVIDIA açılış ayarına dokunmaz (--gpu-koru);
aksi halde her fiş çekilişinde açılış imajı yeniden oluşturulurdu.
"""
from PySide6.QtCore import QObject, Signal

from .. import settings, status
from ..presets import PRESETS


class AutoSwitcher(QObject):
    switching = Signal(str, bool)  # (mod anahtarı, prizde mi)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.last = status.on_ac()
        self.waiting = None  # meşgulken bekleyen hedef mod
        window.timer.timeout.connect(self.check)

    def check(self):
        plugged = status.on_ac()
        if plugged is None:
            return
        if plugged != self.last:
            self.last = plugged
            options = settings.load()
            if options["auto_mode"]:
                self.waiting = options["auto_ac"] if plugged else options["auto_battery"]
        if self.waiting and not self.window.busy:
            target, self.waiting = self.waiting, None
            if target in PRESETS and self.window.active_mode() != target:
                if self.window.apply_mode(target, keep_gpu=True):
                    self.switching.emit(target, plugged)

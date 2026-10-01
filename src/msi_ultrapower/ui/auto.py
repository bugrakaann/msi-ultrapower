"""Prize takınca/çekince ayarlardaki moda geçer (settings: auto_mode, auto_ac, auto_battery).

Uygulama açıkken (tepside bile) çalışır. NVIDIA'yı açılışta kapatmaz (--gpu-koru); aksi halde
her fiş çekilişinde açılış imajı yeniden oluşturulurdu.

Uygulama açılırken de (oturum açılışı) şu anki güç kaynağına uygun mod seçili değilse ona geçer:
bilgisayar prizde kapatılıp pilde açıldıysa bu da bir fiş çekilişidir. Bunu yalnızca parolasız
geçiş açıkken yapar; aksi halde oturum açılır açılmaz parola sorulurdu.
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

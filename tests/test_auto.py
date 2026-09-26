import unittest
from unittest.mock import patch

try:
    from PySide6.QtCore import QCoreApplication, QObject, QTimer
except ImportError:  # PySide6 yoksa (ör. yalın CI) bu testler atlanır
    QObject = object

from pil_modu import settings


class FakeWindow(QObject):
    def __init__(self):
        super().__init__()
        self.timer = QTimer()
        self.busy = False
        self.active = "dengeli"
        self.applied = []

    def active_mode(self):
        return self.active

    def apply_mode(self, key, keep_gpu=False):
        self.applied.append((key, keep_gpu))
        return True


@unittest.skipIf(QObject is object, "PySide6 yok")
class AutoSwitcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def run_switcher(self, readings, options):
        from pil_modu.ui.auto import AutoSwitcher
        window = FakeWindow()
        with patch("pil_modu.status.on_ac", side_effect=readings), \
                patch.object(settings, "load", return_value={**settings.DEFAULTS, **options}):
            switcher = AutoSwitcher(window)
            for _ in readings[1:]:
                switcher.check()
        return window.applied

    def test_unplug_switches_to_battery_without_touching_gpu(self):
        applied = self.run_switcher([True, True, False], {"auto_mode": True})
        self.assertEqual(applied, [("batarya", True)])

    def test_disabled_does_nothing(self):
        self.assertEqual(self.run_switcher([True, False], {"auto_mode": False}), [])

    def test_no_change_no_switch(self):
        self.assertEqual(self.run_switcher([True, True, True], {"auto_mode": True}), [])


if __name__ == "__main__":
    unittest.main()

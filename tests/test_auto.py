import unittest
from unittest.mock import patch

try:
    from PySide6.QtCore import QCoreApplication, QObject, QTimer
except ImportError:  # PySide6 yoksa (ör. yalın CI) bu testler atlanır
    QObject = object

from msi_ultrapower import settings


class FakeWindow(QObject):
    def __init__(self):
        super().__init__()
        self.timer = QTimer()
        self.busy = False
        self.active = "balanced"
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
        from msi_ultrapower.ui.auto import AutoSwitcher
        window = FakeWindow()
        with patch("msi_ultrapower.status.on_ac", side_effect=readings), \
                patch.object(settings, "load", return_value={**settings.DEFAULTS, **options}):
            switcher = AutoSwitcher(window)
            for _ in readings[1:]:
                switcher.check()
        return window.applied

    def test_unplug_switches_to_battery_without_touching_gpu(self):
        applied = self.run_switcher([True, True, False], {"auto_mode": True})
        self.assertEqual(applied, [("battery", True)])

    def test_disabled_does_nothing(self):
        self.assertEqual(self.run_switcher([True, False], {"auto_mode": False}), [])

    def test_startup_on_battery_switches_when_passwordless(self):
        options = {"auto_mode": True, "passwordless": True}
        self.assertEqual(self.run_switcher([False, False], options), [("battery", True)])

    def test_startup_without_passwordless_waits_for_plug_event(self):
        self.assertEqual(self.run_switcher([False, False], {"auto_mode": True}), [])

    def test_startup_in_matching_mode_does_nothing(self):
        options = {"auto_mode": True, "passwordless": True}
        self.assertEqual(self.run_switcher([True, True], options), [])

    def test_no_change_no_switch(self):
        self.assertEqual(self.run_switcher([True, True, True], {"auto_mode": True}), [])


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from pil_modu import plan
from pil_modu.presets import PRESETS
from pil_modu.privileged import hardware as hw


class PresetTests(unittest.TestCase):
    def test_only_battery_modes_disable_nvidia(self):
        self.assertEqual({k for k, p in PRESETS.items() if p.is_battery}, {"batarya", "batarya-48"})

    def test_values_are_allowed_by_helper(self):
        for preset in PRESETS.values():
            planned = plan.hardware_plan(hw.read_state(), preset)
            for path, value in planned.items():
                self.assertTrue(hw.allowed(path, value), f"{preset.key}: {path}={value}")

    def test_battery_turns_keyboard_light_off(self):
        planned = plan.hardware_plan({hw.LED: "2"}, PRESETS["batarya"])
        self.assertEqual(planned[hw.LED], "0")
        planned = plan.hardware_plan({hw.LED: "2"}, PRESETS["dengeli"])
        self.assertEqual(planned[hw.LED], "2")

    def test_battery_enables_device_power_saving(self):
        current = {hw.SOUND_POWER_SAVE: "0", hw.DIRTY_WRITEBACK: "1500", "/sys/bus/pci/x": "on"}
        with patch.object(hw, "RUNTIME_PM", ["/sys/bus/pci/x"]):
            planned = plan.hardware_plan(current, PRESETS["batarya"])
            self.assertEqual(planned[hw.SOUND_POWER_SAVE], "1")
            self.assertEqual(planned[hw.DIRTY_WRITEBACK], "6000")
            self.assertEqual(planned["/sys/bus/pci/x"], "auto")
            balanced = plan.hardware_plan(current, PRESETS["dengeli"])
            self.assertEqual(balanced[hw.SOUND_POWER_SAVE], "0")
            self.assertEqual(balanced["/sys/bus/pci/x"], "on")

    def test_bluetooth_untouched_unless_option_enabled(self):
        bt = "/sys/class/bluetooth/hci0/rfkill0/soft"
        with patch.object(hw, "BLUETOOTH", [bt]):
            for mode in ("batarya", "dengeli"):
                self.assertNotIn(bt, plan.hardware_plan({bt: "0"}, PRESETS[mode]))
            on = {"bluetooth_off_on_battery": True}
            self.assertEqual(plan.hardware_plan({bt: "0"}, PRESETS["batarya"], on)[bt], "1")
            self.assertEqual(plan.hardware_plan({bt: "0"}, PRESETS["dengeli"], on)[bt], "0")

    def test_battery_skips_missing_settings(self):
        self.assertNotIn(hw.SOUND_POWER_SAVE, plan.hardware_plan({}, PRESETS["batarya"]))


if __name__ == "__main__":
    unittest.main()

import unittest

from pil_modu import plan
from pil_modu.presets import PRESETS
from pil_modu.privileged import hardware as hw


class PresetTests(unittest.TestCase):
    def test_only_battery_modes_disable_nvidia(self):
        self.assertEqual({k for k, p in PRESETS.items() if p.is_battery}, {"batarya", "batarya-48"})

    def test_values_are_allowed_by_helper(self):
        for preset in PRESETS.values():
            planned = plan.hardware_plan({}, preset)
            for path, value in planned.items():
                self.assertIn(value, hw.ALLOWED[path], f"{preset.key}: {path}={value}")

    def test_battery_turns_keyboard_light_off(self):
        planned = plan.hardware_plan({hw.LED: "2"}, PRESETS["batarya"])
        self.assertEqual(planned[hw.LED], "0")
        planned = plan.hardware_plan({hw.LED: "2"}, PRESETS["dengeli"])
        self.assertEqual(planned[hw.LED], "2")


if __name__ == "__main__":
    unittest.main()

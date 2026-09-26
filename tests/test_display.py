import unittest

from pil_modu import display
from pil_modu.presets import PRESETS

from helpers import fake_output


class ModeForTests(unittest.TestCase):
    def test_modes_survive_id_change(self):
        self.assertEqual(display.mode_for(fake_output("eDP-1", ("a", "b")), fake_output("eDP-1")), "a")

    def test_unsupported_hz_aborts(self):
        with self.assertRaises(RuntimeError):
            display.mode_for(fake_output("eDP-1"), hz=144)


class ScreenPlanTests(unittest.TestCase):
    def setUp(self):
        self.outputs = [fake_output("eDP-1"), fake_output("HDMI-A-1")]

    def test_battery_disables_nvidia_external(self):
        args = display.screen_plan(self.outputs, self.outputs, PRESETS["batarya"],
                                   nvidia_outputs=("HDMI-A-1",))
        self.assertIn("output.HDMI-A-1.disable", args)
        self.assertIn("output.eDP-1.mode.old", args)

    def test_battery_keeps_igpu_external(self):
        args = display.screen_plan(self.outputs, self.outputs, PRESETS["batarya"])
        self.assertIn("output.HDMI-A-1.mode.old", args)

    def test_battery_can_turn_igpu_external_off(self):
        args = display.screen_plan(self.outputs, self.outputs, PRESETS["batarya"], "kapat")
        self.assertIn("output.HDMI-A-1.disable", args)

    def test_nvidia_external_off_even_if_kept(self):
        args = display.screen_plan(self.outputs, self.outputs, PRESETS["batarya"], "koru",
                                   nvidia_outputs=("HDMI-A-1",))
        self.assertIn("output.HDMI-A-1.disable", args)

    def test_without_kscreen_screen_step_is_skipped(self):
        self.assertEqual(display.screen_plan([], [], PRESETS["batarya"]), [])

    def test_brightness_skipped_when_unknown(self):
        panel = fake_output("eDP-1")
        del panel["brightness"]
        args = display.screen_plan([panel], [panel], PRESETS["dengeli"])
        self.assertFalse(any("brightness" in a for a in args))

    def test_battery_48_uses_48hz_panel(self):
        args = display.screen_plan(self.outputs, self.outputs, PRESETS["batarya-48"])
        self.assertIn("output.eDP-1.mode.low", args)

    def test_no_internal_panel_aborts(self):
        with self.assertRaises(RuntimeError):
            display.screen_plan([fake_output("HDMI-A-1")], [], PRESETS["batarya"])

    def test_restore(self):
        args = display.screen_plan([fake_output("eDP-1", ("a", "b"))], [fake_output("eDP-1")])
        self.assertIn("output.eDP-1.mode.a", args)
        self.assertIn("output.eDP-1.brightness.100", args)


if __name__ == "__main__":
    unittest.main()

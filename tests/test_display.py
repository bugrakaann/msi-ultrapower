import unittest

from msi_ultrapower import display
from msi_ultrapower.presets import PRESETS

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
        args = display.screen_plan(self.outputs, self.outputs, PRESETS["battery"],
                                   nvidia_outputs=("HDMI-A-1",))
        self.assertIn("output.HDMI-A-1.disable", args)
        self.assertIn("output.eDP-1.mode.old", args)

    def test_battery_keeps_igpu_external(self):
        args = display.screen_plan(self.outputs, self.outputs, PRESETS["battery"])
        self.assertIn("output.HDMI-A-1.mode.old", args)

    def test_battery_can_turn_igpu_external_off(self):
        args = display.screen_plan(self.outputs, self.outputs, PRESETS["battery"], "off")
        self.assertIn("output.HDMI-A-1.disable", args)

    def test_nvidia_external_off_even_if_kept(self):
        args = display.screen_plan(self.outputs, self.outputs, PRESETS["battery"], "keep",
                                   nvidia_outputs=("HDMI-A-1",))
        self.assertIn("output.HDMI-A-1.disable", args)

    def test_without_kscreen_screen_step_is_skipped(self):
        self.assertEqual(display.screen_plan([], [], PRESETS["battery"]), [])

    def test_brightness_skipped_when_unknown(self):
        panel = fake_output("eDP-1")
        del panel["brightness"]
        args = display.screen_plan([panel], [panel], PRESETS["balanced"])
        self.assertFalse(any("brightness" in a for a in args))

    def test_battery_48_uses_48hz_panel(self):
        args = display.screen_plan(self.outputs, self.outputs, PRESETS["battery-low-hz"])
        self.assertIn("output.eDP-1.mode.low", args)

    def test_no_internal_panel_aborts(self):
        with self.assertRaises(RuntimeError):
            display.screen_plan([fake_output("HDMI-A-1")], [], PRESETS["battery"])

    def test_restore(self):
        args = display.screen_plan([fake_output("eDP-1", ("a", "b"))], [fake_output("eDP-1")])
        self.assertIn("output.eDP-1.mode.a", args)
        self.assertIn("output.eDP-1.brightness.100", args)


def dual(hdmi_primary=True, hdmi_enabled=True):
    """User layout: laptop (eDP-1) on the left, a large monitor (HDMI-A-1) on the right."""
    panel = fake_output("eDP-1")
    monitor = fake_output("HDMI-A-1", ("big", "big60"))
    for mode in monitor["modes"]:
        mode["size"] = {"width": 2560, "height": 1440}
    panel.update(pos={"x": 0, "y": 0}, priority=2 if hdmi_primary else 1)
    monitor.update(pos={"x": 1536, "y": 0}, priority=1 if hdmi_primary else 2, enabled=hdmi_enabled)
    return [panel, monitor]


def arg(args, name, setting):
    return next((a.split(".", 3)[3] for a in args if a.startswith(f"output.{name}.{setting}.")), None)


class LayoutTests(unittest.TestCase):
    def test_reapplying_keeps_external_as_primary(self):
        outputs = dual()
        args = display.screen_plan(outputs, [fake_output("eDP-1")], PRESETS["performance"])
        self.assertEqual(arg(args, "HDMI-A-1", "priority"), "1")
        self.assertEqual(arg(args, "eDP-1", "priority"), "2")
        self.assertEqual(arg(args, "HDMI-A-1", "position"), "1536,0")
        self.assertEqual(arg(args, "eDP-1", "position"), "0,0")

    def test_scale_and_external_mode_come_from_current_not_first_snapshot(self):
        outputs = dual()
        outputs[0]["scale"] = 1.5
        outputs[1]["currentModeId"] = "big60"
        args = display.screen_plan(outputs, [fake_output("eDP-1")], PRESETS["balanced"])
        self.assertEqual(arg(args, "eDP-1", "scale"), "1.5")
        self.assertEqual(arg(args, "HDMI-A-1", "mode"), "big60")

    def test_battery_leaves_laptop_alone_at_origin(self):
        args = display.screen_plan(dual(), [], PRESETS["battery"], nvidia_outputs=("HDMI-A-1",))
        self.assertIn("output.HDMI-A-1.disable", args)
        self.assertEqual(arg(args, "eDP-1", "priority"), "1")
        self.assertEqual(arg(args, "eDP-1", "position"), "0,0")

    def test_back_from_battery_restores_remembered_layout(self):
        remembered = display.remember(dual())                    # saved before battery mode
        outputs = dual(hdmi_primary=False, hdmi_enabled=False)   # HDMI off, laptop alone
        outputs[1]["currentModeId"] = "big60"                    # while off, KDE may report another mode
        args = display.screen_plan(outputs, [], PRESETS["performance"], remembered=remembered)
        self.assertEqual(arg(args, "HDMI-A-1", "priority"), "1")
        self.assertEqual(arg(args, "HDMI-A-1", "position"), "1536,0")
        self.assertEqual(arg(args, "HDMI-A-1", "mode"), "big")   # the remembered 120 Hz
        self.assertEqual(arg(args, "eDP-1", "priority"), "2")

    def test_new_external_without_memory_goes_right_and_keeps_laptop_primary(self):
        outputs = dual(hdmi_primary=False, hdmi_enabled=False)
        args = display.screen_plan(outputs, [], PRESETS["balanced"])
        self.assertEqual(arg(args, "eDP-1", "priority"), "1")
        self.assertEqual(arg(args, "HDMI-A-1", "priority"), "2")
        self.assertEqual(arg(args, "HDMI-A-1", "position"), "1536,0")  # 1920 / 1.25


if __name__ == "__main__":
    unittest.main()

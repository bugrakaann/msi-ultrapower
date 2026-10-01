import unittest
from dataclasses import replace

from msi_ultrapower import capabilities, describe, display, i18n
from msi_ultrapower.presets import PRESETS

from helpers import fake_output

i18n.setup("en")  # tests that compare text must not depend on the system language

CAPS = capabilities.Capabilities(
    model="MSI Test", shift_modes=("eco", "comfort", "sport", "turbo"),
    fan_modes=("auto", "silent", "basic", "advanced"), cooler_boost=True, turbo=True,
    keyboard_light=True, nvidia=True, charge_limit=True, panel_rates=(48, 60, 120),
    runtime_pm=10, sound_power_save=True, bluetooth=True, nvidia_outputs=("HDMI-A-1",))


class ShiftTests(unittest.TestCase):
    def test_missing_mode_uses_nearest(self):
        self.assertEqual(capabilities.nearest_shift("turbo", ("eco", "comfort", "sport")), "sport")
        self.assertEqual(capabilities.nearest_shift("eco", ("comfort", "sport")), "comfort")

    def test_no_ec(self):
        self.assertIsNone(capabilities.nearest_shift("eco", ()))


class SupportTests(unittest.TestCase):
    def test_all_supported_on_full_machine(self):
        for preset in PRESETS.values():
            self.assertIsNone(capabilities.unsupported_reason(preset, CAPS))

    def test_manual_fan_needs_advanced(self):
        caps = replace(CAPS, fan_modes=("auto", "silent"))
        self.assertIsNotNone(capabilities.unsupported_reason(PRESETS["performance-manual"], caps))

    def test_low_hz_needs_second_rate(self):
        caps = replace(CAPS, panel_rates=(60,))
        self.assertIsNotNone(capabilities.unsupported_reason(PRESETS["battery-low-hz"], caps))


class DescribeTests(unittest.TestCase):
    def test_battery_lists_device_savings(self):
        text = describe.to_html("x", describe.describe(PRESETS["battery"], CAPS))
        for word in ("Bluetooth", "PCI", "Sound card", "120 Hz", "HDMI-A-1"):
            self.assertIn(word, text)

    def test_options_change_battery_description(self):
        rows = dict(describe.describe(PRESETS["battery"], CAPS, {
            "bluetooth_off_on_battery": True, "device_savings": False})[-1][1])
        self.assertEqual(rows["Bluetooth"], "Off")
        self.assertNotIn("PCI devices", rows)

    def test_low_hz_shows_lowest_rate(self):
        screen = dict(describe.describe(PRESETS["battery-low-hz"], CAPS)[0][1])
        self.assertTrue(screen["Built-in display"].startswith("48 Hz"))

    def test_without_ec_or_nvidia(self):
        caps = replace(CAPS, shift_modes=(), fan_modes=(), nvidia=False)
        text = describe.to_html("x", describe.describe(PRESETS["performance"], caps))
        self.assertIn("msi-ec", text)
        self.assertIn("No NVIDIA GPU", text)


class ChangesTests(unittest.TestCase):
    def test_lists_only_real_changes(self):
        from msi_ultrapower.plan import Plan
        from msi_ultrapower.privileged import hardware as hw
        panel = fake_output("eDP-1")
        before = {"profile": "balanced", "outputs": [panel],
                  "hardware": {hw.EC + "shift_mode": "comfort", hw.LED: "2"}}
        plan = Plan(mode="battery", restoring=False, profile="power-saver",
                    screen_args=["output.eDP-1.enable", "output.eDP-1.mode.low",
                                 "output.eDP-1.brightness.30"],
                    rollback_args=[], hardware={hw.EC + "shift_mode": "eco", hw.LED: "2"},
                    gpu_boot="hybrid")
        rows = {label: (old, new) for label, old, new in describe.changes(plan, before)}
        self.assertEqual(rows["Power profile"], ("Balanced", "Power saver"))
        self.assertEqual(rows["eDP-1 refresh rate"], ("120 Hz", "48 Hz"))
        self.assertEqual(rows["eDP-1 brightness"], ("100%", "30%"))
        self.assertEqual(rows["EC mode"], ("comfort", "eco"))
        self.assertNotIn("Keyboard backlight", rows)  # unchanged


class RefreshTests(unittest.TestCase):
    def test_max_and_min(self):
        panel = fake_output("eDP-1")
        self.assertEqual(display.mode_for(panel, hz="max"), "old")
        self.assertEqual(display.mode_for(panel, hz="min"), "low")
        self.assertEqual(display.panel_rates([panel, fake_output("HDMI-A-1")]), [48, 60, 120])


if __name__ == "__main__":
    unittest.main()

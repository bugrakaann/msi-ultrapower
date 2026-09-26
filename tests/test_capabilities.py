import unittest
from dataclasses import replace

from pil_modu import capabilities, describe, display
from pil_modu.presets import PRESETS

from helpers import fake_output

CAPS = capabilities.Capabilities(
    model="MSI Test", shift_modes=("eco", "comfort", "sport", "turbo"),
    fan_modes=("auto", "silent", "basic", "advanced"), cooler_boost=True, turbo=True,
    keyboard_light=True, nvidia=True, charge_limit=True, panel_rates=(48, 60, 120),
    runtime_pm=10, sound_power_save=True, bluetooth=True)


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
        self.assertIsNotNone(capabilities.unsupported_reason(PRESETS["performans-manuel"], caps))

    def test_low_hz_needs_second_rate(self):
        caps = replace(CAPS, panel_rates=(60,))
        self.assertIsNotNone(capabilities.unsupported_reason(PRESETS["batarya-48"], caps))


class DescribeTests(unittest.TestCase):
    def test_battery_lists_device_savings(self):
        text = describe.to_html("x", describe.describe(PRESETS["batarya"], CAPS))
        for word in ("Bluetooth", "PCI", "Ses kartı", "120 Hz", "Kapatılır"):
            self.assertIn(word, text)

    def test_low_hz_shows_lowest_rate(self):
        screen = dict(describe.describe(PRESETS["batarya-48"], CAPS)[0][1])
        self.assertTrue(screen["Dahili ekran"].startswith("48 Hz"))

    def test_without_ec_or_nvidia(self):
        caps = replace(CAPS, shift_modes=(), fan_modes=(), nvidia=False)
        text = describe.to_html("x", describe.describe(PRESETS["performans"], caps))
        self.assertIn("msi-ec", text)
        self.assertIn("Ekran kartı yok", text)


class RefreshTests(unittest.TestCase):
    def test_max_and_min(self):
        panel = fake_output("eDP-1")
        self.assertEqual(display.mode_for(panel, hz="max"), "old")
        self.assertEqual(display.mode_for(panel, hz="min"), "low")
        self.assertEqual(display.panel_rates([panel, fake_output("HDMI-A-1")]), [48, 60, 120])


if __name__ == "__main__":
    unittest.main()

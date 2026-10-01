import unittest

from msi_ultrapower.status import Battery, PowerMeter


def on_battery(watts):
    return Battery("Discharging", 80, watts)


class PowerMeterTests(unittest.TestCase):
    def test_average_is_time_weighted(self):
        meter = PowerMeter()
        meter.add(on_battery(10), now=0)
        meter.add(on_battery(10), now=10)
        meter.add(on_battery(20), now=20)   # 15 W on average between 10 and 20 s
        self.assertEqual(meter.current, 20)
        self.assertAlmostEqual(meter.average, (10 * 10 + 15 * 10) / 20)

    def test_too_short_to_average(self):
        meter = PowerMeter()
        meter.add(on_battery(12), now=0)
        meter.add(on_battery(12), now=4)
        self.assertEqual(meter.current, 12)
        self.assertIsNone(meter.average)

    def test_plugging_in_resets(self):
        meter = PowerMeter()
        meter.add(on_battery(10), now=0)
        meter.add(on_battery(10), now=20)
        meter.add(Battery("Charging", 81, 30), now=22)
        self.assertIsNone(meter.current)
        self.assertIsNone(meter.average)

    def test_sleep_gap_is_ignored(self):
        meter = PowerMeter()
        meter.add(on_battery(10), now=0)
        meter.add(on_battery(10), now=20)
        meter.add(on_battery(10), now=20 + 3600)  # after suspend
        self.assertEqual(meter.span, 20)
        self.assertAlmostEqual(meter.average, 10)


if __name__ == "__main__":
    unittest.main()

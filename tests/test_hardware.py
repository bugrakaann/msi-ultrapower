import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pil_modu.privileged import hardware as hw


class ApplyTests(unittest.TestCase):
    def test_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as d:
            first = Path(d) / "first"
            second = Path(d) / "second"
            first.write_text("old\n")
            second.write_text("old\n")
            allowed = {str(first): {"old", "new"}, str(second): {"old", "new"}}
            original_write = Path.write_text

            def failing(path, value, *args, **kwargs):
                if path == second and value == "new\n":
                    raise OSError("injected failure")
                return original_write(path, value, *args, **kwargs)

            with patch.object(hw, "ALLOWED", allowed), patch.object(Path, "write_text", failing):
                with self.assertRaises(OSError):
                    hw.apply({str(first): "new", str(second): "new"})
            self.assertEqual(first.read_text().strip(), "old")

    def test_rejects_unknown_path(self):
        with self.assertRaises(ValueError):
            hw.validate({"/etc/passwd": "x"})


class ChargeLimitTests(unittest.TestCase):
    def test_writes_and_verifies(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("100\n")
        with patch.object(hw, "CHARGE_LIMIT", f.name):
            hw.write_charge_limit("80")
        self.assertEqual(Path(f.name).read_text().strip(), "80")
        Path(f.name).unlink()

    def test_rejects_other_values(self):
        for value in ("50", "0", "../x"):
            with self.assertRaises(ValueError):
                hw.write_charge_limit(value)


if __name__ == "__main__":
    unittest.main()

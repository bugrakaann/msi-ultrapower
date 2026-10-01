"""READY → COMMIT konuşması, gerçek pkexec yerine sahte bir alt süreçle."""
import contextlib
import io
import sys
import unittest
from unittest.mock import patch

from msi_ultrapower import elevated

# Gerçek yardımcı gibi: uygula → READY, COMMIT bekle → COMMITTED, ardından NVIDIA adımının çıktısı.
FAKE_HELPER = """
import sys
print("note before ready"); print("READY", flush=True)
line = sys.stdin.readline()
if not line.startswith("COMMIT"):
    print("ROLLED_BACK"); sys.exit(0)
print("COMMITTED", flush=True)
print("got: " + line.strip())
print("gpu failed", file=sys.stderr)
sys.exit(1 if "gpu=" in line else 0)
"""


def fake(code=FAKE_HELPER):
    return patch.object(elevated, "hardware", return_value=[sys.executable, "-c", code])


class HardwareHelperTests(unittest.TestCase):
    def test_commit_then_gpu_output_is_streamed(self):
        with fake():
            helper = elevated.HardwareHelper({})
            helper.wait_ready()
            helper.commit("integrated")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                ok = helper.finish()
        self.assertFalse(ok)
        self.assertIn("got: COMMIT gpu=integrated", out.getvalue())
        self.assertIn("gpu failed", out.getvalue())  # hata çıktısı da aktarılır

    def test_restore_commit_sends_save_no(self):
        with fake():
            helper = elevated.HardwareHelper({})
            helper.wait_ready()
            helper.commit(save=False)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertTrue(helper.finish())
        self.assertIn("got: COMMIT save=no", out.getvalue())

    def test_cancelled_password_gives_clear_message(self):
        with fake("import sys; sys.exit(126)"):
            helper = elevated.HardwareHelper({})
            with self.assertRaises(RuntimeError) as error:
                helper.wait_ready()
        self.assertEqual(str(error.exception), elevated.auth_error(126))

    def test_rollback_after_ready(self):
        with fake():
            helper = elevated.HardwareHelper({})
            helper.wait_ready()
            helper.rollback()
        self.assertEqual(helper.process.returncode, 0)


if __name__ == "__main__":
    unittest.main()

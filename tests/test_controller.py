import unittest
from pathlib import Path
from unittest.mock import patch

from msi_ultrapower import controller
from msi_ultrapower.privileged import gpu_boot


class GpuStepTests(unittest.TestCase):
    """NVIDIA adımı yalnızca gerektiğinde çalışır; çalışmadığında parola da sorulmaz."""

    def step(self, boot_mode, keep_gpu, configured, blocked=False):
        with patch.object(controller.status, "NVIDIA_DEVICE", None if blocked else Path("/gpu")), \
                patch.object(gpu_boot, "MOD", Path("/" if blocked else "/yok-boyle-dosya")), \
                patch.object(gpu_boot, "is_configured", return_value=configured):
            return controller.gpu_step(boot_mode, keep_gpu)

    def test_unchanged_setting_is_skipped(self):
        self.assertIsNone(self.step("hybrid", False, configured=True))

    def test_change_is_done(self):
        self.assertEqual(self.step("integrated", False, configured=False), "integrated")

    def test_automatic_mode_does_not_disable_nvidia(self):
        self.assertIsNone(self.step("integrated", True, configured=False))

    def test_automatic_mode_re_enables_disabled_nvidia(self):
        """Pilde NVIDIA kapatıldıysa prize takınca performans modunda kapalı kalmamalı."""
        self.assertEqual(self.step("hybrid", True, configured=False, blocked=True), "hybrid")

    def test_no_nvidia_no_step(self):
        with patch.object(controller.status, "NVIDIA_DEVICE", None), \
                patch.object(gpu_boot, "MOD", Path("/yok-boyle-dosya")):
            self.assertIsNone(controller.gpu_step("integrated", False))


if __name__ == "__main__":
    unittest.main()

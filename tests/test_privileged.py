"""Root yardımcılarının sahte sysfs ile denenen güvenlik kontrolleri."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from msi_ultrapower.privileged import gpu_boot
from msi_ultrapower.privileged import hardware as hw


def fake_connector(root, card, name, vendor, status="connected"):
    """/sys/class/drm/cardN-NAME → device (kart) → device (PCI) yapısını taklit eder."""
    pci = Path(root, "pci", card)
    pci.mkdir(parents=True, exist_ok=True)
    (pci / "vendor").write_text(vendor + "\n")
    card_dir = Path(root, "cards", card)
    card_dir.mkdir(parents=True, exist_ok=True)
    if not (card_dir / "device").exists():
        (card_dir / "device").symlink_to(pci)
    connector = Path(root, "drm", f"{card}-{name}")
    connector.mkdir(parents=True)
    (connector / "status").write_text(status + "\n")
    (connector / "device").symlink_to(card_dir)
    return str(connector)


class MuxTests(unittest.TestCase):
    def check(self, connectors):
        with patch.object(gpu_boot.glob, "glob", return_value=connectors):
            return gpu_boot.internal_panel_on_nvidia()

    def test_hybrid_panel_on_intel(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(self.check([fake_connector(d, "card1", "eDP-1", "0x8086"),
                                         fake_connector(d, "card2", "HDMI-A-1", "0x10de")]))

    def test_mux_discrete_panel_on_nvidia(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(self.check([fake_connector(d, "card1", "eDP-1", "0x8086", "disconnected"),
                                        fake_connector(d, "card2", "eDP-2", "0x10de")]))

    def test_integrated_refused_when_panel_on_nvidia(self):
        with patch.object(gpu_boot.os, "geteuid", return_value=0), \
                patch.object(gpu_boot, "has_integrated_gpu", return_value=True), \
                patch.object(gpu_boot, "internal_panel_on_nvidia", return_value=True):
            with self.assertRaises(RuntimeError):
                gpu_boot.check_preconditions("integrated")
            gpu_boot.check_preconditions("hybrid")  # geri açmak her zaman serbest


class RestoreTests(unittest.TestCase):
    def test_missing_devices_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            present = Path(d, "present")
            present.write_text("old\n")
            state_dir = Path(d, "state")
            state_dir.mkdir()
            (state_dir / "hardware.json").write_text(json.dumps(
                {str(present): "new", str(Path(d, "gone")): "new"}))
            allowed = {str(present): {"old", "new"}, str(Path(d, "gone")): {"old", "new"}}
            with patch.object(hw, "STATE_DIR", state_dir), patch.object(hw, "detect"), \
                    patch.object(hw, "ALLOWED", allowed), patch.object(hw, "RESTORE_WAIT", 0):
                hw.restore()
            self.assertEqual(present.read_text().strip(), "new")

    def test_unspecified_shift_uses_nearest_available(self):
        with patch.object(hw, "available_shift_modes", return_value=["eco", "sport", "turbo"]):
            state = hw.writable({hw.EC + "shift_mode": "unspecified"})
        self.assertEqual(state[hw.EC + "shift_mode"], "eco")


class TransactionTests(unittest.TestCase):
    """Tek parola: donanım ve NVIDIA açılış ayarı aynı yardımcı oturumunda yapılır."""

    def run_transaction(self, stdin):
        calls = []
        with patch.object(hw, "apply", side_effect=lambda s: calls.append(("apply", s)) or {"x": "old"}), \
                patch.object(hw, "persist", side_effect=lambda s: calls.append(("persist", s))), \
                patch.object(hw, "forget", side_effect=lambda: calls.append(("forget",))), \
                patch.object(hw.gpu_boot, "configure", side_effect=lambda m: calls.append(("gpu", m))), \
                patch.object(hw.sys, "stdin", io.StringIO(stdin)), \
                patch("sys.stdout", new_callable=io.StringIO) as out:
            hw.transaction({"x": "new"})
        return calls, out.getvalue().split()

    def test_commit_with_gpu_runs_gpu_after_saving(self):
        calls, out = self.run_transaction("COMMIT gpu=integrated\n")
        self.assertEqual(calls, [("apply", {"x": "new"}), ("persist", {"x": "new"}), ("gpu", "integrated")])
        self.assertEqual(out, ["READY", "COMMITTED"])

    def test_restore_forgets_boot_values(self):
        calls, _out = self.run_transaction("COMMIT save=no\n")
        self.assertIn(("forget",), calls)
        self.assertNotIn("persist", [c[0] for c in calls])

    def test_no_commit_rolls_back_without_gpu(self):
        calls, out = self.run_transaction("")
        self.assertEqual([c[0] for c in calls], ["apply", "apply"])
        self.assertEqual(out, ["READY", "ROLLED_BACK"])


class GpuBootStateTests(unittest.TestCase):
    def test_is_configured_reads_managed_files(self):
        with tempfile.TemporaryDirectory() as d:
            mod, rule = Path(d, "mod.conf"), Path(d, "rule.rules")
            with patch.object(gpu_boot, "MANAGED", (mod, rule)), patch.object(gpu_boot, "MOD", mod), \
                    patch.object(gpu_boot, "RULE", rule), patch.object(gpu_boot.shutil, "which", return_value=None):
                self.assertTrue(gpu_boot.is_configured("hybrid"))
                self.assertFalse(gpu_boot.is_configured("integrated"))
                mod.write_text(gpu_boot.MODPROBE_TEXT)
                rule.write_text(gpu_boot.UDEV_TEXT)
                self.assertTrue(gpu_boot.is_configured("integrated"))
                self.assertFalse(gpu_boot.is_configured("hybrid"))


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from msi_ultrapower import paths


class LegacyMigrationTests(unittest.TestCase):
    def test_moves_pil_modu_data_and_autostart(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".local/share/pil-modu").mkdir(parents=True)
            (home / ".local/share/pil-modu/active.json").write_text("{}")
            (home / ".config/pil-modu").mkdir(parents=True)
            (home / ".config/pil-modu/settings.json").write_text('{"passwordless": true}')
            (home / ".config/autostart").mkdir()
            (home / ".config/autostart/pil-modu.desktop").write_text("Exec=pil-modu-ui --tray\n")
            with patch.object(Path, "home", return_value=home), \
                    patch.object(paths, "DATA_DIR", home / ".local/share/msi-ultrapower"), \
                    patch.object(paths, "CONFIG_DIR", home / ".config/msi-ultrapower"), \
                    patch.object(paths, "SETTINGS", home / ".config/msi-ultrapower/settings.json"):
                self.assertTrue(paths.migrate_legacy())
                self.assertFalse(paths.migrate_legacy())  # ikinci kez bir şey yapmaz
            self.assertTrue((home / ".local/share/msi-ultrapower/active.json").exists())
            self.assertIn('"passwordless": false', (home / ".config/msi-ultrapower/settings.json").read_text())
            self.assertFalse((home / ".config/autostart/pil-modu.desktop").exists())
            self.assertEqual((home / ".config/autostart/msi-ultrapower.desktop").read_text(),
                             "Exec=msi-ultrapower-ui --tray\n")


if __name__ == "__main__":
    unittest.main()

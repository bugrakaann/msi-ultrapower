import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pil_modu import i18n

PO_DIR = Path(__file__).resolve().parent.parent / "po"


@unittest.skipUnless(shutil.which("msgfmt"), "gettext (msgfmt) yok")
class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.locale = tempfile.TemporaryDirectory()
        for po in PO_DIR.glob("*.po"):
            target = Path(self.locale.name, po.stem, "LC_MESSAGES")
            target.mkdir(parents=True)
            subprocess.run(["msgfmt", "--check", "-o", str(target / "pil-modu.mo"), str(po)], check=True)

    def tearDown(self):
        i18n.setup("en")
        self.locale.cleanup()

    def use(self, language):
        with patch.object(i18n, "localedir", return_value=self.locale.name):
            i18n.setup(language)

    def test_every_language_translates_the_main_button(self):
        expected = {"tr": "Uygula", "ru": "Применить", "es": "Aplicar", "ar": "تطبيق"}
        for language, text in expected.items():
            self.use(language)
            self.assertEqual(i18n._("Apply").lstrip(i18n.RLM), text, language)

    def test_percent_position_follows_language(self):
        self.use("tr")
        self.assertEqual(i18n.percent(80), "%80")
        self.use("en")
        self.assertEqual(i18n.percent(80), "80%")

    def test_decimal_separator_follows_language(self):
        self.use("tr")
        self.assertEqual(i18n.decimal(10.94), "10,9")
        self.use("en")
        self.assertEqual(i18n.decimal(10.94), "10.9")

    def test_russian_plural_forms(self):
        self.use("ru")
        forms = [i18n.ngettext("{count} device", "{count} devices", n).format(count=n) for n in (1, 3, 5)]
        self.assertEqual(forms, ["1 устройство", "3 устройства", "5 устройств"])

    def test_arabic_is_right_to_left(self):
        self.use("ar")
        self.assertTrue(i18n.is_rtl())
        self.assertTrue(i18n._("Apply").startswith(i18n.RLM))  # Latin başlayan cümleler de sağa yaslanır
        self.use("tr")
        self.assertFalse(i18n.is_rtl())


if __name__ == "__main__":
    unittest.main()

"""Çeviri: kaynak metinler İngilizce, diğer diller po/*.po dosyalarında.

Dil sırası: ayarlardaki seçim → LANGUAGE/LC_ALL/LC_MESSAGES/LANG → İngilizce.
Arayüz, seçilen dili LANGUAGE ile CLI'ye ve oradan pkexec yardımcılarına geçirir.
"""
import gettext

from . import paths, settings

DOMAIN = "pil-modu"
LANGUAGES = {  # kod → kendi dilindeki adı (ayarlar menüsü)
    "en": "English",
    "tr": "Türkçe",
    "ru": "Русский",
    "es": "Español",
    "ar": "العربية",
}
RIGHT_TO_LEFT = {"ar"}

_translation = gettext.NullTranslations()


def localedir():
    """Geliştirmede derlenmiş build/locale, kurulu pakette /usr/share/locale."""
    development = paths.SOURCE_DIR.parent / "build" / "locale"
    return str(development) if development.is_dir() else None


def setup(language=None):
    """language: "tr" gibi; boş ya da None ise ortam değişkenlerinden seçilir."""
    global _translation
    if language is None:
        language = settings.load()["language"]
    _translation = gettext.translation(DOMAIN, localedir(), languages=[language] if language else None,
                                       fallback=True)


def current():
    """Şu an kullanılan dilin kodu ("en" çeviri yoksa)."""
    code = _translation.info().get("language", "") if isinstance(_translation, gettext.GNUTranslations) else ""
    return code.split("_")[0] or "en"


def is_rtl():
    return current() in RIGHT_TO_LEFT


def _(message):
    return _translation.gettext(message)


def ngettext(singular, plural, n):
    return _translation.ngettext(singular, plural, n)


def N_(message):
    """Yalnızca işaretler (xgettext bulsun diye); çeviri kullanıldığı yerde yapılır."""
    return message


def child_environment():
    """Alt süreçlere (CLI, pkexec) seçilen dili geçirmek için ortam değişkenleri."""
    language = settings.load()["language"]
    return {"LANGUAGE": language} if language else {}


setup()

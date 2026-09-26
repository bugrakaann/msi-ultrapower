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


RLM = "\u200f"   # sağdan sola işareti: "HDMI-A-1 …" gibi Latin başlayan cümleler de sağa yaslansın
FSI, PDI = "\u2068", "\u2069"  # yön yalıtımı: "80% ← 30%" gibi değerler yer değiştirmesin


def directional(text):
    """Sağdan sola dillerde metni sağdan sola paragraf yapar; diğer dillerde aynen döner."""
    return RLM + text if text and is_rtl() else text


def _(message):
    return directional(_translation.gettext(message))


def ngettext(singular, plural, n):
    return directional(_translation.ngettext(singular, plural, n))


def isolate(text):
    """Değeri çevresindeki metnin yönünden bağımsız tutar (sayılar, aygıt adları)."""
    return f"{FSI}{text}{PDI}" if is_rtl() else str(text)


def percent(value):
    """Yüzde yazımı dile göre değişir: 80% (en), %80 (tr)."""
    # Translators: percent sign position, e.g. "%{value}" in Turkish
    return _("{value}%").format(value=value)


def N_(message):
    """Yalnızca işaretler (xgettext bulsun diye); çeviri kullanıldığı yerde yapılır."""
    return message


def child_environment():
    """Alt süreçlere (CLI, pkexec) seçilen dili geçirmek için ortam değişkenleri."""
    language = settings.load()["language"]
    return {"LANGUAGE": language} if language else {}


setup()

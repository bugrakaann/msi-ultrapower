"""Translations: source strings are English, other languages live in po/*.po.

Language order: the choice in Settings → LANGUAGE/LC_ALL/LC_MESSAGES/LANG → English.
The window passes the chosen language to the CLI with LANGUAGE, and from there to the helper.
"""
import gettext

from . import paths, settings

DOMAIN = "msi-ultrapower"
LANGUAGES = {  # code → name in its own language (Settings menu)
    "en": "English",
    "tr": "Türkçe",
    "ru": "Русский",
    "es": "Español",
    "ar": "العربية",
}
RIGHT_TO_LEFT = {"ar"}
DECIMAL_COMMA = {"tr", "ru", "es"}  # 10,9 W

_translation = gettext.NullTranslations()


def localedir():
    """Compiled build/locale in development, /usr/share/locale when installed."""
    development = paths.SOURCE_DIR.parent / "build" / "locale"
    return str(development) if development.is_dir() else None


def setup(language=None):
    """language: such as "tr"; empty or None picks it from the environment."""
    global _translation
    if language is None:
        language = settings.load()["language"]
    _translation = gettext.translation(DOMAIN, localedir(), languages=[language] if language else None,
                                       fallback=True)


def current():
    """Code of the language in use ("en" without a translation)."""
    code = _translation.info().get("language", "") if isinstance(_translation, gettext.GNUTranslations) else ""
    return code.split("_")[0] or "en"


def is_rtl():
    return current() in RIGHT_TO_LEFT


RLM = "\u200f"   # right-to-left mark: sentences starting in Latin script ("HDMI-A-1 …") also align right
FSI, PDI = "\u2068", "\u2069"  # direction isolation: values such as "80% ← 30%" keep their order


def directional(text):
    """Makes the text a right-to-left paragraph in RTL languages; unchanged otherwise."""
    return RLM + text if text and is_rtl() else text


def _(message):
    return directional(_translation.gettext(message))


def ngettext(singular, plural, n):
    return directional(_translation.ngettext(singular, plural, n))


def isolate(text):
    """Keeps a value independent of the surrounding text direction (numbers, device names)."""
    return f"{FSI}{text}{PDI}" if is_rtl() else str(text)


def percent(value):
    """The percent sign position depends on the language: 80% (en), %80 (tr)."""
    # Translators: percent sign position, e.g. "%{value}" in Turkish
    return _("{value}%").format(value=value)


def decimal(value, digits=1):
    """Decimal number; "10,9" in languages that use a decimal comma."""
    text = f"{value:.{digits}f}"
    return text.replace(".", ",") if current() in DECIMAL_COMMA else text


def N_(message):
    """Only marks the string for xgettext; it is translated where it is used."""
    return message


def child_environment():
    """Environment variables that pass the chosen language to child processes (CLI, pkexec)."""
    language = settings.load()["language"]
    return {"LANGUAGE": language} if language else {}


setup()

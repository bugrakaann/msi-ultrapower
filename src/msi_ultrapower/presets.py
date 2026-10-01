"""Güç modlarının tanımı. Komut satırı ve arayüz modları buradan okur.

Yeni bir mod eklemek ya da bir modu değiştirmek için yalnızca bu dosyayı düzenle.
Değerler modeldeki karşılıklarına çevrilir: örneğin EC'de "eco" yoksa en yakın
tasarruf modu, "max" ise panelin desteklediği en yüksek yenileme hızı kullanılır.
"""
from dataclasses import dataclass

from .i18n import N_, _

EXTERNAL_CHOICES = {
    "otomatik": N_("Automatic (by mode)"),
    "koru": N_("Keep on"),
    "kapat": N_("Turn off"),
}


@dataclass(frozen=True)
class Preset:
    key: str             # komut satırındaki adı: msi-ultrapower <key>
    title_source: str    # arayüzde görünen ad (İngilizce kaynak; .title çevrilmişi)
    summary_source: str  # kartta görünen tek satırlık açıklama
    icon: str            # KDE/Breeze tema simgesi
    profile: str         # powerprofilesctl profili
    brightness: int      # dahili ekran parlaklığı (%)
    shift: str           # MSI EC shift_mode (yoksa en yakını)
    boost: str           # Cooler Boost: on/off
    turbo: str           # "0" turbo açık, "1" kapalı (intel_pstate/no_turbo gibi)
    gpu: str             # NVIDIA power/control: on/auto
    fan: str = "auto"    # MSI EC fan_mode
    panel: str = "max"   # dahili ekran Hz'i: "max" en yüksek, "min" en düşük

    @property
    def title(self):
        return _(self.title_source)

    @property
    def summary(self):
        return _(self.summary_source)

    @property
    def is_battery(self):
        """Batarya modları NVIDIA'yı ve harici ekranı kapatır, aygıtları uyutur."""
        return self.profile == "power-saver"


_BATTERY = dict(profile="power-saver", brightness=30, shift="eco", boost="off", turbo="1",
                gpu="auto", icon="battery-profile-powersave")

PRESETS = {p.key: p for p in [
    Preset("performans", N_("Maximum performance"), N_("100% brightness · Turbo · Cooler Boost"),
           icon="battery-profile-performance", profile="performance",
           brightness=100, shift="turbo", boost="on", turbo="0", gpu="on"),
    Preset("performans-manuel", N_("Performance · Manual fan"),
           N_("100% brightness · Turbo · Your own fan curve"),
           icon="adjustlevels", profile="performance", brightness=100,
           shift="turbo", boost="off", turbo="0", gpu="on", fan="advanced"),
    Preset("dengeli", N_("Balanced"), N_("60% brightness · Automatic fan · NVIDIA sleeps when idle"),
           icon="battery-profile-balanced", profile="balanced",
           brightness=60, shift="comfort", boost="off", turbo="0", gpu="auto"),
    Preset("batarya", N_("Maximum battery"), N_("30% brightness · NVIDIA off · Devices sleep"),
           **_BATTERY),
    Preset("batarya-48", N_("Maximum battery · Low Hz"), N_("Lowest Hz · 30% brightness · NVIDIA off"),
           panel="min", **{**_BATTERY, "icon": "monitor"}),
]}

RESTORE_COMMANDS = ("geri", "normal")

# İngilizce komut adları: msi-ultrapower battery == msi-ultrapower batarya
ALIASES = {
    "performance": "performans",
    "performance-manual": "performans-manuel",
    "balanced": "dengeli",
    "battery": "batarya",
    "battery-low-hz": "batarya-48",
    "restore": "geri",
    "status": "durum",
    "charge": "sarj",
}
EXTERNAL_ALIASES = {"auto": "otomatik", "keep": "koru", "off": "kapat"}

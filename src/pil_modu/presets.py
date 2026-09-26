"""Güç modlarının tanımı. Komut satırı ve arayüz modları buradan okur.

Yeni bir mod eklemek ya da bir modu değiştirmek için yalnızca bu dosyayı düzenle.
Değerler modeldeki karşılıklarına çevrilir: örneğin EC'de "eco" yoksa en yakın
tasarruf modu, "max" ise panelin desteklediği en yüksek yenileme hızı kullanılır.
"""
from dataclasses import dataclass

EXTERNAL_CHOICES = {
    "otomatik": "Moda göre otomatik",
    "koru": "Açık tut",
    "kapat": "Kapat",
}


@dataclass(frozen=True)
class Preset:
    key: str             # komut satırındaki adı: pil-modu <key>
    title: str           # arayüzde görünen ad
    summary: str         # kartta görünen tek satırlık açıklama
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
    def is_battery(self):
        """Batarya modları NVIDIA'yı ve harici ekranı kapatır, aygıtları uyutur."""
        return self.profile == "power-saver"


_BATTERY = dict(profile="power-saver", brightness=30, shift="eco", boost="off", turbo="1",
                gpu="auto", icon="battery-profile-powersave")

PRESETS = {p.key: p for p in [
    Preset("performans", "Maksimum performans", "%100 parlaklık · Turbo · Cooler Boost",
           icon="battery-profile-performance", profile="performance",
           brightness=100, shift="turbo", boost="on", turbo="0", gpu="on"),
    Preset("performans-manuel", "Performans · Manuel fan", "%100 parlaklık · Turbo · Fan eğrisi sende",
           icon="adjustlevels", profile="performance", brightness=100,
           shift="turbo", boost="off", turbo="0", gpu="on", fan="advanced"),
    Preset("dengeli", "Dengeli", "%60 parlaklık · Otomatik fan · NVIDIA boşta uyur",
           icon="battery-profile-balanced", profile="balanced",
           brightness=60, shift="comfort", boost="off", turbo="0", gpu="auto"),
    Preset("batarya", "Maksimum batarya", "%30 parlaklık · NVIDIA kapalı · Aygıtlar uyur", **_BATTERY),
    Preset("batarya-48", "Maksimum batarya · Düşük Hz", "En düşük Hz · %30 parlaklık · NVIDIA kapalı",
           panel="min", **{**_BATTERY, "icon": "monitor"}),
]}

RESTORE_COMMANDS = ("geri", "normal")

"""Güç modlarının tanımı. Komut satırı ve arayüz modları buradan okur.

Yeni bir mod eklemek ya da bir modu değiştirmek için yalnızca bu dosyayı düzenle.
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
    hz: int              # ekran yenileme hızı
    brightness: int      # dahili ekran parlaklığı (%)
    shift: str           # MSI EC shift_mode
    boost: str           # Cooler Boost: on/off
    turbo: str           # intel_pstate/no_turbo: "0" turbo açık, "1" kapalı
    gpu: str             # NVIDIA power/control: on/auto
    fan: str = "auto"    # MSI EC fan_mode
    panel_hz: int | None = None  # yalnızca dahili ekran için farklı Hz

    @property
    def is_battery(self):
        """Batarya modları NVIDIA'yı ve harici ekranı kapatır."""
        return self.profile == "power-saver"

    @property
    def internal_hz(self):
        return self.panel_hz or self.hz

    def details(self):
        """Arayüzdeki ayrıntı listesi: (başlık, değer) çiftleri."""
        fan = {"auto": "Otomatik", "advanced": "Manuel eğri (MControlCenter)"}.get(self.fan, self.fan)
        if self.boost == "on":
            fan += " · Cooler Boost"
        return [
            ("Güç profili", {"performance": "Performans", "balanced": "Dengeli",
                             "power-saver": "Güç tasarrufu"}[self.profile]),
            ("Dahili ekran", f"{self.internal_hz} Hz · %{self.brightness} parlaklık"),
            ("CPU turbo", "Açık" if self.turbo == "0" else "Kapalı"),
            ("MSI EC", f"{self.shift} · fan: {fan}"),
            ("NVIDIA", "Yeniden başlatınca devre dışı" if self.is_battery
             else ("Hep uyanık" if self.gpu == "on" else "Boştayken uyur")),
        ]


_BATTERY = dict(profile="power-saver", hz=120, brightness=30, shift="eco",
                boost="off", turbo="1", gpu="auto", icon="battery-profile-powersave")

PRESETS = {p.key: p for p in [
    Preset("performans", "Maksimum performans", "%100 parlaklık · Turbo · Cooler Boost",
           icon="battery-profile-performance", profile="performance", hz=120,
           brightness=100, shift="turbo", boost="on", turbo="0", gpu="on"),
    Preset("performans-manuel", "Performans · Manuel fan", "%100 parlaklık · Turbo · Fan eğrisi sende",
           icon="adjustlevels", profile="performance", hz=120, brightness=100,
           shift="turbo", boost="off", turbo="0", gpu="on", fan="advanced"),
    Preset("dengeli", "Dengeli", "%60 parlaklık · Otomatik fan · NVIDIA boşta uyur",
           icon="battery-profile-balanced", profile="balanced", hz=120,
           brightness=60, shift="comfort", boost="off", turbo="0", gpu="auto"),
    Preset("batarya", "Maksimum batarya", "120 Hz · %30 parlaklık · NVIDIA kapalı", **_BATTERY),
    Preset("batarya-48", "Maksimum batarya · 48 Hz", "48 Hz · %30 parlaklık · NVIDIA kapalı",
           panel_hz=48, **{**_BATTERY, "icon": "monitor"}),
]}

RESTORE_COMMANDS = ("geri", "normal")

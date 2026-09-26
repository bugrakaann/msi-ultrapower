"""Bir modun bu bilgisayarda neyi değiştireceğini okunur metne çevirir.

Arayüzdeki ayrıntı paneli ve kartların ipucu (hover) buradan beslenir. Metinler
plan.py'nin gerçekte yaptığıyla aynı kuralları izler.
"""
from html import escape

from . import capabilities, settings

PROFILES = {"performance": "Performans", "balanced": "Dengeli", "power-saver": "Güç tasarrufu"}
FANS = {"auto": "Otomatik", "silent": "Sessiz", "basic": "Temel",
        "advanced": "Manuel eğri (MControlCenter)"}
ON_OFF = {True: "Açık", False: "Kapalı"}


def _panel_hz(preset, caps):
    if not caps.panel_rates:
        return "En yüksek Hz" if preset.panel == "max" else "En düşük Hz"
    hz = max(caps.panel_rates) if preset.panel == "max" else min(caps.panel_rates)
    return f"{hz} Hz ({'en yüksek' if preset.panel == 'max' else 'en düşük'})"


def _external(preset, caps):
    if preset.is_battery and caps.nvidia_outputs:
        return f"NVIDIA'ya bağlı olanlar ({', '.join(caps.nvidia_outputs)}) kapanır · diğerleri seçime göre"
    return "Aşağıdaki seçime göre · Hz'i değişmez"


def describe(preset, caps, options=None):
    """[(bölüm, [(ayar, değer), ...]), ...]"""
    options = {**settings.DEFAULTS, **(options or {})}
    if caps.screen:
        screen = [("Dahili ekran", _panel_hz(preset, caps)),
                  ("Parlaklık", f"%{preset.brightness}" if caps.brightness
                   else "Değişmez (Plasma 6.1+ gerekli)"),
                  ("Harici ekran", _external(preset, caps))]
    else:
        screen = [("Ekranlar", "Değişmez (KDE Plasma 6 gerekli)")]

    cpu = [("Güç profili", PROFILES[preset.profile]),
           ("CPU turbo", ON_OFF[preset.turbo == "0"] if caps.turbo else "Bu sistemde ayarlanamıyor")]

    if caps.ec:
        shift = capabilities.nearest_shift(preset.shift, caps.shift_modes)
        ec = [("EC modu", shift if shift == preset.shift else f"{shift} ({preset.shift} yok)"),
              ("Fan", FANS.get(preset.fan, preset.fan))]
        if caps.cooler_boost:
            ec.append(("Cooler Boost", ON_OFF[preset.boost == "on"]))
    else:
        ec = [("MSI EC", "msi-ec sürücüsü yok · fan ve EC modu atlanır")]

    if caps.nvidia:
        gpu = [("NVIDIA şimdi", "Hep uyanık" if preset.gpu == "on" else "Boştayken uyur"),
               ("NVIDIA açılışta", "Tamamen kapanır · yeniden başlatma gerekir" if preset.is_battery
                else "Kullanılabilir")]
    else:
        gpu = [("NVIDIA", "Ekran kartı yok")]

    if preset.is_battery:
        devices = []
        if caps.keyboard_light:
            devices.append(("Klavye ışığı", "Kapalı"))
        if options["device_savings"]:
            if caps.runtime_pm:
                devices.append(("PCI aygıtları", f"{caps.runtime_pm} aygıt boştayken uyur"))
            if caps.sound_power_save:
                devices.append(("Ses kartı", "1 sn sessizlikten sonra uyur"))
            devices.append(("Diske yazma", "60 sn'de bir (disk daha uzun uyur)"))
        else:
            devices.append(("Aygıt tasarrufu", "Kapalı (ayarlardan açılabilir)"))
        if caps.bluetooth:
            devices.append(("Bluetooth", "Kapalı" if options["bluetooth_off_on_battery"]
                            else "Değişmez"))
    else:
        devices = [("Klavye ışığı", "İlk moddan önceki haline döner"),
                   ("PCI, ses, Bluetooth, disk", "İlk moddan önceki haline döner")]

    return [("Ekran", screen), ("İşlemci", cpu), ("Fan ve EC", ec),
            ("Ekran kartı", gpu), ("Aygıtlar", devices)]


RESTORE = [("Geri yüklenenler", [
    ("Güç profili", "İlk moddan önceki profil"),
    ("Ekranlar", "Eski düzen, Hz, ölçek ve parlaklık"),
    ("İşlemci ve EC", "Eski turbo, EC modu, fan ve Cooler Boost"),
    ("Aygıtlar", "Eski klavye ışığı, PCI, ses, Bluetooth ve disk ayarları"),
    ("NVIDIA", "Yeniden başlatınca kullanılabilir"),
    ("Şarj sınırı", "Değişmez (ayrı ayar)"),
])]


def to_html(title, sections, note=None):
    """Kart ipucu için zengin metin."""
    rows = []
    for section, items in sections:
        rows.append(f"<tr><td colspan=2 style='padding-top:6px'><b>{escape(section)}</b></td></tr>")
        rows += [f"<tr><td style='padding-right:12px'>{escape(k)}</td><td>{escape(v)}</td></tr>"
                 for k, v in items]
    note_html = f"<p style='color:#da4453'>{escape(note)}</p>" if note else ""
    return f"<p><b>{escape(title)}</b></p>{note_html}<table cellspacing=0>{''.join(rows)}</table>"

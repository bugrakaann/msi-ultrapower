#!/usr/bin/python3
"""Root yetkisiyle sysfs'e yazan donanım yardımcısı.

Bu dosya kasıtlı olarak yalnızca standart kütüphaneyi kullanır ve paketin geri
kalanından hiçbir şey import etmez, çünkü iki farklı şekilde çalıştırılır:

  * pkexec ile doğrudan:   hardware.py '<json>'
        Ayarları uygular, "READY" yazar ve stdin'den COMMIT bekler.
        COMMIT gelmezse eski değerlere döner ("ROLLED_BACK").
        COMMIT gelirse ayarları açılışta geri yüklenmek üzere kaydeder.
  * pkexec ile şarj sınırı:  hardware.py --sarj 80
        Pilin şarj sınırını yazar, doğrular ve açılışta geri yüklenmek üzere kaydeder.
  * Açılışta systemd ile (pil-modu-restore.service):
        python3 -P -m pil_modu.privileged.hardware --restore

Kullanıcı tarafı (pil_modu paketi) ALLOWED, read_state, writable ve validate'i
import ederek aynı izin listesini kullanır.
"""
import glob
import json
import subprocess
import sys
from pathlib import Path

PCI = "/sys/bus/pci/devices/"
EC = "/sys/devices/platform/msi-ec/"
CPU = "/sys/devices/system/cpu/intel_pstate/"
BOOST = "/sys/devices/system/cpu/cpufreq/boost"  # AMD ve acpi-cpufreq: "1" turbo açık
SOUND_POWER_SAVE = "/sys/module/snd_hda_intel/parameters/power_save"  # saniye; 0 = kapalı
DIRTY_WRITEBACK = "/proc/sys/vm/dirty_writeback_centisecs"


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ""


def _first(pattern, default):
    return next(iter(sorted(glob.glob(pattern))), default)


# Model farkları: aygıt adresleri ve adları makineden makineye değişir, bu yüzden aranır.
NVIDIA = sorted(d for d in glob.glob(PCI + "*") if _read(d + "/vendor") == "0x10de")
NVIDIA_GPU = next((d for d in NVIDIA if _read(d + "/class").startswith("0x03")), None)
GPU_PM = [d + "/power/control" for d in NVIDIA]
LED = _first("/sys/class/leds/*::kbd_backlight/brightness",
             "/sys/class/leds/msiacpi::kbd_backlight/brightness")
BAT = str(Path(_first("/sys/class/power_supply/BAT*/charge_control_end_threshold",
                      "/sys/class/power_supply/BAT1/x")).parent) + "/"

# NVIDIA dışındaki PCI aygıtlarının çalışma zamanı güç yönetimi. Sürücüsü desteklemeyen
# aygıt "auto"da da uyanık kalır; sürücüsü olmayan (kullanılmayan Wi-Fi kartı gibi) uyur.
RUNTIME_PM = sorted(p for p in glob.glob(PCI + "*/power/control") if p not in GPU_PM)
BLUETOOTH = sorted(glob.glob("/sys/class/bluetooth/hci*/rfkill*/soft"))  # 1 = kapalı

# Şarj sınırı modlardan bağımsızdır; bu yüzden ALLOWED'da değil.
# msi-ec başlangıç eşiğini kendisi sınırın 10 altına ayarlar.
CHARGE_LIMIT = BAT + "charge_control_end_threshold"
CHARGE_START = BAT + "charge_control_start_threshold"
CHARGE_LIMITS = ("60", "80", "100")

SHIFT_MODES = ("eco", "comfort", "sport", "turbo")  # tasarruftan performansa
FAN_MODES = ("auto", "silent", "basic", "advanced")

# Yazılmasına izin verilen dosyalar ve kabul edilen değerler.
ALLOWED = {
    EC + "shift_mode": set(SHIFT_MODES),
    EC + "fan_mode": set(FAN_MODES),
    EC + "cooler_boost": {"on", "off"},
    CPU + "no_turbo": {"0", "1"},
    BOOST: {"0", "1"},
    LED: str.isdigit,
    **{path: {"auto", "on"} for path in GPU_PM + RUNTIME_PM},
    **{path: {"0", "1"} for path in BLUETOOTH},
    SOUND_POWER_SAVE: str.isdigit,
    DIRTY_WRITEBACK: str.isdigit,
}

STATE_DIR = Path("/var/lib/pil-modu")
RESTORE_SERVICE = "pil-modu-restore.service"
RESTORE_UNIT = Path("/usr/lib/systemd/system") / RESTORE_SERVICE  # paketle kurulur


def read_state():
    """İzin listesindeki mevcut dosyaların şu anki değerleri."""
    return {p: Path(p).read_text().strip() for p in ALLOWED if Path(p).exists()}


def writable(state):
    """Okunabilen ama geri yazılamayan değerleri yazılabilir karşılığına çevirir."""
    state = dict(state)
    if state.get(EC + "shift_mode") == "unspecified":
        state[EC + "shift_mode"] = "comfort"
    return state


def allowed(path, value):
    rule = ALLOWED.get(path)
    if rule is None:
        return False
    return rule(value) if callable(rule) else value in rule


def validate(state):
    for path, value in state.items():
        if not allowed(path, value) or not Path(path).exists():
            raise ValueError(f"Desteklenmeyen ayar: {path}={value}")


def apply(state):
    """Ayarları yazar; bir hata olursa değiştirilenleri geri alır. Eski durumu döndürür."""
    validate(state)
    before = read_state()
    changed = []
    try:
        for path, value in state.items():
            if before[path] == value:
                continue
            Path(path).write_text(value + "\n")
            changed.append(path)
            if Path(path).read_text().strip() != value:
                raise RuntimeError("Doğrulanamadı: " + path)
    except BaseException:
        for path in reversed(changed):
            try:
                Path(path).write_text(writable(before)[path] + "\n")
            except Exception as exc:
                print("Geri alma hatası:", path, exc, file=sys.stderr)
        raise
    return before


def persist(state):
    """Ayarları kaydeder ve açılışta geri yükleyecek servisi etkinleştirir."""
    validate(state)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    target = STATE_DIR / "hardware.json"
    temp = STATE_DIR / "hardware.tmp"
    temp.write_text(json.dumps(state, indent=2))
    temp.chmod(0o600)
    enable_restore_service()
    temp.replace(target)


def enable_restore_service():
    # Paket kurulu değilse (kaynak koddan geliştirme) servis yoktur; yalnızca kaydet.
    if RESTORE_UNIT.exists():
        subprocess.run(["systemctl", "enable", RESTORE_SERVICE], check=True)


def write_charge_limit(value):
    if value not in CHARGE_LIMITS or not Path(CHARGE_LIMIT).exists():
        raise ValueError(f"Desteklenmeyen şarj sınırı: {value}")
    Path(CHARGE_LIMIT).write_text(value + "\n")
    if Path(CHARGE_LIMIT).read_text().strip() != value:
        raise RuntimeError("Doğrulanamadı: " + CHARGE_LIMIT)


def set_charge_limit(value):
    """Şarj sınırını uygular ve açılışta geri yüklenmek üzere kaydeder."""
    write_charge_limit(value)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = STATE_DIR / "charge.tmp"
    temp.write_text(value + "\n")
    temp.chmod(0o600)
    enable_restore_service()
    temp.replace(STATE_DIR / "charge")


def restore():
    errors = []
    if (STATE_DIR / "hardware.json").exists():
        state = json.loads((STATE_DIR / "hardware.json").read_text())
        # Yalnızca Intel ile açılışta GPU işlevleri kasıtlı olarak ortadan kalkar; Bluetooth
        # gibi aygıtlar da henüz hazır olmayabilir. Olmayan dosyaları atla.
        state = {p: v for p, v in state.items() if Path(p).exists()}
        try:
            apply(state)
        except Exception as exc:
            errors.append(exc)
    if (STATE_DIR / "charge").exists():
        write_charge_limit((STATE_DIR / "charge").read_text().strip())
    if errors:
        raise errors[0]


def transaction(target):
    """Uygula → READY → COMMIT beklenir; gelmezse geri al."""
    before = apply(target)
    print("READY", flush=True)
    if sys.stdin.readline().strip() != "COMMIT":
        apply(writable(before))
        print("ROLLED_BACK", flush=True)
        return
    try:
        persist(target)
    except BaseException:
        apply(writable(before))
        raise


def main(argv):
    if argv[1] == "--restore":
        restore()
    elif argv[1] == "--sarj":
        set_charge_limit(argv[2])
    else:
        transaction(json.loads(argv[1]))


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

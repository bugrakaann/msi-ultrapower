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
  * pkexec ile parolasız otomatik mod:  hardware.py --parolasiz 1|0
        Yalnızca bu yardımcının eylemi için polkit kuralı yazar/siler.
  * Açılışta systemd ile (pil-modu-restore.service):
        /usr/lib/pil-modu/pil-modu-hardware --restore

Kullanıcı tarafı (pil_modu paketi) ALLOWED, read_state, writable ve validate'i
import ederek aynı izin listesini kullanır.
"""
import gettext
import glob
import json
import subprocess
import sys
import time
from pathlib import Path

# Standart kütüphane gettext; pkexec LANGUAGE/LANG'ı korur, dil kullanıcınınkiyle aynı olur.
_ = gettext.translation("pil-modu", fallback=True).gettext

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


SHIFT_MODES = ("eco", "comfort", "sport", "turbo")  # tasarruftan performansa
FAN_MODES = ("auto", "silent", "basic", "advanced")
CHARGE_LIMITS = ("60", "80", "100")
# Runtime PM'i kendi yöneten ya da "auto"da sorun çıkardığı bilinen sürücüler (TLP'deki gibi).
RUNTIME_PM_DENY = {"mei_me", "nouveau", "radeon", "amdgpu", "nvidia", "nvidia-gpu"}
CHARGE_PATTERN = "/sys/class/power_supply/BAT*/charge_control_end_threshold"


def _driver(device):
    try:
        return Path(device, "driver").resolve().name
    except OSError:
        return ""


def detect():
    """Model farkları: aygıt adresleri ve adları makineden makineye değişir, bu yüzden aranır.

    İçe aktarılırken çalışır; açılışta modüller geç yüklenirse restore() yeniden çağırır.
    """
    global NVIDIA, NVIDIA_GPU, GPU_PM, LED, BAT, RUNTIME_PM, BLUETOOTH
    global CHARGE_LIMIT, CHARGE_START, ALLOWED
    NVIDIA = sorted(d for d in glob.glob(PCI + "*") if _read(d + "/vendor") == "0x10de")
    NVIDIA_GPU = next((d for d in NVIDIA if _read(d + "/class").startswith("0x03")), None)
    GPU_PM = [d + "/power/control" for d in NVIDIA]
    LED = _first("/sys/class/leds/*::kbd_backlight/brightness",
                 "/sys/class/leds/msiacpi::kbd_backlight/brightness")
    BAT = str(Path(_first(CHARGE_PATTERN,
                          "/sys/class/power_supply/BAT1/x")).parent) + "/"

    # NVIDIA dışındaki PCI aygıtlarının çalışma zamanı güç yönetimi. Sürücüsü desteklemeyen
    # aygıt "auto"da da uyanık kalır; sürücüsü olmayan (kullanılmayan Wi-Fi kartı gibi) uyur.
    RUNTIME_PM = sorted(d + "/power/control" for d in glob.glob(PCI + "*")
                        if d + "/power/control" not in GPU_PM
                        and Path(d, "power/control").exists()
                        and _driver(d) not in RUNTIME_PM_DENY)
    BLUETOOTH = sorted(glob.glob("/sys/class/bluetooth/hci*/rfkill*/soft"))  # 1 = kapalı

    # Şarj sınırı modlardan bağımsızdır; bu yüzden ALLOWED'da değil.
    # msi-ec başlangıç eşiğini kendisi sınırın 10 altına ayarlar.
    CHARGE_LIMIT = BAT + "charge_control_end_threshold"
    CHARGE_START = BAT + "charge_control_start_threshold"

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


detect()

STATE_DIR = Path("/var/lib/pil-modu")
RESTORE_SERVICE = "pil-modu-restore.service"
RESTORE_UNIT = Path("/usr/lib/systemd/system") / RESTORE_SERVICE  # paketle kurulur


def read_state():
    """İzin listesindeki mevcut dosyaların şu anki değerleri."""
    return {p: Path(p).read_text().strip() for p in ALLOWED if Path(p).exists()}


def available_shift_modes():
    listed = _read(EC + "available_shift_modes").split()
    return [m for m in SHIFT_MODES if m in listed] or list(SHIFT_MODES)


def writable(state):
    """Okunabilen ama geri yazılamayan değerleri yazılabilir karşılığına çevirir."""
    state = dict(state)
    if state.get(EC + "shift_mode") == "unspecified":
        # Modelde "comfort" yoksa ona en yakın mod (capabilities.nearest_shift ile aynı kural).
        order = SHIFT_MODES
        state[EC + "shift_mode"] = min(available_shift_modes(), key=lambda m: (
            abs(order.index(m) - order.index("comfort")), order.index(m)))
    return state


def allowed(path, value):
    rule = ALLOWED.get(path)
    if rule is None:
        return False
    return rule(value) if callable(rule) else value in rule


def validate(state):
    for path, value in state.items():
        if not allowed(path, value) or not Path(path).exists():
            raise ValueError(_("Unsupported setting:") + f" {path}={value}")


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
                raise RuntimeError(_("Could not verify:") + " " + path)
    except BaseException:
        for path in reversed(changed):
            try:
                Path(path).write_text(writable(before)[path] + "\n")
            except Exception as exc:
                print(_("Rollback error:"), path, exc, file=sys.stderr)
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
        raise ValueError(_("Unsupported charge limit:") + f" {value}")
    Path(CHARGE_LIMIT).write_text(value + "\n")
    if Path(CHARGE_LIMIT).read_text().strip() != value:
        raise RuntimeError(_("Could not verify:") + " " + CHARGE_LIMIT)


def set_charge_limit(value):
    """Şarj sınırını uygular ve açılışta geri yüklenmek üzere kaydeder."""
    write_charge_limit(value)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = STATE_DIR / "charge.tmp"
    temp.write_text(value + "\n")
    temp.chmod(0o600)
    enable_restore_service()
    temp.replace(STATE_DIR / "charge")


# Açılışta msi-ec ve pil eklentisi sistem servisinden sonra yüklenebilir; bu yollar gelene kadar bekle.
LATE_PREFIXES = (EC, "/sys/class/leds/", "/sys/class/power_supply/")
RESTORE_WAIT = 20  # saniye


def wait_until(ready, timeout=RESTORE_WAIT):
    deadline = time.monotonic() + timeout
    while not ready() and time.monotonic() < deadline:
        time.sleep(0.5)


def restore():
    errors = []
    saved = {}
    if (STATE_DIR / "hardware.json").exists():
        saved = json.loads((STATE_DIR / "hardware.json").read_text())
    late = [p for p in saved if p.startswith(LATE_PREFIXES)]
    charge_saved = (STATE_DIR / "charge").exists()
    wait_until(lambda: all(Path(p).exists() for p in late)
               and (not charge_saved or glob.glob(CHARGE_PATTERN)))
    detect()  # geç gelen aygıtlarla izin listesini yenile

    if saved:
        state = saved
        # Yalnızca tümleşik GPU ile açılışta NVIDIA dosyaları kasıtlı olarak yoktur; Bluetooth
        # gibi aygıtlar da henüz hazır olmayabilir. Olmayan dosyaları atla.
        missing = [p for p in state if not Path(p).exists()]
        if missing:
            print(_("Skipped (device missing):"), *missing, file=sys.stderr)
        state = {p: v for p, v in state.items() if Path(p).exists() and p in ALLOWED}
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


POLKIT_ACTION = "io.github.pilmodu.hardware"
POLKIT_RULE = Path("/etc/polkit-1/rules.d/49-pil-modu.rules")
POLKIT_HEADER = "// Managed by pil-modu hardware.py\n"
# Yalnızca bu yardımcının eylemi; yalnızca yerel, etkin oturumdaki yönetici (wheel) kullanıcılar.
POLKIT_TEXT = POLKIT_HEADER + """polkit.addRule(function(action, subject) {
    if (action.id == "%s" && subject.local && subject.active && subject.isInGroup("wheel")) {
        return polkit.Result.YES;
    }
});
""" % POLKIT_ACTION


def set_passwordless(enabled):
    """Otomatik mod parola sormadan geçebilsin diye polkit kuralını yazar ya da siler."""
    if POLKIT_RULE.exists() and not POLKIT_RULE.read_text().startswith(POLKIT_HEADER):
        raise RuntimeError(_("{path} does not belong to pil-modu; not touched").format(path=POLKIT_RULE))
    if enabled:
        temp = POLKIT_RULE.with_suffix(".tmp")
        temp.write_text(POLKIT_TEXT)
        temp.chmod(0o644)
        temp.replace(POLKIT_RULE)
    else:
        POLKIT_RULE.unlink(missing_ok=True)


def main(argv):
    if argv[1] == "--restore":
        restore()
    elif argv[1] == "--sarj":
        set_charge_limit(argv[2])
    elif argv[1] == "--parolasiz":
        set_passwordless(argv[2] == "1")
    else:
        transaction(json.loads(argv[1]))


def entry():
    """/usr/lib/pil-modu/pil-modu-hardware ve systemd servisi buradan başlar."""
    try:
        main(sys.argv)
    except Exception as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    entry()

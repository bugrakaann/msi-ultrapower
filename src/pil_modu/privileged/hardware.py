#!/usr/bin/python3
"""Root yetkisiyle sysfs'e yazan donanım yardımcısı.

Bu dosya kasıtlı olarak yalnızca standart kütüphaneyi kullanır ve paketin geri
kalanından hiçbir şey import etmez, çünkü iki farklı şekilde çalıştırılır:

  * pkexec ile doğrudan:   hardware.py '<json>'
        Ayarları uygular, "READY" yazar ve stdin'den COMMIT bekler.
        COMMIT gelmezse eski değerlere döner ("ROLLED_BACK").
        COMMIT gelirse ayarları açılışta geri yüklenmek üzere kaydeder.
  * Açılışta systemd ile (pil-modu-restore.service):
        python3 -P -m pil_modu.privileged.hardware --restore

Kullanıcı tarafı (pil_modu paketi) ALLOWED, read_state, writable ve validate'i
import ederek aynı izin listesini kullanır.
"""
import json
import subprocess
import sys
from pathlib import Path

EC = "/sys/devices/platform/msi-ec/"
CPU = "/sys/devices/system/cpu/intel_pstate/"
GPU = "/sys/bus/pci/devices/0000:01:00."
LED = "/sys/class/leds/msiacpi::kbd_backlight/brightness"

# Yazılmasına izin verilen dosyalar ve kabul edilen değerler.
ALLOWED = {
    EC + "shift_mode": {"eco", "comfort", "sport", "turbo"},
    EC + "fan_mode": {"auto", "silent", "basic", "advanced"},
    EC + "cooler_boost": {"on", "off"},
    CPU + "no_turbo": {"0", "1"},
    LED: {"0", "1", "2", "3"},
    **{GPU + str(i) + "/power/control": {"auto", "on"} for i in range(4)},
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


def validate(state):
    for path, value in state.items():
        if path not in ALLOWED or value not in ALLOWED[path] or not Path(path).exists():
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
    # Paket kurulu değilse (kaynak koddan geliştirme) servis yoktur; yalnızca kaydet.
    if RESTORE_UNIT.exists():
        subprocess.run(["systemctl", "enable", RESTORE_SERVICE], check=True)
    temp.replace(target)


def restore():
    state = json.loads((STATE_DIR / "hardware.json").read_text())
    # Yalnızca Intel ile açılışta GPU işlevleri kasıtlı olarak ortadan kalkar.
    state = {p: v for p, v in state.items() if not p.startswith(GPU) or Path(p).exists()}
    apply(state)


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
    else:
        transaction(json.loads(argv[1]))


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

"""Komut satırı arayüzü:  pil-modu <mod> [--harici ...] [--dene]"""
import argparse
import fcntl
import sys

from . import controller, paths, state, status, system
from .presets import EXTERNAL_CHOICES, PRESETS, RESTORE_COMMANDS

DESCRIPTION = "MSI GF65 / KDE: performans, dengeli, batarya ve geri dönüş."


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="pil-modu", description=DESCRIPTION)
    parser.add_argument("mod", choices=[*PRESETS, *RESTORE_COMMANDS, "durum"])
    parser.add_argument("--harici", choices=list(EXTERNAL_CHOICES), default="otomatik",
                        help="Bataryada varsayılan kapalı, diğer modlarda açık")
    parser.add_argument("--dene", action="store_true", help="Ayar değiştirmeden planı göster")
    return parser.parse_args(argv)


def print_status():
    snapshot = system.capture()
    print("Seçilen mod:", state.load_active() or "henüz seçilmedi")
    print("Gerçek güç profili:", snapshot["profile"])
    for output in snapshot["outputs"]:
        if output["connected"]:
            mode = next((m for m in output["modes"] if m["id"] == output["currentModeId"]), {})
            print(output["name"], "açık" if output["enabled"] else "kapalı", mode.get("name", ""),
                  "parlaklık", output.get("brightness"))
    for path, value in snapshot["hardware"].items():
        print(path.removeprefix("/sys/"), "=", value)

    gpu = status.gpu()
    print("NVIDIA gerçek durumu:", gpu.runtime if gpu.present else "PCI aygıtı yok / devre dışı")
    print("NVIDIA sonraki açılış:", "devre dışı" if gpu.blocked_next_boot else "kullanılabilir")

    bat = status.battery()
    if bat:
        print("Pil:", bat.status, f"{bat.capacity}%")
        if bat.watts is not None:
            label = "Pil deşarj gücü:" if bat.discharging else "Pil şarj/akım gücü (sistem tüketimi değil):"
            print(label, round(bat.watts, 2), "W")


def main(argv=None):
    try:
        opt = parse_args(argv)
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with paths.LOCK_FILE.open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Başka bir pil-modu işlemi zaten çalışıyor.") from None
            if opt.mod == "durum":
                print_status()
            else:
                controller.change_mode(opt.mod, opt.harici, opt.dene)
    except Exception as exc:
        print("HATA:", exc, file=sys.stderr)
        return 1
    return 0

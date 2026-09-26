"""Komut satırı arayüzü:  pil-modu <mod> [--harici ...] [--dene]  ·  pil-modu sarj [60|80|100]"""
import argparse
import fcntl
import sys

from . import controller, paths, state, status, system
from .presets import EXTERNAL_CHOICES, PRESETS, RESTORE_COMMANDS
from .privileged import hardware as hw

DESCRIPTION = "MSI dizüstüleri / KDE: performans, dengeli, batarya ve geri dönüş."


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="pil-modu", description=DESCRIPTION)
    parser.add_argument("mod", choices=[*PRESETS, *RESTORE_COMMANDS, "durum", "sarj"])
    parser.add_argument("sinir", nargs="?", choices=hw.CHARGE_LIMITS,
                        help="yalnızca sarj ile: pilin dolacağı en yüksek yüzde")
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
        start, end = status.charge_limits()
        if end is not None:
            print("Şarj sınırı:", f"%{end}", f"(şarj %{start} altına inince başlar)" if start else "")
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
            if opt.mod != "sarj" and opt.sinir:
                raise RuntimeError("Yüzde yalnızca sarj komutuyla kullanılır.")
            if opt.mod == "durum":
                print_status()
            elif opt.mod == "sarj":
                if opt.sinir:
                    controller.set_charge_limit(opt.sinir)
                else:
                    limit = status.charge_limits()[1]
                    print("Şarj sınırı:", f"%{limit}" if limit else "bu cihazda desteklenmiyor")
            else:
                controller.change_mode(opt.mod, opt.harici, opt.dene)
    except Exception as exc:
        print("HATA:", exc, file=sys.stderr)
        return 1
    return 0

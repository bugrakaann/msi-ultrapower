"""Mod geçişinin tamamı: planla → uygula → doğrula → kaydet (ya da geri al)."""
import json
import sys
import time

from . import display, elevated, plan, state, status, system
from .presets import PRESETS
from .privileged import gpu_boot
from .privileged import hardware as hw


def change_mode(mode, external="otomatik", dry_run=False):
    """Bir modu uygular ya da mode "geri"/"normal" ise önceki ayarlara döner."""
    if mode in PRESETS and PRESETS[mode].is_battery and external == "koru":
        raise RuntimeError("Tam batarya modu NVIDIA ve HDMI çıkışını devre dışı bırakır. "
                           "Çift ekran için dengeli modunu seç.")

    before = system.capture()
    restoring = mode not in PRESETS
    if restoring and not state.has_original():
        print("Geri dönüş kaydı yok; ayar değiştirilmedi.")
        return
    original = state.load_original() if state.has_original() else before
    # Programın eski sürümüyle alınan kayıtta sonradan eklenen ayarlar yoktur; şu anki değerle tamamla.
    missing = {k: v for k, v in before["hardware"].items() if k not in original["hardware"]}
    original["hardware"].update(missing)
    p = plan.build(mode, external, before, original)

    if dry_run:
        print_plan(p)
        return

    if original["hardware"].get(hw.EC + "shift_mode") == "unspecified":
        print("Not: Eski EC unspecified değeri yazılamaz; geri dönüşte comfort kullanılır.", flush=True)
    if not state.has_original() or missing:
        state.save_original(original)

    apply_plan(p, before)

    if restoring:
        state.forget_all()
    else:
        state.save_active(mode, external)
    state.log_history(mode, external)
    print("CPU, ekran ve EC ayarları uygulandı:", mode, flush=True)

    apply_gpu_boot(p.gpu_boot)
    print("Durum: pil-modu durum | Geri dönüş: pil-modu geri")


def apply_plan(p, before):
    """Donanım + güç profili + ekranı birlikte uygular; bir adım bile başarısız olursa hepsi geri alınır."""
    helper = elevated.HardwareHelper(p.hardware)
    kde_changed = False
    try:
        helper.wait_ready()
        kde_changed = True
        system.set_power_profile(p.profile)
        system.apply_screen(p.screen_args)
        time.sleep(2)  # KDE ayarları yerleşsin

        actual = system.capture()
        if actual["profile"] != p.profile:
            raise RuntimeError("Güç profili başka bir uygulama tarafından değiştirildi")
        plan.verify_hardware(p, actual["hardware"])
        display.verify_screen(p.screen_args, before["outputs"], actual["outputs"])
        helper.commit()
    except BaseException:
        if kde_changed:
            rollback_kde(before["profile"], p.rollback_args)
        helper.rollback()
        raise


def rollback_kde(profile, screen_args):
    for step in (lambda: system.set_power_profile(profile),
                 lambda: system.apply_screen(screen_args)):
        try:
            step()
        except Exception as exc:
            print("Geri alma hatası:", exc, file=sys.stderr)


def apply_gpu_boot(boot_mode):
    if status.NVIDIA_DEVICE is None and not gpu_boot.MOD.exists():
        print("NVIDIA ekran kartı yok; GPU açılış ayarı atlandı.", flush=True)
        return
    if not elevated.configure_gpu_boot(boot_mode):
        raise RuntimeError("CPU/ekran profili uygulandı, ancak GPU açılış tercihi tamamlanamadı. "
                           "Aynı modu yeniden çalıştır.")
    gpu_present = status.gpu().present
    if boot_mode == "integrated" and gpu_present:
        print("NVIDIA henüz devre dışı değil. Tam batarya modu için yeniden başlatman gerekiyor.", flush=True)
    elif boot_mode == "hybrid" and not gpu_present:
        print("NVIDIA şu anda devre dışı. Tekrar kullanmak için yeniden başlatman gerekiyor.", flush=True)
    else:
        print("GPU durumu seçilen modla uyumlu.", flush=True)


def print_plan(p):
    print("Sonraki açılış GPU modu:", p.gpu_boot)
    print("Profil:", p.profile)
    print("kscreen-doctor", *p.screen_args)
    print(json.dumps(p.hardware, indent=2))


def set_charge_limit(limit):
    if not elevated.set_charge_limit(limit):
        raise RuntimeError("Şarj sınırı ayarlanamadı.")
    print(f"Şarj sınırı: %{limit}", flush=True)

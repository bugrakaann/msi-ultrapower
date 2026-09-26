"""Mod geçişinin tamamı: planla → uygula → doğrula → kaydet (ya da geri al)."""
import json
import sys
import time
from dataclasses import dataclass

from . import capabilities, display, elevated, plan, settings, state, status, system
from .i18n import _
from .presets import PRESETS
from .privileged import gpu_boot
from .privileged import hardware as hw


@dataclass
class Prepared:
    plan: plan.Plan
    before: dict      # şu anki anlık görüntü
    original: dict    # ilk moddan önceki ayarlar (eksikleri tamamlanmış)
    missing: dict     # eski kayıtta olmayıp eklenen ayarlar
    caps: capabilities.Capabilities


def prepare(mode, external="otomatik", before=None):
    """Hiçbir şeyi değiştirmeden planı hazırlar. Arayüzün "değişecekler" listesi de bunu kullanır."""
    before = before or system.capture()
    caps = capabilities.detect(before["outputs"])
    nvidia_screens = [o["name"] for o in before["outputs"]
                      if o["connected"] and o["enabled"] and o["name"] in caps.nvidia_outputs]
    if mode in PRESETS and PRESETS[mode].is_battery and external == "koru" and nvidia_screens:
        raise RuntimeError(_("{outputs} is wired to NVIDIA and cannot stay on in battery mode, "
                             "because NVIDIA is turned off. Use balanced mode for two screens.")
                           .format(outputs=", ".join(nvidia_screens)))
    original = state.load_original() if state.has_original() else before
    # Programın eski sürümüyle alınan kayıtta sonradan eklenen ayarlar yoktur; şu anki değerle tamamla.
    missing = {k: v for k, v in before["hardware"].items() if k not in original["hardware"]}
    original["hardware"].update(missing)
    p = plan.build(mode, external, before, original, settings.load(), caps)
    return Prepared(p, before, original, missing, caps)


def change_mode(mode, external="otomatik", dry_run=False, keep_gpu=False):
    """Bir modu uygular ya da mode "geri"/"normal" ise önceki ayarlara döner.

    keep_gpu: NVIDIA açılış ayarına dokunma (otomatik mod; initramfs her seferinde yenilenmesin).
    """
    restoring = mode not in PRESETS
    if restoring and not state.has_original():
        print(_("No saved settings to restore; nothing changed."))
        return
    prepared = prepare(mode, external)
    p, before, original, missing = prepared.plan, prepared.before, prepared.original, prepared.missing

    if dry_run:
        print_plan(p)
        return

    if original["hardware"].get(hw.EC + "shift_mode") == "unspecified":
        print(_("Note: the old EC value 'unspecified' cannot be written back; the closest mode is used."),
              flush=True)
    if not state.has_original() or missing:
        state.save_original(original)

    apply_plan(p, before)

    if restoring:
        state.forget_all()
    else:
        state.save_active(mode, external)
    state.log_history(mode, external)
    print(_("CPU, display and EC settings applied:"), mode, flush=True)

    if keep_gpu:
        print(_("NVIDIA boot setting left unchanged."), flush=True)
    else:
        apply_gpu_boot(p.gpu_boot)
    print(_("Status: pil-modu status | Restore: pil-modu restore"))


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
            raise RuntimeError(_("The power profile was changed by another program"))
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
            print(_("Rollback error:"), exc, file=sys.stderr)


def apply_gpu_boot(boot_mode):
    if status.NVIDIA_DEVICE is None and not gpu_boot.MOD.exists():
        print(_("No NVIDIA GPU; boot setting skipped."), flush=True)
        return
    if not elevated.configure_gpu_boot(boot_mode):
        raise RuntimeError(_("CPU and display settings were applied, but the NVIDIA boot setting "
                             "could not be completed. Apply the same mode again."))
    gpu_present = status.gpu().present
    if boot_mode == "integrated" and gpu_present:
        print(_("NVIDIA is not disabled yet. Restart to finish battery mode."), flush=True)
    elif boot_mode == "hybrid" and not gpu_present:
        print(_("NVIDIA is currently disabled. Restart to use it again."), flush=True)
    else:
        print(_("The GPU state matches the selected mode."), flush=True)


def print_plan(p):
    print(_("GPU mode at next boot:"), p.gpu_boot)
    print(_("Profile:"), p.profile)
    print("kscreen-doctor", *p.screen_args)
    print(json.dumps(p.hardware, indent=2))


def set_charge_limit(limit):
    if not elevated.set_charge_limit(limit):
        raise RuntimeError(_("The charge limit could not be set."))
    print(_("Charge limit:"), f"{limit}%", flush=True)


def set_passwordless(enabled):
    if not elevated.set_passwordless(enabled):
        raise RuntimeError(_("The password rule could not be changed."))
    print(_("Automatic switching without a password: {state}").format(
        state=_("on") if enabled else _("off")), flush=True)

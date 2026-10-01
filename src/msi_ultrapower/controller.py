"""A complete mode switch: plan → apply → verify → save (or roll back)."""
import json
import sys
import time
from dataclasses import dataclass

from . import capabilities, display, elevated, plan, settings, state, status, system
from .i18n import _, percent
from .presets import PRESETS
from .privileged import gpu_boot
from .privileged import hardware as hw


@dataclass
class Prepared:
    plan: plan.Plan
    before: dict      # current snapshot
    original: dict    # settings before the first mode (with missing keys filled in)
    missing: dict     # settings missing from the old snapshot and added now
    caps: capabilities.Capabilities


def prepare(mode, external="auto", before=None, caps=None):
    """Prepares the plan without changing anything. The window's list of changes uses it too.

    caps: the window passes what it detected at startup, so previews do not detect again.
    """
    before = before or system.capture()
    caps = caps or capabilities.detect(before["outputs"])
    nvidia_screens = [o["name"] for o in before["outputs"]
                      if o["connected"] and o["enabled"] and o["name"] in caps.nvidia_outputs]
    if mode in PRESETS and PRESETS[mode].is_battery and external == "keep" and nvidia_screens:
        raise RuntimeError(_("{outputs} is wired to NVIDIA and cannot stay on in battery mode, "
                             "because NVIDIA is turned off. Use balanced mode for two screens.")
                           .format(outputs=", ".join(nvidia_screens)))
    original = state.load_original() if state.has_original() else before
    # A snapshot from an older version lacks settings added later; fill them with current values.
    missing = {k: v for k, v in before["hardware"].items() if k not in original["hardware"]}
    original["hardware"].update(missing)
    p = plan.build(mode, external, before, original, settings.load(), caps, state.load_layouts())
    return Prepared(p, before, original, missing, caps)


def change_mode(mode, external="auto", dry_run=False, keep_gpu=False):
    """Applies a mode, or goes back to the previous settings when mode is "restore".

    keep_gpu: do not disable NVIDIA at boot (automatic mode, so the boot image is not rebuilt
    on every unplug). NVIDIA is still re-enabled when switching to a non-battery mode.
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
    # The user's current display layout (primary, positions) is restored for this combination.
    state.save_layout(before["outputs"])

    gpu_mode = gpu_step(p.gpu_boot, keep_gpu)
    helper = apply_plan(p, before, gpu_mode)

    if restoring:
        state.forget_all()
    else:
        state.save_active(mode, external)
    state.log_history(mode, external)
    print(_("CPU, display and EC settings applied:"), mode, flush=True)

    if not helper.finish() and gpu_mode:
        raise RuntimeError(_("CPU and display settings were applied, but the NVIDIA boot setting "
                             "could not be completed. Apply the same mode again."))
    report_gpu(p.gpu_boot, gpu_mode, keep_gpu)
    print(_("Status: msi-ultrapower status | Restore: msi-ultrapower restore"))


def gpu_step(boot_mode, keep_gpu):
    """NVIDIA boot mode to pass to the helper; None if nothing changes (and no password is asked)."""
    if status.NVIDIA_DEVICE is None and not gpu_boot.MOD.exists():
        return None  # no NVIDIA
    if keep_gpu and boot_mode == "integrated":
        return None
    return None if gpu_boot.is_configured(boot_mode) else boot_mode


def apply_plan(p, before, gpu_mode=None):
    """Applies hardware, power profile and displays together; if any step fails, all are rolled back.

    One privileged helper is used: the NVIDIA boot setting (gpu_mode) starts in the same session
    after COMMIT and is awaited with helper.finish(), so the returned helper may still be running.
    """
    helper = elevated.HardwareHelper(p.hardware)
    kde_changed = False
    try:
        helper.wait_ready()
        kde_changed = True
        system.set_power_profile(p.profile)
        system.apply_screen(p.screen_args)
        time.sleep(2)  # let the KDE settings settle

        actual = system.capture()
        if actual["profile"] != p.profile:
            raise RuntimeError(_("The power profile was changed by another program"))
        plan.verify_hardware(p, actual["hardware"])
        display.verify_screen(p.screen_args, before["outputs"], actual["outputs"])
        # After a restore there is no mode left to re-apply at boot.
        helper.commit(gpu_mode, save=not p.restoring)
    except BaseException:
        if kde_changed:
            rollback_kde(before["profile"], p.rollback_args)
        helper.rollback()
        raise
    return helper


def rollback_kde(profile, screen_args):
    for step in (lambda: system.set_power_profile(profile),
                 lambda: system.apply_screen(screen_args)):
        try:
            step()
        except Exception as exc:
            print(_("Rollback error:"), exc, file=sys.stderr)


def report_gpu(boot_mode, gpu_mode, keep_gpu):
    """Reports whether NVIDIA matches the selected mode and whether a restart is needed."""
    if status.NVIDIA_DEVICE is None and not gpu_boot.MOD.exists():
        print(_("No NVIDIA GPU; boot setting skipped."), flush=True)
        return
    if keep_gpu and boot_mode == "integrated" and gpu_mode is None:
        print(_("NVIDIA boot setting left unchanged."), flush=True)
        return
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
    error = elevated.set_charge_limit(limit)
    if error:
        raise RuntimeError(_("The charge limit could not be set.") + " " + error)
    print(_("Charge limit:"), percent(limit), flush=True)


def set_passwordless(enabled):
    error = elevated.set_passwordless(enabled)
    if error:
        raise RuntimeError(_("The password rule could not be changed.") + " " + error)
    print(_("Automatic switching without a password: {state}").format(
        state=_("on") if enabled else _("off")), flush=True)

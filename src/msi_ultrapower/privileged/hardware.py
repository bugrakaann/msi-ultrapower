"""Hardware helper that writes sysfs as root. Uses only the standard library and its
sibling module gpu_boot (also standard library only).

How it runs (always through /usr/lib/msi-ultrapower/msi-ultrapower-hardware):

  * mode switch with pkexec:   '<json>'
        Applies the settings, prints "READY" and waits for COMMIT on stdin.
        Without COMMIT it goes back to the old values ("ROLLED_BACK").
        With COMMIT it saves the settings for boot ("COMMITTED") and, if asked, also sets the
        NVIDIA boot setting with the same authorization, so a mode switch asks for one password.
  * charge limit with pkexec:  --charge 80
        Writes and verifies the battery charge limit and saves it for boot.
  * password-free switching with pkexec:  --passwordless 1|0
        Writes or removes a polkit rule for this helper's action only.
  * at boot from systemd (msi-ultrapower-restore.service):  --restore

The user side (the msi_ultrapower package) imports ALLOWED, read_state, writable and
validate, so both sides use the same allow-list.
"""
import gettext
import glob
import json
import subprocess
import sys
import time
from pathlib import Path

from . import gpu_boot

# Standard library gettext; pkexec keeps LANGUAGE/LANG, so the language matches the user's.
_ = gettext.translation("msi-ultrapower", fallback=True).gettext

PCI = "/sys/bus/pci/devices/"
EC = "/sys/devices/platform/msi-ec/"
CPU = "/sys/devices/system/cpu/intel_pstate/"
BOOST = "/sys/devices/system/cpu/cpufreq/boost"  # AMD and acpi-cpufreq: "1" means turbo on
SOUND_POWER_SAVE = "/sys/module/snd_hda_intel/parameters/power_save"  # seconds; 0 = off
DIRTY_WRITEBACK = "/proc/sys/vm/dirty_writeback_centisecs"


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ""


def _first(pattern, default):
    return next(iter(sorted(glob.glob(pattern))), default)


SHIFT_MODES = ("eco", "comfort", "sport", "turbo")  # from saving to performance
FAN_MODES = ("auto", "silent", "basic", "advanced")
CHARGE_LIMITS = ("60", "80", "100")
# Drivers that manage runtime PM themselves or are known to misbehave with "auto" (as in TLP).
RUNTIME_PM_DENY = {"mei_me", "nouveau", "radeon", "amdgpu", "nvidia", "nvidia-gpu"}
CHARGE_PATTERN = "/sys/class/power_supply/BAT*/charge_control_end_threshold"


def _driver(device):
    try:
        return Path(device, "driver").resolve().name
    except OSError:
        return ""


def detect():
    """Model differences: device addresses and names differ between machines, so they are searched.

    Runs on import; restore() calls it again when modules load late at boot.
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

    # Runtime power management of PCI devices other than NVIDIA. A device whose driver does not
    # support it stays awake even with "auto"; one without a driver (unused Wi-Fi card) sleeps.
    RUNTIME_PM = sorted(d + "/power/control" for d in glob.glob(PCI + "*")
                        if d + "/power/control" not in GPU_PM
                        and Path(d, "power/control").exists()
                        and _driver(d) not in RUNTIME_PM_DENY)
    BLUETOOTH = sorted(glob.glob("/sys/class/bluetooth/hci*/rfkill*/soft"))  # 1 = off

    # The charge limit is independent of modes, so it is not in ALLOWED.
    # msi-ec sets the start threshold to 10 below the limit by itself.
    CHARGE_LIMIT = BAT + "charge_control_end_threshold"
    CHARGE_START = BAT + "charge_control_start_threshold"

    # Files that may be written and the values they accept.
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

STATE_DIR = Path("/var/lib/msi-ultrapower")
RESTORE_SERVICE = "msi-ultrapower-restore.service"
RESTORE_UNIT = Path("/usr/lib/systemd/system") / RESTORE_SERVICE  # installed by the package


def read_state():
    """Current values of the allow-listed files that exist."""
    return {p: Path(p).read_text().strip() for p in ALLOWED if Path(p).exists()}


def available_shift_modes():
    listed = _read(EC + "available_shift_modes").split()
    return [m for m in SHIFT_MODES if m in listed] or list(SHIFT_MODES)


def writable(state):
    """Maps values that can be read but not written back to a writable equivalent."""
    state = dict(state)
    if state.get(EC + "shift_mode") == "unspecified":
        # Without "comfort", the nearest mode (same rule as capabilities.nearest_shift).
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
    """Writes the settings and undoes the changed ones on error. Returns the old state."""
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
    """Saves the settings and enables the service that restores them at boot."""
    validate(state)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    target = STATE_DIR / "hardware.json"
    temp = STATE_DIR / "hardware.tmp"
    temp.write_text(json.dumps(state, indent=2))
    temp.chmod(0o600)
    enable_restore_service()
    temp.replace(target)


def enable_restore_service():
    # Without the package (development from source) there is no service; just save.
    if RESTORE_UNIT.exists():
        subprocess.run(["systemctl", "enable", RESTORE_SERVICE], check=True)


def write_charge_limit(value):
    if value not in CHARGE_LIMITS or not Path(CHARGE_LIMIT).exists():
        raise ValueError(_("Unsupported charge limit:") + f" {value}")
    Path(CHARGE_LIMIT).write_text(value + "\n")
    if Path(CHARGE_LIMIT).read_text().strip() != value:
        raise RuntimeError(_("Could not verify:") + " " + CHARGE_LIMIT)


def set_charge_limit(value):
    """Applies the charge limit and saves it for boot."""
    write_charge_limit(value)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = STATE_DIR / "charge.tmp"
    temp.write_text(value + "\n")
    temp.chmod(0o600)
    enable_restore_service()
    temp.replace(STATE_DIR / "charge")


# At boot msi-ec and the battery extension may load after the service; wait for these paths.
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
    detect()  # refresh the allow-list with late devices

    if saved:
        state = saved
        # When booted with the integrated GPU only, NVIDIA files are missing on purpose, and
        # devices such as Bluetooth may not be ready yet. Skip missing files.
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


def parse_commit(line):
    """"COMMIT gpu=integrated save=no" → {"gpu": "integrated", "save": "no"}; None if not COMMIT."""
    words = line.split()
    if not words or words[0] != "COMMIT":
        return None
    return dict(word.split("=", 1) for word in words[1:] if "=" in word)


def forget():
    """Back to the previous settings: no mode values are left to restore at boot (the charge limit is separate)."""
    (STATE_DIR / "hardware.json").unlink(missing_ok=True)


def transaction(target):
    """Apply → READY → wait for COMMIT; roll back without it.

    COMMIT options: gpu=integrated|hybrid (also sets the NVIDIA boot setting),
    save=no (restoring previous settings; the values restored at boot are removed).
    """
    before = apply(target)
    print("READY", flush=True)
    options = parse_commit(sys.stdin.readline())
    if options is None:
        apply(writable(before))
        print("ROLLED_BACK", flush=True)
        return
    try:
        if options.get("save") == "no":
            forget()
        else:
            persist(target)
    except BaseException:
        apply(writable(before))
        raise
    print("COMMITTED", flush=True)
    if "gpu" in options:
        # The hardware settings are saved; they stay even if the GPU step fails.
        try:
            gpu_boot.configure(options["gpu"])
        except Exception as exc:
            raise RuntimeError(_("GPU configuration error:") + f" {exc}") from exc


# Only this helper's action, and it only does allow-listed work.
POLKIT_ACTIONS = ("io.github.bugrakaann.msiultrapower.hardware",)
POLKIT_RULE = Path("/etc/polkit-1/rules.d/49-msi-ultrapower.rules")
POLKIT_HEADER = "// Managed by msi-ultrapower hardware.py\n"
# Only msi-ultrapower actions; only local administrators (wheel) in an active session.
POLKIT_TEXT = POLKIT_HEADER + """polkit.addRule(function(action, subject) {
    var actions = [%s];
    if (actions.indexOf(action.id) >= 0 && subject.local && subject.active
            && subject.isInGroup("wheel")) {
        return polkit.Result.YES;
    }
});
""" % ", ".join(f'"{a}"' for a in POLKIT_ACTIONS)


def set_passwordless(enabled):
    """Writes or removes the polkit rule that lets modes apply without the administrator password."""
    if POLKIT_RULE.exists() and not POLKIT_RULE.read_text().startswith(POLKIT_HEADER):
        raise RuntimeError(_("{path} does not belong to msi-ultrapower; not touched").format(path=POLKIT_RULE))
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
    elif argv[1] == "--charge":
        set_charge_limit(argv[2])
    elif argv[1] == "--passwordless":
        set_passwordless(argv[2] == "1")
    else:
        transaction(json.loads(argv[1]))


def entry():
    """Entry point of /usr/lib/msi-ultrapower/msi-ultrapower-hardware and the systemd service."""
    try:
        main(sys.argv)
    except Exception as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

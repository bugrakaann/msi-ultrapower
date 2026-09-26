"""Harici komutlar için ince katman: powerprofilesctl ve kscreen-doctor."""
import json
import subprocess

from .privileged import hardware as hw


def run(*args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=30)
    output = p.stdout + p.stderr
    if p.returncode or "applying config failed" in output.lower():
        raise RuntimeError(" ".join(args[:2]) + ": " + p.stderr.strip() + p.stdout.strip())
    return p.stdout.strip()


def get_power_profile():
    return run("powerprofilesctl", "get")


def set_power_profile(profile):
    run("powerprofilesctl", "set", profile)


def get_outputs():
    return json.loads(run("kscreen-doctor", "-j"))["outputs"]


def apply_screen(args):
    run("kscreen-doctor", *args)


def capture():
    """Geri dönüş için saklanan anlık görüntü (JSON'a yazılabilir sözlük)."""
    return {"profile": get_power_profile(), "outputs": get_outputs(), "hardware": hw.read_state()}

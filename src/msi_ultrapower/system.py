"""Harici komutlar için ince katman: powerprofilesctl ve kscreen-doctor."""
import json
import shutil
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
    """Ekranlar; kscreen-doctor yoksa (KDE dışı) boş liste."""
    if not shutil.which("kscreen-doctor"):
        return []
    return json.loads(run("kscreen-doctor", "-j"))["outputs"]


def apply_screen(args):
    if args:
        run("kscreen-doctor", *args)


def capture():
    """Geri dönüş için saklanan anlık görüntü (JSON'a yazılabilir sözlük)."""
    return {"profile": get_power_profile(), "outputs": get_outputs(), "hardware": hw.read_state()}


def plasma_version():
    """"6.7.5" gibi; Plasma yoksa boş."""
    if not shutil.which("plasmashell"):
        return ""
    try:
        return run("plasmashell", "--version").split()[-1]
    except (RuntimeError, IndexError, OSError):
        return ""

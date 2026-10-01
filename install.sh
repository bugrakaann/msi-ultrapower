#!/usr/bin/env bash
# msi-ultrapower installer for Arch-based distributions.
#
#   curl -fsSL https://raw.githubusercontent.com/bugrakaann/msi-ultrapower/main/install.sh | bash
#
# Downloads the source, builds the pacman package and installs it. Running it again updates.
# Everything is inside main(), so nothing runs if the download is cut off halfway.
set -euo pipefail

REPO="https://github.com/bugrakaann/msi-ultrapower.git"
BRANCH="${MSI_ULTRAPOWER_BRANCH:-main}"

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m==> Warning:\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m==> Error:\033[0m %s\n' "$*" >&2; exit 1; }

main() {
    [ "$(id -u)" -ne 0 ] || die "Run this as your normal user, not root (sudo is asked when needed)."
    command -v pacman >/dev/null || die "pacman not found. msi-ultrapower supports Arch-based distributions only."
    [ -e /dev/tty ] || die "A terminal is required (pacman asks for confirmation)."

    if ! command -v plasmashell >/dev/null; then
        warn "KDE Plasma was not found. Display settings (refresh rate, brightness) will be skipped."
    fi

    say "Installing build tools (git, base-devel) if missing..."
    sudo pacman -S --needed git base-devel </dev/tty

    local work
    work="$(mktemp -d)"
    trap 'rm -rf "$work"' EXIT

    say "Downloading msi-ultrapower ($BRANCH)..."
    git clone --quiet --depth 1 --branch "$BRANCH" "$REPO" "$work/msi-ultrapower"

    say "Building and installing the package..."
    (cd "$work/msi-ultrapower/packaging/arch" && makepkg -sfci </dev/tty)

    if [ ! -d /sys/devices/platform/msi-ec ]; then
        warn "The msi-ec driver is not loaded: fan, EC mode, Cooler Boost and the charge limit are unavailable."
        warn "Install it from the AUR (for example: yay -S msi-ec-dkms-git), then restart."
    fi

    say "Done. Open \"Power Modes\" from the application menu, or run: msi-ultrapower --help"
    say "Check what works on this laptop: msi-ultrapower doctor"
}

main "$@"

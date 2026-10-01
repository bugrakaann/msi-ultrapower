"""Power mode definitions. The command line and the window read the modes from here.

To add or change a mode, edit only this file. Values are mapped to what the model
supports: for example, without an "eco" EC mode the nearest saving mode is used, and
"max" means the highest refresh rate of the panel.
"""
from dataclasses import dataclass

from .i18n import N_, _

EXTERNAL_CHOICES = {
    "auto": N_("Automatic (by mode)"),
    "keep": N_("Keep on"),
    "off": N_("Turn off"),
}


@dataclass(frozen=True)
class Preset:
    key: str             # name on the command line: msi-ultrapower <key>
    title_source: str    # name shown in the window (English source; .title is translated)
    summary_source: str  # one-line summary on the card
    icon: str            # KDE/Breeze theme icon
    profile: str         # powerprofilesctl profile
    brightness: int      # built-in display brightness (%)
    shift: str           # MSI EC shift_mode (or the nearest one)
    boost: str           # Cooler Boost: on/off
    turbo: str           # "0" turbo on, "1" off (like intel_pstate/no_turbo)
    gpu: str             # NVIDIA power/control: on/auto
    fan: str = "auto"    # MSI EC fan_mode
    panel: str = "max"   # built-in refresh rate: "max" highest, "min" lowest

    @property
    def title(self):
        return _(self.title_source)

    @property
    def summary(self):
        return _(self.summary_source)

    @property
    def is_battery(self):
        """Battery modes turn NVIDIA and NVIDIA-wired displays off and let devices sleep."""
        return self.profile == "power-saver"


_BATTERY = dict(profile="power-saver", brightness=30, shift="eco", boost="off", turbo="1",
                gpu="auto", icon="battery-profile-powersave")

PRESETS = {p.key: p for p in [
    Preset("performance", N_("Maximum performance"), N_("100% brightness · Turbo · Cooler Boost"),
           icon="battery-profile-performance", profile="performance",
           brightness=100, shift="turbo", boost="on", turbo="0", gpu="on"),
    Preset("performance-manual", N_("Performance · Manual fan"),
           N_("100% brightness · Turbo · Your own fan curve"),
           icon="adjustlevels", profile="performance", brightness=100,
           shift="turbo", boost="off", turbo="0", gpu="on", fan="advanced"),
    Preset("balanced", N_("Balanced"), N_("60% brightness · Automatic fan · NVIDIA sleeps when idle"),
           icon="battery-profile-balanced", profile="balanced",
           brightness=60, shift="comfort", boost="off", turbo="0", gpu="auto"),
    Preset("battery", N_("Maximum battery"), N_("30% brightness · NVIDIA off · Devices sleep"),
           **_BATTERY),
    Preset("battery-low-hz", N_("Maximum battery · Low Hz"), N_("Lowest Hz · 30% brightness · NVIDIA off"),
           panel="min", **{**_BATTERY, "icon": "monitor"}),
]}

RESTORE_COMMAND = "restore"

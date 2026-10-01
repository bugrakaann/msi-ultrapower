# msi-ultrapower — power modes for MSI laptops on KDE Plasma

**English** · [Türkçe](README.tr.md)

One click switches your MSI laptop between performance, balanced and battery modes.
Each mode sets the power profile, display refresh rate and brightness, the MSI EC
(fan, shift mode, Cooler Boost), CPU turbo, keyboard backlight, device power saving
and the NVIDIA GPU together, and rolls everything back if any step fails.

![Power Modes window](docs/screenshot.png)

- **See before you apply.** The window lists exactly which settings will change on *your*
  machine ("11 settings will change: brightness 100% → 30% …"). Hovering a mode shows everything it does.
- **Battery care.** Charge limit of 60 / 80 / 100%, restored at boot.
- **Battery mode like TLP, plus more.** PCI runtime power management, sound card and disk power
  saving, and the NVIDIA GPU fully disabled at the next boot.
- **Automatic mode.** Switches mode when you plug the charger in or out.
- **System tray.** Change modes and the charge limit without opening the window.
- **Live status.** Battery, current and average power use on battery, CPU/GPU temperature and fan speed, NVIDIA state (also in the tray tooltip).
- **Languages.** English, Türkçe, Русский, Español, العربية (right-to-left).

## Modes

| Mode (CLI) | Power profile / turbo | EC / fan | Built-in display | NVIDIA |
|---|---|---|---|---|
| `performance` | performance / on | turbo / Cooler Boost | highest Hz · 100% | always awake |
| `performance-manual` | performance / on | turbo / `advanced` (MControlCenter curve) | highest Hz · 100% | always awake |
| `balanced` | balanced / on | comfort / auto | highest Hz · 60% | sleeps when idle |
| `battery` | power-saver / off | eco / auto | highest Hz · 30% | off after a restart |
| `battery-low-hz` | power-saver / off | eco / auto | lowest Hz (e.g. 48) · 30% | off after a restart |

Battery modes also turn off the keyboard backlight and let PCI devices, the sound card and the
disk sleep (can be turned off in Settings). Bluetooth can optionally be turned off too.
External displays keep their refresh rate and resolution in every mode. In battery modes,
only outputs wired to the NVIDIA GPU are forced off; others follow your choice.

Other modes and **Restore previous settings** put these back as they were before the first mode.

## Requirements and compatibility

- **Arch-based distribution** (Arch, CachyOS, EndeavourOS, Manjaro) with **KDE Plasma 6**
  and `power-profiles-daemon`.
- **[msi-ec](https://github.com/BeardOverflow/msi-ec)** for fan, EC mode, Cooler Boost and the
  charge limit (AUR: `msi-ec-dkms-git`). msi-ec supports a list of EC firmware versions; without
  it, those settings are skipped and everything else still works.

The program adapts to the model instead of assuming one:

| Area | How it adapts |
|---|---|
| EC | Uses the shift and fan modes your EC reports; a missing mode is replaced by the nearest one. The manual-fan mode is disabled if the EC has no `advanced` fan mode. |
| Display | Uses the panel's highest / lowest refresh rate (120, 144, 165, 240 Hz panels work). Single-rate panels disable the low-Hz mode. |
| NVIDIA | Found by vendor, not by PCI address. Laptops without NVIDIA skip the GPU step. |
| **MUX switch** | If the BIOS GPU mode is *Discrete* and NVIDIA drives the built-in display, turning NVIDIA off is **refused** (it would black out the screen). Choose *MSHybrid/Optimus* in the BIOS. |
| CPU turbo | Intel (`intel_pstate/no_turbo`) and AMD (`cpufreq/boost`). |
| Other | Battery, keyboard backlight and Bluetooth are looked up by name; missing ones are skipped. Running TLP, auto-cpufreq or tuned is detected and reported as a conflict. |

Run `msi-ultrapower doctor` to see what works on your laptop. Developed on a GF65 Thin 9SEXR;
reports from other models are very welcome (see [Reporting your model](#reporting-your-model)).

## Install

```
git clone https://github.com/bugrakaann/msi-ultrapower.git
cd msi-ultrapower
make install      # builds the package and installs it with pacman (also used to update)
make uninstall    # removes it (sudo pacman -R msi-ultrapower)
```

To restore display and hardware settings before removing, run `msi-ultrapower restore` first.
Your own data stays in `~/.local/share/msi-ultrapower` and `~/.config/msi-ultrapower`.

## Usage

Open **Power Modes** from the application menu: pick a mode, check what will change, press **Apply**.
The ⚙ button opens Settings (language, battery mode options, automatic mode, tray).

Command line (Turkish command names work too):

```
msi-ultrapower balanced                      # apply a mode
msi-ultrapower balanced --external keep      # keep external displays on (auto | keep | off)
msi-ultrapower battery --dry-run             # show the plan without changing anything
msi-ultrapower status                        # show the real current values
msi-ultrapower restore                       # go back to the settings before the first mode
msi-ultrapower charge 80                     # charge the battery up to 80% (60 | 80 | 100)
msi-ultrapower doctor                        # compatibility report
msi-ultrapower-ui --tray                     # start in the system tray
```

### Automatic mode

In Settings, choose a mode for *plugged in* and one for *on battery*. The app switches when the
charger is plugged in or out, as long as it is running (the tray is enough; enable
*Start in the system tray when I log in*). Automatic switches do not touch the NVIDIA boot setting,
so the boot image is not rebuilt every time you unplug; apply a battery mode by hand to turn
NVIDIA fully off.

### No password prompts

In Settings, *Do not ask for the administrator password* adds a polkit rule that lets local,
active administrators (`wheel`) run the msi-ultrapower helper without a password: switching modes,
the charge limit and automatic mode no longer ask. Nothing else is allowed. The rule is removed
when you turn the option off or uninstall.

## Reporting your model

Open an issue with the output of:

```
msi-ultrapower doctor
```

It lists your model, EC firmware, available EC/fan modes, panel refresh rates, which outputs are
wired to NVIDIA and any conflicting services.

## Translations

Translations live in `po/`. To add or fix a language, edit or create `po/<code>.po`
(start from `po/msi-ultrapower.pot`), run `make locale && make run` to try it, and open a pull request.
The current translations were machine-assisted; native speakers are welcome to improve them.

## Security and rollback

- Root is only used by one small helper, `/usr/lib/msi-ultrapower/msi-ultrapower-hardware`,
  started with `pkexec` (polkit action `io.github.bugrakaann.msiultrapower.hardware`). A mode switch
  asks for the password once, including the NVIDIA boot setting; it is not asked at all when the
  NVIDIA setting does not change. There is no always-running root service and no sudo rule.
- The hardware helper only writes files on an allow-list (`ALLOWED` in
  `privileged/hardware.py`), with allowed values.
- It applies the settings and waits for `COMMIT`. If the KDE side (profile, displays)
  cannot be verified, everything is rolled back. *Restore previous settings* also removes the
  values restored at boot.
- If the GPU configuration fails, its files are restored and the boot images rebuilt.

**Recovery:** if the graphical session does not start, switch to a TTY (Ctrl+Alt+F3) and run

```
sudo /usr/lib/msi-ultrapower/msi-ultrapower-gpu-boot hybrid
```

then restart. This only removes the NVIDIA block this tool added.

## What gets installed

| Path | What |
|---|---|
| `/usr/bin/msi-ultrapower`, `/usr/bin/msi-ultrapower-ui` | Commands |
| `/usr/lib/msi-ultrapower/` | Root helper (the polkit action points here) and the GPU recovery command |
| `/usr/lib/python3.X/site-packages/msi_ultrapower/` | Program code |
| `/usr/share/polkit-1/actions/io.github.bugrakaann.msiultrapower.policy` | Polkit actions |
| `/usr/lib/systemd/system/msi-ultrapower-restore.service` | Restores hardware settings and the charge limit at boot |
| `/usr/share/locale/*/LC_MESSAGES/msi-ultrapower.mo` | Translations |
| `/var/lib/msi-ultrapower/` | Hardware values and charge limit restored at boot |
| `/etc/modprobe.d/90-msi-ultrapower-nvidia.conf`, `/etc/udev/rules.d/50-msi-ultrapower-nvidia.rules`, `/etc/{mkinitcpio,dracut}.conf.d/99-msi-ultrapower-gpu.conf` | Battery modes only: disable NVIDIA at boot |
| `~/.config/msi-ultrapower/settings.json` | Your settings |
| `~/.local/share/msi-ultrapower/` | Settings before the first mode, active mode, history |

## Development

```
make test     # unit tests
make run      # run the UI from src/ without installing
make po       # extract strings to po/msi-ultrapower.pot and update translations
make locale   # compile translations for make run
make clean    # remove build leftovers
```

```
src/msi_ultrapower/
├── presets.py        ← the modes; edit only this file to change a mode
├── capabilities.py   ← what this laptop supports (model differences)
├── plan.py           ← computes what will change (touches nothing)
├── describe.py       ← turns a plan into readable text for the UI
├── controller.py     ← a full switch: plan → apply → verify → save / roll back
├── display.py        ← display plan and verification (kscreen-doctor)
├── i18n.py           ← translations (gettext)
├── privileged/       ← code that runs as ROOT; standard library only
└── ui/               ← graphical interface (PySide6), tray and automatic mode
```

The UI never touches hardware itself: it runs the CLI, so the terminal and the window always
behave the same.

## Disclaimer

msi-ultrapower is an unofficial project and is not affiliated with or endorsed by Micro-Star
International (MSI). It writes to the embedded controller, kernel module and boot settings;
use it at your own risk. It comes with no warranty (see sections 15–16 of the license).

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

# msi-ultrapower

**Power modes for MSI laptops on KDE Plasma.**

**English** · [Türkçe](README.tr.md) · [Русский](README.ru.md) · [Español](README.es.md) · [العربية](README.ar.md)

One click switches your MSI laptop between performance, balanced and battery modes. Each mode sets
the power profile, screen refresh rate and brightness, fan and EC mode, CPU turbo, keyboard light,
device power saving and the NVIDIA GPU together, and undoes everything if a step fails.

![Power Modes window](docs/screenshot.png)

## Install

On Arch, CachyOS, EndeavourOS or Manjaro with KDE Plasma 6:

```sh
curl -fsSL https://raw.githubusercontent.com/bugrakaann/msi-ultrapower/main/install.sh | bash
```

Run the same command again to update. For fan, EC mode, Cooler Boost and the charge limit, also
install the [msi-ec](https://github.com/BeardOverflow/msi-ec) driver from the AUR
(`msi-ec-dkms-git`) and restart. Without it, everything else still works.

<details>
<summary>Install manually</summary>

```sh
git clone https://github.com/bugrakaann/msi-ultrapower.git
cd msi-ultrapower
make install
```

</details>

## How to use

1. Open **Power Modes** from the application menu.
2. Pick a mode. The window lists exactly what will change on your laptop.
3. Press **Apply** and enter your password.

To go back to how things were before you first used the app, press **Restore previous settings**.
Battery modes turn the NVIDIA GPU fully off after a restart; the window tells you when a restart
is needed.

### Modes

| Mode | What it does |
|---|---|
| **Maximum performance** | Performance profile, turbo, Cooler Boost, highest refresh rate, 100% brightness |
| **Performance · Manual fan** | Same, with your own fan curve (set it in MControlCenter) |
| **Balanced** | Balanced profile, automatic fan, 60% brightness, NVIDIA sleeps when idle |
| **Maximum battery** | Power saver, no turbo, 30% brightness, NVIDIA off, devices sleep, keyboard light off |
| **Maximum battery · Low Hz** | Same, plus the lowest refresh rate of the screen |

External displays keep their resolution and refresh rate. Outputs wired to NVIDIA turn off in
battery modes, because NVIDIA is off.

### Settings (⚙)

- **Charge limit** – charge the battery up to 60, 80 or 100%. 60–80% extends battery life.
- **Automatic mode** – switch modes when the charger is plugged in or out.
- **Do not ask for the administrator password** – no password for mode changes, the charge limit
  and automatic mode.
- **Start in the system tray** – switch modes and see battery, power use and temperatures from the tray.
- **Battery mode options** – let devices sleep, turn Bluetooth off.
- **Language** – English, Türkçe, Русский, Español, العربية.

### Command line

```sh
msi-ultrapower balanced            # performance, performance-manual, balanced, battery, battery-low-hz
msi-ultrapower battery --dry-run   # show what would change, change nothing
msi-ultrapower restore             # back to the settings before the first mode
msi-ultrapower charge 80           # charge limit: 60, 80 or 100
msi-ultrapower status              # current values
msi-ultrapower doctor              # what works on this laptop
```

## Compatibility

Developed on an MSI GF65 Thin 9SEXR. The app detects what your laptop supports instead of assuming
one model: EC and fan modes, screen refresh rates (120–240 Hz), Intel or AMD turbo, and whether
there is an NVIDIA GPU. Missing features are skipped and shown in the window.

- **MUX switch:** if the BIOS GPU mode is *Discrete*, NVIDIA drives the screen and the app will
  not turn it off. Choose *MSHybrid/Optimus* in the BIOS to use battery modes fully.
- **TLP, auto-cpufreq, tuned** conflict with power profiles; the app warns when one is running.

Run `msi-ultrapower doctor` and [open an issue](https://github.com/bugrakaann/msi-ultrapower/issues/new?template=model-report.md)
with the output to report how it works on your model.

## Uninstall

```sh
msi-ultrapower restore        # optional: put your previous settings back
sudo pacman -R msi-ultrapower
```

Your settings stay in `~/.config/msi-ultrapower` and `~/.local/share/msi-ultrapower`.

## Troubleshooting

**The desktop does not start after choosing a battery mode.** Switch to a text console with
Ctrl+Alt+F3, log in and run:

```sh
sudo /usr/lib/msi-ultrapower/msi-ultrapower-gpu-boot hybrid
```

Then restart. This only removes the NVIDIA block added by msi-ultrapower.

**Something failed.** Press **Show log** in the window, or run the same mode from a terminal to
see the full output.

## How it works

- Root access is used by one small helper, started with `pkexec`. It only writes an allow-list of
  settings (`ALLOWED` in `src/msi_ultrapower/privileged/hardware.py`). There is no background root service.
- Settings are applied, verified, and only then saved. If anything cannot be verified, all of it
  is rolled back.
- Hardware settings and the charge limit are restored at boot by `msi-ultrapower-restore.service`.

## Contributing

- **Translations** live in `po/`. They were machine-assisted; fixes from native speakers are welcome.
- **Development:** `make run` starts the app from the source, `make test` runs the tests,
  `make po` updates the translation files. Modes are defined in `src/msi_ultrapower/presets.py`.

## Disclaimer

msi-ultrapower is an unofficial project and is not affiliated with or endorsed by Micro-Star
International (MSI). It changes embedded controller, kernel module and boot settings; use it at
your own risk. It comes with no warranty.

## License

[GPL-3.0-or-later](LICENSE)

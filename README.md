# rog-lighting

A small, local-only, Armoury Crate–style lighting panel for ASUS ROG laptops on Linux. It controls the **keyboard backlight** and the **Slash LED bar** on the back of the lid, and it can make **Fn+F2 / Fn+F3** work again.

It was written for the ROG Zephyrus G14 (2024, GA403) on Ubuntu 24.04. There, the stock 6.8 kernel's ASUS driver fails to load, so the brightness keys do nothing, and asusctl doesn't work out of the box.

> Unofficial project. Not affiliated with or endorsed by ASUS. "ROG", "Armoury Crate" and "Zephyrus" are trademarks of ASUSTeK Computer Inc.

## Features

- **Keyboard backlight:** brightness Off / Low / Medium / High, plus Static, Breathing, Color cycle and Rainbow effects with color and speed.
- **Slash lighting:** on/off, brightness, 15 animations, and the pause between loops.
- **Fn+F2 / Fn+F3:** an optional background helper handles the brightness keys and restores your settings at login and after sleep.
- **Command line:** for scripts and key bindings.
- **No service, no root at runtime, no extra dependencies.**

## Supported hardware

| Model | Keyboard | Slash | Status |
| --- | --- | --- | --- |
| ROG Zephyrus G14 2024 (GA403UU) | ✅ `0b05:19b6` | ✅ `0b05:193b` | Developed on this model |

Many ROG laptops from 2020 onward use the same keyboard controller (`0b05:19b6`), so keyboard control will likely work on them too. The Slash bar only exists on 2024+ G14/G16 models, and 2025 models may use different packets. If you try another model, please open an issue with the results.

## Requirements

- Linux with GTK4 and libadwaita for Python. On Ubuntu 24.04 these are installed by default; otherwise install them:
  ```bash
  sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
  ```
- sudo once, to install the udev rule.

## Install

```bash
git clone https://github.com/Gavin-Tan1/rog-lighting.git
cd rog-lighting
./install.sh
```

The installer:

- copies the app to `~/.local/share/rog-lighting`
- adds **ROG Lighting** to your app menu
- installs one udev rule (`/etc/udev/rules.d/70-rog-lighting.rules`), which is the only step that needs sudo

Afterwards, `rog-lighting status` should show both devices as `ok`.

## Usage

Open **ROG Lighting** from your app menu. To make the brightness keys work, turn on **Fn+F2 / Fn+F3 hotkeys** in the Background section.

```bash
~/.local/share/rog-lighting/rog-lighting status        # detected devices and permissions
~/.local/share/rog-lighting/rog-lighting kbd 0..3      # keyboard brightness
~/.local/share/rog-lighting/rog-lighting slash on|off  # Slash bar
~/.local/share/rog-lighting/rog-lighting apply         # re-send saved settings
~/.local/share/rog-lighting/rog-lighting daemon --debug-keys   # print hotkey codes
```

## Uninstall

```bash
~/.local/share/rog-lighting/uninstall.sh
```

## How it works

The app sends HID feature reports straight to the lighting controllers through `/dev/hidraw*`:

| Device | USB ID | Report | Size |
| --- | --- | --- | --- |
| Keyboard (Aura) | `0b05:19b6` | `0x5a` brightness, `0x5d` effects | 17 bytes |
| Slash bar | `0b05:193b` | `0x5e` | 128 bytes |

Unlike tools that use libusb, it never detaches the keyboard driver, so your keyboard keeps working while lighting changes.

The hotkey helper reads the ASUS vendor report `0x5a` from the keyboard's hidraw node. That's where the firmware sends Fn+F2 (`0xc5`) and Fn+F3 (`0xc4`).

Why the keys don't work on stock Ubuntu 24.04: on kernel 6.8, `asus-nb-wmi` fails to probe (`error -17`, a conflict with `amd_pmf` over `platform_profile`). As a result, no `asus::kbd_backlight` LED is created and nothing handles the brightness keys. Newer kernels may fix this, in which case you may not need this app for the keyboard.

## Privacy

- **No network access, telemetry, analytics or logs.**
- **Files it writes:** settings go to `~/.config/rog-lighting/settings.json`. If you enable the hotkey helper, it also adds an autostart entry at `~/.config/autostart/rog-lighting-daemon.desktop`.
- **Keystrokes:** the hotkey helper only acts on ASUS hotkey reports. It never stores or sends keystrokes.

## Security note

The udev rule uses `uaccess`, so only the user logged in at the laptop gets access, not every account on the system. One caveat: the keyboard's hidraw node carries the keyboard's input reports, so any program running as you could read your keystrokes from it. Most desktop setups already allow this in other ways, but if it matters to you, remove the rule with `uninstall.sh`.

## Troubleshooting

- **"no permission" in `status`:** run `./install.sh` again, then log out and back in.
- **Fn keys don't respond:** turn the hotkey switch off, run `rog-lighting daemon --debug-keys` and press the keys. Then open an issue with what it prints.
- **The keyboard looks wrong after an effect:** choose Static and a color in the app, or run `rog-lighting apply`.

## Contributing

This project is open source, and anyone can contribute tests, fixes, model support or improvements. See [CONTRIBUTING.md](CONTRIBUTING.md). Run the tests with:

```bash
python3 -m unittest discover -s tests -v
```

## Credits

The packet formats are based on reverse-engineering work by these projects:

- [rogauracore](https://github.com/wroberts/rogauracore) (MIT)
- [asusctl](https://gitlab.com/asus-linux/asusctl) (MPL-2.0)
- [G-Helper](https://github.com/seerge/g-helper) (GPL-3.0)

No code from these projects is included.

## License

[MIT](LICENSE). You're free to use, modify and share this project.

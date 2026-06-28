# Pi Cage Kiosk Setup

For a Raspberry Pi without a full desktop environment, Cage is a good first
choice. Cage is the minimal Wayland kiosk compositor; Chromium is still the app
runtime.

```text
systemd/login
  cage
    chromium
      http://127.0.0.1:8090
```

## Packages

Start from Raspberry Pi OS Lite and install only the pieces needed for a browser
kiosk:

```sh
sudo apt update
sudo apt install cage chromium-browser
```

Package names may vary slightly by Raspberry Pi OS/Debian release. If
`chromium-browser` is unavailable, check for `chromium`.

## Manual Test

Start the kiosk UI server:

```sh
cd ~/hermes-pi-kiosk
python3 -m http.server 8090 --directory public
```

From the Pi console, launch Chromium inside Cage:

```sh
cage -- chromium-browser \
  --kiosk \
  --ozone-platform=wayland \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  http://127.0.0.1:8090
```

If Chromium complains about the binary name, try `chromium` instead of
`chromium-browser`.

## Installer Script

The project includes a helper script for the Pi:

```sh
scripts/install-pi-kiosk.sh
```

To also create systemd user services for the static web server and Cage kiosk:

```sh
scripts/install-pi-kiosk.sh --with-systemd
```

The script is intentionally conservative. It installs `cage`, Chromium, and
`python3`, then writes user services only when `--with-systemd` is passed.

Useful overrides:

```sh
HERMES_KIOSK_PORT=8090 scripts/install-pi-kiosk.sh --with-systemd
HERMES_KIOSK_URL=http://127.0.0.1:8090 scripts/install-pi-kiosk.sh --with-systemd
```

## Recommendation

Use Cage if the Pi is dedicated to this car screen. Use Raspberry Pi OS Desktop
only if you want normal desktop tools available locally on the touchscreen.

For this project, do not build against Wayland directly. Keep the UI as a web
app and let Cage handle fullscreen display.

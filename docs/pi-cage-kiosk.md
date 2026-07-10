# Pi Cage Kiosk Setup

For a Raspberry Pi without a full desktop environment, Cage is a good first
choice. Cage is the minimal Wayland kiosk compositor; `surf` is the lightweight
browser runtime.

```text
systemd/login
  cage
    surf
      http://127.0.0.1:8090
```

## Packages

Start from Raspberry Pi OS Lite and install only the pieces needed for a browser
kiosk:

```sh
sudo apt update
sudo apt install alsa-utils cage gpsd surf
```

## Manual Test

Start the kiosk UI server:

```sh
cd ~/hermes-pi-kiosk
scripts/hermes-kiosk-server.py
```

From the Pi console, launch `surf` inside Cage:

```sh
cage -- surf http://127.0.0.1:8090
```

## Installer Script

The project includes a helper script for the Pi:

```sh
scripts/install-pi-kiosk.sh
```

To also create systemd services for the static web server and Cage kiosk:

```sh
scripts/install-pi-kiosk.sh --with-systemd
```

The script is intentionally conservative. It installs `alsa-utils`, `cage`,
`surf`, and `python3`, then writes system services only when `--with-systemd` is
passed.
The web server runs as the kiosk user, while Cage runs from a system service
attached to `tty1` so it can acquire a local DRM session.

The local web server also exposes a small audio test API. By default it records
four seconds from ALSA's `default` capture device and plays the WAV back through
ALSA's `default` playback device.

The same server polls gpsd locally and exposes `/api/gps/status` for the kiosk
UI. Speed is converted from gpsd's meters-per-second value to km/h in the local
server response.

Useful overrides:

```sh
HERMES_KIOSK_PORT=8090 scripts/install-pi-kiosk.sh --with-systemd
HERMES_KIOSK_URL=http://127.0.0.1:8090 scripts/install-pi-kiosk.sh --with-systemd
HERMES_AUDIO_RECORD_SECONDS=4 scripts/install-pi-kiosk.sh --with-systemd
HERMES_AUDIO_CAPTURE_DEVICE=default scripts/install-pi-kiosk.sh --with-systemd
HERMES_AUDIO_PLAYBACK_DEVICE=default scripts/install-pi-kiosk.sh --with-systemd
HERMES_GPSD_HOST=127.0.0.1 scripts/install-pi-kiosk.sh --with-systemd
HERMES_GPSD_PORT=2947 scripts/install-pi-kiosk.sh --with-systemd
```

## Recommendation

Use Cage if the Pi is dedicated to this car screen. Use Raspberry Pi OS Desktop
only if you want normal desktop tools available locally on the touchscreen.

For this project, do not build against Wayland directly. Keep the UI as a web
app and let Cage handle fullscreen display.

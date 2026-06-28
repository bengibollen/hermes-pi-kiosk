# Hermes Pi Kiosk

Lightweight touchscreen kiosk UI for the Hermes car Raspberry Pi.

This project is separate from:

- `hermes-drive`: backend trip context API
- `gps-tui`: GPS diagnostics and logging tool

The kiosk UI is intended to run fullscreen in Chromium on the Pi's 800x460 touch
display. A small local Pi agent can later serve this UI, read `gpsd`, publish
locations to Hermes Drive, and expose local hardware/task controls.

## Display Stack

Chromium is enough for the application target. Wayland or X11 is the operating
system display stack underneath Chromium.

Recommended first setup:

- Raspberry Pi OS Lite with Cage, or Raspberry Pi OS with Desktop
- Chromium in kiosk mode
- Localhost web app served by a small Pi agent or static file server

Do not build against Wayland directly unless the UI later needs native display
integration. For this project, HTML/CSS/JavaScript in Chromium is the right
abstraction.

If the Pi has no desktop environment installed, see `docs/pi-cage-kiosk.md`.

## Initial UI Goals

- Fit 800x460 without scrolling
- Large touch-friendly controls
- Show GPS/backend/agent status
- Provide push-to-talk and task buttons
- Stay usable without network access to Hermes Drive
- Avoid heavy maps and animation in the first version

## Run Locally

From this project directory:

```sh
python3 -m http.server 8090 --directory public
```

Then open:

```text
http://127.0.0.1:8090
```

On the Pi, Chromium can later launch this URL in kiosk mode.

## Pi Install Helper

On Raspberry Pi OS Lite, run:

```sh
scripts/install-pi-kiosk.sh
```

To also create systemd user services:

```sh
scripts/install-pi-kiosk.sh --with-systemd
```

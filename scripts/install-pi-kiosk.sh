#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_URL="${HERMES_KIOSK_URL:-http://127.0.0.1:8090}"
PORT="${HERMES_KIOSK_PORT:-8090}"

usage() {
  cat <<EOF
Usage: scripts/install-pi-kiosk.sh [--with-systemd]

Installs packages needed to run Hermes Pi Kiosk on Raspberry Pi OS Lite.

Options:
  --with-systemd   Create and enable user services for the local web server
                   and Cage/Chromium kiosk.

Environment:
  HERMES_KIOSK_URL    URL Chromium opens. Default: ${APP_URL}
  HERMES_KIOSK_PORT   Local static server port. Default: ${PORT}
EOF
}

WITH_SYSTEMD=0
for arg in "$@"; do
  case "$arg" in
    --with-systemd)
      WITH_SYSTEMD=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This installer expects a Debian/Raspberry Pi OS system with apt-get." >&2
  exit 1
fi

echo "Installing kiosk packages..."
sudo apt-get update

if apt-cache show chromium-browser >/dev/null 2>&1; then
  CHROMIUM_PACKAGE="chromium-browser"
elif apt-cache show chromium >/dev/null 2>&1; then
  CHROMIUM_PACKAGE="chromium"
else
  echo "Could not find chromium-browser or chromium in apt." >&2
  exit 1
fi

sudo apt-get install -y \
  cage \
  "${CHROMIUM_PACKAGE}" \
  python3

if command -v chromium-browser >/dev/null 2>&1; then
  CHROMIUM_BIN="$(command -v chromium-browser)"
elif command -v chromium >/dev/null 2>&1; then
  CHROMIUM_BIN="$(command -v chromium)"
else
  echo "Chromium package installed, but no chromium binary was found on PATH." >&2
  exit 1
fi

echo "Using Chromium binary: ${CHROMIUM_BIN}"

if [[ "${WITH_SYSTEMD}" -eq 0 ]]; then
  cat <<EOF

Package install complete.

Manual test:
  cd "${PROJECT_DIR}"
  python3 -m http.server "${PORT}" --directory public

Then from the Pi console:
  cage -- "${CHROMIUM_BIN}" --kiosk --ozone-platform=wayland --noerrdialogs --disable-infobars --disable-session-crashed-bubble "${APP_URL}"

Run again with --with-systemd to create user services.
EOF
  exit 0
fi

SYSTEMD_DIR="${HOME}/.config/systemd/user"
mkdir -p "${SYSTEMD_DIR}"

cat > "${SYSTEMD_DIR}/hermes-kiosk-web.service" <<EOF
[Unit]
Description=Hermes Pi Kiosk static web server

[Service]
WorkingDirectory=${PROJECT_DIR}
ExecStart=/usr/bin/python3 -m http.server ${PORT} --directory public
Restart=always
RestartSec=2

[Install]
WantedBy=default.target
EOF

cat > "${SYSTEMD_DIR}/hermes-kiosk.service" <<EOF
[Unit]
Description=Hermes Pi Kiosk display
After=hermes-kiosk-web.service
Wants=hermes-kiosk-web.service

[Service]
ExecStart=/usr/bin/cage -- ${CHROMIUM_BIN} --kiosk --ozone-platform=wayland --noerrdialogs --disable-infobars --disable-session-crashed-bubble ${APP_URL}
Restart=always
RestartSec=2

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable hermes-kiosk-web.service hermes-kiosk.service

cat <<EOF

Systemd user services installed and enabled:
  hermes-kiosk-web.service
  hermes-kiosk.service

Start them now with:
  systemctl --user start hermes-kiosk-web.service hermes-kiosk.service

If they should start automatically after boot without an interactive login, run:
  sudo loginctl enable-linger "$USER"

Check logs with:
  journalctl --user -u hermes-kiosk.service -f
EOF

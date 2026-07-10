#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_URL="${HERMES_KIOSK_URL:-http://127.0.0.1:8090}"
PORT="${HERMES_KIOSK_PORT:-8090}"
AUDIO_RECORD_SECONDS="${HERMES_AUDIO_RECORD_SECONDS:-4}"
AUDIO_CAPTURE_DEVICE="${HERMES_AUDIO_CAPTURE_DEVICE:-default}"
AUDIO_PLAYBACK_DEVICE="${HERMES_AUDIO_PLAYBACK_DEVICE:-default}"
GPSD_HOST="${HERMES_GPSD_HOST:-127.0.0.1}"
GPSD_PORT="${HERMES_GPSD_PORT:-2947}"

usage() {
  cat <<EOF
Usage: scripts/install-pi-kiosk.sh [--with-systemd]

Installs packages needed to run Hermes Pi Kiosk on Raspberry Pi OS Lite.

Options:
  --with-systemd   Create and enable system services for the local web server
                   and Cage/surf kiosk on tty1.

Environment:
  HERMES_KIOSK_URL    URL surf opens. Default: ${APP_URL}
  HERMES_KIOSK_PORT   Local static server port. Default: ${PORT}
  HERMES_KIOSK_USER   User to run kiosk services as. Default: ${USER}
  HERMES_AUDIO_RECORD_SECONDS
                      Audio test recording length. Default: ${AUDIO_RECORD_SECONDS}
  HERMES_AUDIO_CAPTURE_DEVICE
                      ALSA capture device. Default: ${AUDIO_CAPTURE_DEVICE}
  HERMES_AUDIO_PLAYBACK_DEVICE
                      ALSA playback device. Default: ${AUDIO_PLAYBACK_DEVICE}
  HERMES_GPSD_HOST    gpsd host. Default: ${GPSD_HOST}
  HERMES_GPSD_PORT    gpsd port. Default: ${GPSD_PORT}
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

sudo apt-get install -y \
  alsa-utils \
  cage \
  gpsd \
  surf \
  python3

if command -v surf >/dev/null 2>&1; then
  BROWSER_BIN="$(command -v surf)"
else
  echo "surf package installed, but no surf binary was found on PATH." >&2
  exit 1
fi

echo "Using browser binary: ${BROWSER_BIN}"

if [[ "${WITH_SYSTEMD}" -eq 0 ]]; then
  cat <<EOF

Package install complete.

Manual test:
  cd "${PROJECT_DIR}"
  HERMES_KIOSK_PORT="${PORT}" \\
    HERMES_AUDIO_RECORD_SECONDS="${AUDIO_RECORD_SECONDS}" \\
    HERMES_AUDIO_CAPTURE_DEVICE="${AUDIO_CAPTURE_DEVICE}" \\
    HERMES_AUDIO_PLAYBACK_DEVICE="${AUDIO_PLAYBACK_DEVICE}" \\
    HERMES_GPSD_HOST="${GPSD_HOST}" \\
    HERMES_GPSD_PORT="${GPSD_PORT}" \\
    scripts/hermes-kiosk-server.py

Then from the Pi console:
  cage -- "${BROWSER_BIN}" "${APP_URL}"

Run again with --with-systemd to create system services.
EOF
  exit 0
fi

KIOSK_USER="${HERMES_KIOSK_USER:-${USER}}"
KIOSK_UID="$(id -u "${KIOSK_USER}")"
SYSTEMD_DIR="/etc/systemd/system"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

cat > "${TMP_DIR}/hermes-kiosk-web.service" <<EOF
[Unit]
Description=Hermes Pi Kiosk static web server
After=network-online.target
Wants=network-online.target

[Service]
User=${KIOSK_USER}
WorkingDirectory=${PROJECT_DIR}
Environment=HERMES_KIOSK_PORT=${PORT}
Environment=HERMES_AUDIO_RECORD_SECONDS=${AUDIO_RECORD_SECONDS}
Environment=HERMES_AUDIO_CAPTURE_DEVICE=${AUDIO_CAPTURE_DEVICE}
Environment=HERMES_AUDIO_PLAYBACK_DEVICE=${AUDIO_PLAYBACK_DEVICE}
Environment=HERMES_GPSD_HOST=${GPSD_HOST}
Environment=HERMES_GPSD_PORT=${GPSD_PORT}
ExecStart=${PROJECT_DIR}/scripts/hermes-kiosk-server.py
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

cat > "${TMP_DIR}/hermes-kiosk.service" <<EOF
[Unit]
Description=Hermes Pi Kiosk display
After=systemd-user-sessions.service hermes-kiosk-web.service
Wants=hermes-kiosk-web.service
Conflicts=getty@tty1.service
After=getty@tty1.service

[Service]
User=${KIOSK_USER}
PAMName=login
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
StandardInput=tty
StandardOutput=journal
StandardError=journal
UtmpIdentifier=tty1
UtmpMode=user
Environment=XDG_RUNTIME_DIR=/run/user/${KIOSK_UID}
Environment=HOME=/home/${KIOSK_USER}
ExecStart=/usr/bin/cage -- ${BROWSER_BIN} ${APP_URL}
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

if systemctl --user list-unit-files hermes-kiosk-web.service hermes-kiosk.service >/dev/null 2>&1; then
  systemctl --user disable --now hermes-kiosk-web.service hermes-kiosk.service >/dev/null 2>&1 || true
fi

sudo install -m 0644 "${TMP_DIR}/hermes-kiosk-web.service" "${SYSTEMD_DIR}/hermes-kiosk-web.service"
sudo install -m 0644 "${TMP_DIR}/hermes-kiosk.service" "${SYSTEMD_DIR}/hermes-kiosk.service"
sudo systemctl daemon-reload
sudo systemctl enable hermes-kiosk-web.service hermes-kiosk.service

cat <<EOF

Systemd services installed and enabled:
  hermes-kiosk-web.service
  hermes-kiosk.service

Start them now with:
  sudo systemctl start hermes-kiosk-web.service hermes-kiosk.service

Check logs with:
  journalctl -u hermes-kiosk.service -f
EOF

#!/usr/bin/env python3
import json
import os
import subprocess
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"
STATE_DIR = Path(os.environ.get("HERMES_KIOSK_STATE_DIR", "/tmp/hermes-kiosk"))
AUDIO_FILE = STATE_DIR / "audio-test.wav"
RECORD_SECONDS = int(os.environ.get("HERMES_AUDIO_RECORD_SECONDS", "4"))
ARECORD_DEVICE = os.environ.get("HERMES_AUDIO_CAPTURE_DEVICE", "default")
APLAY_DEVICE = os.environ.get("HERMES_AUDIO_PLAYBACK_DEVICE", "default")


class KioskHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def log_message(self, fmt, *args):
        print("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def do_GET(self):
        if self.path.startswith("/api/audio/status"):
            self.write_json(
                {
                    "ok": True,
                    "recordSeconds": RECORD_SECONDS,
                    "hasRecording": AUDIO_FILE.exists(),
                    "recordingPath": str(AUDIO_FILE),
                    "captureDevice": ARECORD_DEVICE,
                    "playbackDevice": APLAY_DEVICE,
                }
            )
            return

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/audio/loopback":
            query = parse_qs(parsed.query)
            seconds = parse_seconds(query.get("seconds", [str(RECORD_SECONDS)])[0])
            self.handle_audio_loopback(seconds)
            return

        if parsed.path == "/api/audio/play":
            self.handle_audio_playback()
            return

        self.write_json({"ok": False, "error": "Not found"}, HTTPStatus.NOT_FOUND)

    def handle_audio_loopback(self, seconds):
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        record_cmd = [
            "arecord",
            "-D",
            ARECORD_DEVICE,
            "-f",
            "S16_LE",
            "-r",
            "16000",
            "-c",
            "1",
            "-d",
            str(seconds),
            str(AUDIO_FILE),
        ]

        playback_cmd = ["aplay", "-D", APLAY_DEVICE, str(AUDIO_FILE)]

        record = run_command(record_cmd, seconds + 8)
        if record["returncode"] != 0:
            self.write_json({"ok": False, "stage": "record", **record}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        playback = run_command(playback_cmd, seconds + 8)
        if playback["returncode"] != 0:
            self.write_json({"ok": False, "stage": "playback", **playback}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self.write_json(
            {
                "ok": True,
                "recordSeconds": seconds,
                "recordingPath": str(AUDIO_FILE),
                "record": record,
                "playback": playback,
            }
        )

    def handle_audio_playback(self):
        if not AUDIO_FILE.exists():
            self.write_json({"ok": False, "error": "No test recording exists yet"}, HTTPStatus.NOT_FOUND)
            return

        playback = run_command(["aplay", "-D", APLAY_DEVICE, str(AUDIO_FILE)], RECORD_SECONDS + 8)
        if playback["returncode"] != 0:
            self.write_json({"ok": False, "stage": "playback", **playback}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self.write_json({"ok": True, "recordingPath": str(AUDIO_FILE), "playback": playback})

    def write_json(self, payload, status=HTTPStatus.OK):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def parse_seconds(raw):
    try:
        value = int(raw)
    except ValueError:
        value = RECORD_SECONDS
    return min(max(value, 1), 15)


def run_command(cmd, timeout):
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except FileNotFoundError as exc:
        return {"returncode": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": 124,
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": "Command timed out",
        }


def main():
    port = int(os.environ.get("HERMES_KIOSK_PORT", "8090"))
    server = ThreadingHTTPServer(("127.0.0.1", port), KioskHandler)
    print(f"Serving Hermes Pi Kiosk on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping Hermes Pi Kiosk server")


if __name__ == "__main__":
    main()

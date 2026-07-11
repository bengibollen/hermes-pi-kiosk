#!/usr/bin/env python3
import json
import os
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request
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
GPSD_HOST = os.environ.get("HERMES_GPSD_HOST", "127.0.0.1")
GPSD_PORT = int(os.environ.get("HERMES_GPSD_PORT", "2947"))
GPSD_TIMEOUT_SECONDS = float(os.environ.get("HERMES_GPSD_TIMEOUT_SECONDS", "1.5"))
DRIVE_BASE_URL = os.environ.get("HERMES_DRIVE_URL", "http://127.0.0.1:8000").rstrip("/")
DRIVE_TIMEOUT_SECONDS = float(os.environ.get("HERMES_DRIVE_TIMEOUT_SECONDS", "3"))
DEVICE_ID = os.environ.get("HERMES_DEVICE_ID", "car-pi")
SUBJECT_ID = os.environ.get("HERMES_SUBJECT_ID", "default")
VEHICLE_ID = os.environ.get("HERMES_VEHICLE_ID", "default")


class KioskHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def log_message(self, fmt, *args):
        print("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def do_GET(self):
        if self.path.startswith("/api/gps/status"):
            self.write_json(read_gps_status())
            return

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

        if parsed.path == "/api/drive/action":
            query = parse_qs(parsed.query)
            action = query.get("action", [""])[0]
            self.handle_drive_action(action)
            return

        self.write_json({"ok": False, "error": "Not found"}, HTTPStatus.NOT_FOUND)

    def handle_drive_action(self, action):
        if action == "start-trip":
            response = call_drive_api(
                "/api/drive/trips/start",
                body={
                    "deviceId": DEVICE_ID,
                    "subjectId": SUBJECT_ID,
                    "vehicleId": VEHICLE_ID,
                },
            )
        elif action == "stop-trip":
            response = call_drive_api(
                "/api/drive/trips/stop",
                query={"subjectId": SUBJECT_ID, "vehicleId": VEHICLE_ID},
            )
        elif action in {"food", "parking"}:
            gps = read_gps_status()
            response = call_drive_api(
                f"/api/drive/{action}",
                query={
                    "subjectId": SUBJECT_ID,
                    "vehicleId": VEHICLE_ID,
                    "responseMode": "json",
                },
                body=build_location_payload(gps),
            )
        else:
            self.write_json(
                {"ok": False, "error": f"Unsupported drive action: {action}"},
                HTTPStatus.BAD_REQUEST,
            )
            return

        status = HTTPStatus.OK if response.get("ok") else HTTPStatus.BAD_GATEWAY
        self.write_json(response, status)

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


def read_gps_status():
    try:
        with socket.create_connection((GPSD_HOST, GPSD_PORT), timeout=GPSD_TIMEOUT_SECONDS) as gpsd:
            gpsd.settimeout(GPSD_TIMEOUT_SECONDS)
            gpsd.sendall(b'?WATCH={"enable":true,"json":true};\n')

            best_tpv = None
            best_sky = None
            deadline = GPSD_TIMEOUT_SECONDS
            gpsd.settimeout(deadline)

            for _ in range(12):
                line = read_socket_line(gpsd)
                if not line:
                    continue
                message = json.loads(line)
                message_class = message.get("class")
                if message_class == "TPV":
                    best_tpv = message
                    if message.get("mode", 0) >= 2:
                        break
                elif message_class == "SKY":
                    best_sky = message

            return build_gps_response(best_tpv, best_sky)
    except (ConnectionRefusedError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "status": "Unavailable",
            "error": str(exc),
            "speedKmh": 0,
            "mode": 0,
            "time": None,
            "lat": None,
            "lon": None,
            "alt": None,
            "track": None,
            "satellitesUsed": None,
            "satellitesVisible": None,
        }


def read_socket_line(sock):
    chunks = []
    while True:
        char = sock.recv(1)
        if not char:
            return b"".join(chunks).decode("utf-8").strip()
        if char == b"\n":
            return b"".join(chunks).decode("utf-8").strip()
        chunks.append(char)


def build_gps_response(tpv, sky):
    if not tpv:
        return {
            "ok": False,
            "status": "No data",
            "speedKmh": 0,
            "mode": 0,
            "time": None,
            "lat": None,
            "lon": None,
            "alt": None,
            "track": None,
            "satellitesUsed": count_satellites(sky, True),
            "satellitesVisible": count_satellites(sky, False),
        }

    mode = int(tpv.get("mode", 0))
    speed_mps = float(tpv.get("speed", 0) or 0)
    return {
        "ok": True,
        "status": gps_status_label(mode),
        "speedKmh": speed_mps * 3.6,
        "mode": mode,
        "time": tpv.get("time"),
        "lat": tpv.get("lat"),
        "lon": tpv.get("lon"),
        "alt": tpv.get("altHAE", tpv.get("altMSL", tpv.get("alt"))),
        "track": tpv.get("track"),
        "satellitesUsed": count_satellites(sky, True),
        "satellitesVisible": count_satellites(sky, False),
    }


def gps_status_label(mode):
    if mode >= 3:
        return "3D fix"
    if mode == 2:
        return "2D fix"
    if mode == 1:
        return "No fix"
    return "Unknown"


def count_satellites(sky, used_only):
    if not sky or "satellites" not in sky:
        return None
    satellites = sky.get("satellites", [])
    if used_only:
        return sum(1 for satellite in satellites if satellite.get("used"))
    return len(satellites)


def build_location_payload(gps):
    if not gps.get("ok") or not isinstance(gps.get("lat"), (int, float)):
        return None
    if not isinstance(gps.get("lon"), (int, float)):
        return None

    return {
        "deviceId": DEVICE_ID,
        "subjectId": SUBJECT_ID,
        "vehicleId": VEHICLE_ID,
        "timestamp": gps.get("time") or current_utc_timestamp(),
        "lat": gps["lat"],
        "lon": gps["lon"],
        "speedKmh": gps.get("speedKmh"),
        "heading": gps.get("track"),
        "source": "gpsd",
    }


def current_utc_timestamp():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def call_drive_api(path, query=None, body=None):
    url = DRIVE_BASE_URL + path
    if query:
        url += "?" + urllib.parse.urlencode(query)

    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=DRIVE_TIMEOUT_SECONDS) as response:
            response_body = response.read().decode("utf-8")
            parsed = parse_response_body(response_body)
            return {
                "ok": 200 <= response.status < 300,
                "statusCode": response.status,
                "driveUrl": url,
                "response": parsed,
                "message": extract_drive_message(parsed),
            }
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8")
        parsed = parse_response_body(response_body)
        return {
            "ok": False,
            "statusCode": exc.code,
            "driveUrl": url,
            "response": parsed,
            "message": extract_drive_message(parsed) or str(exc),
        }
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return {
            "ok": False,
            "statusCode": None,
            "driveUrl": url,
            "response": None,
            "message": str(exc),
        }


def parse_response_body(response_body):
    if not response_body:
        return None
    try:
        return json.loads(response_body)
    except json.JSONDecodeError:
        return response_body


def extract_drive_message(response):
    if isinstance(response, dict):
        if response.get("message"):
            return response["message"]
        active_trip_id = response.get("activeTripId")
        if active_trip_id:
            return "Trip active"
        if "activeTripId" in response:
            return "Trip stopped"
    if isinstance(response, str):
        return response
    return None


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

#!/usr/bin/env python3
import json
import os
import re
import shlex
import subprocess
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
USAGE_FILE = BASE_DIR / "process_usage.json"


class ProcessUsageTracker:
    """
    Samples nethogs text output and keeps:
    - current process speeds
    - estimated daily and all-time usage totals
    """

    PROC_RE = re.compile(r"^(.+)/(\d+)/(\d+)\s+([0-9]*\.?[0-9]+)\s+([0-9]*\.?[0-9]+)$")

    def __init__(self, usage_file):
        self.usage_file = usage_file
        self.lock = threading.Lock()
        self.current = {}
        self.db = {"daily": {}, "all_time": {}}
        self.last_save_ts = 0.0
        self.status = "starting"
        self.last_error = ""
        self._load()
        self.thread = None

    def _load(self):
        if not self.usage_file.exists():
            return
        try:
            self.db = json.loads(self.usage_file.read_text(encoding="utf-8"))
            if "daily" not in self.db:
                self.db["daily"] = {}
            if "all_time" not in self.db:
                self.db["all_time"] = {}
        except (json.JSONDecodeError, OSError):
            self.db = {"daily": {}, "all_time": {}}

        self._compact_legacy_entries()

    def _compact_usage_map(self, usage_map):
        compacted = {}
        for _key, row in usage_map.items():
            app_name = self._normalize_app_name(row.get("name", "unknown"))
            app_key = app_name.lower()
            out = compacted.setdefault(
                app_key,
                {
                    "name": app_name,
                    "download_bytes": 0.0,
                    "upload_bytes": 0.0,
                    "total_bytes": 0.0,
                },
            )
            out["download_bytes"] += float(row.get("download_bytes", 0.0))
            out["upload_bytes"] += float(row.get("upload_bytes", 0.0))
            out["total_bytes"] += float(row.get("total_bytes", 0.0))
        return compacted

    def _compact_legacy_entries(self):
        for day, day_map in list(self.db.get("daily", {}).items()):
            if isinstance(day_map, dict):
                self.db["daily"][day] = self._compact_usage_map(day_map)
        if isinstance(self.db.get("all_time"), dict):
            self.db["all_time"] = self._compact_usage_map(self.db["all_time"])

    def _save(self, force=False):
        now = time.time()
        if not force and now - self.last_save_ts < 3:
            return
        self.usage_file.write_text(json.dumps(self.db, indent=2), encoding="utf-8")
        self.last_save_ts = now

    @staticmethod
    def _normalize_app_name(raw_name):
        text = (raw_name or "").strip()
        if not text:
            return "unknown"
        try:
            parts = shlex.split(text)
            if parts:
                text = parts[0]
        except ValueError:
            pass

        if text.startswith("/"):
            text = os.path.basename(text)
        if "/" in text:
            text = text.split("/")[-1]
        if not text:
            return "unknown"
        return text

    def _add_usage(self, app_key, app_name, down_kbps, up_kbps, seconds):
        down_bytes = down_kbps * 1024.0 * seconds
        up_bytes = up_kbps * 1024.0 * seconds
        total_bytes = down_bytes + up_bytes
        if total_bytes <= 0:
            return

        today = date.today().isoformat()
        daily = self.db["daily"].setdefault(today, {})
        daily_row = daily.setdefault(
            app_key,
            {
                "name": app_name,
                "download_bytes": 0.0,
                "upload_bytes": 0.0,
                "total_bytes": 0.0,
            },
        )
        daily_row["download_bytes"] += down_bytes
        daily_row["upload_bytes"] += up_bytes
        daily_row["total_bytes"] += total_bytes

        all_time_row = self.db["all_time"].setdefault(
            app_key,
            {
                "name": app_name,
                "download_bytes": 0.0,
                "upload_bytes": 0.0,
                "total_bytes": 0.0,
            },
        )
        all_time_row["download_bytes"] += down_bytes
        all_time_row["upload_bytes"] += up_bytes
        all_time_row["total_bytes"] += total_bytes

    def _sample_loop(self):
        cmd = ["nethogs", "-t", "-d", "1"]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            self.status = "error"
            self.last_error = "nethogs not installed"
            print("nethogs is not installed; process stats disabled.")
            return
        except Exception as exc:
            self.status = "error"
            self.last_error = f"failed to start nethogs: {exc}"
            print(f"Failed to start nethogs: {exc}")
            return

        self.status = "running"
        self.last_error = ""
        print("Process tracker started via nethogs.")

        last_flush = time.time()
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.strip()
            if line.startswith("Refreshing:"):
                with self.lock:
                    self.current = {}
                continue
            m = self.PROC_RE.match(line)
            if not m:
                continue

            proc_name, _pid_s, _uid_s, down_s, up_s = m.groups()
            down_kbps = float(down_s)
            up_kbps = float(up_s)
            app_name = self._normalize_app_name(proc_name)
            app_key = app_name.lower()

            down_bps = down_kbps * 1024.0
            up_bps = up_kbps * 1024.0

            with self.lock:
                row = self.current.setdefault(
                    app_key,
                    {
                        "key": app_key,
                        "name": app_name,
                        "download_bps": 0.0,
                        "upload_bps": 0.0,
                        "total_bps": 0.0,
                    },
                )
                row["download_bps"] += down_bps
                row["upload_bps"] += up_bps
                row["total_bps"] += down_bps + up_bps
                self._add_usage(app_key, app_name, down_kbps, up_kbps, 1.0)
                now = time.time()
                if now - last_flush >= 3:
                    self._save()
                    last_flush = now

        rc = proc.wait()
        if rc != 0:
            self.status = "error"
            self.last_error = (
                "nethogs exited. Run server as sudo or grant "
                "cap_net_admin,cap_net_raw to nethogs."
            )

    @staticmethod
    def _sort_usage_rows(rows):
        out = []
        for key, item in rows.items():
            out.append(
                {
                    "key": key,
                    "name": item.get("name", "unknown"),
                    "download_bytes": item.get("download_bytes", 0.0),
                    "upload_bytes": item.get("upload_bytes", 0.0),
                    "total_bytes": item.get("total_bytes", 0.0),
                }
            )
        out.sort(key=lambda x: x["total_bytes"], reverse=True)
        return out[:15]

    def get_snapshot(self):
        today = date.today().isoformat()
        with self.lock:
            current_rows = list(self.current.values())
            current_rows.sort(key=lambda x: x["total_bps"], reverse=True)
            current_rows = current_rows[:20]

            daily_rows = self._sort_usage_rows(self.db["daily"].get(today, {}))
            all_time_rows = self._sort_usage_rows(self.db["all_time"])

            return {
                "tracker": "nethogs",
                "tracker_status": self.status,
                "tracker_error": self.last_error,
                "daily_date": today,
                "current_processes": current_rows,
                "daily_top": daily_rows,
                "all_time_top": all_time_rows,
            }

    def start(self):
        self.thread = threading.Thread(target=self._sample_loop, daemon=True)
        self.thread.start()


PROCESS_TRACKER = ProcessUsageTracker(USAGE_FILE)


def read_network_totals():
    """
    Returns total (rx_bytes, tx_bytes) across active interfaces from /proc/net/dev.
    Loopback is skipped to avoid counting local-only traffic.
    """
    rx_total = 0
    tx_total = 0

    with open("/proc/net/dev", "r", encoding="utf-8") as f:
        lines = f.readlines()[2:]  # skip headers

    for line in lines:
        if ":" not in line:
            continue
        iface, data = line.split(":", 1)
        iface = iface.strip()
        if iface == "lo":
            continue

        parts = data.split()
        if len(parts) < 16:
            continue

        rx_bytes = int(parts[0])
        tx_bytes = int(parts[8])
        rx_total += rx_bytes
        tx_total += tx_bytes

    return rx_total, tx_total


class Handler(BaseHTTPRequestHandler):
    last_snapshot = None

    def _write_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_index(self):
        if not INDEX_FILE.exists():
            self.send_error(500, "index.html not found")
            return

        content = INDEX_FILE.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            self._serve_index()
            return

        if path == "/api/stats":
            now = time.time()
            rx, tx = read_network_totals()

            if Handler.last_snapshot is None:
                Handler.last_snapshot = {"ts": now, "rx": rx, "tx": tx}
                self._write_json(
                    {
                        "download_bps": 0.0,
                        "upload_bps": 0.0,
                        "download_total_bytes": rx,
                        "upload_total_bytes": tx,
                    }
                )
                return

            prev = Handler.last_snapshot
            dt = max(now - prev["ts"], 1e-6)
            down_bps = max((rx - prev["rx"]) / dt, 0.0)
            up_bps = max((tx - prev["tx"]) / dt, 0.0)

            Handler.last_snapshot = {"ts": now, "rx": rx, "tx": tx}
            self._write_json(
                {
                    "download_bps": down_bps,
                    "upload_bps": up_bps,
                    "download_total_bytes": rx,
                    "upload_total_bytes": tx,
                }
            )
            return

        if path == "/api/processes":
            self._write_json(PROCESS_TRACKER.get_snapshot())
            return

        self.send_error(404, "Not found")

    def log_message(self, fmt, *args):
        # keep terminal output clean
        return


def main():
    host = "0.0.0.0"
    port = 8765
    PROCESS_TRACKER.start()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Network usage UI running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

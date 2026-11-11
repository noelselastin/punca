"""Windows-owned Punca processes and a loopback-only page with the current public URL."""
from __future__ import annotations

import argparse
import datetime as dt
import html
import http.server
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import urllib.request
import psutil

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PUBLIC_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com\b")


def healthy(url):
    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            if response.status != 200:
                return False
            if url.endswith("/api/health"):
                return json.load(response).get("ok") is True
            return True
    except Exception:
        return False


class Service:
    def __init__(self, spec, runtime):
        self.spec, self.runtime = spec, runtime
        self.process = None
        self.failures = 0
        self.started = 0
        self.log_path = None
        self.log_offset = 0
        self.url = None
        wanted = [str(arg).lower() for arg in spec["command"]]
        matches = []
        for process in psutil.process_iter(["pid", "ppid", "cmdline"]):
            try:
                if [str(arg).lower() for arg in (process.info["cmdline"] or [])] == wanted:
                    matches.append(process)
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
        parents = {process.pid for process in matches}
        self.process = next((p for p in matches if p.info["ppid"] not in parents), None)
        if self.process:
            self.started = time.monotonic()
            logging.info("Adopted existing %s (PID %s)", spec["name"], self.process.pid)
            try:
                prior = json.loads((runtime / "status.json").read_text())["services"][spec["name"]]
                if prior.get("pid") == self.process.pid and prior.get("logPath"):
                    self.log_path = Path(prior["logPath"])
                    self.url = prior.get("publicUrl")
            except (OSError, KeyError, ValueError):
                pass

    def start(self):
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log_path = self.runtime / f"{self.spec['name']}-{stamp}.log"
        env = os.environ.copy()
        env.update(self.spec.get("env", {}))
        with self.log_path.open("ab", buffering=0) as output:
            self.process = psutil.Popen(
                self.spec["command"], cwd=self.spec["cwd"], env=env,
                stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                creationflags=NO_WINDOW,
            )
        self.started, self.failures, self.log_offset, self.url = time.monotonic(), 0, 0, None
        logging.info("Started %s (PID %s)", self.spec["name"], self.process.pid)

    def stop_owned(self):
        if self.process and self.process.is_running():
            # Only a created process or one with an exact matching command is stopped.
            children = self.process.children(recursive=True)
            for process in reversed(children):
                try:
                    process.kill()
                except psutil.NoSuchProcess:
                    pass
            self.process.kill()
            psutil.wait_procs(children + [self.process], timeout=15)
        self.process, self.url = None, None

    def check(self):
        is_tunnel = self.spec.get("tunnel", False)
        ok = healthy(self.spec["health"])
        if self.process and not self.process.is_running():
            logging.warning("%s stopped", self.spec["name"])
            self.process, self.url = None, None
        # Healthy services that were already running are preserved until they stop.
        if not self.process and not ok:
            self.start()
        if is_tunnel and self.log_path:
            with self.log_path.open("r", encoding="utf-8", errors="replace") as log:
                log.seek(self.log_offset)
                chunk = log.read()
                self.log_offset = log.tell()
            found = PUBLIC_URL.search(chunk)
            if found:
                self.url = found.group(0)
                logging.info("Current public URL: %s", self.url)
            if "Unauthorized: Tunnel not found" in chunk:
                logging.warning("Cloudflare discarded this quick tunnel; replacing it")
                self.stop_owned()
                self.start()
                ok = False
        if self.process and time.monotonic() - self.started > 60:
            self.failures = 0 if ok else self.failures + 1
            # Give cloudflared several minutes to reconnect after sleep/network loss.
            limit = 12 if is_tunnel else 3
            if self.failures >= limit:
                logging.warning("%s failed %s health checks; restarting", self.spec['name'], self.failures)
                self.stop_owned()
                self.start()
                ok = False
        return {"healthy": ok, "pid": self.process.pid if self.process else None,
                "ownership": "supervised" if self.process else "existing",
                "logPath": str(self.log_path) if self.log_path else None,
                "publicUrl": self.url if is_tunnel and ok else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    runtime = Path(config["runtime"])
    runtime.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(runtime / "supervisor.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s")
    status = {"publicUrl": None, "services": {}, "updatedAt": None}

    class Dashboard(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/status.json":
                body, content_type = json.dumps(status).encode(), "application/json"
            elif self.path == "/public" and status.get("publicUrl"):
                self.send_response(302)
                self.send_header("Location", status["publicUrl"])
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            else:
                public_url = status.get("publicUrl")
                public = (f'<a href="{html.escape(public_url)}">{html.escape(public_url)}</a>'
                          if public_url else "Starting or reconnecting. This page refreshes automatically.")
                rows = "".join(f'<li>{html.escape(name)}: {"running" if info["healthy"] else "starting / recovering"}</li>'
                               for name, info in status["services"].items())
                body = f'''<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="20">
<title>Punca links</title><style>body{{font:17px system-ui;max-width:850px;margin:70px auto;padding:24px;background:#101d32;color:#eef2ef}}a{{color:#a9d8c7}}li{{margin:12px 0}}</style></head><body>
<h1>Punca links</h1><p><b>Public version:</b> {public}</p>
<p><b>Latest local preview:</b> <a href="http://localhost:5173">http://localhost:5173</a></p>
<ul>{rows}</ul><p>This computer must be awake and online for the public site to work. The temporary public address can change after recovery.</p>
<p>The public version is the last published release. Pending changes remain in the local preview.</p></body></html>'''.encode()
                content_type = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    # Binding first also prevents a second supervisor from starting duplicate children.
    server = http.server.ThreadingHTTPServer(("127.0.0.1", config["statusPort"]), Dashboard)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    services = [Service(spec, runtime) for spec in config["services"]]
    logging.info("Supervisor started (PID %s)", os.getpid())
    while True:
        snapshot = {}
        for service in services:
            try:
                snapshot[service.spec["name"]] = service.check()
            except Exception:
                logging.exception("Could not check %s; will retry", service.spec["name"])
                snapshot[service.spec["name"]] = {"healthy": False, "publicUrl": None}
        public_url = next((s["publicUrl"] for s in snapshot.values() if s.get("publicUrl")), None)
        status.update(services=snapshot, publicUrl=public_url, updatedAt=dt.datetime.now().astimezone().isoformat())
        tmp = runtime / "status.tmp"
        tmp.write_text(json.dumps(status, indent=2), encoding="utf-8")
        tmp.replace(runtime / "status.json")
        time.sleep(15)


if __name__ == "__main__":
    main()

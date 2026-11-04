"""Run existing Vue source with an explicit local API URL; no business edits."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import time

import requests

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def local_frontend(api_url, evidence_dir):
    frontend = ROOT / "upstream/frontend"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    with (evidence_dir / "frontend.log").open("w") as log:
        process = subprocess.Popen(
            ["node", "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", str(port), "--strictPort"],
            cwd=frontend, env={**os.environ, "VITE_API_URL": api_url}, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            with requests.Session() as http:
                http.trust_env = False
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("Vite exited; inspect frontend.log")
                    try:
                        if http.get(url, timeout=1).status_code == 200:
                            break
                    except requests.RequestException:
                        pass
                    time.sleep(0.1)  # Server readiness polling, never a browser timing workaround.
                else:
                    raise TimeoutError("Vite not ready")
            yield url
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            (evidence_dir / "frontend.json").write_text(json.dumps({
                "frontend_url": url, "VITE_API_URL": api_url,
                "process_stopped": process.poll() is not None,
                "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=frontend, text=True).strip(),
            }, indent=2) + "\n")

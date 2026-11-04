"""Own only a newly created database and child process; never use the demo DB."""
import hashlib
import io
import tarfile
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import time
from contextlib import contextmanager, closing
from dataclasses import dataclass

import requests

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class BackendEnvironment:
    api_url: str
    database: Path


@contextmanager
def isolated_backend(evidence_dir, variant="fixed"):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    report = {"mode": "isolated temporary SQLite", "startup_ok": False}
    process = None
    temp = tempfile.TemporaryDirectory(prefix="realworld-stage2-")
    database = Path(temp.name) / "test.sqlite3"
    source = Path(temp.name) / "backend"
    source.mkdir()
    baseline = json.loads((ROOT / "config/upstream.json").read_text())["backend"]["commit"]
    report.update(backend_variant=variant, baseline_commit=baseline)
    report["database"] = str(database)
    env = {**os.environ, "DEBUG": "True", "DATABASE_URL": f"file:{database}"}
    command = [str(ROOT / ".venv-backend/bin/python"), "manage.py"]
    try:
        archive = subprocess.check_output(["git", "-C", str(ROOT / "upstream/backend"), "archive", baseline])
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(source, filter="data")
        if variant == "fixed":
            patch = ROOT / "patches/BUG-001.patch"
            check = subprocess.run(["git", "apply", "--check", str(patch)], cwd=source,
                                   text=True, capture_output=True)
            if check.returncode:
                raise RuntimeError(f"BUG-001 patch cannot apply to baseline {baseline}: {check.stderr.strip()}")
            subprocess.run(["git", "apply", str(patch)], cwd=source, check=True)
            report["patch_sha256"] = hashlib.sha256(patch.read_bytes()).hexdigest()
        elif variant != "baseline":
            raise ValueError(f"Unknown backend variant: {variant}")
        with (evidence_dir / "backend.log").open("w") as log:
            subprocess.run(command + ["migrate", "--noinput"], cwd=source,
                           env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            process = subprocess.Popen(command + ["runserver", f"127.0.0.1:{port}", "--noreload"],
                                       cwd=source, env=env,
                                       stdout=log, stderr=subprocess.STDOUT)
            url = f"http://127.0.0.1:{port}/api"
            with requests.Session() as session:
                session.trust_env = False
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("Backend exited; inspect backend.log")
                    try:
                        if session.get(url + "/tags", timeout=1).status_code == 200:
                            break
                    except requests.RequestException:
                        pass
                    time.sleep(0.1)
                else:
                    raise TimeoutError("Backend not ready in 20 seconds; inspect backend.log")
            report["startup_ok"] = True
            report["api_url"] = url
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as conn:
                conn.row_factory = sqlite3.Row
                schema = {}
                for table in ("articles_article", "accounts_user"):
                    schema[table] = {
                        "columns": [dict(row) for row in conn.execute("SELECT * FROM pragma_table_info(?)", (table,))],
                        "foreign_keys": [dict(row) for row in conn.execute("SELECT * FROM pragma_foreign_key_list(?)", (table,))],
                    }
                (evidence_dir / "schema.json").write_text(json.dumps(schema, indent=2) + "\n")
            yield BackendEnvironment(url, database)
    finally:
        try:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                report["process_stopped"] = process.poll() is not None
            if database.exists():
                with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as conn:
                    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    report["rows_before_disposal"] = {
                        table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                        for table in ("accounts_user", "articles_article", "articles_tag") if table in tables
                    }
        finally:
            temp.cleanup()
            report["database_removed"] = not database.exists()
            (evidence_dir / "cleanup.json").write_text(json.dumps(report, indent=2) + "\n")
        if report["startup_ok"]:
            assert report["rows_before_disposal"]["articles_article"] == 0, "Article cleanup leaked rows"

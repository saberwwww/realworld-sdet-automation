"""Run the real pytest fixtures, preserve failure status and always write a summary."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tempfile

from summarize_junit import summarize

ROOT = Path(__file__).resolve().parents[1]


def stop_group(process):
    for sig, wait in ((signal.SIGINT, 15), (signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            pass


def interrupt_run(*_):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fixed", "baseline"), default="fixed")
    parser.add_argument("--suite", choices=("all", "api", "ui", "db"), default="all")
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--diagnostic", choices=("ui", "db"), help="Explicit intentional failure, never a passing CI run")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    out = (args.run_dir or ROOT / ".runtime/runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")).resolve()
    if out.exists():
        raise SystemExit(f"Refusing to overwrite existing evidence: {out}")
    out.mkdir(parents=True)
    # Chromium Unix sockets cannot use the long GitHub workspace path.
    # mkdtemp creates a private, unique directory; only this invocation removes it.
    temporary = Path(tempfile.mkdtemp(prefix="rw-", dir="/tmp"))
    command = [str(ROOT / ".venv-test/bin/python"), "-m", "pytest", "-v",
               f"--backend-variant={args.mode}", f"--evidence-dir={out}",
               f"--junitxml={out / 'results.xml'}", f"--output={out / 'artifacts'}"]
    if args.diagnostic:
        command += ["tests/ui/diagnostics_demo.py" if args.diagnostic == "ui" else "tests/demos/db_failure_demo.py"]
    elif args.suite in ("api", "ui"):
        command += [f"tests/{args.suite}"]
    elif args.suite == "db":
        command += ["-m", "db"]
    if args.reverse:
        command.append("--reverse-order")
    metadata = {"platform": platform.platform(), "python": platform.python_version(),
                "mode": args.mode, "suite": args.suite, "diagnostic": args.diagnostic,
                "command": command, "github_actions": os.getenv("GITHUB_ACTIONS") == "true"}
    code, process = 2, None
    previous = signal.signal(signal.SIGTERM, interrupt_run)
    try:
        metadata["node"] = subprocess.check_output(["node", "--version"], text=True).strip()
        with (out / "pytest.txt").open("w") as log:
            process = subprocess.Popen(command, cwd=ROOT, env={**os.environ, "TMPDIR": str(temporary),
                                       "PLAYWRIGHT_BROWSERS_PATH": str(ROOT / ".runtime/pw-browsers")},
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            code = process.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        code = 124
        metadata["interrupted"] = "timeout"
    except KeyboardInterrupt:
        code = 130
        metadata["interrupted"] = "interrupt or SIGTERM"
    finally:
        if process is not None and process.poll() is None:
            stop_group(process)
        signal.signal(signal.SIGTERM, previous)
        # This directory was created solely by this invocation; never delete a user DB.
        shutil.rmtree(temporary)
        metadata["temporary_root"] = str(temporary)
        metadata["temporary_root_removed"] = not temporary.exists()
        if (out / "results.xml").exists():
            try:
                report = summarize(out / "results.xml")
                (out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
                print(json.dumps(report["totals"]))
            except Exception as exc:
                (out / "report-error.txt").write_text(str(exc))
                if code == 0:
                    code = 2
        metadata["exit_code"] = code
        (out / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
        print(f"Evidence: {out}; pytest exit code: {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())

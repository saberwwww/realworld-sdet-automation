"""Same reproducible installation entry point for macOS and Ubuntu CI."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    subprocess.run(list(args), cwd=ROOT, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-browser-system-deps", action="store_true", help="Linux CI: install Playwright OS packages")
    args = parser.parse_args()
    if sys.version_info[:3] != (3, 13, 7):
        raise SystemExit("Reproducible profile requires Python 3.13.7")
    for executable, expected in (("node", "v22.18.0"), ("npm", "10.9.3")):
        actual = subprocess.check_output([executable, "--version"], text=True).strip()
        if actual != expected:
            raise SystemExit(f"{executable}: expected {expected}, got {actual}; choose the pinned runtime on PATH")
    run(sys.executable, "scripts/checkout_upstream.py")
    for name, lock in (("backend", "backend-sqlite.lock.txt"), ("test", "ui-test.lock.txt")):
        target = ROOT / f".venv-{name}"
        if not target.exists():
            venv.EnvBuilder(with_pip=True).create(target)
        python = str(target / "bin/python")
        run(python, "-m", "pip", "install", "-r", str(ROOT / "config" / lock))
        run(python, "-m", "pip", "check")
    lock = ROOT / "config/frontend-package-lock.json"
    destination = ROOT / "upstream/frontend/package-lock.json"
    if destination.exists() and destination.read_bytes() != lock.read_bytes():
        raise SystemExit("Frontend package-lock differs; refusing to overwrite it")
    shutil.copyfile(lock, destination)
    run("npm", "--prefix", "upstream/frontend", "ci", "--ignore-scripts", "--no-audit", "--no-fund")
    run("npm", "--prefix", "upstream/frontend", "run", "build", env={**os.environ, "VITE_API_URL": "http://127.0.0.1:8000/api"})
    install = [str(ROOT / ".venv-test/bin/python"), "-m", "playwright", "install", "chromium"]
    if args.with_browser_system_deps:
        if not sys.platform.startswith("linux"):
            raise SystemExit("--with-browser-system-deps is for Linux only")
        install.append("--with-deps")
    run(*install, env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(ROOT / ".runtime/pw-browsers")})
    print("Setup complete. Run: python3 scripts/run_tests.py")


if __name__ == "__main__":
    main()

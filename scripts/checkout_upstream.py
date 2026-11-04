"""Fetch fixed public sources, or verify existing clones without resetting them."""
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "config/upstream.json").read_text())
for name in ("backend", "frontend"):
    entry = manifest[name]
    target = root / "upstream" / name
    if not target.exists():
        subprocess.run(["git", "clone", entry["url"], str(target)], check=True)
        subprocess.run(["git", "-C", str(target), "checkout", "--detach", entry["commit"]], check=True)
    head = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
    if head != entry["commit"]:
        raise SystemExit(f"{name}: expected {entry['commit']}, got {head}; refusing to reset existing source")
    subprocess.run(["git", "-C", str(target), "diff", "--exit-code", "HEAD", "--"], check=True)
frontend = root / "upstream/frontend"
subprocess.run(["git", "-C", str(frontend), "submodule", "update", "--init"], check=True)
spec = subprocess.check_output(["git", "-C", str(frontend / "realworld"), "rev-parse", "HEAD"], text=True).strip()
if spec != manifest["realworld_spec"]["commit"]:
    raise SystemExit("RealWorld spec commit mismatch")
subprocess.run(["git", "-C", str(frontend / "realworld"), "diff", "--exit-code", "HEAD", "--"], check=True)
print("Pinned upstream and spec commits verified; no reset or business edits")

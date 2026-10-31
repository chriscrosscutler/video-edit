"""Builds a scripts/<name>.swift Apple Vision tool into ~/.cache/video-edit/ on first use (macOS)."""
import shutil
import subprocess
import sys
from pathlib import Path

CACHE = Path.home() / ".cache" / "video-edit"


def tool(name: str) -> Path:
    src = Path(__file__).resolve().parent / f"{name}.swift"
    out = CACHE / name
    if sys.platform != "darwin" or not shutil.which("swiftc"):
        sys.exit(f"{name}: needs macOS with swiftc (Xcode command line tools)")
    if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
        CACHE.mkdir(parents=True, exist_ok=True)
        p = subprocess.run(["swiftc", "-O", str(src), "-o", str(out)], capture_output=True, text=True)
        if p.returncode:
            sys.exit(f"{name}: swiftc failed:\n{p.stderr}")
    return out

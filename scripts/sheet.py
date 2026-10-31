#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Contact sheet of a video: how a model sees footage, and how anyone checks a render.

Usage:
  sheet.py VIDEO OUT.jpg [--every S] [--cols N] [--width PX]   one frame every S seconds (default 1)
  sheet.py VIDEO OUT.jpg --at 0,2.5,7.1 [--cols N] [--width PX] these moments (cut points, overlays)
  sheet.py VIDEO OUT.jpg --frames 0,75,212                      these frame numbers (at the file's fps)

Frames are laid out left to right, top to bottom, in time order. Name each sheet after what it
checks; a model reading it should get the times list alongside.
"""
import argparse
import json
import math
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path


def run(cmd: list[str]) -> str:
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode:
        sys.exit(f"sheet: {' '.join(cmd[:3])}...: {out.stderr.strip()[-400:]}")
    return out.stdout


def info(path: str) -> tuple[float, float]:
    p = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-print_format", "json",
                        "-show_entries", "stream=avg_frame_rate:format=duration", path]))
    return float(p["format"]["duration"]), float(Fraction(p["streams"][0]["avg_frame_rate"]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("out")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--every", type=float, default=1.0)
    g.add_argument("--at", help="comma-separated seconds")
    g.add_argument("--frames", help="comma-separated frame numbers")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--width", type=int, default=270, help="width of each frame in px")
    a = ap.parse_args()
    dur, fps = info(a.video)
    if a.frames:
        times = [int(x) / fps for x in a.frames.split(",")]
    elif a.at:
        times = [float(x) for x in a.at.split(",")]
    else:
        times = [i * a.every for i in range(max(1, math.ceil(dur / a.every)))]
    times = [min(max(t, 0.0), max(dur - 1 / fps, 0.0)) for t in times]
    cols = min(a.cols, len(times))
    rows = math.ceil(len(times) / cols)
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(times):
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", a.video, "-frames:v", "1",
                 "-vf", f"scale={a.width}:-2", f"{tmp}/{i:04d}.png"])
        run(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i", f"{tmp}/%04d.png",
             "-vf", f"tile={cols}x{rows}:padding=4:color=black", "-frames:v", "1", "-q:v", "3", a.out])
    print(json.dumps({"sheet": str(Path(a.out)), "cols": cols, "rows": rows,
                      "times": [round(t, 3) for t in times]}))


if __name__ == "__main__":
    main()

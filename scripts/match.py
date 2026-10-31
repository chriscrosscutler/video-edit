#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Match a take's exposure and white balance to a reference take.

Usage: match.py REF CLIP [--ref-at T,..] [--at T,..] [--region x0,y0,x1,y1] [--strength 1]
                [--apply OUT.mp4]

Prints {"grade", "gains", "ref", "clip"}: "grade" is an ffmpeg filter for the EDL's per-segment
"grade" (or grade.md's RGB round trip). It measures the mean red, green and blue of the
mid-tones (pixels neither near black nor near white) in a few frames of each file, and scales
each channel of CLIP to REF's. --region measures only that part of the frame (fractions,
origin top-left): put it on the face so skin matches, which is what viewers compare. Sample
frames where both takes show the same thing; a different shirt or wall pulls the match.
--strength 0.5 goes half way. --apply also writes CLIP corrected, at master quality.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

W, H = 72, 128


def frames(path: str, times: list[float] | None) -> list[bytes]:
    if not times:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                    "csv=p=0", path], capture_output=True, text=True).stdout or 0)
        times = [dur * k / 6 for k in range(1, 6)]
    out = []
    for t in times:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf",
                              f"scale={W}:{H}:out_color_matrix=bt709,format=rgb24", "-f", "rawvideo", "-"],
                             capture_output=True).stdout
        if len(raw) == W * H * 3:
            out.append(raw)
    if not out:
        sys.exit(f"match: no frames read from {path}")
    return out


def means(shots: list[bytes], region: tuple[float, ...]) -> list[float]:
    x0, y0, x1, y1 = (round(v * n) for v, n in zip(region, (W, H, W, H)))
    sums, count = [0.0, 0.0, 0.0], 0
    for raw in shots:
        for y in range(y0, y1):
            row = raw[(y * W + x0) * 3:(y * W + x1) * 3]
            for i in range(0, len(row), 3):
                r, g, b = row[i], row[i + 1], row[i + 2]
                if 20 < max(r, g, b) and min(r, g, b) < 235:  # mid-tones only: clipped pixels lie
                    sums[0] += r
                    sums[1] += g
                    sums[2] += b
                    count += 1
    if not count:
        sys.exit("match: no mid-tone pixels in the region")
    return [s / count for s in sums]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref")
    ap.add_argument("clip")
    ap.add_argument("--ref-at", help="seconds, comma-separated (default: five spread through the file)")
    ap.add_argument("--at", help="seconds in CLIP, comma-separated")
    ap.add_argument("--region", default="0,0,1,1")
    ap.add_argument("--strength", type=float, default=1.0)
    ap.add_argument("--apply")
    a = ap.parse_args()
    times = lambda s: [float(x) for x in s.split(",")] if s else None  # noqa: E731
    region = tuple(float(x) for x in a.region.split(","))
    ref = means(frames(a.ref, times(a.ref_at)), region)
    clip = means(frames(a.clip, times(a.at)), region)
    gains = [1 + (r / c - 1) * a.strength for r, c in zip(ref, clip)]
    grade = "colorchannelmixer=rr={:.4f}:gg={:.4f}:bb={:.4f}".format(*gains)
    print(json.dumps({"grade": grade, "gains": [round(g, 4) for g in gains],
                      "ref": [round(v, 1) for v in ref], "clip": [round(v, 1) for v in clip]}))
    if max(abs(g - 1) for g in gains) > 0.35:
        print("match: over 35% on a channel: different light, not a small drift; check the sample frames",
              file=sys.stderr)
    if a.apply:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a.clip, "-vf",
                        f"format=gbrp,{grade},format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:"
                        "colorspace=bt709:range=tv", "-c:v", "libx264", "-preset", "slow", "-crf", "15",
                        "-c:a", "copy", "-movflags", "+faststart", str(Path(a.apply))], check=True)


if __name__ == "__main__":
    main()

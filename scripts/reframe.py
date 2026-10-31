#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Reframe wide footage to vertical (or any aspect) with a crop that follows the face, calmly.

Usage: reframe.py SRC OUT.mp4 [--size 1080x1920] [--faces FACES.json] [--step 3] [--hold 0.12]
                  [--ease 0.6] [--json PATH.json]

Finds faces with faces.swift (macOS; or pass --faces, the same JSON from another detector), takes
the biggest face each sample, and moves a full-height crop of the output's aspect to keep it
centred. The camera holds still while the face stays within --hold (fraction of the crop width)
of centre, eases over --ease seconds when it moves, and jumps without gliding at a cut (the face
moving over a third of the frame between samples). With no face it holds; with none ever, the
crop stays centred. Writes OUT at master quality with the sound copied; --json writes the crop's
left edge per frame (pixels). A 1080-line source cropped to 9:16 is 608 px wide and upscales
1.8x: shoot 4K when the edit will reframe.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
TAGS = "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"


def probe(path: str) -> tuple[int, int, float, int]:
    p = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                                   "-show_entries", "stream=width,height,avg_frame_rate,nb_read_packets",
                                   "-of", "json", path], capture_output=True, text=True, check=True).stdout)
    v = p["streams"][0]
    return v["width"], v["height"], float(Fraction(v["avg_frame_rate"])), int(v["nb_read_packets"])


def path(samples: list[tuple[int, float | None]], n: int, fps: float, hold: float, ease: float) -> list[float]:
    """Crop centre per frame (fraction of the crop width as unit for hold; positions in source fractions)."""
    target, last = [], 0.5
    known = [(f, x) for f, x in samples if x is not None]
    if not known:
        return [0.5] * n
    # hold the first sighting before it, the last after it, and interpolate between sightings
    j = 0
    for f in range(n):
        while j + 1 < len(known) and known[j + 1][0] <= f:
            j += 1
        f0, x0 = known[j]
        if f < f0:
            last = x0
        elif j + 1 < len(known):
            f1, x1 = known[j + 1]
            last = x0 if abs(x1 - x0) > 0.33 else x0 + (x1 - x0) * (f - f0) / (f1 - f0)
        else:
            last = x0
        target.append(last)
    cam, cur = [], target[0]
    k = 1 / max(ease * fps / 3, 1)  # an exponential follow settles in about `ease` seconds
    for f, t in enumerate(target):
        if f and abs(t - target[f - 1]) > 0.33:
            cur = t  # a cut: jump with it
        elif abs(t - cur) > hold:
            cur += (t - cur - (hold if t > cur else -hold) * 0.5) * k
        cam.append(cur)
    # run the follow backwards too, so moves start as gently as they end
    back, cur = [], cam[-1]
    for f in range(n - 1, -1, -1):
        if f < n - 1 and abs(cam[f] - cam[f + 1]) > 0.2:
            cur = cam[f]
        else:
            cur += (cam[f] - cur) * k
        back.append(cur)
    return back[::-1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--faces")
    ap.add_argument("--step", type=int, default=3)
    ap.add_argument("--hold", type=float, default=0.12)
    ap.add_argument("--ease", type=float, default=0.6)
    ap.add_argument("--json")
    a = ap.parse_args()
    ow, oh = (int(x) for x in a.size.split("x"))
    W, H, fps, n = probe(a.src)
    cw = min(W, round(H * ow / oh / 2) * 2)
    if a.faces:
        rows = json.loads(Path(a.faces).read_text())
    else:
        from _swift import tool
        rows = json.loads(subprocess.run([str(tool("faces")), a.src, str(a.step), str(fps)],
                                         capture_output=True, text=True, check=True).stdout)
    samples = []
    for frame, boxes in rows:
        good = [b for b in boxes if b[4] >= 0.5]
        big = max(good, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), default=None)
        samples.append((int(frame), (big[0] + big[2]) / 2 if big else None))
    hold = a.hold * cw / W
    centres = path(sorted(samples), n, fps, hold, a.ease)
    lefts = [min(max(round(c * W - cw / 2), 0), W - cw) for c in centres]
    if a.json:
        Path(a.json).write_text(json.dumps(lefts))
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        for f, x in enumerate(lefts):
            if not f or x != lefts[f - 1]:
                fh.write(f"{f / fps:.4f} crop@rf x {x};\n")
        cmds = fh.name
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a.src, "-vf",
                    f"sendcmd=f='{cmds}',crop@rf=w={cw}:h={H}:x={lefts[0]}:y=0,scale={ow}:{oh}:flags=lanczos:"
                    f"out_color_matrix=bt709:out_range=tv,setsar=1,format=yuv420p,{TAGS}",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-color_primaries", "bt709",
                    "-color_trc", "bt709", "-colorspace", "bt709", "-c:a", "copy", "-movflags", "+faststart",
                    a.out], check=True)
    Path(cmds).unlink()
    moves = sum(1 for p, q in zip(lefts, lefts[1:]) if p != q)
    print(json.dumps({"out": a.out, "crop": [cw, H], "frames": n, "moving_frames": moves,
                      "faces_seen": sum(1 for _, x in samples if x is not None), "samples": len(samples)}))


if __name__ == "__main__":
    main()

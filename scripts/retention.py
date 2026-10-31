#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Read a posted video's retention graph against its EDL: where viewers left, and what was on.

Usage: retention.py EDL.json CURVE.csv [--top 3]

CURVE.csv: "seconds,percent" rows read off the platform's retention graph (TikTok Studio, the
Instagram and YouTube apps show it; there is no export, so read a point every second or two, and
at every visible kink). Prints, per segment, viewers at its start and end and the loss per second;
then the steepest drops, each with the line being said (from the words files) and the segment's
"why". Use it to plan the next video, not to re-cut a posted one: a drop at 0-3 s is the hook,
a drop at a cut is the cut, a slow slide is length. Platforms count a replay as retention over
100% at the end; that is a loop, not an error.
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import edl as E  # noqa: E402


def curve(path: str) -> list[tuple[float, float]]:
    pts = []
    for row in csv.reader(Path(path).read_text().splitlines()):
        try:
            pts.append((float(row[0]), float(row[1].rstrip("%"))))
        except (ValueError, IndexError):
            continue  # a header row
    if len(pts) < 2:
        sys.exit(f"retention: {path} needs two or more seconds,percent rows")
    return sorted(pts)


def at(pts: list[tuple[float, float]], t: float) -> float:
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / ((t1 - t0) or 1)
    return pts[-1][1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edl")
    ap.add_argument("curve")
    ap.add_argument("--top", type=int, default=3)
    a = ap.parse_args()
    plan = E.Plan(Path(a.edl))
    pts, fps = curve(a.curve), plan.fps
    rows = plan.timeline()
    words = E.timeline_words(plan)
    print(f"{'seg':>3} {'start':>6} {'end':>6} {'kept%':>6} {'left%':>6} {'%/s':>5}  why")
    for r, s in zip(rows, plan.segs):
        t0, t1 = r["start"] / fps, (r["start"] + r["dur"]) / fps
        v0, v1 = at(pts, t0), at(pts, t1)
        print(f"{r['k']:>3} {t0:6.2f} {t1:6.2f} {v0:6.1f} {v1:6.1f} {(v0 - v1) / max(t1 - t0, 0.01):5.1f}  "
              f"{s.get('why', '')[:60]}")
    hook = at(pts, 3.0)
    print(f"\nat 3 s: {hook:.0f}% still watching")
    end = (rows[-1]["start"] + rows[-1]["dur"]) / fps
    steps = [(at(pts, t / 2) - at(pts, t / 2 + 1), t / 2) for t in range(0, int(end * 2) - 1)]
    shown = []
    for drop, t in sorted(steps, reverse=True):
        if len(shown) >= a.top or drop <= 0:
            break
        if any(abs(t - u) < 1.5 for u in shown):
            continue
        shown.append(t)
        r = next((x for x in rows if x["start"] <= t * fps < x["start"] + x["dur"]), rows[-1])
        said = " ".join(w["text"] for w in words if t - 0.5 <= w["start"] < t + 1.5)
        cut = min((abs(x["start"] / fps - t) for x in rows[1:]), default=99)
        near = f", {cut:.1f}s from a cut" if cut < 1 else ""
        print(f"drop {drop:.1f}% at {t:.1f}-{t + 1:.1f}s (segment {r['k']}{near}): {said[:80]!r}")


if __name__ == "__main__":
    main()

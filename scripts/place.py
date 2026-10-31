#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Text never covers a face: move each caption or title to the clear spot nearest its usual one.

Usage: place.py FACES.json TEXT.json [-o OUT.json] [--kind caption|title] [options]

FACES.json: [[frame, [[x0, y0, x1, y1, confidence], ...]], ...] in frame fractions, origin top-left,
  sampled every few frames of the CUT (run faces.swift on a draft render, not on the sources).
TEXT.json: phrases from captions.py -f json --fps N (startFrame, endFrame, lines), or titles
  shaped the same way. Each gets "place": {x0, x1, bottom} (captions) or {x0, x1, top} (titles),
  which templates/remotion/PhraseCaptions.tsx and CalmText.tsx read.

  --size 1080x1920   frame
  --font-size 76     px; --line-height 1.2; --em 0.56 (average glyph width in em for a bold sans;
                     measure your font and raise it for wide faces or emoji)
  --home 1400        captions: usual bottom edge (default --bottom); titles: usual top edge (default 300)
  --top 290 --bottom 1400   the band text may use (platform bars above and below)
  --x0 90 --x1 890   the column text may use (left of the right-hand buttons)
Exit 1 when a phrase has nowhere clear to go: shorten it, shrink it, or let it wait out the face.
"""
import argparse
import json
import sys
from pathlib import Path

GROW = (0.05, 0.4, 0.05, 0.08)  # face box grown left, up (hair), right, down (chin) by its own size
MIN_CONF = 0.5
STEP_PX = 10
PAD = 16  # px kept between text and a face


def boxes(faces: list, s: int, e: int, W: int, H: int) -> list[tuple[float, float, float, float]]:
    """Every grown face box sampled in [s, e] or one sample either side (a face between samples), in px."""
    frames = [f for f, _ in faces]
    step = min((b - a for a, b in zip(frames, frames[1:]) if b > a), default=1)
    out = []
    for f, fs in faces:
        if s - step <= f <= e + step:
            for x0, y0, x1, y1, c in fs:
                if c < MIN_CONF:
                    continue
                w, h = x1 - x0, y1 - y0
                out.append(((x0 - GROW[0] * w) * W - PAD, (y0 - GROW[1] * h) * H - PAD,
                            (x1 + GROW[2] * w) * W + PAD, (y1 + GROW[3] * h) * H + PAD))
    return out


def hits(r: tuple[float, float, float, float], bs: list) -> bool:
    return any(r[0] < b[2] and b[0] < r[2] and r[1] < b[3] and b[1] < r[3] for b in bs)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("faces")
    ap.add_argument("text")
    ap.add_argument("-o", "--out")
    ap.add_argument("--kind", choices=["caption", "title"], default="caption")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--font-size", type=float, default=76)
    ap.add_argument("--line-height", type=float, default=1.2)
    ap.add_argument("--em", type=float, default=0.56)
    ap.add_argument("--home", type=float)
    ap.add_argument("--top", type=float, default=290)
    ap.add_argument("--bottom", type=float, default=1400)
    ap.add_argument("--x0", type=float, default=90)
    ap.add_argument("--x1", type=float, default=890)
    a = ap.parse_args()
    W, H = (int(x) for x in a.size.split("x"))
    faces = json.loads(Path(a.faces).read_text())
    items = json.loads(Path(a.text).read_text())
    home = a.home if a.home is not None else (a.bottom if a.kind == "caption" else 300.0)
    cx = (a.x0 + a.x1) / 2
    stuck = []
    for it in items:
        lines = it.get("lines") or [it.get("text", "")]
        h = len(lines) * a.font_size * a.line_height
        w = min(max(len(x) for x in lines) * a.font_size * a.em, a.x1 - a.x0)
        bs = boxes(faces, it["startFrame"], it["endFrame"], W, H)
        # candidate top edges, nearest the usual spot first
        usual = home - h if a.kind == "caption" else home
        tops = [t for t in range(int(a.top), int(a.bottom - h) + 1, STEP_PX)]
        tops.sort(key=lambda t: abs(t - usual))
        free = next((t for t in tops if not hits((cx - w / 2, t, cx + w / 2, t + h), bs)), None)
        if free is None:
            stuck.append(f"frames {it['startFrame']}-{it['endFrame']} \"{' / '.join(lines)}\": no clear spot")
            continue
        if abs(free - usual) < STEP_PX:
            it.pop("place", None)
            continue
        it["place"] = ({"x0": a.x0, "x1": a.x1, "bottom": round(free + h)} if a.kind == "caption"
                       else {"x0": a.x0, "x1": a.x1, "top": round(free)})
    text = json.dumps(items, indent=1)
    moved = sum(1 for it in items if "place" in it)
    if a.out:
        Path(a.out).write_text(text + "\n")
        print(f"{moved} of {len(items)} moved off a face -> {a.out}")
    else:
        print(text)
    for s in stuck:
        print(f"text-on-face: {s}", file=sys.stderr)
    sys.exit(1 if stuck else 0)


if __name__ == "__main__":
    main()

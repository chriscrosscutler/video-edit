#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Pick a cover frame: eyes open, in focus, and the best looking by Apple Vision's aesthetics score.

Usage: cover.py VIDEO OUT.jpg [--every 0.25] [--top N SHEET.jpg] [--json OUT.json] [--grid x0,y0,x1,y1]

Scores a frame every --every seconds with cover.swift (macOS), then drops frames where the largest
face has its eyes shut or lowered or looks down (at a product, a card), frames softer than the clip's median, and utility shots (a receipt, a
screenshot) while anything else is left; the highest aesthetics score wins (before macOS 15, the
sharpest frame). Writes that frame at full resolution (.jpg or .png).

  --json OUT.json   the pick: time, frame, scores, faces, and title_box, the tallest band of the
                    profile-grid crop that clears every face (fractions, origin top-left; null when
                    a face fills it), for a cover title that still reads on the profile grid
  --grid 0,0.125,1,0.875   the crop the profile grid shows, fractions of the frame: Instagram shows
                    the centre 3:4 of a 9:16 video (1080x1440 at y 240-1680 of 1080x1920)
  --top N SHEET.jpg also a contact sheet (sheet.py) of the N best, at least a second apart, best first
Run it on the graded cut before captions go on, so no half-sentence caption sits on the cover, and
upload the picture as the custom cover; a cover title goes in title_box.
"""
import argparse
import json
import statistics
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _swift import tool  # noqa: E402

# Measured on one creator's real takes (2026-10-31); re-check on other faces. Eye height over width:
# facing the camera 0.27-0.38, eyes lowered to a card 0.19-0.21, shut 0.06-0.14. Head pitch in radians:
# facing the camera -0.15 to 0.14, looking down at what is in her hands 0.24-0.29.
EYES_SHUT = 0.22
LOOKS_DOWN = 0.2
MIN_CONF = 0.5
GROW = (0.05, 0.4, 0.05, 0.08)  # face box grown left, up (hair), right, down (chin), as place.py does


def run(cmd: list) -> str:
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"cover: {Path(str(cmd[0])).name} failed:\n{p.stderr.strip()[-1500:]}")
    return p.stdout


def probe(path: str) -> dict:
    p = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-print_format", "json",
                        "-show_streams", "-show_format", path]))
    if not p.get("streams"):
        sys.exit(f"cover: no video stream in {path}")
    v = p["streams"][0]
    rot = next((int(sd["rotation"]) for sd in v.get("side_data_list", []) if "rotation" in sd), 0) % 360
    w, h = v["width"], v["height"]
    matrix = v.get("color_space") if v.get("color_space") not in (None, "unknown", "reserved") else None
    if not matrix:  # untagged: HD is BT.709, SD BT.601, the guess players make
        matrix = "bt709" if max(w, h) >= 1280 or min(w, h) > 576 else "bt601"
    return {"fps": float(Fraction(v["avg_frame_rate"])), "start": float(p["format"].get("start_time") or 0),
            "size": (h, w) if rot in (90, 270) else (w, h),
            "matrix": {"bt470bg": "bt601", "bt2020nc": "bt2020", "bt2020c": "bt2020"}.get(matrix, matrix)}


def largest(row: dict) -> list | None:
    faces = [f for f in row["faces"] if f[4] >= MIN_CONF]
    return max(faces, key=lambda f: (f[2] - f[0]) * (f[3] - f[1])) if faces else None


def eyes(row: dict) -> float | None:
    """Mean eye openness of the largest confident face, or None without one."""
    f = largest(row)
    open_ = [e for e in f[5:7] if e is not None] if f else []
    return sum(open_) / len(open_) if open_ else None


def pitch(row: dict) -> float | None:
    """The largest confident face's head pitch, positive looking down, or None."""
    f = largest(row)
    return f[7] if f and len(f) > 7 else None


def title_box(row: dict, grid: list) -> list | None:
    """The tallest band of the grid crop, full crop width, that no grown face box enters."""
    gx0, gy0, gx1, gy1 = grid
    blocked = []
    for x0, y0, x1, y1, c, *_ in row["faces"]:
        w, h = x1 - x0, y1 - y0
        if c >= MIN_CONF and x0 - GROW[0] * w < gx1 and gx0 < x1 + GROW[2] * w:
            blocked.append((max(gy0, y0 - GROW[1] * h), min(gy1, y1 + GROW[3] * h)))
    gaps, top = [], gy0
    for a, b in sorted(blocked):
        if a > top:
            gaps.append((top, a))
        top = max(top, b)
    if top < gy1:
        gaps.append((top, gy1))
    if not gaps:
        return None
    a, b = max(gaps, key=lambda g: g[1] - g[0])
    return [round(gx0, 4), round(a, 4), round(gx1, 4), round(b, 4)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--every", type=float, default=0.25, help="seconds between scored frames")
    ap.add_argument("--top", nargs=2, metavar=("N", "SHEET"))
    ap.add_argument("--json")
    ap.add_argument("--grid", default="0,0.125,1,0.875")
    a = ap.parse_args()
    grid = [float(x) for x in a.grid.split(",")]
    if len(grid) != 4 or not (0 <= grid[0] < grid[2] <= 1 and 0 <= grid[1] < grid[3] <= 1):
        sys.exit("cover: --grid is x0,y0,x1,y1 in fractions of the frame")
    info = probe(a.video)
    fps = info["fps"]
    rows = json.loads(run([tool("cover"), a.video, max(1, round(a.every * fps)), fps]))
    if not rows:
        sys.exit(f"cover: no frames read from {a.video}")
    median = statistics.median(r["sharpness"] for r in rows)
    pool, dropped = rows, {}
    tests = {"eyes": lambda r: (e := eyes(r)) is None or e >= EYES_SHUT,
             "down": lambda r: (p := pitch(r)) is None or p < LOOKS_DOWN,
             "soft": lambda r: r["sharpness"] >= median,
             "utility": lambda r: not r["utility"]}
    for why, keep in tests.items():
        kept = [r for r in pool if keep(r)]
        if kept:
            dropped[why] = len(pool) - len(kept)
            pool = kept
        else:
            print(f"cover: every frame left fails the {why} test; keeping them", file=sys.stderr)
    scored = any(r["aesthetic"] is not None for r in pool)

    def score(r: dict) -> float:
        return r["aesthetic"] if scored else r["sharpness"] / max(median, 1e-9)

    ranked = sorted(pool, key=lambda r: (score(r), r["sharpness"]), reverse=True)
    best = ranked[0]

    def at(r: dict) -> float:
        return max(0.0, (r["frame"] - 0.5) / fps - info["start"])  # half a frame early lands on the frame

    ext = Path(a.out).suffix.lower()
    if ext in (".jpg", ".jpeg"):  # JPEG is BT.601 full range
        vf = f"scale=in_color_matrix={info['matrix']}:out_color_matrix=bt601:out_range=pc,format=yuvj444p"
    else:
        vf = f"scale=in_color_matrix={info['matrix']},format=rgb24"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at(best):.4f}", "-i", a.video, "-frames:v", "1", "-vf", vf,
         "-q:v", "2", a.out])
    result = {"frame": best["frame"], "time": round(best["frame"] / fps - info["start"], 3),
              "aesthetic": best["aesthetic"], "utility": best["utility"], "sharpness": best["sharpness"],
              "eyes": eyes(best), "faces": best["faces"], "title_box": title_box(best, grid), "grid": grid,
              "size": list(info["size"]), "sampled": len(rows), "dropped": dropped,
              "score": "aesthetic" if scored else "sharpness (aesthetics need macOS 15)"}
    if a.top:
        n = max(1, int(a.top[0]))
        top = []
        for r in ranked:  # a second apart, so the sheet shows choices, not near-copies
            if all(abs(r["frame"] - t["frame"]) >= fps for t in top):
                top.append(r)
            if len(top) == n:
                break
        top += [r for r in ranked if r not in top][:n - len(top)]
        run([sys.executable, HERE / "sheet.py", a.video, a.top[1], "--at", ",".join(f"{at(r):.3f}" for r in top),
             "--cols", min(n, 6)])
        result["top"] = [{"frame": r["frame"], "time": round(r["frame"] / fps - info["start"], 3),
                          "aesthetic": r["aesthetic"], "sharpness": r["sharpness"]} for r in top]
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=1) + "\n")
    print(f"{a.out}: frame {best['frame']} ({result['time']:.2f} s), {result['score']} "
          f"{best['aesthetic'] if scored else round(best['sharpness'])}; {len(pool)} of {len(rows)} frames "
          f"passed" + (f"; title box {result['title_box']}" if result["title_box"] else "; no clear title band"))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Privacy blur: addresses, phone numbers, emails, barcodes and long numbers on screen, found and covered.

Usage: redact.py VIDEO OUT.mp4 [--find KINDS] [--box x0,y0,x1,y1@T0-T1 ...] [--track x0,y0,x1,y1@T ...]
                 [--step 3] [--pad 0.02] [--style blur|pixel|box] [--regions REGIONS.json] [--dry-run]
                 [--sheet SHEET.jpg] [--sure-only]

  --find all          address,phone,email,barcode,digits,url, or any of them comma-separated:
      address   a number and a street word (123 Main Street), a PO box, apt/suite, a state and ZIP
                (IL 62704), a ZIP+4, a UK postcode; the lines beside it in the same block (the
                name above the street) go with it
      phone     (555) 123-4567, 555.123.4567, +44 20 7946 0958, 07700 900123
      email     name@example.com
      barcode   any barcode or QR code (a shipping label's 2D code holds the address)
      digits    tracking numbers (1Z...) and any run of 8 or more digits, spaces or dashes allowed
      url       https://..., www...., or a bare name.com (product boxes have these: leave url out there)
  --box x0,y0,x1,y1@T0-T1   also cover this box (fractions, origin top-left) from T0 to T1 seconds;
                            @T0- runs to the end; no @ covers the whole video
  --track x0,y0,x1,y1@T     also cover what is in this box at T seconds, followed by track.swift until lost
  --step 3                  read every 3rd frame; a region is filled in between and held two samples
                            beyond its first and last sighting
  --pad 0.02                grow every box by this fraction of the frame's short side
  --style blur              blur (default), box (solid black, the only cover nothing can undo), or
                            pixel (a look only: pixelated text can be read back)
  --regions REGIONS.json    cover these regions (a --dry-run's output, edited) instead of reading the video
  --dry-run                 print the regions as JSON and render nothing
  --sheet SHEET.jpg         one frame per region, its box drawn in red, in the order of the list
  --sure-only               leave out found regions marked unsure (after the sheet shows they are print)

A region is "unsure" when OCR never read it with full confidence: upside-down print, curved
embroidery and packaging small print read as garbage that can look like a phone number or a
postcode. Unsure regions are covered unless --sure-only or the JSON drops them; look at the sheet.

Text is read by ocr.swift (Apple Vision, macOS). A line that matches once is covered for as long as
it is seen, even on frames where it reads differently. Every region and the text that triggered it
goes to stderr; read that list and watch the render before posting: OCR misses blurred, tiny,
curved and handwritten text, so add a --box or --track for anything it missed. Needs a constant
frame rate and SDR (edl.py conform); the render matches edl.py's master settings, audio copied.
"""
import argparse
import bisect
import difflib
import json
import math
import re
import subprocess
import sys
import tempfile
from collections import Counter
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _swift import tool  # noqa: E402

KINDS = ("address", "phone", "email", "barcode", "digits", "url")
TAGS = "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"
STATES = ("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
          "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC PR VI GU").split()
STREET = ("street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|court|place|pl|terrace|circle|cir|"
          "parkway|pkwy|highway|hwy|way|loop|trail|close|crescent|grove|gardens|mews|row|walk|hill|square")
I = re.IGNORECASE
PATTERNS = [
    # a name word between number and street word keeps "100 ct" and "2 way" out
    ("address", re.compile(rf"\b\d{{1,6}}[a-z]?\s+(?:[a-z][\w.'-]*\s+){{1,4}}(?:{STREET})\b", I)),
    ("address", re.compile(r"\bp\.?\s?o\.?\s?box\s+\d+", I)),
    ("address", re.compile(r"\b(?:apt|suite|ste)\.?\s*#?\s*\d+", I)),
    ("address", re.compile(rf"\b(?:{'|'.join(STATES)}),?\s+\d{{5}}(?:-\d{{4}})?\b")),
    ("address", re.compile(r"\b\d{5}-\d{4}\b")),
    ("address", re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[ABD-HJLNP-UW-Z]{2}\b")),
    ("phone", re.compile(r"(?<![\w+])(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]\d{4}(?!\w)")),
    ("phone", re.compile(r"(?<!\w)\+\d[\d\s().-]{7,}\d(?!\w)")),
    ("phone", re.compile(r"(?<!\w)0\d{2,4}[\s-]?\d{3}[\s-]?\d{3,4}(?!\w)")),
    ("email", re.compile(r"[\w.+-]+\s?@\s?[\w-]+(?:\.[\w-]+)+")),
    ("url", re.compile(r"\b(?:https?://|www\.)\S+", I)),
    ("url", re.compile(r"\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|co|us|uk|ca|au|de|fr|app|"
                       r"shop|store|me|ly|gl|tv|info|biz|edu|gov)\b(?:/\S*)?", I)),
    ("digits", re.compile(r"\d(?:[\s-]?\d){7,}")),
]
SURE = 0.9  # Vision reports 0.3, 0.5 or 1.0; garbage from print it cannot read comes back at 0.3-0.5
DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}")


def run(cmd: list) -> str:
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"redact: {Path(str(cmd[0])).name} failed:\n{p.stderr.strip()[-1500:]}")
    return p.stdout


def probe(path: str) -> dict:
    p = json.loads(run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-print_format",
                        "json", "-show_streams", path]))
    if not p.get("streams"):
        sys.exit(f"redact: no video stream in {path}")
    v = p["streams"][0]
    rot = next((int(sd["rotation"]) for sd in v.get("side_data_list", []) if "rotation" in sd), 0) % 360
    avg, real = Fraction(v.get("avg_frame_rate", "0/1")), Fraction(v.get("r_frame_rate", "0/1"))
    if not avg or not real or abs(avg - real) / real > 0.01:
        sys.exit(f"redact: {path} has a variable frame rate: conform it first (edl.py conform)")
    if v.get("color_transfer") in ("arib-std-b67", "smpte2084"):
        sys.exit(f"redact: {path} is HDR: conform it to BT.709 SDR first (edl.py conform)")
    w, h = v["width"], v["height"]
    fps = float(avg)
    return {"size": (h, w) if rot in (90, 270) else (w, h), "rate": avg, "fps": fps,
            "frames": int(v.get("nb_read_packets") or 0), "offset": round(float(v.get("start_time") or 0) * fps),
            "start": float(v.get("start_time") or 0), "coded": (w, h),
            "matrix": v.get("color_space") if v.get("color_space") not in (None, "unknown", "reserved") else None}


def kinds(text: str) -> dict:
    """Every kind of sensitive text in one OCR line, each with the first text that matched."""
    if text.startswith("barcode:"):
        return {"barcode": text}
    found = {}
    for kind, rx in PATTERNS:
        if kind in found:
            continue
        for m in rx.finditer(text):
            s = m.group()
            if kind == "phone" and s.startswith("+") and not 9 <= sum(c.isdigit() for c in s) <= 15:
                continue
            if kind == "digits" and DATE.fullmatch(s):
                continue
            found[kind] = s
            break
    squashed = re.sub(r"[\s-]", "", text.upper())
    if "digits" not in found and (m := re.search(r"1Z[0-9A-Z]{16}", squashed)):
        found["digits"] = m.group()
    return found


def classify(lines: list, find: set) -> None:
    """Marks each line's hits; an address pulls in the lines up to two steps away in its block."""
    for d in lines:
        d["hits"] = {k: s for k, s in kinds(d["text"]).items() if k in find}
    if "address" not in find:
        return
    grow = [(d, 0) for d in lines if "address" in d["hits"]]
    while grow:
        a, depth = grow.pop()
        ax0, ay0, ax1, ay1 = a["box"]
        ah = ay1 - ay0
        if depth >= 2 or not ah:
            continue
        for d in lines:
            x0, y0, x1, y1 = d["box"]
            if d["hits"] or d["barcode"]:
                continue
            if x0 < ax1 and ax0 < x1 and 0.5 < (y1 - y0) / ah < 2 and max(y0 - ay1, ay0 - y1) < ah:
                d["hits"]["address"] = f"{d['text']} (beside an address)"
                d["conf"] = min(d["conf"], a["conf"])  # only as sure as the address it sits beside
                grow.append((d, depth + 1))


def iou(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def centre(b) -> tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def extrapolate(keys: list, f: float) -> list:
    """The box at frame f from the last two keys' motion (or the last key, if it is alone)."""
    k = keys[-1]
    if len(keys) < 2 or keys[-1][0] == keys[-2][0]:
        return list(k[1:])
    p = keys[-2]
    u = (f - k[0]) / (k[0] - p[0])
    return [k[j] + u * (k[j] - p[j]) for j in range(1, 5)]


def tracks(samples: list, step: int, fps: float, find: set) -> list:
    """OCR lines joined across samples by overlap (with motion) and similar text."""
    gap = max(3 * step, round(fps))  # unread longer than a second: a new region
    live, done = [], []
    for frame, found in samples:
        lines = [{"box": tuple(r[:4]), "conf": r[4], "text": r[5], "barcode": r[5].startswith("barcode:")}
                 for r in found]
        classify(lines, find)
        pairs = []
        for ti, t in enumerate(live):
            guess = extrapolate(t["keys"], frame)
            for di, d in enumerate(lines):
                if t["barcode"] != d["barcode"]:
                    continue
                b = d["box"]
                o = max(iou(guess, b), iou(t["keys"][-1][1:], b))
                sim = difflib.SequenceMatcher(None, t["text"], d["text"]).ratio()
                # the same words a line or two away: text moving faster than its own height per sample
                near = math.dist(centre(guess), centre(b)) < 2.5 * max(guess[3] - guess[1], b[3] - b[1])
                if o >= 0.1 or (near and sim >= 0.8):
                    pairs.append((o + 0.5 * sim, ti, di))
        took, used = set(), set()
        for _, ti, di in sorted(pairs, reverse=True):
            if ti in took or di in used:
                continue
            took.add(ti)
            used.add(di)
            t, d = live[ti], lines[di]
            t["keys"].append([frame, *d["box"]])
            t["text"] = d["text"]
            t["hits"] += d["hits"].items()
            if d["hits"]:
                t["conf"] = max(t["conf"], d["conf"])
        for di, d in enumerate(lines):
            if di not in used:
                live.append({"keys": [[frame, *d["box"]]], "text": d["text"], "barcode": d["barcode"],
                             "hits": list(d["hits"].items()), "conf": d["conf"] if d["hits"] else 0.0})
        done += [t for t in live if frame - t["keys"][-1][0] > gap]
        live = [t for t in live if frame - t["keys"][-1][0] <= gap]
    return done + live


def found_regions(video: str, info: dict, step: int, find: set) -> list:
    samples = json.loads(run([tool("ocr"), video, step, info["fps"]]))
    out = []
    for t in tracks(samples, step, info["fps"], find):
        if not t["hits"]:
            continue
        kind = Counter(k for k, _ in t["hits"]).most_common(1)[0][0]
        out.append({"kind": kind, "text": next(s for k, s in t["hits"] if k == kind),
                    "sure": t["conf"] >= SURE, "conf": t["conf"], "hold": [2 * step, 2 * step], "keys": t["keys"]})
    return out


def parse_box(spec: str, what: str) -> tuple[list, str]:
    box, _, when = spec.partition("@")
    v = [float(x) for x in box.split(",")] if box.count(",") == 3 else []
    if len(v) != 4 or not (0 <= v[0] < v[2] <= 1 and 0 <= v[1] < v[3] <= 1):
        sys.exit(f"redact: {what} {spec!r}: the box is x0,y0,x1,y1 in fractions of the frame, origin top-left")
    return v, when


def manual_boxes(specs: list, info: dict) -> list:
    out, fps, first = [], info["fps"], info["offset"]
    last = first + max(info["frames"] - 1, 0)
    for spec in specs:
        box, when = parse_box(spec, "--box")
        t0, _, t1 = when.partition("-")
        f0 = first + math.floor(float(t0) * fps) if t0 else first
        f1 = min(first + math.ceil(float(t1) * fps), last) if t1 else last
        out.append({"kind": "box", "text": spec, "hold": [0, 0], "keys": [[f0, *box], [max(f0, f1), *box]]})
    return out


def tracked_boxes(video: str, specs: list, info: dict, step: int) -> list:
    out = []
    for spec in specs:
        box, when = parse_box(spec, "--track")
        start = info["offset"] + round(float(when or 0) * info["fps"])
        p = subprocess.run([str(tool("track")), video, str(start), ",".join(map(str, box)),
                            "--fps", str(info["fps"])], capture_output=True, text=True)
        if p.returncode:
            sys.exit(f"redact: track failed:\n{p.stderr.strip()[-800:]}")
        if p.stderr.strip():
            print(f"redact: --track {spec}: {p.stderr.strip()}", file=sys.stderr)
        rows = json.loads(p.stdout)
        if not rows:
            print(f"redact: --track {spec}: lost on its first frame, nothing to follow", file=sys.stderr)
        keys = [[f, *b[:4]] for i, (f, b) in enumerate(rows) if i % step == 0 or i == len(rows) - 1]
        out.append({"kind": "track", "text": spec, "hold": [0, step], "keys": keys})
    return out


def box_at(r: dict, frames: list, f: int) -> list | None:
    keys, (before, after) = r["keys"], r.get("hold", [0, 0])
    if f < frames[0] - before or f > frames[-1] + after:
        return None
    if f <= frames[0] or f >= frames[-1]:
        # held: the last box, stretched over where its motion would have carried it
        k = keys[:2][::-1] if f <= frames[0] else keys[-2:]
        e = extrapolate(k, f)
        b = k[-1][1:]
        return [min(b[0], e[0]), min(b[1], e[1]), max(b[2], e[2]), max(b[3], e[3])]
    i = bisect.bisect_right(frames, f)
    a, b = keys[i - 1], keys[i]
    u = (f - a[0]) / (b[0] - a[0])
    return [a[j] + u * (b[j] - a[j]) for j in range(1, 5)]


def render(video: str, out: str, regions: list, info: dict, style: str, pad: float) -> None:
    W, H = info["size"]
    mw, mh = -(-W // 4), -(-H // 4)  # mask at quarter size, rounded outward, stretched back up
    padpx = pad * min(W, H)
    sizes = []
    for r in regions:
        side = sorted(min((k[3] - k[1]) * W, (k[4] - k[2]) * H) for k in r["keys"])
        sizes.append(side[len(side) // 2])
    s = max(sizes)  # the widest region's short side sets one strength for all: stronger only flattens more
    if style == "blur":
        fx = (f"scale={mw}:{mh}:flags=area,gblur=sigma={min(max(0.6 * s, 10), 150) / 4:.1f}:steps=3,"
              f"scale={W}:{H}:flags=bilinear")
    elif style == "pixel":
        b = int(min(max(0.5 * s, 12), 96))
        fx = f"pixelize=w={b}:h={b}"
    else:
        fx = "drawbox=c=black:t=fill"
    m = info["matrix"]
    if not m:
        w, h = info["coded"]
        m = "bt709" if max(w, h) >= 1280 or min(w, h) > 576 else "bt601"
    m = {"smpte170m": "bt601", "bt470bg": "bt601"}.get(m, m)
    # Both streams retimed to the same exact grid, so every mask frame meets its own picture frame.
    pts = f"settb=AVTB,setpts={info['start']:.6f}/TB+N*{info['rate'].denominator}/({info['rate'].numerator}*TB)"
    graph = (f"[0:v]scale=in_color_matrix={m}:out_color_matrix=bt709:out_range=tv,{pts},split[a][b];[b]{fx}[fx];"
             f"[1:v]{pts},scale={W}:{H}:flags=neighbor,format=gray[m];[fx][m]alphamerge[top];"
             f"[a][top]overlay=format=auto:shortest=1,format=yuv420p,{TAGS}[v]")
    rate = f"{info['rate'].numerator}/{info['rate'].denominator}"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", video, "-f", "rawvideo", "-pix_fmt", "gray", "-video_size",
           f"{mw}x{mh}", "-framerate", rate, "-i", "-", "-filter_complex", graph, "-map", "[v]", "-map", "0:a?",
           "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p", "-color_primaries", "bt709",
           "-color_trc", "bt709", "-colorspace", "bt709", "-c:a", "copy", "-movflags", "+faststart", out]
    frames = [[k[0] for k in r["keys"]] for r in regions]
    empty = bytes(mw * mh)
    with tempfile.TemporaryFile() as err:
        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err)
        try:
            # a second spare in case the count is short; the picture ending ends the render (shortest=1)
            for i in range(info["frames"] + math.ceil(info["fps"])):
                f = i + info["offset"]
                boxes = [b for r, fs in zip(regions, frames) if (b := box_at(r, fs, f))]
                if not boxes:
                    ff.stdin.write(empty)
                    continue
                mask = bytearray(mw * mh)
                for x0, y0, x1, y1 in boxes:
                    c0 = max(0, math.floor((x0 * W - padpx) * mw / W))
                    c1 = min(mw, math.ceil((x1 * W + padpx) * mw / W))
                    r0 = max(0, math.floor((y0 * H - padpx) * mh / H))
                    r1 = min(mh, math.ceil((y1 * H + padpx) * mh / H))
                    if c1 > c0:
                        row = b"\xff" * (c1 - c0)
                        for y in range(r0, r1):
                            mask[y * mw + c0:y * mw + c1] = row
                ff.stdin.write(mask)
            ff.stdin.close()
        except BrokenPipeError:
            pass
        if ff.wait():
            err.seek(0)
            sys.exit(f"redact: ffmpeg failed:\n{err.read().decode(errors='replace').strip()[-1500:]}")


def sheet(video: str, regions: list, info: dict, path: str) -> None:
    """Each region's middle frame with its box in red, six across, in list order."""
    W, H = info["size"]
    with tempfile.TemporaryDirectory() as d:
        for i, r in enumerate(regions[:36]):
            f, x0, y0, x1, y1 = r["keys"][len(r["keys"]) // 2]
            x, y = round(x0 * W), round(y0 * H)
            box = f"drawbox=x={x}:y={y}:w={max(round(x1 * W) - x, 4)}:h={max(round(y1 * H) - y, 4)}:c=red:t=8"
            run(["ffmpeg", "-v", "error", "-ss", f"{(f - info['offset']) / info['fps']:.3f}", "-i", video,
                 "-frames:v", "1", "-vf", f"{box},scale=360:-2", f"{d}/r{i:03d}.png"])
        n = min(len(regions), 36)
        cols = min(n, 6)
        run(["ffmpeg", "-v", "error", "-y", "-i", f"{d}/r%03d.png", "-vf",
             f"tile={cols}x{-(-n // cols)}:padding=6:color=white", "-frames:v", "1", "-q:v", "3", path])
    if len(regions) > 36:
        print(f"redact: the sheet shows the first 36 of {len(regions)} regions", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--find", default="all")
    ap.add_argument("--box", action="append", default=[])
    ap.add_argument("--track", action="append", default=[])
    ap.add_argument("--step", type=int, default=3)
    ap.add_argument("--pad", type=float, default=0.02)
    ap.add_argument("--style", choices=["blur", "pixel", "box"], default="blur")
    ap.add_argument("--regions", help="regions to cover instead of reading the video")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sheet")
    ap.add_argument("--sure-only", action="store_true")
    a = ap.parse_args()
    find = set(KINDS) if a.find == "all" else set(a.find.split(","))
    if find - set(KINDS):
        sys.exit(f"redact: --find takes {','.join(KINDS)} or all, not {','.join(sorted(find - set(KINDS)))}")
    step = max(1, a.step)
    info = probe(a.video)
    if a.regions:
        loaded = json.loads(Path(a.regions).read_text())
        regions = loaded["regions"] if isinstance(loaded, dict) else loaded
    else:
        regions = found_regions(a.video, info, step, find)
    if a.sure_only:
        regions = [r for r in regions if r.get("sure", True)]
    regions += manual_boxes(a.box, info) + tracked_boxes(a.video, a.track, info, step)
    regions = sorted((r for r in regions if r.get("keys")), key=lambda r: r["keys"][0][0])
    for i, r in enumerate(regions, 1):
        r["id"] = i
        r["keys"] = sorted([k[0], *(round(x, 4) for x in k[1:5])] for k in r["keys"])
        t0 = (r["keys"][0][0] - info["offset"]) / info["fps"]
        t1 = (r["keys"][-1][0] - info["offset"]) / info["fps"]
        text = r.get("text", "")
        text = text if len(text) <= 28 else text[:27] + "…"
        unsure = "" if r.get("sure", True) else f"  unsure (OCR confidence {r['conf']:.1f}): look before covering"
        print(f"redact: {i} {r.get('kind', 'box')} {t0:.2f}-{t1:.2f} s: {text!r}{unsure}", file=sys.stderr)
    if a.sheet and regions:
        sheet(a.video, regions, info, a.sheet)
    if a.dry_run:
        print(json.dumps({"video": a.video, "fps": info["fps"], "size": list(info["size"]), "regions": regions},
                         indent=1))
        return
    if not regions:
        print("redact: nothing found to cover; no render (add --box or --track for what OCR missed)",
              file=sys.stderr)
        sys.exit(1)
    render(a.video, a.out, regions, info, a.style, a.pad)
    print(f"{a.out}: {len(regions)} region{'s' * (len(regions) != 1)} covered ({a.style})")


if __name__ == "__main__":
    main()

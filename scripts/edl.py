#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""The edit decision list (EDL): one JSON file every stage reads, and ffmpeg renders.

Usage:
  edl.py conform SRC... -o DIR [--fps 30] [--cover 1440x2560] [--channel N] [--stabilize]
                 [--denoise light|strong]
      Constant-rate, BT.709 SDR, rotation-baked H.264 intermediates (HLG/PQ tone-mapped: VideoToolbox
      on macOS, zscale elsewhere). Do this once at intake; cut and composite only conformed files.
      --stabilize: ffmpeg deshake plus a 4% punch-in to hide the edges (handheld only: phones
      already stabilize). --denoise: hqdn3d (light) or nlmeans (strong, slow) for dim footage.
  edl.py check EDL.json        pacing and sanity report; exit 1 on errors
  edl.py words EDL.json [-o OUT.json]   the kept words in timeline time, each with its "seg"
  edl.py render EDL.json OUT.mp4 [--draft]   cut, dissolves, cutaways, speed, audio; master quality
  edl.py qa EDL.json OUT.mp4 [--sheet S.jpg] [--lufs -14 | --no-loudness] [--tp -1]
            [--scopes S.png] [--no-ocr] [--allow TEXT ...]
      delivery checks: H.264 yuv420p at the EDL size and fps, BT.709 tags, frame count, A/V sync,
      AAC 48 kHz stereo, moov first, loudness, a pop at any cut (a warning); --sheet writes a frame
      after every change. Notes on clipped or crushed levels and shots that don't match their
      neighbours (--scopes writes a waveform and vectorscope per change). On macOS, reads the text
      on screen every half second (ocr.swift): another app's watermark or personal details (an
      address, phone, email, a tracking number) are errors; a price, a URL or a barcode are
      warnings. --allow skips text containing TEXT (the brand's own site).

EDL shape (times in seconds in the source; paths relative to the EDL file):
  {"fps": 30, "size": [1080, 1920],
   "sources": {"t1": {"path": "work/IMG_1.mp4", "words": "work/IMG_1.words.json"}, "b1": "broll/pour.mp4"},
   "segments": [{"src": "t1", "in": 1.2, "out": 6.85, "why": "lines 0-2, the payoff"},
                {"src": "t1", "in": 9.4, "out": 14.0, "transition": {"type": "fade", "frames": 16}},
                {"src": "b1", "in": 0.3, "out": 15.3, "gain_db": -12, "afade": 0.25, "why": "interlude"}],
   "cutaways": [{"src": "b1", "in": 0.3, "out": 3.3, "at": 4.0, "fade": 6, "why": "shows the pour"}],
   "limits": {"min_shot": 2.0, "min_save": 0.6, "cutaway": [2, 6], "max_len": 180}}
A transition is centred on the cut and eats handles (frames/2 of extra source on each side), so
the timeline keeps its length and the audio still cuts hard on the word. Its type is any ffmpeg
xfade transition (fade, dissolve, fadeblack, wipeleft, slideup, smoothleft, circleopen, ...).
Segment options: gain_db, mute, afade (audio fade seconds, default 0.008 de-click), crop
[x, y, w, h] as fractions of the source, zoom (centre punch-in, 1-2). Cutaways cover the picture
only; the voice runs on under them. A cutaway from a transparent source (ProRes 4444, PNG
sequence: a title) overlays the shot, so it has no length limit and is not a shot change.

Split edits: "audio_lead": 6 starts a segment's sound 6 frames before its picture (a J cut: we
hear the next line or place first); "audio_trail": 6 runs its sound 6 frames under the next
shot (an L cut). The timeline keeps its length; the source needs those frames beyond in/out.

Speed (segments and cutaways): "speed": 2 plays twice as fast (0.5 is slow motion), with the
voice time-stretched at its own pitch; "speed": [[0, 1], [0.4, 4], [0.6, 4], [1, 1]] ramps the
rate over the fraction of the source span, linear between keys, and mutes the source sound (lay
music or an effect over it). "smooth": true makes slow motion with motion-interpolated frames
(minterpolate, slow to render) instead of repeated ones. A sped segment takes no transition
handles or split edit.

Multicam: sync.py measures each extra camera's "offset" (seconds its clock runs behind the
first), set on its source; then every segment's in/out is in the first camera's clock, so
switching angles is changing "src". "audio_src": "a" keeps one mic's sound under any angle.
"grade": "colorchannelmixer=rr=1.04:bb=0.95" (match.py) grades a segment or cutaway in RGB.

Top level: "room_tone": "work/tone.wav" (quiet.py tone) fills muted, silent and ramped segments
instead of digital silence. "sfx": [{"path": "sfx/whoosh.wav", "at": {"seg": 2}, "gain_db": -8,
"align": "peak", "offset": 0}] lays sound effects on the dialogue: "at" is timeline seconds or
an anchor, {"seg": k} (the cut into segment k), {"word": i} (word i of `edl.py words`) or
{"cutaway": j}; "align": "peak" lands the effect's loudest moment on the anchor (a whoosh peaks
on the cut, a hit on the word) instead of its start.
"""
import argparse
import json
from array import array
import platform
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

LIMITS = {"min_shot": 2.0, "min_save": 0.6, "cutaway": [2.0, 6.0], "max_len": 180.0}

# ffmpeg 8 writes only the matrix from -color_* flags; setparams tags transfer and primaries too.
# setparams only relabels: every scale converts the matrix and range first (matrix_in + CONVERT).
TAGS = "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"
CONVERT = "out_color_matrix=bt709:out_range=tv"
# ffmpeg 8.1 xfade transitions ("custom" needs expressions, so it is left out).
XFADE = set("""fade wipeleft wiperight wipeup wipedown slideleft slideright slideup slidedown circlecrop
rectcrop distance fadeblack fadewhite radial smoothleft smoothright smoothup smoothdown circleopen
circleclose vertopen vertclose horzopen horzclose dissolve pixelize diagtl diagtr diagbl diagbr hlslice
hrslice vuslice vdslice hblur fadegrays wipetl wipetr wipebl wipebr squeezeh squeezev zoomin fadefast
fadeslow hlwind hrwind vuwind vdwind coverleft coverright coverup coverdown revealleft revealright
revealup revealdown""".split())
RAMP_STEPS = 24  # a ramp plays as this many constant-rate pieces, short enough to read as a curve
SFX_GAIN_DB = -8.0
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def run(cmd: list[str]) -> str:
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode:
        sys.exit(f"edl: {cmd[0]} failed:\n{out.stderr.strip()[-1500:]}")
    return out.stdout


def probe(path: Path) -> dict:
    p = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                        "-show_format", str(path)]))
    v = next((s for s in p["streams"] if s["codec_type"] == "video"), {})
    rot = next((int(sd["rotation"]) for sd in v.get("side_data_list", []) if "rotation" in sd), 0) % 360
    w, h = v.get("width", 0), v.get("height", 0)
    return {"duration": float(p["format"].get("duration", 0) or 0),
            "audio": any(s["codec_type"] == "audio" for s in p["streams"]),
            "fps": float(Fraction(v.get("avg_frame_rate", "0/1") or "0/1")) if v else 0.0,
            "hdr": v.get("color_transfer") in ("arib-std-b67", "smpte2084"),
            # a transparent source (a ProRes 4444 or PNG title) overlays the shot instead of replacing it
            "alpha": v.get("pix_fmt", "").startswith(("yuva", "rgba", "argb", "bgra", "abgr", "gbrap", "ya")),
            "matrix": v.get("color_space") if v.get("color_space") not in (None, "unknown", "reserved") else None,
            "coded": (w, h), "rotation": rot, "size": (h, w) if rot in (90, 270) else (w, h)}


def matrix_in(p: dict) -> str:
    """scale options naming an untagged source's matrix (scale alone reads untagged as BT.601).

    A tag wins; untagged HD is BT.709 and SD BT.601, the guess mpv and browsers make."""
    if p["matrix"]:
        return ""
    w, h = p["coded"]
    return f"in_color_matrix={'bt709' if max(w, h) >= 1280 or min(w, h) > 576 else 'bt601'}:"


def speed_pieces(item: dict, src_s: float) -> list[tuple[float, float, float]] | None:
    """A sped clip's map from source to timeline: (source offset, timeline offset, slope) pieces in
    seconds, or None at 1x. A ramp plays as RAMP_STEPS constant-rate pieces."""
    sp = item.get("speed", 1)
    if isinstance(sp, (int, float)):
        return None if sp == 1 else [(0.0, 0.0, 1 / sp)]
    keys = sorted((float(p), float(v)) for p, v in sp)

    def rate(p: float) -> float:
        for (p0, v0), (p1, v1) in zip(keys, keys[1:]):
            if p <= p1:
                return v0 + (v1 - v0) * (min(max(p, p0), p1) - p0) / ((p1 - p0) or 1)
        return keys[-1][1]

    pieces, y = [], 0.0
    for j in range(RAMP_STEPS):
        k = 1 / rate((j + 0.5) / RAMP_STEPS)
        pieces.append((src_s * j / RAMP_STEPS, y, k))
        y += src_s / RAMP_STEPS * k
    return pieces


def warp(pieces: list[tuple[float, float, float]], x: float) -> float:
    """Timeline offset of source offset x."""
    x0, y0, k = next((p for p in reversed(pieces) if p[0] <= x), pieces[0])
    return y0 + (x - x0) * k


def bad_speed(sp) -> str | None:
    if isinstance(sp, (int, float)):
        return None if 0 < sp <= 100 else f"{sp} is outside 0-100"
    try:
        keys = [(float(p), float(v)) for p, v in sp]
    except (TypeError, ValueError):
        return f"{sp!r} is neither a rate nor [[p, rate], ...] ramp keys"
    if len(keys) < 2 or any(not 0 <= p <= 1 or not 0 < v <= 100 for p, v in keys):
        return "ramp keys need two or more [p, rate] with p in 0-1 and rate in 0-100"
    return None


def ramped(item: dict) -> bool:
    return not isinstance(item.get("speed", 1), (int, float))


def retime(pieces: list[tuple[float, float, float]], fps: int, smooth: bool) -> str:
    """Filters that retime a clip read from its in point, then resample to the timeline rate."""
    expr = ""
    for x0, y0, k in reversed(pieces):
        piece = f"{y0:.6f}+(T-STARTT-{x0:.6f})*{k:.6f}"
        expr = f"if(lt(T-STARTT,{prev_x0:.6f}),{piece},{expr})" if expr else piece
        prev_x0 = x0
    slow = smooth and max(k for _, _, k in pieces) > 1
    resample = f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:vsbmc=1" if slow else f"fps={fps}"
    return f"setpts='({expr})/TB',{resample}"


def atempo(rate: float) -> str:
    """atempo takes 0.5-100 per instance: chain halves for slower rates."""
    out = []
    while rate < 0.5:
        out.append("atempo=0.5")
        rate /= 0.5
    return ",".join([*out, f"atempo={rate:.6f}"])


def peak_time(path: Path) -> float:
    import quiet
    a = quiet.pcm(str(path), None)
    return max(range(len(a)), key=lambda i: abs(a[i])) / quiet.SR if len(a) else 0.0


# ---------------------------------------------------------------- conform

def conform(srcs: list[str], out_dir: Path, fps: int, cover: str | None, channel: int | None,
            stabilize: bool = False, denoise: str | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    filters = run(["ffmpeg", "-hide_banner", "-filters"])
    mapping = {}
    for s in srcs:
        src = Path(s)
        p = probe(src)
        dst = out_dir / (src.stem + ".mp4")
        w, h = p["size"]
        crop = ""
        if cover:
            tw, th = (int(x) for x in cover.split("x"))
            k = max(tw / w, th / h)
            w, h = round(w * k / 2) * 2, round(h * k / 2) * 2
            crop = f"crop={tw}:{th},"
        fix = {"light": "hqdn3d=1.5:1.5:6:6,", "strong": "nlmeans=s=2.5:p=7:r=9,"}.get(denoise or "", "")
        if stabilize:
            # deshake fills the edges it moves in from; a 4% punch-in crops them back off
            fix += f"deshake=rx=48:ry=48:edge=mirror,scale={round(w * 1.04 / 2) * 2}:-2,crop={w}:{h},"
        tail = f"{fix}{crop}fps={fps},format=yuv420p,setsar=1,{TAGS}"
        pre: list[str] = []
        if p["hdr"] and platform.system() == "Darwin":
            # VideoToolbox tone-maps HLG/PQ when scale_vt changes the colour tags; rotate on the GPU too.
            tr = {270: "transpose_vt=dir=clock,", 90: "transpose_vt=dir=cclock,",
                  180: "transpose_vt=dir=clock,transpose_vt=dir=clock,"}.get(p["rotation"], "")
            pre = ["-noautorotate", "-hwaccel", "videotoolbox", "-hwaccel_output_format", "videotoolbox_vld"]
            vf = (f"{tr}scale_vt=w={w}:h={h}:color_matrix=bt709:color_primaries=bt709:"
                  f"color_transfer=bt709,hwdownload,format=p010le,{tail}")
        elif p["hdr"] and " zscale " in filters:
            vf = (f"zscale=w={w}:h={h}:t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
                  f"tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,{tail}")
        elif p["hdr"]:
            sys.exit(f"edl: {src} is HDR and this ffmpeg has neither VideoToolbox (macOS) nor zscale: "
                     "install an ffmpeg built with libzimg")
        else:
            vf = f"scale={w}:{h}:flags=lanczos:{matrix_in(p)}{CONVERT},{tail}"
        af = ["-af", f"pan=mono|c0=c{channel}"] if channel is not None and p["audio"] else []
        audio = ["-c:a", "aac", "-b:a", "320k", "-ar", "48000", *af] if p["audio"] else ["-an"]
        run(["ffmpeg", "-y", "-v", "error", *pre, "-i", str(src), "-vf", vf, "-c:v", "libx264",
             "-preset", "medium", "-crf", "14", "-g", str(fps // 2), "-pix_fmt", "yuv420p",
             "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
             *audio, "-movflags", "+faststart", str(dst)])
        mapping[src.stem] = str(dst)
        print(f"{src} -> {dst}{' (tone-mapped)' if p['hdr'] else ''}")
    print(json.dumps(mapping, indent=1))


# ---------------------------------------------------------------- shared timeline math

class Plan:
    def __init__(self, path: Path):
        self.path = path
        self.edl = json.loads(path.read_text())
        self.fps = int(self.edl.get("fps", 30))
        self.size = tuple(self.edl.get("size", [1080, 1920]))
        self.limits = {**LIMITS, **self.edl.get("limits", {})}
        self.sources = {k: ({"path": v} if isinstance(v, str) else v) for k, v in self.edl["sources"].items()}
        self.info = {k: probe(self.file(k)) for k in self.sources if self.file(k).exists()}
        self.segs = self.edl["segments"]
        self.cutaways = self.edl.get("cutaways", [])
        for item in [*self.segs, *self.cutaways]:
            if msg := bad_speed(item.get("speed", 1)):
                sys.exit(f"edl: {item['src']} {item['in']}-{item['out']}: speed {msg}")
            for key in (item["src"], item.get("audio_src")):
                if key and key not in self.sources:
                    sys.exit(f"edl: no source {key!r} (sources: {', '.join(self.sources)})")

    def local(self, key: str, t: float) -> float:
        """A shared-clock time in a source's own clock (sync.py measures each source's offset)."""
        return t - float(self.sources[key].get("offset", 0))

    def file(self, key: str) -> Path:
        return (self.path.parent / self.sources[key]["path"]).resolve()

    def f(self, t: float) -> int:
        return round(t * self.fps)

    def span(self, item: dict) -> tuple[int, list | None]:
        """Timeline frames a segment or cutaway fills, and its speed pieces (None at 1x)."""
        src = self.f(item["out"]) - self.f(item["in"])  # an offset moves in and out alike
        pieces = speed_pieces(item, src / self.fps)
        return (src if pieces is None else round(warp(pieces, src / self.fps) * self.fps)), pieces

    def timeline(self) -> list[dict]:
        """Per segment: source frames in/out, timeline frames dur and start, transition handles
        pre/post, speed pieces, and a0/a1: where its sound starts and ends relative to its picture
        (frames; a split edit moves them)."""
        rows, t = [], 0
        for k, s in enumerate(self.segs):
            i, o = self.f(self.local(s["src"], s["in"])), self.f(self.local(s["src"], s["out"]))
            dur, pieces = self.span(s)
            rows.append({"k": k, "in": i, "out": o, "dur": dur, "start": t, "pre": 0, "post": 0,
                         "speed": pieces, "a0": 0, "a1": 0})
            t += dur
        for k in range(1, len(rows)):
            a, b = rows[k - 1], rows[k]
            if not (a["speed"] or b["speed"]):
                a["a1"] = b["a0"] = (int(self.segs[k - 1].get("audio_trail", 0))
                                     - int(self.segs[k].get("audio_lead", 0)))
            tr = self.segs[k].get("transition")
            if not tr:
                continue
            b["want"] = int(tr.get("frames", 16)) // 2
            if a["speed"] or b["speed"]:
                continue
            src_a = self.info.get(self.segs[k - 1]["src"])
            room_a = self.f(src_a["duration"]) - a["out"] if src_a else 0
            room_b = b["in"]
            half = min(int(tr.get("frames", 16)) // 2, room_a, room_b, a["dur"] // 2, b["dur"] // 2)
            a["post"], b["pre"] = half, half
        return rows

    def tone(self) -> Path | None:
        t = self.edl.get("room_tone")
        return (self.path.parent / (t if isinstance(t, str) else t["path"])).resolve() if t else None

    def sfx(self) -> list[dict]:
        """Each sound effect with the timeline second its start lands on."""
        rows, words, out = self.timeline(), None, []
        for c in self.edl.get("sfx", []):
            at = c.get("at", 0)
            if isinstance(at, dict) and "seg" in at:
                t = rows[at["seg"]]["start"] / self.fps
            elif isinstance(at, dict) and "word" in at:
                words = words or timeline_words(self)
                t = words[at["word"]]["start"]
            elif isinstance(at, dict) and "cutaway" in at:
                t = float(self.cutaways[at["cutaway"]]["at"])
            elif isinstance(at, dict):
                raise KeyError(f"sfx anchor {at} is not seg, word or cutaway")
            else:
                t = float(at)
            path = (self.path.parent / c["path"]).resolve()
            lead = peak_time(path) if c.get("align") == "peak" and path.exists() else 0.0
            out.append({**c, "file": path, "t": t + float(c.get("offset", 0)) - lead})
        return out


# ---------------------------------------------------------------- check

def check(plan: Plan) -> int:
    lim, fps = plan.limits, plan.fps
    errs, warns = [], []
    for k, s in plan.sources.items():
        if not plan.file(k).exists():
            errs.append(f"source {k}: {plan.file(k)} not found")
    rows = plan.timeline()
    total = sum(r["dur"] for r in rows)
    for r, s in zip(rows, plan.segs):
        tag = f"segment {r['k']} ({s['src']} {s['in']:.2f}-{s['out']:.2f})"
        info = plan.info.get(s["src"])
        if r["dur"] <= 0:
            errs.append(f"{tag}: out is not after in")
        if info and r["out"] > plan.f(info["duration"]) + 1:
            errs.append(f"{tag}: out is past the source's end ({info['duration']:.2f}s)")
        if r["in"] < 0:
            errs.append(f"{tag}: starts before its source does (check the source's offset)")
        if s.get("audio_src") and plan.info.get(s["audio_src"]) and not plan.info[s["audio_src"]]["audio"]:
            errs.append(f"{tag}: audio_src {s['audio_src']} has no sound")
        if r.get("want") and r["pre"] < r["want"]:
            warns.append(f"{tag}: transition wants {2 * r['want']} frames, has handles for {2 * r['pre']}")
        kind = (s.get("transition") or {}).get("type", "fade")
        if s.get("transition") and kind not in XFADE:
            errs.append(f"{tag}: transition {kind!r} is not an ffmpeg xfade type "
                        "(fade, dissolve, fadeblack, smoothleft, ...; `ffmpeg -h filter=xfade` lists all)")
        if (s.get("audio_lead") or s.get("audio_trail")) and r["speed"]:
            warns.append(f"{tag}: a sped segment takes no split edit; audio_lead/audio_trail ignored")
        if info and r["in"] + r["a0"] < 0:
            errs.append(f"{tag}: its sound starts {-r['a0']} frames early but the source has {r['in']} before in")
        if info and r["out"] + r["a1"] > plan.f(info["duration"]):
            errs.append(f"{tag}: its sound runs {r['a1']} frames on, past the source's end")
        if max(abs(r["a0"]), abs(r["a1"])) >= r["dur"] > 0:
            errs.append(f"{tag}: a split edit as long as the segment")
    for a, b, sa, sb in zip(rows, rows[1:], plan.segs, plan.segs[1:]):
        if sa["src"] == sb["src"] and not sb.get("transition"):
            gap = sb["in"] - sa["out"]
            if 0 <= gap < lim["min_save"]:
                warns.append(f"cut at {b['start'] / fps:.2f}s saves only {gap:.2f}s: join the segments "
                             "so the pause plays")
            elif gap < 0 and sb["out"] > sa["in"]:
                warns.append(f"segment {b['k']} replays {-gap:.2f}s of segment {a['k']}")
    # shots: every visible change is a cut, a transition midpoint or a cutaway edge
    changes = {r["start"] for r in rows[1:]}
    lo_c, hi_c = lim["cutaway"]
    for c in plan.cutaways:
        at, d = plan.f(c["at"]), plan.span(c)[0]
        overlay = plan.info.get(c["src"], {}).get("alpha", False)
        if not overlay:
            changes |= {at, at + d}
        if not overlay and not lo_c * fps <= d <= hi_c * fps:
            warns.append(f"cutaway {c['src']} at {c['at']:.2f}s runs {d / fps:.2f}s (want {lo_c}-{hi_c}s)")
        if at + d > total:
            errs.append(f"cutaway {c['src']} at {c['at']:.2f}s runs past the end")
        if c["src"] in plan.info and plan.local(c["src"], c["out"]) > plan.info[c["src"]]["duration"] + 1 / fps:
            errs.append(f"cutaway {c['src']}: out is past the source's end")
    marks = sorted({0, total, *changes})
    for a, b in zip(marks, marks[1:]):
        if 0 < b - a < lim["min_shot"] * fps:
            warns.append(f"shot {a / fps:.2f}-{b / fps:.2f}s lasts {(b - a) / fps:.2f}s (under "
                         f"{lim['min_shot']}s): hold it, join it, or drop the change")
    busy = [m for m in marks[1:-1] if sum(1 for x in marks[1:-1] if m <= x < m + 3 * fps) > 1]
    if busy:
        warns.append(f"{len(busy)} spots change more than once in 3s, first at {busy[0] / fps:.2f}s")
    if total > lim["max_len"] * fps:
        warns.append(f"runs {total / fps:.1f}s, over max_len {lim['max_len']}s")
    if plan.tone() and not plan.tone().exists():
        errs.append(f"room_tone {plan.tone()} not found")
    try:
        for c in plan.sfx():
            if not c["file"].exists():
                errs.append(f"sfx {c['path']} not found")
            elif not 0 <= c["t"] < total / fps:
                warns.append(f"sfx {c['path']} starts at {c['t']:.2f}s, outside the {total / fps:.2f}s timeline")
    except (KeyError, IndexError) as e:
        errs.append(f"sfx anchor: {e}")
    print(f"{len(rows)} segments, {len(plan.cutaways)} cutaways, {total / fps:.2f}s ({total} frames)")
    for e in errs:
        print(f"ERROR {e}")
    for w in warns:
        print(f"warn  {w}")
    return 1 if errs else 0


# ---------------------------------------------------------------- words

def timeline_words(plan: Plan) -> list[dict]:
    """Words where they are heard: a split edit moves a segment's sound, speed retimes it, and a
    muted or ramped segment says nothing."""
    import _words

    cache: dict[str, list[dict]] = {}
    out = []
    for r, s in zip(plan.timeline(), plan.segs):
        key = s["src"] if r["speed"] else s.get("audio_src", s["src"])
        wf = plan.sources[key].get("words")
        if not wf or s.get("mute") or ramped(s):
            continue
        if key not in cache:
            cache[key] = _words.load(plan.path.parent / wf)
        fps = plan.fps
        a_in = plan.f(plan.local(key, s["in"]))
        lo, hi = (a_in + r["a0"]) / fps, (a_in + r["out"] - r["in"] + r["a1"]) / fps
        t0 = (r["start"] + r["a0"]) / fps
        rate = float(s.get("speed", 1))
        for w in cache[key]:
            mid = (w["start"] + w["end"]) / 2
            if lo <= mid < hi:
                out.append({"text": w["text"], "seg": r["k"],
                            "start": round(t0 + (max(w["start"], lo) - lo) / rate, 3),
                            "end": round(t0 + (min(w["end"], hi) - lo) / rate, 3)})
    return out


# ---------------------------------------------------------------- render

def render(plan: Plan, dst: Path, draft: bool) -> None:
    fps, (W, H) = plan.fps, plan.size
    rows = plan.timeline()
    for k, info in plan.info.items():
        if info["hdr"]:
            sys.exit(f"edl: source {k} is HDR: run `edl.py conform` first")
    args: list[str] = []
    graph: list[str] = []
    tone, tone_cfg = plan.tone(), plan.edl.get("room_tone")
    stereo = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"

    def add(*opts: str) -> int:
        args.extend(opts)
        return args.count("-i") - 1

    def frame_chain(item: dict, pix: str = "yuv420p", timing: str = "") -> str:
        c = item.get("crop")
        z = float(item.get("zoom", 1.0))
        crop = f"crop=iw*{c[2]}:ih*{c[3]}:iw*{c[0]}:ih*{c[1]}," if c else ""
        # a grade (match.py, grade.md) works in RGB on the BT.709-converted frame
        grade = f"format=gbrp,{item['grade']}," if item.get("grade") else ""
        return (f"{timing or f'fps={fps}'},{crop}scale={round(W * z)}:{round(H * z)}:"
                f"force_original_aspect_ratio=increase:flags=lanczos:{matrix_in(plan.info[item['src']])}"
                f"{CONVERT},crop={W}:{H},setsar=1,{grade}format={pix}")

    def shape(seg: dict, d: float) -> str:
        fade = float(seg.get("afade", 0.008))
        return (f"{stereo},volume={float(seg.get('gain_db', 0))}dB,afade=t=in:d={fade},"
                f"afade=t=out:st={max(d - fade, 0):.4f}:d={fade}")

    def silence(k: int, d: float) -> None:
        if tone:
            n = add("-stream_loop", "-1", "-i", str(tone))
            g = float(tone_cfg.get("gain_db", 0)) if isinstance(tone_cfg, dict) else 0.0
            graph.append(f"[{n}:a]atrim=start={0.7 * k:.3f}:duration={d:.4f},asetpts=PTS-STARTPTS,{stereo},"
                         f"volume={g}dB,afade=t=in:d=0.03,afade=t=out:st={max(d - 0.03, 0):.4f}:d=0.03[a{k}]")
        else:
            graph.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={d:.4f},"
                         f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{k}]")

    for r, s in zip(rows, plan.segs):
        k, d = r["k"], r["dur"] / fps
        src = str(plan.file(s["src"]))
        sound = plan.info[s["src"]]["audio"] and not s.get("mute")
        if r["speed"]:
            span = (r["out"] - r["in"]) / fps
            n = add("-ss", f"{r['in'] / fps:.4f}", "-t", f"{span + 0.5:.4f}", "-i", src)
            graph.append(f"[{n}:v]{frame_chain(s, timing=retime(r['speed'], fps, bool(s.get('smooth'))))},"
                         f"trim=end_frame={r['dur']},setpts=PTS-STARTPTS,settb=AVTB[v{k}]")
            if sound and not ramped(s):
                graph.append(f"[{n}:a]atrim=duration={span:.4f},asetpts=PTS-STARTPTS,"
                             f"{atempo(float(s['speed']))},apad,atrim=duration={d:.4f},{shape(s, d)}[a{k}]")
            else:
                silence(k, d)
            continue
        # read enough source for the transition handles and the split edit, whichever reaches further
        lead, tail = max(r["pre"], -r["a0"], 0), max(r["post"], r["a1"], 0)
        if r["in"] < lead:
            sys.exit(f"edl: segment {k} needs {lead} frames before its in point: run `edl.py check`")
        n = add("-ss", f"{(r['in'] - lead) / fps:.4f}", "-t", f"{(lead + r['dur'] + tail) / fps + 0.5:.4f}",
                "-i", src)
        graph.append(f"[{n}:v]{frame_chain(s)},trim=start_frame={lead - r['pre']}:"
                     f"end_frame={lead + r['dur'] + r['post']},setpts=PTS-STARTPTS,settb=AVTB[v{k}]")
        ad = (r["dur"] - r["a0"] + r["a1"]) / fps
        if s.get("audio_src") and not s.get("mute"):
            # multicam: this angle's picture over another source's sound, same moment in the shared clock
            a_in = plan.f(plan.local(s["audio_src"], s["in"])) + r["a0"]
            m = add("-ss", f"{a_in / fps:.4f}", "-t", f"{ad + 0.5:.4f}", "-i", str(plan.file(s["audio_src"])))
            graph.append(f"[{m}:a]atrim=duration={ad:.4f},asetpts=PTS-STARTPTS,{shape(s, ad)}[a{k}]")
        elif sound:
            graph.append(f"[{n}:a]atrim=start={(lead + r['a0']) / fps:.4f}:duration={ad:.4f},"
                         f"asetpts=PTS-STARTPTS,{shape(s, ad)}[a{k}]")
        else:
            silence(k, ad)
    acc, acc_len = "v0", rows[0]["dur"] + rows[0]["post"]
    for r, s in zip(rows[1:], plan.segs[1:]):
        k = r["k"]
        if r["pre"]:
            dur = 2 * r["pre"]
            kind = s["transition"].get("type", "fade")
            graph.append(f"[{acc}][v{k}]xfade=transition={kind}:duration={dur / fps:.4f}:"
                         f"offset={(acc_len - dur) / fps:.4f}[x{k}]")
            acc_len += r["pre"] + r["dur"] + r["post"] - dur
        else:
            graph.append(f"[{acc}][v{k}]concat=n=2:v=1:a=0[x{k}]")
            acc_len += r["dur"] + r["post"]
        acc = f"x{k}"
    cues = plan.sfx()
    graph.append("".join(f"[a{r['k']}]" for r in rows) + f"concat=n={len(rows)}:v=0:a=1[{'adlg' if cues else 'aout'}]")
    for j, c in enumerate(cues):
        n = add("-i", str(c["file"]))
        graph.append(f"[{n}:a]atrim=start={max(-c['t'], 0):.4f},asetpts=PTS-STARTPTS,{stereo},"
                     f"volume={float(c.get('gain_db', SFX_GAIN_DB))}dB,adelay={round(max(c['t'], 0) * 1000)}:all=1[s{j}]")
    if cues:
        graph.append("[adlg]" + "".join(f"[s{j}]" for j in range(len(cues)))
                     + f"amix=inputs={len(cues) + 1}:normalize=0:duration=first:dropout_transition=0[aout]")
    for j, c in enumerate(plan.cutaways):
        i0, at = plan.f(plan.local(c["src"], c["in"])), plan.f(c["at"])
        d, pieces = plan.span(c)
        fade = int(c.get("fade", 0))
        alpha = (f",fade=t=in:d={fade / fps:.4f}:alpha=1,"
                 f"fade=t=out:st={(d - fade) / fps:.4f}:d={fade / fps:.4f}:alpha=1") if fade else ""
        n = add("-ss", f"{i0 / fps:.4f}", "-t", f"{(plan.f(plan.local(c['src'], c['out'])) - i0) / fps + 0.5:.4f}",
                "-i", str(plan.file(c["src"])))
        timing = retime(pieces, fps, bool(c.get("smooth"))) if pieces else ""
        # yuva420p keeps a cutaway's own alpha (a ProRes 4444 title) as well as the fade's.
        graph.append(f"[{n}:v]{frame_chain(c, 'yuva420p', timing)},trim=end_frame={d}{alpha},"
                     f"setpts=PTS-STARTPTS+{at / fps:.4f}/TB[c{j}]")
        graph.append(f"[{acc}][c{j}]overlay=eof_action=pass:enable='between(t,{at / fps:.4f},"
                     f"{(at + d) / fps - 0.001:.4f})'[o{j}]")
        acc = f"o{j}"
    graph.append(f"[{acc}]format=yuv420p,{TAGS}[vout]")
    quality = ["-preset", "veryfast", "-crf", "23"] if draft else ["-preset", "slow", "-crf", "15"]
    total = sum(r["dur"] for r in rows)
    run(["ffmpeg", "-y", "-v", "error", *args, "-filter_complex", ";".join(graph),
         "-map", "[vout]", "-map", "[aout]", "-frames:v", str(total), "-r", str(fps),
         "-c:v", "libx264", *quality, "-pix_fmt", "yuv420p", "-color_primaries", "bt709",
         "-color_trc", "bt709", "-colorspace", "bt709", "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
         "-movflags", "+faststart", str(dst)])
    print(f"{dst}: {total} frames, {total / fps:.2f}s")


# ---------------------------------------------------------------- qa

def moov_first(path: Path) -> bool:
    """True when the moov atom comes before mdat (faststart), read from the top-level atoms."""
    with open(path, "rb") as fh:
        while len(head := fh.read(8)) == 8:
            size, kind = int.from_bytes(head[:4], "big"), head[4:8]
            if kind in (b"moov", b"mdat"):
                return kind == b"moov"
            if size == 1:
                size = int.from_bytes(fh.read(8), "big") - 8
            elif size == 0:
                return False
            fh.seek(size - 8, 1)
    return False


# Text on screen, read by ocr.swift. Watermarks and personal details fail QA; the rest is a warning.
# A watermark reads as a short line on its own ("TikTok", "@handle", "Made with CapCut"); a sentence
# that names an app ("TikTok made me buy it") is a notice, not a watermark.
WATERMARK = re.compile(r"^\W*(tik ?tok|capcut|inshot|kinemaster|splice|vn video editor|"
                       r"made with (capcut|inshot|kinemaster|splice|vn))\W*$", re.I)
PRIVATE = [("an email address", re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.I)),
           ("a phone number", re.compile(r"(\+?\d{1,2}[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}\b")),
           ("a street address", re.compile(r"\b\d{1,5} [a-z0-9 .]{2,30}\b(st|street|ave|avenue|rd|road|dr|drive|ln|"
                                           r"lane|blvd|way|ct|court|pl|place|close|crescent)\b\.?", re.I)),
           ("a postcode", re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b")),
           ("a tracking number", re.compile(r"\b1Z[0-9A-Z]{16}\b|\b\d{12,22}\b"))]
NOTICE = [("a price", re.compile(r"[$£€¥]\s?\d|\b\d+[.,]\d{2}\s?(usd|eur|gbp)\b|\bprice\b", re.I),
           "affiliate programmes (Amazon Associates) forbid prices that are not live"),
          ("a URL", re.compile(r"\b(https?://|www\.)\S+|\b[a-z0-9-]{2,}\.(com|net|org|io|co|shop|store|ly|link|me)\b",
                               re.I), "on-screen links are not clickable; say where the link is instead"),
          ("an app name", re.compile(r"\b(tik ?tok|capcut|instagram|reels|youtube|shorts|snapchat|facebook)\b", re.I),
           "fine when spoken to the viewer; a leftover watermark is not")]


def screen_text(out: Path, fps: int, allow: list[str]) -> tuple[list[str], list[str]]:
    """Errors and warnings from the text on screen every half second (macOS: ocr.swift)."""
    if not (HERE / "ocr.swift").exists():
        return [], ["on-screen text not read: scripts/ocr.swift is missing"]
    from _swift import tool
    rows = json.loads(run([str(tool("ocr")), str(out), str(max(fps // 2, 1)), str(fps)]))
    errs, warns, seen = [], [], set()
    for frame, boxes in rows:
        for *_, conf, text in boxes:
            key = text.lower().strip()
            key = (key, conf >= 0.9)  # a line read unsure first and sure later is reported again
            if conf < 0.5 or key in seen or any(x.lower() in key[0] for x in allow):
                continue
            seen.add(key)
            at = f"{frame / fps:.1f}s {text[:40]!r}"
            wm = WATERMARK.search(text)
            hit = None if wm else next((name for name, rx in PRIVATE if rx.search(text)), None)
            if text.startswith("barcode:"):
                warns.append(f"{frame / fps:.1f}s a barcode or QR code: blur it if it is a shipping label (redact.py)")
            elif wm or hit:
                what, fix = (("another app's watermark or credit", "platforms rank reposts with one lower") if wm
                             else (f"{hit} on screen", "blur it (redact.py)"))
                if conf >= 0.9:
                    errs.append(f"{at}: {what}: {fix}")
                else:  # Vision reads print it cannot make out (upside down, curved) as garbage at 0.5
                    warns.append(f"{at}: possibly {what} (OCR unsure): look at the frame")
            elif note := next(((name, why) for name, rx, why in NOTICE if rx.search(text)), None):
                warns.append(f"{at}: {note[0]} on screen: {note[1]}")
    return errs, warns


def levels(out: Path, rows: list[dict], plan: Plan) -> list[str]:
    """Notes from signalstats on a small copy: clipped highlights, crushed shadows, shots whose
    brightness or colour jumps from the shot before (a take to match)."""
    meta = run(["ffmpeg", "-v", "error", "-i", str(out), "-vf", "scale=270:480,signalstats,metadata=print:file=-",
                "-an", "-f", "null", "-"])
    stats, cur = [], {}
    for line in meta.splitlines():
        if line.startswith("frame:"):
            if cur:
                stats.append(cur)
            cur = {}
        elif "=" in line and "signalstats." in line:
            k, v = line.split("signalstats.", 1)[1].split("=", 1)
            cur[k] = float(v)
    if cur:
        stats.append(cur)
    if not stats:
        return []
    notes = []
    clip = sum(1 for f in stats if f.get("YHIGH", 0) >= 234) / len(stats)
    crush = sum(1 for f in stats if f.get("YLOW", 255) <= 17) / len(stats)
    if clip > 0.2:
        notes.append(f"highlights clip (a tenth of the picture at white) in {clip:.0%} of frames: lower exposure")
    if crush > 0.2:
        notes.append(f"shadows crush (a tenth of the picture at black) in {crush:.0%} of frames: lift the blacks")
    means = []
    for r in rows:
        part = stats[r["start"]:r["start"] + r["dur"]] or stats[-1:]
        means.append({k: sum(f.get(k, 0) for f in part) / len(part) for k in ("YAVG", "UAVG", "VAVG")})
    for r, a, b, sa, sb in zip(rows[1:], means, means[1:], plan.segs, plan.segs[1:]):
        if sa["src"] == sb["src"]:
            continue
        dy, du, dv = b["YAVG"] - a["YAVG"], b["UAVG"] - a["UAVG"], b["VAVG"] - a["VAVG"]
        if abs(dy) > 18 or abs(du) > 5 or abs(dv) > 5:
            how = [w for w, c in (("brighter" if dy > 0 else "darker", abs(dy) > 18),
                                  ("warmer" if dv - du > 0 else "cooler", max(abs(du), abs(dv)) > 5)) if c]
            notes.append(f"segment {r['k']} at {r['start'] / plan.fps:.2f}s is {' and '.join(how)} than the shot "
                         f"before: match.py")
    return notes


def clicks(out: Path, cuts: list[float]) -> list[str]:
    """Cuts where the sound jumps: a step between two samples within 3 ms of the cut, far steeper
    than any in the 100 ms around it. That is a pop the ear hears even when the picture is clean;
    a hard cut through a held note, or a segment with no afade, makes one."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-vn", "-ac", "1", "-ar", "48000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    pcm = array("h")
    pcm.frombytes(raw[: len(raw) // 2 * 2])
    if sys.byteorder == "big":
        pcm.byteswap()
    sr, near, wide = 48000, 144, 4800  # 3 ms, 100 ms
    notes = []
    for t in cuts:
        c = round(t * sr)
        if c - wide < 1 or c + wide > len(pcm):
            continue
        jump = max(abs(pcm[i] - pcm[i - 1]) for i in range(c - near, c + near))
        steps = sorted(abs(pcm[i] - pcm[i - 1]) for i in (*range(c - wide, c - 2 * near),
                                                          *range(c + 2 * near, c + wide)))
        usual = max(steps[int(len(steps) * 0.99)], 1)
        if jump >= 1500 and jump >= 4 * usual:  # 1500 is -27 dBFS; a tone or noise reads near 1x
            notes.append(f"{t:.2f}s: the sound pops at the cut ({jump / usual:.0f}x the usual step): "
                         "give the segment an afade, or snap the cut into quiet (quiet.py)")
    return notes


def scopes(out: Path, picks: list[int], dst: Path) -> None:
    """Picture, waveform and vectorscope side by side for each picked frame, one row each."""
    sel = "+".join(f"eq(n\\,{f})" for f in picks)
    run(["ffmpeg", "-y", "-v", "error", "-i", str(out), "-filter_complex",
         f"[0:v]select='{sel}',scale=144:256,format=yuv444p,split=3[p][w][s];"
         "[w]waveform=intensity=0.1:graticule=green:flags=numbers+dots:scale=digital,scale=256:256[wf];"
         "[s]vectorscope=mode=color3:graticule=color:flags=name,scale=256:256[vs];"
         f"[p][wf][vs]hstack=3,tile=1x{len(picks)}", "-frames:v", "1", "-update", "1", str(dst)])


def qa(plan: Plan, out: Path, sheet: Path | None, lufs: float | None, tp: float,
       scope: Path | None = None, ocr: bool = True, allow: list[str] | None = None) -> int:
    """Delivery checks on a render: picture, sync, tags, faststart, loudness; a sheet at every change."""
    fps, (W, H) = plan.fps, plan.size
    info = json.loads(run(["ffprobe", "-v", "error", "-count_frames", "-print_format", "json",
                           "-show_streams", "-show_format", str(out)]))
    streams = info["streams"]
    v = next((s for s in streams if s["codec_type"] == "video"), None)
    a = next((s for s in streams if s["codec_type"] == "audio"), None)
    rows = plan.timeline()
    total = sum(r["dur"] for r in rows)
    errs: list[str] = []
    warns: list[str] = []
    if v is None:
        sys.exit(f"edl: {out} has no video")
    want = {"codec_name": "h264", "pix_fmt": "yuv420p", "width": W, "height": H,
            "color_space": "bt709", "color_transfer": "bt709", "color_primaries": "bt709"}
    errs += [f"video {k} is {v.get(k)}, want {w}" for k, w in want.items() if v.get(k) != w]
    if Fraction(v.get("r_frame_rate", "0/1")) != fps:
        errs.append(f"frame rate {v.get('r_frame_rate')}, want {fps}")
    frames = int(v.get("nb_read_frames", 0))
    if frames != total:
        errs.append(f"{frames} frames, the EDL makes {total}")
    if a is None:
        errs.append("no audio stream")
    else:
        if (a.get("codec_name"), a.get("sample_rate"), a.get("channels")) != ("aac", "48000", 2):
            errs.append(f"audio {a.get('codec_name')} {a.get('sample_rate')} Hz {a.get('channels')} ch, "
                        "want aac 48000 Hz stereo")
        drift = abs(float(a.get("duration", 0)) - frames / fps)
        if drift > 0.05:
            errs.append(f"audio runs {drift:.3f}s off the picture")
    if not moov_first(out):
        errs.append("moov is not at the front: encode with -movflags +faststart")
    loud = ""
    if lufs is not None and a is not None:
        import master
        m = master.measure(str(out))
        loud = f", {m['lufs']:.1f} LUFS, {m['true_peak']:.1f} dBTP"
        if abs(m["lufs"] - lufs) > 0.5:
            errs.append(f"loudness {m['lufs']:.1f} LUFS, want {lufs} (master.py mix)")
        if m["true_peak"] > tp + 0.1:
            errs.append(f"true peak {m['true_peak']:.1f} dBTP, over {tp}")
    mbps, mb = int(info["format"].get("bit_rate", 0)) / 1e6, out.stat().st_size / 1e6
    print(f"{out}: {W}x{H} {frames} frames {frames / fps:.2f}s, {mbps:.1f} Mbps, {mb:.0f} MB{loud}")
    if mbps > 25 or mb > 300:
        print("note: over Instagram's API upload limits (25 Mbps, 300 MB); app uploads are fine")
    # the frame just after every change (cut, transition midpoint, cutaway edge), plus first and last
    marks = {r["start"] for r in rows[1:]}
    for c in plan.cutaways:
        at = plan.f(c["at"])
        marks |= {at, at + plan.span(c)[0]}
    picks = sorted({0, frames - 1, *(min(m + 2, frames - 1) for m in marks if 0 < m < frames)})
    if sheet:
        subprocess.run([sys.executable, str(HERE / "sheet.py"), str(out), str(sheet),
                        "--frames", ",".join(map(str, picks))], check=True)
    if scope:
        scopes(out, picks[:12], scope)
    if ocr and sys.platform == "darwin":
        e, w = screen_text(out, fps, allow or [])
        errs, warns = errs + e, warns + w
    if a is not None:
        warns += clicks(out, [r["start"] / fps for r in rows[1:]])
    for n in levels(out, rows, plan):
        print(f"note  {n}")
    for w in warns:
        print(f"warn  {w}")
    for e in errs:
        print(f"ERROR {e}")
    return 1 if errs else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("conform")
    c.add_argument("srcs", nargs="+")
    c.add_argument("-o", "--out", required=True)
    c.add_argument("--fps", type=int, default=30)
    c.add_argument("--cover")
    c.add_argument("--channel", type=int)
    c.add_argument("--stabilize", action="store_true")
    c.add_argument("--denoise", choices=["light", "strong"])
    sub.add_parser("check").add_argument("edl")
    w = sub.add_parser("words")
    w.add_argument("edl")
    w.add_argument("-o", "--out")
    r = sub.add_parser("render")
    r.add_argument("edl")
    r.add_argument("out")
    r.add_argument("--draft", action="store_true")
    q = sub.add_parser("qa")
    q.add_argument("edl")
    q.add_argument("out")
    q.add_argument("--sheet")
    q.add_argument("--lufs", type=float, default=-14.0)
    q.add_argument("--no-loudness", action="store_true")
    q.add_argument("--tp", type=float, default=-1.0)
    q.add_argument("--scopes")
    q.add_argument("--no-ocr", action="store_true")
    q.add_argument("--allow", action="append", default=[])
    a = ap.parse_args()
    if a.cmd == "conform":
        conform(a.srcs, Path(a.out), a.fps, a.cover, a.channel, a.stabilize, a.denoise)
    elif a.cmd == "check":
        sys.exit(check(Plan(Path(a.edl))))
    elif a.cmd == "words":
        text = json.dumps(timeline_words(Plan(Path(a.edl))), indent=1)
        Path(a.out).write_text(text + "\n") if a.out else print(text)
    elif a.cmd == "qa":
        sys.exit(qa(Plan(Path(a.edl)), Path(a.out), Path(a.sheet) if a.sheet else None,
                    None if a.no_loudness else a.lufs, a.tp, Path(a.scopes) if a.scopes else None,
                    not a.no_ocr, a.allow))
    else:
        render(Plan(Path(a.edl)), Path(a.out), a.draft)


if __name__ == "__main__":
    main()

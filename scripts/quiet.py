#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Never cut off a word: find where the audio is really quiet and move cuts there.

Usage:
  quiet.py stretches FILE [--db auto|-30] [--min 0.04] [--channel N]
      Prints {"lufs", "threshold_db", "quiet": [[start, end], ...]} in seconds.
  quiet.py snap EDL.json [-o OUT.json] [--min-save 0.6] [--handle 0.12]
      Moves each talking segment's in and out points into the nearest quiet (outward only, so a
      kept word is never shortened), joins same-take segments whose cut would save under
      --min-save seconds, and rounds to frames. Writes the EDL with "warnings".
  quiet.py tone FILE OUT.wav [--channel N]
      The longest quiet stretch, as room tone for edl.py's "room_tone" (fills muted and sped-up
      segments so the noise floor never drops to digital silence).

A talking source is one with "words" (a transcript file) or "kind": "talk" in the EDL's
sources; B-roll and interludes are cut on action and left alone. Quiet means RMS below the
file's integrated loudness minus 14 dB for --min seconds (10 ms hops), which suits a voice
recorded close to the mic. Noise between words (bags, a recorder) stays above that: a cut that
cannot find quiet is reported, and a voice detector (silero-vad, pyannote) is the next step.
"""
import argparse
import json
import math
import re
import subprocess
import sys
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _words  # noqa: E402

HOP = 0.01  # seconds per level value
SR = 16000
PAUSE_MIN = 0.12  # a quiet stretch this long is a pause a cut can move to
SNAP_MAX = 0.6  # how far a cut may move out to reach a pause
DIP = 0.1  # with no pause in reach, the quietest frame this close


def pcm(path: str, channel: int | None) -> array:
    af = [] if channel is None else ["-af", f"pan=mono|c0=c{channel}"]
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", *af, "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True)
    if out.returncode:
        sys.exit(f"quiet: {path}: {out.stderr.decode()[-300:]}")
    a = array("h")
    a.frombytes(out.stdout[: len(out.stdout) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    return a


def levels(samples: array) -> list[float]:
    hop = int(SR * HOP)
    out = []
    for i in range(0, len(samples) - hop + 1, hop):
        chunk = samples[i:i + hop]
        ms = sum(x * x for x in chunk) / hop
        out.append(10 * math.log10(ms / 32768.0 ** 2 + 1e-12))
    return out


def lufs(path: str, channel: int | None) -> float:
    af = ("" if channel is None else f"pan=mono|c0=c{channel},") + "ebur128"
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", af,
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    return float(m[-1]) if m else -23.0


def stretches(level: list[float], db: float, min_s: float) -> list[tuple[float, float]]:
    out, start = [], None
    for i, v in enumerate([*level, 0.0]):
        if v < db and start is None:
            start = i
        elif v >= db and start is not None:
            if (i - start) * HOP >= min_s:
                out.append((round(start * HOP, 3), round(i * HOP, 3)))
            start = None
    return out


class Audio:
    def __init__(self, path: str, db: str = "auto", min_s: float = 0.04, channel: int | None = None):
        self.lufs = lufs(path, channel)
        self.db = self.lufs - 14.0 if db == "auto" else float(db)
        self.level = levels(pcm(path, channel))
        self.dur = len(self.level) * HOP
        self.quiet = stretches(self.level, self.db, min_s)
        self.pauses = [q for q in self.quiet if q[1] - q[0] >= PAUSE_MIN]

    def at(self, t: float) -> float:
        return self.level[min(max(int(t / HOP), 0), len(self.level) - 1)]


def snap_edge(t: float, edge: str, a: Audio, fps: float, handle: float, words: list[dict],
              warns: list[str], label: str) -> float:
    """The in ("lo") or out ("hi") point moved outward into quiet, on a frame."""
    fr = 1 / fps
    if (edge == "hi" and t >= a.dur - 0.02) or (edge == "lo" and t <= 0.02):
        return t
    q = next((q for q in a.quiet if q[0] - 0.01 <= t < q[1] + 0.01), None)
    if q:  # already quiet: the nearest frame inside the stretch
        ks = [k for k in range(round(t * fps) - 2, round(t * fps) + 3) if q[0] <= k * fr < q[1]]
        if ks:
            return min(ks, key=lambda k: abs(k * fr - t)) * fr

    def bare(t0: float, t1: float) -> bool:  # no whole word between: never pull in another line
        return not any(t0 <= w["start"] and w["end"] <= t1 for w in words)

    if edge == "hi":
        p = next((p for p in a.pauses if p[0] > t), None)
        if p and p[0] - t <= SNAP_MAX and bare(t, p[0]):
            return math.ceil(min(p[0] + handle, (p[0] + p[1]) / 2, a.dur) * fps) * fr
        ks = range(round(t * fps), int(min(t + DIP, a.dur) * fps) + 1)
    else:
        p = next((p for p in reversed(a.pauses) if p[1] < t), None)
        if p and t - p[1] <= SNAP_MAX and bare(p[1], t):
            return math.floor(max(p[1] - handle, (p[0] + p[1]) / 2, 0.0) * fps) * fr
        ks = range(round(t * fps), math.ceil(max(t - DIP, 0.0) * fps) - 1, -1)
    k = min(ks, key=lambda k: a.at(k * fr)) if ks else round(t * fps)
    if a.at(k * fr) >= a.db:
        warns.append(f"{label}: the {'out' if edge == 'hi' else 'in'} point at {k * fr:.2f}s lands in "
                     f"sound ({a.at(k * fr):.0f} dB, quiet is under {a.db:.0f}): run a voice detector "
                     "or pick another line boundary")
    return k * fr


def source(edl: dict, key: str) -> dict:
    s = edl["sources"][key]
    return {"path": s} if isinstance(s, str) else s


def snap(edl: dict, min_save: float, handle: float, base: Path = Path(".")) -> dict:
    """base: the EDL's folder; source and words paths are relative to it, as in edl.py."""
    fps = float(edl.get("fps", 30))
    audio: dict[str, Audio] = {}
    words: dict[str, list[dict]] = {}
    warns: list[str] = []
    segs = [dict(s) for s in edl["segments"]]
    for i, s in enumerate(segs):
        key = s.get("audio_src", s["src"])  # snap to the sound that is heard (multicam: the best mic)
        src = source(edl, key)
        if not (src.get("words") or src.get("kind") == "talk") or s.get("snap") is False:
            continue
        if key not in audio:
            audio[key] = Audio(str(base / src["path"]), channel=src.get("channel"))
            words[key] = _words.load(str(base / src["words"])) if src.get("words") else []
        a, ws = audio[key], words[key]
        # times are in the shared clock; a synced source's own clock runs `offset` seconds behind it
        off = float(src.get("offset", 0))
        label = f"segment {i} ({s['src']} {s['in']:.2f}-{s['out']:.2f})"
        s["in"] = round(snap_edge(s["in"] - off, "lo", a, fps, handle, ws, warns, label) + off, 4)
        s["out"] = round(snap_edge(s["out"] - off, "hi", a, fps, handle, ws, warns, label) + off, 4)
    joined: list[dict] = []
    for s in segs:
        prev = joined[-1] if joined else None
        gap = s["in"] - prev["out"] if prev else None
        if (prev and prev["src"] == s["src"] and not s.get("transition") and gap is not None
                and -0.001 <= gap < min_save):
            warns.append(f"joined {prev['src']} {prev['out']:.2f}-{s['in']:.2f}: that cut would save "
                         f"only {gap:.2f}s, so the pause plays")
            prev["out"] = s["out"]
            prev["why"] = "; ".join(x for x in (prev.get("why"), s.get("why")) if x)
        else:
            joined.append(s)
    return {**edl, "segments": joined, "warnings": [*edl.get("warnings", []), *warns]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("stretches")
    st.add_argument("file")
    st.add_argument("--db", default="auto")
    st.add_argument("--min", type=float, default=0.04)
    st.add_argument("--channel", type=int)
    sn = sub.add_parser("snap")
    sn.add_argument("edl")
    sn.add_argument("-o", "--out")
    sn.add_argument("--min-save", type=float, default=0.6)
    sn.add_argument("--handle", type=float, default=0.12)
    tn = sub.add_parser("tone")
    tn.add_argument("file")
    tn.add_argument("out")
    tn.add_argument("--channel", type=int)
    a = ap.parse_args()
    if a.cmd == "tone":
        au = Audio(a.file, channel=a.channel)
        best = max(au.quiet, key=lambda q: q[1] - q[0], default=(0.0, 0.0))
        lo, hi = best[0] + 0.05, best[1] - 0.05  # clear of the words either side
        if hi - lo < 0.5:
            sys.exit(f"quiet: {a.file} has no quiet stretch of 0.5 s (longest {max(hi - lo, 0):.2f} s): "
                     "record 10 s of the room with nobody talking")
        af = [] if a.channel is None else ["-af", f"pan=mono|c0=c{a.channel}"]
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{lo:.3f}", "-t", f"{hi - lo:.3f}", "-i", a.file,
                        "-vn", *af, "-ac", "2", "-ar", "48000", a.out], check=True)
        print(json.dumps({"from": round(lo, 3), "to": round(hi, 3), "seconds": round(hi - lo, 3)}))
        return
    if a.cmd == "stretches":
        au = Audio(a.file, a.db, a.min, a.channel)
        print(json.dumps({"lufs": au.lufs, "threshold_db": round(au.db, 1), "quiet": au.quiet}))
        return
    edl = json.loads(Path(a.edl).read_text())
    out = snap(edl, a.min_save, a.handle, Path(a.edl).parent)
    text = json.dumps(out, indent=1)
    if a.out:
        Path(a.out).write_text(text + "\n")
        print(f"{len(out['segments'])} segments, {len(out['warnings'])} warnings -> {a.out}")
        for w in out["warnings"]:
            print(f"  - {w}")
    else:
        print(text)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""A typed-on title and its key sounds, from one schedule so every click lands on its letter.

Usage: typeon.py "TEXT" -o work/title [--fps 30] [--cps 14] [--seed 1] [--samples DIR]

Writes work/title.json, {"text", "fps", "frames", "end", "seconds"}: frames[i] is the frame
(counted from the title's first frame) on which character i appears. Pass it to the Remotion
TypeOn component (frames={schedule.frames}). Writes work/title.wav: a key sound on each of those
frames, 48 kHz stereo, starting at the title's first frame. Add it to the EDL's "sfx" with "at"
set to the title's start on the timeline; the script prints that entry.

Rhythm: about --cps characters a second with a human unevenness (seeded, so a re-run is the same),
a beat after a space, longer after a comma and longest after a full stop or a line break ("\\n"
in TEXT). At least one frame between characters, so --cps above the frame rate saturates.

Sound: synthesized by default (a filtered tick, a low thock, a softer key release; the space bar
lower and longer). No licence needed. --samples DIR uses recorded key sounds instead (.wav, .aif,
.mp3, .m4a), one picked per key; a file with "space" in its name is used for spaces. Licensed or
CC0 recordings only (references/compliance.md).
"""
import argparse
import json
import math
import random
import subprocess
import sys
import wave
from array import array
from pathlib import Path

RATE = 48000
PAUSES = {" ": 1.35, ",": 3.0, ";": 3.0, ":": 3.0, ".": 5.0, "!": 5.0, "?": 5.0, "\n": 4.0}


def schedule(text: str, fps: int, cps: float, rng: random.Random) -> list[int]:
    frames, t = [], 0.0
    for i, ch in enumerate(text):
        f = max(round(t), frames[-1] + 1) if frames else 0
        frames.append(f)
        t = f + fps / cps * rng.uniform(0.65, 1.35) * PAUSES.get(ch, 1.0) * (0.8 if text[i + 1:i + 2] == ch else 1.0)
    return frames


def biquad_bandpass(x: list[float], f0: float, q: float) -> list[float]:
    w = 2 * math.pi * f0 / RATE
    alpha = math.sin(w) / (2 * q)
    b0, b2, a0, a1, a2 = alpha, -alpha, 1 + alpha, -2 * math.cos(w), 1 - alpha
    y, x1, x2, y1, y2 = [], 0.0, 0.0, 0.0, 0.0
    for v in x:
        out = (b0 * v + b2 * x2 - a1 * y1 - a2 * y2) / a0
        x2, x1, y2, y1 = x1, v, y1, out
        y.append(out)
    return y


def key(rng: random.Random, space: bool) -> list[float]:
    n = int(RATE * (0.16 if space else 0.11))
    tick_tau, thock_tau = (0.006, 0.028) if space else (0.0035, 0.013)
    f_tick = rng.uniform(1300, 1900) if space else rng.uniform(2400, 4200)
    f_thock = rng.uniform(105, 140) if space else rng.uniform(165, 260)
    noise = [rng.uniform(-1, 1) * math.exp(-i / (RATE * tick_tau)) for i in range(n)]
    tick = biquad_bandpass(noise, f_tick, 1.4)
    out = [tick[i] * 2.2 + 0.55 * math.sin(2 * math.pi * f_thock * i / RATE) * math.exp(-i / (RATE * thock_tau))
           for i in range(n)]
    rel = int(RATE * rng.uniform(0.045, 0.075))  # the key coming back up: the same tick, softer
    for i in range(n - rel):
        out[rel + i] += tick[i] * 0.6 * (0.35 if not space else 0.5)
    return out


def load(path: Path) -> list[float]:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
                         capture_output=True).stdout
    a = array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    return [v / 32768 for v in a]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text")
    ap.add_argument("-o", "--out", required=True, help="path without extension: writes .json and .wav")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--cps", type=float, default=14.0, help="characters a second (10-16 reads as typing)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--samples", help="folder of recorded key sounds to use instead of synthesized ones")
    a = ap.parse_args()
    text = a.text.replace("\\n", "\n")
    if not text.strip():
        sys.exit("typing: nothing to type")
    rng = random.Random(a.seed)
    frames = schedule(text, a.fps, a.cps, rng)
    keys, spaces = [], []
    if a.samples:
        files = sorted(p for p in Path(a.samples).iterdir() if p.suffix.lower() in {".wav", ".aif", ".aiff", ".mp3", ".m4a"})
        if not files:
            sys.exit(f"typing: no .wav, .aif, .mp3 or .m4a files in {a.samples}")
        spaces = [load(p) for p in files if "space" in p.name.lower()]
        keys = [load(p) for p in files if "space" not in p.name.lower()] or spaces
    end_s = frames[-1] / a.fps + 0.45
    left, right = [0.0] * int(end_s * RATE), [0.0] * int(end_s * RATE)
    for ch, f in zip(text, frames):
        if ch == "\n":
            continue
        space = ch.isspace()
        snd = rng.choice(spaces if space and spaces else keys) if keys else key(rng, space)
        gain = 10 ** (rng.uniform(-2.5, 1.0) / 20) * (0.8 if space else 1.0)
        pan = rng.uniform(-0.15, 0.15)
        start = round(f / a.fps * RATE)
        for i, v in enumerate(snd[: len(left) - start]):
            left[start + i] += v * gain * (1 - pan)
            right[start + i] += v * gain * (1 + pan)
    peak = max(max(map(abs, left)), max(map(abs, right))) or 1.0
    scale = 10 ** (-6 / 20) / peak  # peak at -6 dBFS; set the level in the mix with sfx gain_db
    pcm = array("h", (max(-32767, min(32767, round(v * scale * 32767))) for pair in zip(left, right) for v in pair))
    if sys.byteorder == "big":
        pcm.byteswap()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out.with_suffix(".wav")), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
    info = {"text": text, "fps": a.fps, "frames": frames, "end": frames[-1], "seconds": round(frames[-1] / a.fps, 2)}
    out.with_suffix(".json").write_text(json.dumps(info) + "\n")
    print(json.dumps({"json": str(out.with_suffix(".json")), "wav": str(out.with_suffix(".wav")),
                      "characters": len(text), "typed_in": info["seconds"],
                      "sfx": {"path": str(out.with_suffix(".wav")), "at": "TITLE_START_SECONDS", "gain_db": -12}}))


if __name__ == "__main__":
    main()

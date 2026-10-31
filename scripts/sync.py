#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Line up two phones (or a phone and a recorder) by their sound: the offset for an EDL source.

Usage: sync.py REF OTHER... [--window 120] [--max 30]

Prints, per OTHER, {"file", "offset", "confidence"}: offset is how many seconds OTHER's clock runs
behind REF's (REF time = OTHER time + offset). Put it on OTHER's EDL source as "offset" and write
every segment in REF's clock; switching angles is then just changing "src", and "audio_src" keeps
the better mic under every angle (edl.py).

Matches the loudness envelope (10 ms steps) of the first --window seconds by FFT
cross-correlation, searching up to --max seconds either way; a clap or a spoken count at the
start makes it certain. Confidence is the best peak over the next best one more than 0.5 s away:
under 1.5 means the two files share little sound (different rooms, music over one): check the
sheet or sync by a clap by eye.
"""
import argparse
import cmath
import json
import math
import subprocess
import sys
from array import array

RATE = 8000
HOP = 80  # samples per envelope step: 10 ms


def envelope(path: str, window: float) -> list[float]:
    out = subprocess.run(["ffmpeg", "-v", "error", "-t", str(window), "-i", path, "-vn", "-ac", "1",
                          "-ar", str(RATE), "-f", "s16le", "-"], capture_output=True)
    if out.returncode or not out.stdout:
        sys.exit(f"sync: {path} has no sound to sync by: {out.stderr.decode()[-300:]}")
    a = array("h")
    a.frombytes(out.stdout[: len(out.stdout) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    env = [math.log10(1 + sum(x * x for x in a[i:i + HOP]) / HOP) for i in range(0, len(a) - HOP + 1, HOP)]
    # onsets carry the timing; steady hum and level differences between mics do not
    d = [max(b - c, 0.0) for b, c in zip(env[1:], env)]
    m = sum(d) / max(len(d), 1)
    sd = (sum((x - m) ** 2 for x in d) / max(len(d), 1)) ** 0.5 or 1.0
    return [(x - m) / sd for x in d]


def fft(x: list[complex], inverse: bool = False) -> list[complex]:
    n = len(x)
    a = list(x)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    size = 2
    sign = 1 if inverse else -1
    while size <= n:
        w = cmath.exp(sign * 2j * math.pi / size)
        half = size // 2
        for start in range(0, n, size):
            wk = 1 + 0j
            for k in range(start, start + half):
                t = wk * a[k + half]
                a[k + half] = a[k] - t
                a[k] += t
                wk *= w
        size *= 2
    return [v / n for v in a] if inverse else a


def offset(ref: list[float], other: list[float], max_lag: int) -> tuple[float, float]:
    n = 1 << math.ceil(math.log2(len(ref) + len(other)))
    fa = fft([complex(v) for v in ref] + [0j] * (n - len(ref)))
    fb = fft([complex(v) for v in other] + [0j] * (n - len(other)))
    corr = [v.real for v in fft([x * y.conjugate() for x, y in zip(fa, fb)], inverse=True)]
    # corr[k] pairs ref[i + k] with other[i]: ref time = other time + k steps
    lags = [(k if k < n // 2 else k - n) for k in range(n)]
    pairs = [(c, lag) for c, lag in zip(corr, lags) if abs(lag) <= max_lag]
    best, lag = max(pairs)
    rival = max((c for c, x in pairs if abs(x - lag) > 50), default=0.0)
    i = lag % n
    y0, y1, y2 = corr[(i - 1) % n], corr[i], corr[(i + 1) % n]
    frac = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2) if (y0 - 2 * y1 + y2) else 0.0  # parabolic peak
    return (lag + frac) * HOP / RATE, best / rival if rival > 0 else float("inf")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref")
    ap.add_argument("others", nargs="+")
    ap.add_argument("--window", type=float, default=120.0, help="seconds of each file to compare")
    ap.add_argument("--max", type=float, default=30.0, help="largest offset to search, seconds")
    a = ap.parse_args()
    ref = envelope(a.ref, a.window)
    out = []
    for f in a.others:
        off, conf = offset(ref, envelope(f, a.window), int(a.max * RATE / HOP))
        out.append({"file": f, "offset": round(off, 3), "confidence": round(min(conf, 99.0), 2)})
        if conf < 1.5:
            print(f"sync: {f}: weak match (confidence {conf:.2f}); check by eye", file=sys.stderr)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

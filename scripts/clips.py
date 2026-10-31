#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Long video to short clips: code lists the stretches that can stand alone, the model picks.

Usage:
  clips.py WORDS.json [--min 20] [--max 60] [--gap 0.6]
      Numbered candidates: each starts at a sentence start, ends at a sentence end, runs
      --min to --max seconds, with its opening and closing words. "needs setup" marks a start
      that leans on what came before (and, but, so, this, he ...): fine if the clip's first
      seconds make the reference clear, otherwise pick another.
  clips.py WORDS.json --pick 3,7 --src talk.mp4 -o clips/ [--fps 30] [--size 1080x1920]
      An EDL per picked clip (clips/clip-3.json ...): one segment on the source with the words
      file attached. Run quiet.py snap on each (it finds the true pauses), then cut, drop lines
      and reframe (reframe.py) as for any video.

Sentences end at . ? ! or at a pause of --gap seconds. Choose clips that open on a claim, a
question or a number and close on a payoff; the list is ordered by time, not ranked.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _words  # noqa: E402

LEANS = {"and", "but", "so", "because", "or", "which", "that", "this", "these", "those", "it", "he", "she",
         "they", "then", "also", "anyway", "plus"}


def sentences(words: list[dict], gap: float) -> list[tuple[int, int]]:
    out, start = [], 0
    for i, w in enumerate(words):
        nxt = words[i + 1]["start"] if i + 1 < len(words) else None
        if w["text"].rstrip('"\'').endswith((".", "?", "!")) or nxt is None or nxt - w["end"] >= gap:
            out.append((start, i))
            start = i + 1
    return out


def candidates(words: list[dict], lo: float, hi: float, gap: float) -> list[dict]:
    sents = sentences(words, gap)
    out = []
    for a, (s0, _) in enumerate(sents):
        fits = [e1 for _, e1 in sents[a:] if lo <= words[e1]["end"] - words[s0]["start"] <= hi]
        for e1 in sorted({fits[0], fits[-1]} if fits else set()):
            first = words[s0]["text"].lower().strip(",.!?\"'")
            out.append({"start": round(words[s0]["start"], 2), "end": round(words[e1]["end"], 2),
                        "seconds": round(words[e1]["end"] - words[s0]["start"], 1),
                        "opens": " ".join(w["text"] for w in words[s0:s0 + 12]),
                        "closes": " ".join(w["text"] for w in words[max(e1 - 7, s0):e1 + 1]),
                        "needs_setup": first in LEANS})
    for i, c in enumerate(out):
        c["id"] = i
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words")
    ap.add_argument("--min", type=float, default=20.0)
    ap.add_argument("--max", type=float, default=60.0)
    ap.add_argument("--gap", type=float, default=0.6)
    ap.add_argument("--pick")
    ap.add_argument("--src")
    ap.add_argument("-o", "--out")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--size", default="1080x1920")
    a = ap.parse_args()
    words = _words.load(a.words)
    cands = candidates(words, a.min, a.max, a.gap)
    if not a.pick:
        for c in cands:
            flag = "  [needs setup]" if c["needs_setup"] else ""
            print(f"{c['id']:>3}  {c['start']:7.2f}-{c['end']:7.2f}  {c['seconds']:5.1f}s{flag}\n"
                  f"     opens:  {c['opens']}\n     closes: ...{c['closes']}")
        if not cands:
            print(f"no stretch of {a.min:g}-{a.max:g}s between sentence ends; widen --min/--max or --gap")
        return
    if not (a.src and a.out):
        sys.exit("clips: --pick needs --src and -o")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    w, h = (int(x) for x in a.size.split("x"))
    for i in (int(x) for x in a.pick.split(",")):
        c = cands[i]
        rel = lambda p: os.path.relpath(Path(p).resolve(), out.resolve())  # noqa: E731
        edl = {"fps": a.fps, "size": [w, h],
               "sources": {"t1": {"path": rel(a.src), "words": rel(a.words)}},
               "segments": [{"src": "t1", "in": max(c["start"] - 0.1, 0), "out": c["end"] + 0.15,
                             "why": f"clip {i}: {c['opens'][:50]}"}],
               "cutaways": []}
        (out / f"clip-{i}.json").write_text(json.dumps(edl, indent=1) + "\n")
        print(out / f"clip-{i}.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Phrase captions from word timings: a clause at a time, up to two lines, broken where a reader
would break them, shown just before each phrase is heard.

Usage: captions.py WORDS.json -f srt|vtt|ass|json|remotion [-o OUT] [options]

WORDS.json is any transcriber's output (see _words.py) in timeline time; `edl.py words` makes it
for a cut. Words may carry "seg" (the timeline segment): a caption never spans a cut.

  --max-chars 32     per caption (two lines of a bold sans at ~76 px on 1080 wide)
  --max-words 7      per caption
  --lead 0.15        seconds a caption shows before its first word is heard (0.1-0.2)
  --plain            drop trailing , . ; : from words (short-form look); keep ? !
  --case lower|upper keep as spoken by default
  --fps 30           json adds startFrame/endFrame at this rate, to each phrase and to each of its
                     words (for PhraseCaptions' word highlights)
  --size 1080x1920 --font "TikTok Sans" --font-size 76 --bottom 1500   (ass only: frame, font, and
                     the y of the captions' bottom edge, clear of the platform buttons)
remotion writes Caption[] (one per word) for @remotion/captions createTikTokStyleCaptions.
"""
import argparse
import itertools
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _words  # noqa: E402

GAP_BREAK = 0.5  # a pause this long starts a new phrase
JOIN = 1.0  # a lone word joins the phrase next to it across a pause shorter than this
SHORT = 12  # a caption under this many characters reads as an orphan
HOLD = 0.6  # a gap shorter than this to the next caption is bridged, so text doesn't flicker

# A caption never ends on a word that leads into the next ("a / million bucks"), parts a verb
# from its particle ("check it / out"), and likes to start on a clause opener.
LEADS = frozenset(
    "a an the my your his her its our their this that these those of to in on at for with from by "
    "about into like and or but so if because i we they he she is are was were am be been will "
    "would can could should do does did it's i'm i've you're we're they're that's there's just very "
    "really too super not".split())
PARTICLES = frozenset({"off", "out", "up", "down", "over", "back"})
STARTS = frozenset(
    "and but so or because if when then i we they he she it's i'm i've you're we're they're that's "
    "there's".split())


def bare(w: dict) -> str:
    return re.sub(r"[^\w'’-]", "", w["text"]).lower().replace("’", "'")


def phrases(words: list[dict]) -> list[list[dict]]:
    """Runs between natural breaks (punctuation, a cut, a pause); a leading or lone word moves
    to its neighbour unless that crosses a sentence end or a long pause."""
    runs: list[list[dict]] = []
    for i, w in enumerate(words):
        p = words[i - 1] if i else None
        if (p is None or re.search(r"[,.;:!?]$", p["text"]) or w.get("seg", 0) != p.get("seg", 0)
                or w["start"] - p["end"] > GAP_BREAK):
            runs.append([])
        runs[-1].append(w)

    def near(a: dict, b: dict) -> bool:
        return (a.get("seg", 0) == b.get("seg", 0) and b["start"] - a["end"] < JOIN
                and not re.search(r"[.!?]$", a["text"]))

    out: list[list[dict]] = []
    for k, run in enumerate(runs):
        nxt = runs[k + 1] if k + 1 < len(runs) else None
        if nxt and (len(run) == 1 or bare(run[-1]) in LEADS) and near(run[-1], nxt[0]):
            nxt.insert(0, run.pop())
        if len(run) == 1 and out and near(out[-1][-1], run[0]):
            out[-1] += run
        elif run:
            out.append(run)
    return out


def split(run: list[dict], max_chars: int, max_words: int) -> list[list[dict]]:
    """The cheapest way to cut a run into captions: each costs 1, a short one more, a pause or a
    clause opener makes a break cheaper, a leading word or a particle makes it dear."""
    said = [bare(w) for w in run]
    at = [0, *itertools.accumulate(len(w["text"]) + 1 for w in run)]

    def after(i: int) -> float:
        pause = min(max(run[i + 1]["start"] - run[i]["end"], 0.0), GAP_BREAK)
        return (3.0 * (said[i] in LEADS or said[i][:1].isdigit()) + 2.0 * (said[i + 1] in PARTICLES)
                - 0.5 * (said[i + 1] in STARTS) - 3.0 * pause)

    cost = [0.0] + [math.inf] * len(run)
    back = [0] * (len(run) + 1)
    for b in range(1, len(run) + 1):
        for a in range(max(0, b - max_words), b):
            chars = at[b] - at[a] - 1
            if chars > max_chars and b - a > 1:
                continue
            c = cost[a] + 1 + 2 * max(0.0, 1 - chars / SHORT) ** 2 + (after(a - 1) if a else 0.0)
            if c < cost[b]:
                cost[b], back[b] = c, a
    chunks, b = [], len(run)
    while b:
        chunks.insert(0, run[back[b]:b])
        b = back[b]
    return chunks


def two_lines(texts: list[str], max_chars: int) -> list[str]:
    """One line if it fits half the budget, else the most even break that neither ends a line on
    a leading word nor leaves one short word alone."""
    full = " ".join(texts)
    if len(full) <= max_chars // 2 + 2 or len(texts) < 2:
        return [full]

    def cost(i: int) -> float:
        top, low = " ".join(texts[:i]), " ".join(texts[i:])
        lead = re.sub(r"[^\w'-]", "", texts[i - 1]).lower().replace("’", "'") in LEADS
        return max(len(top), len(low)) + 6 * lead + 8 * (min(len(top), len(low)) < 6)

    best = min(range(1, len(texts)), key=cost)
    return [" ".join(texts[:best]), " ".join(texts[best:])]


def build(words: list[dict], a: argparse.Namespace) -> list[dict]:
    chunks = [c for r in phrases(words) for c in split(r, a.max_chars, a.max_words)]

    def text(w: dict) -> str:
        t = re.sub(r"[,.;:]+$", "", w["text"]) if a.plain else w["text"]
        return t.lower() if a.case == "lower" else t.upper() if a.case == "upper" else t

    out: list[dict] = []
    for k, ch in enumerate(chunks):
        start = max(0.0, ch[0]["start"] - a.lead)
        if out:
            start = max(start, out[-1]["end"])
        end = ch[-1]["end"] + 0.2
        if k + 1 < len(chunks):
            nxt = max(0.0, chunks[k + 1][0]["start"] - a.lead)
            end = nxt if nxt - ch[-1]["end"] < HOLD else min(end, nxt)
        end = max(end, start + 0.1)
        texts = [text(w) for w in ch]
        row = {"start": round(start, 3), "end": round(end, 3), "text": " ".join(texts),
               "lines": two_lines(texts, a.max_chars),
               "words": [{"text": t, "start": w["start"], "end": w["end"]} for t, w in zip(texts, ch)]}
        if a.fps:
            row["startFrame"], row["endFrame"] = round(start * a.fps), round(end * a.fps)
            for wd in row["words"]:
                wd["startFrame"], wd["endFrame"] = round(wd["start"] * a.fps), round(wd["end"] * a.fps)
        out.append(row)
    return out


def stamp(t: float, sep: str) -> str:
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}{sep}{ms % 1000:03d}"


def ass(caps: list[dict], a: argparse.Namespace) -> str:
    w, h = (int(x) for x in a.size.split("x"))
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{a.font},{a.font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,0,3,2,{w // 12},{w // 12},{h - a.bottom},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def t(x: float) -> str:  # ASS wants h:mm:ss.cc
        cs = round(x * 100)
        return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"
    rows = [f"Dialogue: 0,{t(c['start'])},{t(c['end'])},Caption,,0,0,0,," + "\\N".join(c["lines"])
            for c in caps]
    return head + "\n".join(rows) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words")
    ap.add_argument("-f", "--format", choices=["srt", "vtt", "ass", "json", "remotion"], default="json")
    ap.add_argument("-o", "--out")
    ap.add_argument("--max-chars", type=int, default=32)
    ap.add_argument("--max-words", type=int, default=7)
    ap.add_argument("--lead", type=float, default=0.15)
    ap.add_argument("--plain", action="store_true")
    ap.add_argument("--case", choices=["lower", "upper"])
    ap.add_argument("--fps", type=float)
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--font", default="TikTok Sans")
    ap.add_argument("--font-size", type=int, default=76)
    ap.add_argument("--bottom", type=int, default=1500)
    a = ap.parse_args()
    raw = json.loads(Path(a.words).read_text())
    words = _words.load(a.words)
    if isinstance(raw, list) and raw and "seg" in raw[0]:
        for w, r in zip(words, raw):
            w["seg"] = r.get("seg", 0)
    caps = build(words, a)
    if a.format == "json":
        text = json.dumps(caps, indent=1)
    elif a.format == "remotion":
        text = json.dumps([{"text": (" " if i else "") + wd["text"], "startMs": round(wd["start"] * 1000),
                            "endMs": round(wd["end"] * 1000), "timestampMs": round(wd["start"] * 1000),
                            "confidence": None}
                           for i, wd in enumerate(w for c in caps for w in c["words"])], indent=1)
    elif a.format == "ass":
        text = ass(caps, a)
    else:
        sep = "," if a.format == "srt" else "."
        blocks = [(f"{i}\n" if a.format == "srt" else "")
                  + f"{stamp(c['start'], sep)} --> {stamp(c['end'], sep)}\n" + "\n".join(c["lines"])
                  for i, c in enumerate(caps, 1)]
        text = ("WEBVTT\n\n" if a.format == "vtt" else "") + "\n\n".join(blocks) + "\n"
    if a.out:
        Path(a.out).write_text(text)
        print(f"{len(caps)} captions -> {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()

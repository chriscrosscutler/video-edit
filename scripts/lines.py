#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Number a transcript's lines for the plan, and mark the takes to drop.

Usage:
  lines.py WORDS.json [--gap 0.5] [--json]

Prints `index: start-end text` for each line, the numbering plan.json uses for keep, hold and
hooks. A line ends at . ? or ! or at a pause of --gap seconds or more. Code that turns plan.json
into an EDL reads --json, so the plan and the cut count lines the same way. Marks:

  retake N   this line starts over as line N, the same opening words: keep N, drop this one
  repeat N   line N says this again, most words shared: keep one, usually the later
  filler     um, uh, er, erm: only when the transcriber kept them (captions.md)

Marks are hints from the words alone. Read both takes before dropping one: the earlier take is
sometimes the better read.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _words  # noqa: E402

FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "hmm", "mm"}
END = re.compile(r"[.?!…][\"'”’)\]]*$")


def bare(text: str) -> str:
    return re.sub(r"[^\w']+", "", text.lower())


def split(words: list[dict], gap: float = 0.5) -> list[dict]:
    """Lines: runs of words broken at end punctuation or at a pause of `gap` seconds."""
    lines, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        last = i == len(words) - 1
        if last or END.search(w["text"]) or words[i + 1]["start"] - w["end"] >= gap:
            ws = [words[k] for k in cur]
            lines.append({"index": len(lines), "start": ws[0]["start"], "end": ws[-1]["end"],
                          "text": " ".join(x["text"] for x in ws), "words": [cur[0], cur[-1]], "marks": []})
            cur = []
    return lines


def mark(lines: list[dict], words: list[dict], within: float = 30.0) -> list[dict]:
    """A line that the next few lines start over or say again; fillers by count."""
    said = [[bare(words[k]["text"]) for k in range(ln["words"][0], ln["words"][1] + 1)] for ln in lines]
    said = [[t for t in s if t and t not in FILLERS] for s in said]
    for i, ln in enumerate(lines):
        fill = sum(bare(words[k]["text"]) in FILLERS for k in range(ln["words"][0], ln["words"][1] + 1))
        if fill:
            ln["marks"].append({"kind": "filler", "count": fill})
        a = said[i]
        for j in range(i + 1, min(i + 4, len(lines))):
            if lines[j]["start"] - ln["end"] > within:
                break
            b = said[j]
            # The last word of a false start is often cut off ("the fir-"), so it only has to begin the next.
            if 2 <= len(a) < len(b) and a[:-1] == b[:len(a) - 1] and b[len(a) - 1].startswith(a[-1][:3]):
                ln["marks"].append({"kind": "retake", "of": j})
                break
            shared = len(set(a) & set(b))
            if min(len(set(a)), len(set(b))) >= 3 and shared / min(len(set(a)), len(set(b))) >= 0.7:
                ln["marks"].append({"kind": "repeat", "of": j})
                break
    return lines


def label(m: dict) -> str:
    return f"filler x{m['count']}" if m["kind"] == "filler" else f"{m['kind']} {m['of']}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words")
    ap.add_argument("--gap", type=float, default=0.5, help="a pause this long ends a line (seconds)")
    ap.add_argument("--json", action="store_true", help="the lines as JSON, with word index ranges")
    a = ap.parse_args()
    words = _words.load(a.words)
    lines = mark(split(words, a.gap), words)
    if a.json:
        print(json.dumps(lines, indent=1))
        return
    for ln in lines:
        tail = f"   [{', '.join(label(m) for m in ln['marks'])}]" if ln["marks"] else ""
        print(f"{ln['index']}: {ln['start']:.2f}-{ln['end']:.2f} {ln['text']}{tail}")


if __name__ == "__main__":
    main()

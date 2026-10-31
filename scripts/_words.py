"""Word timings from any common transcriber, as [{"text", "start", "end"}] in seconds.

Reads WhisperX, faster-whisper, mlx-whisper and OpenAI verbose_json (segments[].words[] or a
top-level words[]), Deepgram (results.channels[0].alternatives[0].words), Remotion's Caption[]
(startMs/endMs) and a plain list of {word|text, start, end}. A word the aligner could not time
(WhisperX leaves digits like "50" without start/end) is spread evenly between its neighbours;
spell numerals out before aligning to avoid that (captions.md).
"""
import json
from pathlib import Path


def _rows(data) -> list[dict]:
    if isinstance(data, list):
        return data
    if "segments" in data:
        return [w for s in data["segments"] for w in s.get("words", [])]
    if "words" in data:
        return data["words"]
    if "results" in data:  # Deepgram
        return data["results"]["channels"][0]["alternatives"][0]["words"]
    raise ValueError("no words found: expected segments[].words, words[], results (Deepgram) or a list")


def _word(r: dict) -> dict:
    text = r.get("punctuated_word") or r.get("word") or r.get("text") or ""
    if "startMs" in r:
        start, end = r["startMs"] / 1000, r["endMs"] / 1000
    else:
        start, end = r.get("start"), r.get("end")
    return {"text": text.strip(), "start": start, "end": end}


def fill_gaps(words: list[dict]) -> list[dict]:
    """Give untimed words even slices of the time between their timed neighbours."""
    i = 0
    while i < len(words):
        if words[i]["start"] is not None and words[i]["end"] is not None:
            i += 1
            continue
        j = i
        while j < len(words) and (words[j]["start"] is None or words[j]["end"] is None):
            j += 1
        lo = words[i - 1]["end"] if i else (words[j]["start"] if j < len(words) else 0.0)
        hi = words[j]["start"] if j < len(words) else lo + 0.3 * (j - i)
        step = max(hi - lo, 0.0) / (j - i)
        for k in range(i, j):
            words[k]["start"] = round(lo + step * (k - i), 3)
            words[k]["end"] = round(lo + step * (k - i + 1), 3)
        i = j
    return words


def load(path: str | Path) -> list[dict]:
    words = [_word(r) for r in _rows(json.loads(Path(path).read_text()))]
    return fill_gaps([w for w in words if w["text"]])

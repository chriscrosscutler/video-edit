#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""What an editor must know about each file before planning a cut.

Usage: probe.py FILE... [--json] [--levels]

Prints display size (after rotation), fps (and whether it varies), frames, duration, colour
(SDR, HLG or PQ), audio layout and, with --levels, each channel's RMS so a two-mic recording
can use its louder mic. Ends with what to do about anything that would break a frame-exact edit.
"""
import json
import re
import subprocess
import sys
from fractions import Fraction


def ffprobe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
        capture_output=True, text=True)
    if out.returncode:
        sys.exit(f"probe: {path}: {out.stderr.strip() or 'ffprobe failed'}")
    return json.loads(out.stdout)


def rotation(v: dict) -> int:
    for sd in v.get("side_data_list", []):
        if "rotation" in sd:
            return int(sd["rotation"]) % 360
    return int(v.get("tags", {}).get("rotate", 0)) % 360


def rate(s: str | None) -> float:
    try:
        return float(Fraction(s)) if s and s != "0/0" else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def channel_rms(path: str, index: int) -> list[float]:
    """RMS dB of each channel of audio stream `index`."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-map", f"0:a:{index}",
         "-af", "astats=measure_overall=none", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    return [float(x) for x in re.findall(r"RMS level dB: (-?[\d.]+|-inf)", out.replace("-inf", "-120"))]


def facts(path: str, levels: bool) -> dict:
    p = ffprobe(path)
    v = next((s for s in p["streams"] if s["codec_type"] == "video"), None)
    auds = [s for s in p["streams"] if s["codec_type"] == "audio"]
    dur = float(p["format"].get("duration", 0) or 0)
    f: dict = {"file": path, "duration_s": round(dur, 3), "notes": []}
    if v:
        rot = rotation(v)
        w, h = int(v["width"]), int(v["height"])
        if rot in (90, 270):
            w, h = h, w
        avg, real = rate(v.get("avg_frame_rate")), rate(v.get("r_frame_rate"))
        trc = v.get("color_transfer", "")
        hdr = {"arib-std-b67": "HLG", "smpte2084": "PQ"}.get(trc, "")
        dovi = any("DOVI" in sd.get("side_data_type", "") or "Dolby" in sd.get("side_data_type", "")
                   for sd in v.get("side_data_list", []))
        f.update({
            "video": v["codec_name"], "size": [w, h], "rotation": rot, "fps": round(avg, 3),
            "vfr": bool(avg and real and abs(avg - real) > 0.01),
            "frames": int(v.get("nb_frames", 0) or 0) or round(avg * dur),
            "pix_fmt": v.get("pix_fmt"), "transfer": trc or "unknown",
            "primaries": v.get("color_primaries", "unknown"),
            "range": hdr or ("SDR" if trc in ("bt709", "", "unknown") else trc),
            "dolby_vision": dovi,
        })
        if hdr:
            f["notes"].append(f"{hdr} HDR: tone-map to BT.709 SDR once, at intake, before any overlay "
                              "(render.md 'HDR to SDR')")
        if f["vfr"]:
            f["notes"].append(f"variable frame rate ({real:g} nominal, {avg:g} average): conform to a "
                              "constant rate (fps filter) before cutting by frame")
        if rot:
            f["notes"].append(f"rotated {rot} degrees: ffmpeg autorotates on decode; size above is "
                              "as displayed")
        if w * 16 != h * 9:
            f["notes"].append(f"{w}x{h} is not 9:16: a vertical edit crops or letterboxes it")
    f["audio"] = []
    for i, a in enumerate(auds):
        row = {"codec": a["codec_name"], "channels": a.get("channels"),
               "rate": int(a.get("sample_rate", 0) or 0), "layout": a.get("channel_layout", "")}
        if levels:
            row["rms_db"] = channel_rms(path, i)
            ch = row["rms_db"]
            if len(ch) == 2 and abs(ch[0] - ch[1]) > 3:
                loud = 0 if ch[0] > ch[1] else 1
                f["notes"].append(f"audio {i}: channel {loud} is {abs(ch[0] - ch[1]):.0f} dB louder: "
                                  f"use it alone (pan=mono|c0=c{loud}); summing two mics combs")
        f["audio"].append(row)
    if not auds:
        f["notes"].append("no audio: a silent take is footage (B-roll or an interlude), not a line")
    return f


def line(f: dict) -> str:
    if "size" not in f:
        return f"{f['file']}: audio only, {f['duration_s']} s"
    w, h = f["size"]
    a = ", ".join(f"{x['channels']}ch {x['rate'] // 1000}k" for x in f["audio"]) or "no audio"
    return (f"{f['file']}: {w}x{h} {f['fps']:g}{' VFR' if f['vfr'] else ''} fps, {f['frames']} frames, "
            f"{f['duration_s']} s, {f['video']} {f['pix_fmt']} {f['range']}, {a}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    rows = [facts(p, "--levels" in sys.argv) for p in args]
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=1))
        return
    for f in rows:
        print(line(f))
        for n in f["notes"]:
            print(f"  - {n}")


if __name__ == "__main__":
    main()

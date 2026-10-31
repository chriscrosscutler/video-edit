#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""The final mix: a music bed ducked under the voice, then one gain and a limiter to the target.

Usage:
  master.py measure FILE                  integrated LUFS, true peak (dBTP), loudness range
  master.py mix VIDEO OUT.mp4 [--music M.wav] [--gap-db -9] [--lufs -14] [--tp -1]
      VIDEO's audio is the voice edit. The music is levelled to --gap-db under the voice, looped
      or cut to length, and pushed down about 12 dB more while the voice talks (sidechain), so it
      sits 15-20 dB under the voice and comes up between phrases. The mix gets one gain to --lufs
      and a sample-peak limiter 0.5 dB under --tp; never loudnorm's dynamic mode, which pumps.
      The video stream is copied untouched.
"""
import argparse
import json
import re
import subprocess
import sys


def ff(args: list[str]) -> str:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args], capture_output=True, text=True)
    if out.returncode:
        sys.exit(f"master: ffmpeg failed:\n{out.stderr.strip()[-1200:]}")
    return out.stderr


def measure(path: str, chain: str = "") -> dict:
    err = ff(["-i", path, "-vn", "-af", f"{chain}{',' if chain else ''}loudnorm=print_format=json",
              "-f", "null", "-"])
    m = json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", err)[-1])
    return {"lufs": float(m["input_i"]), "true_peak": float(m["input_tp"]), "lra": float(m["input_lra"])}


def duration(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "csv=p=0", path], capture_output=True, text=True)
    return float(out.stdout.strip())


def mix(video: str, dst: str, music: str | None, gap_db: float, lufs: float, tp: float) -> None:
    voice = measure(video)
    if music:
        bed_gain = voice["lufs"] + gap_db - measure(music)["lufs"]
        d = duration(video)
        graph = (f"[1:a]aloop=loop=-1:size=2e9,atrim=duration={d:.3f},volume={bed_gain:.2f}dB,"
                 f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[bed];"
                 f"[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,asplit[v][key];"
                 f"[bed][key]sidechaincompress=threshold=0.02:ratio=4:attack=50:release=450[duck];"
                 f"[v][duck]amix=inputs=2:normalize=0:duration=first[mix]")
        inputs = ["-i", video, "-i", music]
    else:
        graph, inputs = "[0:a]anull[mix]", ["-i", video]
    # pass 1: loudness of the mix; pass 2: one gain, then the limiter
    tmp = ff([*inputs, "-filter_complex", graph + ";[mix]loudnorm=print_format=json[o]", "-map", "[o]",
              "-f", "null", "-"])
    got = float(json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", tmp)[-1])["input_i"])
    limit = 10 ** ((tp - 0.5) / 20)
    final = graph + f";[mix]volume={lufs - got:.2f}dB,alimiter=limit={limit:.4f}:level=false,aresample=48000[out]"
    ff(["-y", *inputs, "-filter_complex", final, "-map", "0:v?", "-map", "[out]", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", dst])
    print(json.dumps({"voice_in": voice, "out": measure(dst)}))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("measure").add_argument("file")
    m = sub.add_parser("mix")
    m.add_argument("video")
    m.add_argument("out")
    m.add_argument("--music")
    m.add_argument("--gap-db", type=float, default=-9.0)
    m.add_argument("--lufs", type=float, default=-14.0)
    m.add_argument("--tp", type=float, default=-1.0)
    a = ap.parse_args()
    if a.cmd == "measure":
        print(json.dumps(measure(a.file)))
    else:
        mix(a.video, a.out, a.music, a.gap_db, a.lufs, a.tp)


if __name__ == "__main__":
    main()

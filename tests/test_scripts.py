#!/usr/bin/env python3
"""Runs every script on synthetic clips: python3 tests/test_scripts.py (needs ffmpeg 7+, ~1 min)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

S = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(S))
from blender_title import PRORES_VF  # noqa: E402  (runs without bpy)

TITLE_RGB = (232, 74, 95)
# Three spoken lines (a tone stands in for the voice) with quiet between them.
LINES = [(0.1, 2.0, "so this is the best mask"), (3.0, 5.0, "i use it every night"),
         (5.6, 7.95, "check it out")]


def sh(*cmd, ok=True) -> subprocess.CompletedProcess:
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if ok and p.returncode:
        raise AssertionError(f"{cmd} exited {p.returncode}:\n{p.stdout}\n{p.stderr}")
    return p


def py(script, *args, ok=True) -> subprocess.CompletedProcess:
    return sh(sys.executable, S / script, *args, ok=ok)


def ff(*args) -> None:
    sh("ffmpeg", "-y", "-v", "error", *args)


def words() -> dict:
    out = []
    for start, end, text in LINES:
        ws = text.split()
        step = (end - start) / len(ws)
        out += [{"word": w, "start": round(start + i * step, 3), "end": round(start + (i + 1) * step - 0.05, 3)}
                for i, w in enumerate(ws)]
    return {"segments": [{"words": out}]}


def gray(path: Path, frame: int) -> bytes:
    return subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"select=eq(n\\,{frame}),scale=108:192",
                           "-frames:v", "1", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                          capture_output=True, check=True).stdout


def alpha(webm: Path, frame: int) -> bytes:
    return subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", str(webm), "-vf",
                           f"select=eq(n\\,{frame}),alphaextract,scale=108:192", "-frames:v", "1", "-pix_fmt", "gray",
                           "-f", "rawvideo", "-"], capture_output=True, check=True).stdout


def frames(path: Path) -> int:
    return int(sh("ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                  "stream=nb_read_frames", "-of", "csv=p=0", path).stdout)


def rgba(png: Path) -> list[tuple]:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(png), "-pix_fmt", "rgba", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    return [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]


SWIFTC = sys.platform == "darwin" and shutil.which("swiftc")
BLENDER = os.environ.get("BLENDER") or shutil.which("blender") or next(
    (p for p in ["/Applications/Blender.app/Contents/MacOS/Blender"] if Path(p).exists()), None)


def px(path: Path, frame: int, x: int, y: int) -> tuple:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"select=eq(n\\,{frame}),crop=2:2:{x}:{y}",
                          "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    return tuple(raw[:3])


def off(a: tuple, b: tuple) -> int:
    return max(abs(x - y) for x, y in zip(a, b))


def diff(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def pcm(path: Path, t0: float, t1: float) -> list[int]:
    from array import array
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t0), "-t", str(t1 - t0), "-i", str(path), "-vn",
                          "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    a = array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    return list(a)


def zcr(path: Path, t0: float, t1: float) -> float:
    """Zero crossings per second: about 440 for the 220 Hz voice tone, thousands for noise."""
    a = pcm(path, t0, t1)
    return sum(1 for x, y in zip(a, a[1:]) if (x < 0) != (y < 0)) / (t1 - t0)


def rms(path: Path, t0: float, t1: float) -> float:
    a = pcm(path, t0, t1)
    return (sum(x * x for x in a) / max(len(a), 1)) ** 0.5


class Scripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp(prefix="video-edit-"))
        d = cls.d
        voice = "+".join(f"between(t,{a},{b})" for a, b, _ in LINES)
        ff("-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=8", "-f", "lavfi",
           "-i", f"aevalsrc='0.3*sin(2*PI*220*t)*({voice})':s=48000:d=8",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
           d / "talk.mp4")
        ff("-f", "lavfi", "-i", "mandelbrot=s=1080x1920:r=30", "-f", "lavfi", "-i", "anoisesrc=a=0.05:d=6",
           "-t", "6", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac",
           d / "broll.mp4")
        # A ProRes 4444 title, encoded the way blender_title.py prints: a coloured box on a clear background.
        ff("-f", "lavfi", "-i", "color=white@0:s=1080x1920:r=30:d=3,format=rgba,"
           "drawbox=x=340:y=300:w=400:h=200:color=0x%02X%02X%02X@1:t=fill:replace=1" % TITLE_RGB,
           "-vf", PRORES_VF, "-c:v", "prores_ks", "-profile:v", "4444", d / "title.mov")
        ff("-f", "lavfi", "-i", "sine=f=440:d=12:sample_rate=48000", "-ac", "2", d / "music.wav")
        (d / "talk.words.json").write_text(json.dumps(words()))
        cls.edl = {"fps": 30, "size": [1080, 1920],
                   "sources": {"t1": {"path": "talk.mp4", "words": "talk.words.json"}, "b1": "broll.mp4",
                               "ti": "title.mov"},
                   "segments": [{"src": "t1", "in": 0.05, "out": 2.2},
                                {"src": "b1", "in": 0.5, "out": 3.5, "gain_db": -12,
                                 "transition": {"type": "fade", "frames": 16}},
                                {"src": "t1", "in": 2.9, "out": 7.98}],
                   "cutaways": []}
        cls.write("cut.json", cls.edl)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    @classmethod
    def write(cls, name: str, data) -> Path:
        (cls.d / name).write_text(json.dumps(data))
        return cls.d / name

    def render(self, name: str, edl: dict) -> Path:
        out = self.d / f"{name}.mp4"
        if not out.exists():
            py("edl.py", "render", self.write(f"{name}.json", edl), out)
        return out

    def test_probe(self):
        info = json.loads(py("probe.py", self.d / "talk.mp4", "--json").stdout)[0]
        self.assertEqual((info["size"], info["fps"], info["frames"], info["vfr"]), ([1080, 1920], 30.0, 240, False))

    def test_sheet(self):
        out = json.loads(py("sheet.py", self.d / "talk.mp4", self.d / "s.jpg", "--frames", "0,75,212").stdout)
        self.assertEqual(len(out["times"]), 3)
        self.assertGreater((self.d / "s.jpg").stat().st_size, 1000)

    def test_quiet(self):
        q = json.loads(py("quiet.py", "stretches", self.d / "talk.mp4").stdout)["quiet"]
        self.assertTrue(any(a <= 2.1 and b >= 2.9 for a, b in q), q)
        bad = dict(self.edl, segments=[{"src": "t1", "in": 0.05, "out": 1.5}, {"src": "t1", "in": 3.3, "out": 7.98}])
        snapped = self.d / "snapped.json"
        py("quiet.py", "snap", self.write("bad.json", bad), "-o", snapped)
        segs = json.loads(snapped.read_text())["segments"]
        self.assertGreaterEqual(segs[0]["out"], 1.5)  # mid-line out moves outward, never in
        self.assertLessEqual(segs[1]["in"], 3.3)

    def test_check(self):
        self.assertIn("frames", py("edl.py", "check", self.d / "cut.json").stdout)
        segs = [dict(s) for s in self.edl["segments"]]
        segs[1]["transition"] = {"type": "cube", "frames": 16}
        p = py("edl.py", "check", self.write("cube.json", dict(self.edl, segments=segs)), ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("not an ffmpeg xfade type", p.stdout + p.stderr)

    def test_words_and_captions(self):
        tl = self.d / "tl.json"
        py("edl.py", "words", self.d / "cut.json", "-o", tl)
        ws = json.loads(tl.read_text())
        self.assertEqual({w["seg"] for w in ws}, {0, 2})
        for f in ("srt", "vtt", "ass", "json", "remotion"):
            out = self.d / f"caps.{f}"
            py("captions.py", tl, "-f", f, "-o", out, "--fps", "30")
            self.assertGreater(out.stat().st_size, 20, f)
        phrases = json.loads((self.d / "caps.json").read_text())
        self.assertTrue(all(len(p["lines"]) <= 2 for p in phrases))
        early = [p["words"][0]["start"] - p["start"] for p in phrases]
        self.assertTrue(min(early) >= 0 and max(early) > 0.1, early)  # shown just before it is heard

    def test_place(self):
        tl = self.d / "tl2.json"
        py("edl.py", "words", self.d / "cut.json", "-o", tl)
        caps = self.d / "caps2.json"
        py("captions.py", tl, "-f", "json", "-o", caps, "--fps", "30")
        faces = self.write("faces.json", [[f, [[0.3, 0.62, 0.7, 0.78, 0.9]]] for f in range(0, 361, 15)])
        out = self.d / "placed.json"
        py("place.py", faces, caps, "-o", out)
        for p in json.loads(out.read_text()):
            self.assertLessEqual(p["place"]["bottom"], 0.62 * 1920)

    def test_render_and_qa(self):
        out = self.render("plain", self.edl)
        rows = py("edl.py", "qa", self.d / "plain.json", out, "--no-loudness", "--sheet", self.d / "qa.jpg")
        self.assertIn("frames", rows.stdout)
        self.assertTrue((self.d / "qa.jpg").exists())
        final = self.d / "final.mp4"
        py("master.py", "mix", out, final, "--music", self.d / "music.wav")
        m = json.loads(py("master.py", "measure", final).stdout)
        self.assertAlmostEqual(m["lufs"], -14, delta=0.5)
        self.assertLessEqual(m["true_peak"], -1)
        py("edl.py", "qa", self.d / "plain.json", final)
        late = self.d / "late.mp4"  # moov at the end
        ff("-i", final, "-c", "copy", late)
        p = py("edl.py", "qa", self.d / "plain.json", late, ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("moov", p.stdout)

    def test_qa_hears_a_pop_at_a_cut(self):
        # A held tone whose sign flips at 1 s: a hard cut with no fade. AAC smears the step but keeps it.
        ff("-f", "lavfi", "-i", "aevalsrc='if(lt(t,1),0.3,-0.3)*cos(2*PI*220*t)':s=48000:d=2",
           "-c:a", "aac", self.d / "pop.m4a")
        ff("-f", "lavfi", "-i", "aevalsrc='0.3*cos(2*PI*220*t)':s=48000:d=2", "-c:a", "aac", self.d / "held.m4a")
        sys.path.insert(0, str(S))
        import edl as E
        self.assertEqual(len(E.clicks(self.d / "pop.m4a", [1.0, 1.5])), 1)
        self.assertEqual(E.clicks(self.d / "held.m4a", [1.0, 1.5]), [])
        out = self.render("plain", self.edl)  # every segment has the default 8 ms afade
        self.assertEqual(E.clicks(out, [r["start"] / 30 for r in E.Plan(self.d / "plain.json").timeline()[1:]]), [])

    def test_lines_marks_retakes(self):
        rows, t = [], 0.0
        for line, pause in (("So the fir-", 0.6), ("So the first thing you do is wash your face.", 0.15),
                            ("Um, I use warm water, uh, every night.", 0.15),
                            ("I use warm water every single night.", 0.8), ("Then the mask goes on", 0.15)):
            for w in line.split():
                rows.append({"word": w, "start": round(t, 2), "end": round(t + 0.3, 2)})
                t += 0.35
            t += pause
        lines = json.loads(py("lines.py", self.write("takes.words.json", rows), "--json").stdout)
        self.assertEqual([ln["text"].split()[0] for ln in lines], ["So", "So", "Um,", "I", "Then"])  # . and pauses
        self.assertEqual(lines[0]["marks"], [{"kind": "retake", "of": 1}])
        self.assertEqual(lines[2]["marks"], [{"kind": "filler", "count": 2}, {"kind": "repeat", "of": 3}])
        self.assertEqual(lines[1]["marks"] + lines[3]["marks"] + lines[4]["marks"], [])
        self.assertEqual(lines[4]["words"], [len(rows) - 5, len(rows) - 1])
        text = py("lines.py", self.d / "takes.words.json").stdout
        self.assertIn("0: 0.00-1.00 So the fir-   [retake 1]", text)

    def test_alpha_cutaway(self):
        base = self.render("plain", self.edl)
        titled = self.render("titled", dict(self.edl, cutaways=[{"src": "ti", "in": 0, "out": 2, "at": 1, "fade": 0}]))
        self.assertNotIn("cutaway ti", py("edl.py", "check", self.d / "titled.json").stdout)  # an overlay, not a cut
        a, b = gray(base, 45), gray(titled, 45)
        box = [i for i in range(len(a)) if 34 <= i % 108 < 74 and 30 <= i // 108 < 50]
        rest = [i for i in range(len(a)) if 80 <= i // 108]
        self.assertLess(diff(bytes(a[i] for i in rest), bytes(b[i] for i in rest)), 3)  # clear: footage shows
        self.assertGreater(diff(bytes(a[i] for i in box), bytes(b[i] for i in box)), 20)  # the box shows
        self.assertLessEqual(off(px(titled, 45, 540, 400), TITLE_RGB), 4)  # in its own colour

    def test_colour_matrix(self):
        # One green patch encoded four ways; every one must come out as the tagged BT.709 one does.
        patch = "color=c=0x20C040:s={}:r=30:d=3"
        tags = "setparams=color_primaries={0}:color_trc={0}:colorspace={0}:range={1}"
        for name, size, matrix, tag in [("c709", "1080x1920", "bt709", tags.format("bt709", "tv")),
                                        ("c601", "1080x1920", "bt601", tags.format("smpte170m", "tv")),
                                        ("u709", "1080x1920", "bt709", tags.format("unknown", "unknown")),
                                        ("u601", "480x854", "bt601", tags.format("unknown", "unknown"))]:
            ff("-f", "lavfi", "-i", patch.format(size), "-vf",
               f"scale=out_color_matrix={matrix}:out_range=tv,format=yuv420p,{tag}",
               "-c:v", "libx264", "-preset", "ultrafast", self.d / f"{name}.mp4")
        edl = {"fps": 30, "size": [1080, 1920], "sources": {k: f"{k}.mp4" for k in ("c709", "c601", "u709", "u601")},
               "segments": [{"src": k, "in": 0, "out": 2.5} for k in ("c709", "c601", "u709", "u601")]}
        out = self.render("matrix", edl)
        ref = px(out, 30, 500, 900)
        for k, f in [("c601", 105), ("u709", 180), ("u601", 255)]:
            self.assertLessEqual(off(px(out, f, 500, 900), ref), 3, k)
        py("edl.py", "conform", self.d / "c601.mp4", self.d / "u709.mp4", "-o", self.d / "conformed")
        for k in ("c601", "u709"):
            self.assertLessEqual(off(px(self.d / "conformed" / f"{k}.mp4", 30, 500, 900), ref), 3, f"conform {k}")

    @unittest.skipUnless(SWIFTC, "matte.swift needs macOS and swiftc")
    def test_matte(self):
        tool = self.d / "matte"
        sh("swiftc", "-O", S / "matte.swift", "-o", tool)
        clip, photo = self.d / "talk.mp4", os.environ.get("VIDEO_EDIT_PERSON")  # a photo of one person
        if photo:
            clip = self.d / "person.mp4"
            ff("-loop", "1", "-framerate", "30", "-i", photo, "-t", "1", "-vf",
               "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=yuv420p",
               "-c:v", "libx264", "-preset", "ultrafast", clip)
        mask, cut = self.d / "mask.mp4", self.d / "person.webm"
        sh(tool, clip, mask, "--person", cut)
        self.assertEqual({frames(mask), frames(cut)}, {frames(clip)})
        m, a = gray(mask, 15), alpha(cut, 15)
        self.assertLess(diff(m, a), 8)  # the cutout's alpha is the matte, softened
        if photo:
            self.assertTrue(max(m) > 240 and min(m) < 15, "the person is white, the rest black")
        else:
            self.assertLess(max(m), 30)  # no person, no matte
        rot = self.d / "rot.mp4"
        ff("-display_rotation", "90", "-i", self.d / "talk.mp4", "-t", "0.5", "-c", "copy", rot)
        self.assertIn("rotated", sh(tool, rot, self.d / "x.mp4", ok=False).stderr)

    def test_speed(self):
        edl = dict(self.edl, segments=[{"src": "t1", "in": 0.05, "out": 2.2},
                                       {"src": "b1", "in": 0.5, "out": 3.5, "speed": 2},
                                       {"src": "t1", "in": 2.9, "out": 4.9, "speed": [[0, 1], [0.5, 3], [1, 1]]},
                                       {"src": "t1", "in": 5.6, "out": 7.98, "speed": 0.5}])
        out = self.render("speed", edl)
        sys.path.insert(0, str(S))
        import edl as E
        rows = E.Plan(self.d / "speed.json").timeline()
        self.assertEqual(rows[1]["dur"], 45)
        self.assertTrue(30 < rows[2]["dur"] < 60, rows[2]["dur"])  # a ramp up to 3x and back
        self.assertEqual(rows[3]["dur"], 142)
        self.assertEqual(frames(out), sum(r["dur"] for r in rows))
        py("edl.py", "qa", self.d / "speed.json", out, "--no-loudness", "--no-ocr")
        tl = self.d / "speed-words.json"
        py("edl.py", "words", self.d / "speed.json", "-o", tl)
        ws = json.loads(tl.read_text())
        self.assertNotIn(2, {w["seg"] for w in ws})  # a ramp mutes its sound, so no captions
        slow = [w for w in ws if w["seg"] == 3]
        self.assertAlmostEqual(slow[0]["start"], rows[3]["start"] / 30, delta=0.05)  # "check" at 5.6 s
        self.assertGreater(slow[-1]["end"] - slow[0]["start"], 4.0)  # 2.3 s of words at half speed
        self.assertLess(zcr(out, rows[3]["start"] / 30 + 0.1, rows[3]["start"] / 30 + 0.6), 700)  # pitch kept
        p = py("edl.py", "check", self.write("bad-speed.json", dict(edl, segments=[dict(edl["segments"][0], speed=0)])),
               ok=False)
        self.assertIn("speed 0 is outside", p.stderr)

    def test_split_edit(self):
        # noise, then a toned line, then noise: J and L cuts move the tone over the noise shots' edges
        segs = [{"src": "b1", "in": 0.5, "out": 2.5}, {"src": "t1", "in": 3.2, "out": 4.4},
                {"src": "b1", "in": 3.0, "out": 5.0}]
        plain = self.render("split-plain", dict(self.edl, segments=segs))
        segs[1] = dict(segs[1], audio_lead=6, audio_trail=6)
        split = self.render("split", dict(self.edl, segments=segs))
        self.assertEqual(frames(split), 156)
        self.assertGreater(zcr(plain, 1.82, 1.98), 2000)
        self.assertLess(zcr(split, 1.82, 1.98), 1000)  # J: the line is heard before its shot
        self.assertLess(zcr(split, 3.22, 3.38), 1000)  # L: and runs on under the next
        self.assertGreater(zcr(split, 4.0, 4.5), 2000)
        py("edl.py", "qa", self.d / "split.json", split, "--no-loudness", "--no-ocr")
        tl = self.d / "split-words.json"
        py("edl.py", "words", self.d / "split.json", "-o", tl)
        self.assertLess(min(w["start"] for w in json.loads(tl.read_text())), 2.0)  # captions follow the sound
        bad = [dict(segs[0]), {"src": "t1", "in": 0.1, "out": 1.5, "audio_lead": 9}]
        p = py("edl.py", "check", self.write("bad-split.json", dict(self.edl, segments=bad)), ok=False)
        self.assertIn("starts 9 frames early", p.stdout)

    def test_room_tone_and_sfx(self):
        tone = self.d / "tone.wav"
        ff("-f", "lavfi", "-i", "anoisesrc=a=0.01:d=3:c=pink", "-ac", "2", "-ar", "48000", tone)
        ff("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d=0.3", "-f", "lavfi",
           "-i", "sine=f=1000:d=0.05:sample_rate=48000", "-filter_complex", "[1]aformat=channel_layouts=stereo[b];"
           "[0][b]concat=n=2:v=0:a=1", self.d / "hit.wav")
        segs = [{"src": "b1", "in": 0.5, "out": 2.5, "mute": True}, {"src": "b1", "in": 3.0, "out": 5.0, "mute": True}]
        silent = self.render("muted", dict(self.edl, segments=segs))
        self.assertLess(rms(silent, 0.5, 1.5), 2)
        filled = self.render("toned", dict(self.edl, segments=segs, room_tone="tone.wav",
                                           sfx=[{"path": "hit.wav", "at": {"seg": 1}, "align": "peak", "gain_db": 0}]))
        self.assertGreater(rms(filled, 0.5, 1.5), 20)  # room tone, not digital silence
        a = pcm(filled, 1.5, 2.5)
        peak = 1.5 + max(range(len(a)), key=lambda i: abs(a[i])) / 16000
        self.assertAlmostEqual(peak, 2.0, delta=0.06)  # the hit lands on the cut into segment 1
        self.assertEqual(frames(filled), 120)
        p = py("edl.py", "check", self.write("bad-sfx.json", dict(self.edl, sfx=[{"path": "hit.wav", "at": {"seg": 9}}])),
               ok=False)
        self.assertIn("sfx anchor", p.stdout)
        out = json.loads(py("quiet.py", "tone", self.d / "broll.mp4", self.d / "rt.wav", ok=False).stdout or "{}")
        self.assertTrue(out == {} or out["seconds"] >= 0.5)

    def test_qa_scopes_and_conform_fixes(self):
        out = self.render("plain", self.edl)
        rows = py("edl.py", "qa", self.d / "plain.json", out, "--no-loudness", "--no-ocr",
                  "--scopes", self.d / "scopes.png")
        self.assertTrue((self.d / "scopes.png").stat().st_size > 5000, rows.stdout)
        fixed = self.d / "fixed"
        py("edl.py", "conform", self.d / "talk.mp4", "-o", fixed, "--stabilize", "--denoise", "light")
        info = json.loads(py("probe.py", fixed / "talk.mp4", "--json").stdout)[0]
        self.assertEqual((info["size"], info["frames"]), ([1080, 1920], 240))

    def test_sync_and_multicam(self):
        other = self.d / "phone2.wav"  # the same room from a second phone: started 1.3 s later, noisier
        ff("-ss", "1.3", "-i", self.d / "talk.mp4", "-f", "lavfi", "-i", "anoisesrc=a=0.02:d=8", "-filter_complex",
           "[0:a]volume=0.6[v];[v][1:a]amix=inputs=2:duration=first", "-ac", "2", other)
        got = json.loads(py("sync.py", self.d / "talk.mp4", other).stdout)[0]
        self.assertAlmostEqual(got["offset"], 1.3, delta=0.02)
        self.assertGreater(got["confidence"], 1.5)
        ff("-f", "lavfi", "-i", "mandelbrot=s=1080x1920:r=30", "-t", "6.7", "-c:v", "libx264", "-preset", "ultrafast",
           "-pix_fmt", "yuv420p", self.d / "cam2.mp4")  # a second angle with no sound of its own
        edl = dict(self.edl, sources={**self.edl["sources"], "c2": {"path": "cam2.mp4", "offset": 1.3}},
                   segments=[{"src": "t1", "in": 0.05, "out": 2.2},
                             {"src": "c2", "in": 2.9, "out": 5.0, "audio_src": "t1"},
                             {"src": "t1", "in": 5.6, "out": 7.98}])
        out = self.render("multicam", edl)
        self.assertEqual(frames(out), 64 + 63 + 71)
        self.assertLess(zcr(out, 2.5, 3.5), 1000)  # the first phone's sound under the second angle
        want = gray(self.d / "cam2.mp4", 48 + 6)  # c2 at 2.9 s - 1.3 s, six frames in
        self.assertEqual(min(range(66, 75), key=lambda f: diff(gray(out, f), want)), 70)
        tl = self.d / "mc-words.json"
        py("edl.py", "words", self.d / "multicam.json", "-o", tl)
        self.assertEqual({w["seg"] for w in json.loads(tl.read_text())}, {0, 1, 2})

    def test_match_and_grade(self):
        tinted = self.d / "tinted.mp4"
        ff("-i", self.d / "talk.mp4", "-t", "4", "-vf", "format=gbrp,colorchannelmixer=rr=0.8:bb=0.9,format=yuv420p",
           "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "copy", tinted)
        got = json.loads(py("match.py", self.d / "talk.mp4", tinted, "--ref-at", "1,2,3", "--at", "1,2,3").stdout)
        r, g, b = got["gains"]
        self.assertAlmostEqual(r, 1.25, delta=0.08)
        self.assertAlmostEqual(g, 1.0, delta=0.04)
        self.assertAlmostEqual(b, 1.11, delta=0.06)
        edl = dict(self.edl, sources={**self.edl["sources"], "tt": "tinted.mp4"},
                   segments=[{"src": "tt", "in": 0.5, "out": 3.5, "grade": got["grade"]}])
        out = self.render("graded", edl)
        ref, before, after = px(self.d / "talk.mp4", 45, 540, 300), px(tinted, 45, 540, 300), px(out, 30, 540, 300)
        self.assertLess(off(after, ref), off(before, ref))

    def test_reframe(self):
        wide = self.d / "wide.mp4"
        ff("-f", "lavfi", "-i", "nullsrc=s=1920x1080:r=30:d=3,geq=lum='X/W*255':cb=128:cr=128", "-c:v", "libx264",
           "-preset", "ultrafast", "-pix_fmt", "yuv420p", wide)
        faces = self.write("wide-faces.json", [[f, [[0.2, 0.3, 0.3, 0.5, 0.9]] if f < 45 else [[0.7, 0.3, 0.8, 0.5, 0.9]]]
                                               for f in range(0, 90, 3)])
        lefts = self.d / "lefts.json"
        got = json.loads(py("reframe.py", wide, self.d / "tall.mp4", "--faces", faces, "--json", lefts).stdout)
        self.assertEqual(got["crop"], [608, 1080])
        x = json.loads(lefts.read_text())
        self.assertTrue(150 <= x[10] <= 260, x[10])  # face centred at 0.25 of 1920
        self.assertGreater(x[46] - x[44], 600)  # a cut jumps with the face instead of gliding
        self.assertTrue(1050 <= x[80] <= 1230, x[80])
        self.assertEqual(frames(self.d / "tall.mp4"), 90)
        self.assertLess(gray(self.d / "tall.mp4", 10)[96 * 108 + 54], gray(self.d / "tall.mp4", 80)[96 * 108 + 54])

    def test_retention_and_clips(self):
        curve = self.d / "curve.csv"
        curve.write_text("seconds,percent\n0,100\n1,80\n3,62\n5,58\n6,40\n7.5,36\n")
        out = py("retention.py", self.d / "cut.json", curve).stdout
        self.assertIn("at 3 s: 62%", out)
        self.assertIn("drop 18.0% at 5.0-6.0s (segment 1, 0.1s from a cut)", out)
        listing = py("clips.py", self.d / "talk.words.json", "--min", "2", "--max", "6").stdout
        self.assertIn("opens:  so this is the best mask", listing)
        py("clips.py", self.d / "talk.words.json", "--min", "2", "--max", "6", "--pick", "0", "--src",
           self.d / "talk.mp4", "-o", self.d / "clips")
        self.assertIn("frames", py("edl.py", "check", self.d / "clips" / "clip-0.json").stdout)

    def test_typing(self):
        out = json.loads(py("typeon.py", "fresh bread,\\nevery sunday.", "-o", self.d / "type", "--seed", "2").stdout)
        sched = json.loads(Path(out["json"]).read_text())
        f, text = sched["frames"], sched["text"]
        self.assertEqual((len(f), f[0], text[12]), (len(text), 0, "\n"))
        self.assertTrue(all(b > a for a, b in zip(f, f[1:])))
        gaps = sorted(b - a for a, b in zip(f, f[1:]))
        self.assertGreater(f[13] - f[11], 2 * gaps[len(gaps) // 2])  # a beat after the comma and line break
        wav = Path(out["wav"])
        a = [abs(v) for v in pcm(wav, 0, 4)]
        top = max(a)
        win = lambda t0, t1: max(a[int(t0 * 16000):int(t1 * 16000)])  # noqa: E731
        for ch, fr in zip(text, f):
            if ch != "\n":  # a click starts on every character's frame
                self.assertGreater(win(fr / 30, fr / 30 + 0.012), 0.2 * top, (ch, fr))
        self.assertLess(win(f[11] / 30 + 0.14, f[13] / 30 - 0.003), 0.05 * top)  # nothing in the pause
        self.assertAlmostEqual(float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                        "csv=p=0", wav).stdout), f[-1] / 30 + 0.45, delta=0.02)
        keys = self.d / "keys"
        keys.mkdir()
        ff("-f", "lavfi", "-i", "sine=f=1000:d=0.02", keys / "k1.wav")
        ff("-f", "lavfi", "-i", "sine=f=150:d=0.06", keys / "space.wav")
        out = json.loads(py("typeon.py", "ab c", "-o", self.d / "rec", "--samples", keys, "--cps", "6").stdout)
        f = json.loads(Path(out["json"]).read_text())["frames"]
        self.assertLess(zcr(Path(out["wav"]), f[2] / 30 + 0.005, f[2] / 30 + 0.045), 500)  # the space sample
        self.assertGreater(zcr(Path(out["wav"]), f[3] / 30 + 0.002, f[3] / 30 + 0.018), 1500)  # a key sample

    @unittest.skipUnless(BLENDER, "Blender not installed (set BLENDER=/path/to/blender)")
    def test_blender_title(self):
        def title(name, *args):
            sh(BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "-P", S / "blender_title.py", "--",
               *args, "--frames", "20", "--out", self.d / name / "f_####")
            return [rgba(self.d / name / f"f_{f:04d}.png") for f in (1, 12)]  # clear, then held (frames 10-15)

        first, held = title("bt_text", "--text", "Acme Club", "--y", "0.2")
        self.assertEqual(max(p[3] for p in first), 0)  # starts clear
        solid = [p for p in held if p[3] == 255]
        self.assertGreater(len(solid), 5000)
        self.assertTrue(all(min(p[:3]) >= 250 for p in solid))  # flat white stays white
        rows = [i // 1080 for i, p in enumerate(held) if p[3]]
        self.assertAlmostEqual((min(rows) + max(rows)) / 2 / 1920, 0.2, delta=0.02)
        svg = self.d / "logo.svg"
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100" width="200" height="100">'
                       '<circle cx="50" cy="50" r="40" fill="#e84a5f"/><path d="M110 10h80v80h-80z" fill="#2a363b"/>'
                       '</svg>')
        held = title("bt_svg", "--svg", svg)[1]
        cols = {p[:3] for p in held if p[3] == 255}
        self.assertIn((232, 74, 95), cols)  # the logo keeps its own fills
        self.assertIn((42, 54, 59), cols)

    def test_blender_title_outside_blender(self):
        self.assertIn("--text", py("blender_title.py", "--help").stdout)
        p = py("blender_title.py", "--", "--text", "Hi", "--out", self.d / "f_####", ok=False)
        self.assertIn("runs inside Blender", p.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

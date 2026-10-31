#!/usr/bin/env python3
"""Apple Vision tools on synthetic clips: python3 tests/test_vision.py (macOS with swiftc, about a minute).

This ffmpeg has no drawtext, so text cards are drawn by a small CoreText helper and OCR reads real
glyphs. The first OCR run after a boot loads Vision's model and can take half a minute on its own.
"""
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_scripts import SWIFTC, S, ff, frames, py, sh  # noqa: E402

sys.path.insert(0, str(S))

W, H = 720, 1280
# card OUT.png W H RRGGBB item...: text|x|y|size|string or qr|x|y|size|payload, px from the top left.
CARD = r'''
import CoreGraphics
import CoreImage
import CoreText
import Foundation
import ImageIO

let a = CommandLine.arguments
let (w, h) = (Int(a[2])!, Int(a[3])!)
let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                    space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
let bg = UInt32(a[4], radix: 16)!
ctx.setFillColor(red: CGFloat(bg >> 16 & 255) / 255, green: CGFloat(bg >> 8 & 255) / 255, blue: CGFloat(bg & 255) / 255, alpha: 1)
ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
for item in a.dropFirst(5) {
    let f = item.split(separator: "|", maxSplits: 4).map(String.init)
    let (x, y, size) = (CGFloat(Double(f[1])!), CGFloat(Double(f[2])!), CGFloat(Double(f[3])!))
    if f[0] == "qr" {
        let qr = CIFilter(name: "CIQRCodeGenerator", parameters: ["inputMessage": Data(f[4].utf8)])!
        let img = qr.outputImage!.samplingNearest()
        let big = img.transformed(by: CGAffineTransform(scaleX: size / img.extent.width, y: size / img.extent.height))
        ctx.interpolationQuality = .none
        ctx.draw(CIContext().createCGImage(big, from: big.extent)!, in: CGRect(x: x, y: CGFloat(h) - y - size, width: size, height: size))
    } else {
        let font = CTFontCreateWithName("Helvetica-Bold" as CFString, size, nil)
        let attrs: [NSAttributedString.Key: Any] = [.init(kCTFontAttributeName as String): font,
                                                     .init(kCTForegroundColorAttributeName as String): CGColor(gray: 0, alpha: 1)]
        ctx.textPosition = CGPoint(x: x, y: CGFloat(h) - y - CTFontGetAscent(font))
        CTLineDraw(CTLineCreateWithAttributedString(NSAttributedString(string: f[4], attributes: attrs)), ctx)
    }
}
let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: a[1]) as CFURL, "public.png" as CFString, 1, nil)!
CGImageDestinationAddImage(dest, ctx.makeImage()!, nil)
guard CGImageDestinationFinalize(dest) else { exit(1) }
'''
LABEL = [("text", 60, 120, 44, "Thank you for your order"), ("text", 60, 300, 40, "Jane Doe"),
         ("text", 60, 360, 40, "123 Main Street"), ("text", 60, 420, 40, "Springfield, IL 62704"),
         ("text", 60, 520, 36, "(555) 123-4567"), ("text", 60, 600, 36, "jane.doe@example.com"),
         ("qr", 420, 800, 240, "https://example.com/t/1Z999AA10123456784")]
TAG = (40, 200, 150, 300)  # the moving tag's top left at t=0, and its speed in px/s


def tag_at(n: int) -> tuple[int, int]:
    t = n / 30
    return round(TAG[0] + TAG[2] * t), round(TAG[1] + TAG[3] * t)


def luma(path: Path, n: int, x: int, y: int, w: int, h: int) -> list[int]:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"select=eq(n\\,{n}),crop={w}:{h}:{x}:{y}",
                          "-frames:v", "1", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    return list(raw)


def spread(path: Path, n: int, *box) -> float:
    return statistics.pstdev(luma(path, n, *box))


def gap(a: Path, b: Path, n: int, *box) -> float:
    return statistics.fmean(abs(p - q) for p, q in zip(luma(a, n, *box), luma(b, n, *box)))


class Rules(unittest.TestCase):
    """redact.py's patterns: no Vision needed."""

    def test_classify(self):
        from redact import kinds
        hits = {"123 Main Street": "address", "10 Downing St": "address", "Springfield, IL 62704": "address",
                "London SW1A 1AA": "address", "PO Box 4410": "address", "(555) 123-4567": "phone",
                "+44 20 7946 0958": "phone", "07700 900123": "phone", "jane.doe@example.com": "email",
                "www.example.com/x": "url", "barcode:0123456789012": "barcode",
                "1Z 999 AA1 01 2345 6784": "digits", "9400 1000 0000 0000 0000 00": "digits",
                "Order # 112-1234567-1234567": "digits"}
        for text, kind in hits.items():
            self.assertIn(kind, kinds(text), text)
        for text in ("Thank you for your order", "120 ct", "2 way radio", "10 sq ft", "NET WT 12 OZ (340g)",
                     "Best before 2026-10-31", "Fresh coffee daily", "SPF 50"):
            self.assertEqual(kinds(text), {}, text)

    def test_confidence(self):
        # Vision reads upside-down or curved print as garbage at 0.3-0.5; one sure sighting makes a track sure
        from redact import KINDS, SURE, tracks
        phone, street, name = [0.1, 0.5, 0.4, 0.53], [0.1, 0.40, 0.5, 0.43], [0.1, 0.36, 0.5, 0.39]
        samples = [[0, [[*phone, 0.5, "1900 104 5115"], [*street, 0.5, "12 Mill Lane"], [*name, 1.0, "Jane Doe"]]],
                   [3, [[*phone, 0.5, "1900 104 5115"]]]]
        conf = {t["text"]: t["conf"] for t in tracks(samples, 3, 30, set(KINDS)) if t["hits"]}
        self.assertLess(conf["1900 104 5115"], SURE)
        self.assertLess(conf["Jane Doe"], SURE)  # beside an unsure address: no surer than it
        samples[1][1][0][4] = 1.0
        conf = {t["text"]: t["conf"] for t in tracks(samples, 3, 30, set(KINDS)) if t["hits"]}
        self.assertGreaterEqual(conf["1900 104 5115"], SURE)


@unittest.skipUnless(SWIFTC, "the Vision tools need macOS and swiftc")
class Vision(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from _swift import tool
        cls.tool = staticmethod(tool)
        cls.d = d = Path(tempfile.mkdtemp(prefix="video-edit-vision-"))
        (d / "card.swift").write_text(CARD)
        sh("swiftc", "-O", d / "card.swift", "-o", d / "card")

        def card(name, w, h, bg, items):
            sh(d / "card", d / name, w, h, bg, *("|".join(map(str, i)) for i in items))

        def still(png, out, secs, *vf):
            ff("-loop", "1", "-framerate", "30", "-i", d / png, "-t", secs, *vf, "-c:v", "libx264", "-preset",
               "ultrafast", "-pix_fmt", "yuv420p", d / out)

        card("label.png", W, H, "F4F1EA", LABEL)
        still("label.png", "label.mp4", 2)
        # stored on its side with a display matrix, the way a phone keeps a portrait clip
        ff("-i", d / "label.mp4", "-t", 0.5, "-vf", "transpose=2", "-c:v", "libx264", "-preset", "ultrafast",
           d / "coded.mp4")
        ff("-display_rotation", -90, "-i", d / "coded.mp4", "-c", "copy", d / "rotated.mp4")

        card("marks.png", W, H, "F4F1EA", [("text", 60, 200, 56, "CapCut"), ("text", 60, 500, 44, "TikTok made me buy it"),
                                           ("text", 60, 800, 44, "Only $19.99 today")])
        still("marks.png", "marks.mp4", 1)
        card("tag.png", 380, 90, "FFFFFF", [("text", 14, 22, 40, "42 Baker Street")])
        card("plain.png", W, H, "8A8F99", [("text", 60, 1100, 40, "Fresh coffee daily")])
        x0, y0, vx, vy = TAG
        ff("-loop", "1", "-framerate", "30", "-i", d / "plain.png", "-loop", "1", "-framerate", "30", "-i", d / "tag.png",
           "-filter_complex", f"[0][1]overlay=x='{x0}+{vx}*t':y='{y0}+{vy}*t',format=yuv420p", "-t", 2,
           "-c:v", "libx264", "-preset", "ultrafast", d / "moving.mp4")

        ff("-f", "lavfi", "-i", f"color=c=0x303030:s={W}x{H}:r=30:d=2", "-f", "lavfi", "-i", "testsrc2=s=160x160:r=30:d=2",
           "-filter_complex", "[0][1]overlay=x='80+200*t':y='300+150*t'", "-c:v", "libx264", "-preset", "ultrafast",
           d / "square.mp4")

        ff("-f", "lavfi", "-i", f"testsrc2=s={W}x{H}:r=30:d=1", "-frames:v", "1", d / "still.png")
        ff("-loop", "1", "-framerate", "30", "-i", d / "still.png", "-filter_complex",
           "[0]split[a][b];[a]trim=end_frame=24,setpts=PTS-STARTPTS,gblur=sigma=6[soft];"
           "[b]trim=end_frame=36,setpts=PTS-STARTPTS[sharp];[soft][sharp]concat=n=2:v=1:a=0,format=yuv420p",
           "-c:v", "libx264", "-preset", "ultrafast", d / "softfirst.mp4")

        # an apple and a teddy, then the teddy alone: subject lifting finds emoji on a plain ground
        card("both.png", W, H, "FFFFFF", [("text", 40, 500, 260, "\U0001F34E"), ("text", 400, 500, 260, "\U0001F9F8")])
        card("teddy.png", W, H, "FFFFFF", [("text", 400, 500, 260, "\U0001F9F8")])
        still("both.png", "both.mp4", 0.5)
        still("teddy.png", "teddy.mp4", 0.5)
        ff("-i", d / "both.mp4", "-i", d / "teddy.mp4", "-filter_complex", "[0][1]concat=n=2:v=1:a=0",
           "-c:v", "libx264", "-preset", "ultrafast", d / "subject.mp4")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def ocr(self, clip: str, step: int) -> list:
        return json.loads(sh(self.tool("ocr"), self.d / clip, step).stdout)

    def test_ocr(self):
        rows = self.ocr("label.mp4", 15)
        self.assertEqual([f for f, _ in rows], [0, 15, 30, 45])
        found = {r[5]: r for r in rows[0][1]}
        street = found["123 Main Street"]
        self.assertAlmostEqual(street[0], 60 / W, delta=0.01)
        self.assertTrue(street[1] < 380 / H < street[3], street)  # the line's middle, in fractions from the top
        self.assertIn("barcode:https://example.com/t/1Z999AA10123456784", found)
        qr = found["barcode:https://example.com/t/1Z999AA10123456784"]
        self.assertAlmostEqual(qr[0], 420 / W, delta=0.02)
        self.assertAlmostEqual(qr[3], 1040 / H, delta=0.02)
        turned = {r[5]: r for r in self.ocr("rotated.mp4", 15)[0][1]}  # read upright, boxes as ffmpeg shows it
        for a, b in zip(turned["123 Main Street"][:4], street[:4]):
            self.assertAlmostEqual(a, b, delta=0.01)

    def test_qa_screen_text(self):
        import edl
        errs, warns = edl.screen_text(self.d / "label.mp4", 30, [])
        for what in ("a street address", "a phone number", "an email address"):
            self.assertTrue(any(what in e for e in errs), (what, errs))
        self.assertTrue(any("barcode or QR code" in w for w in warns), warns)
        self.assertFalse(any("Thank you" in e or "Jane Doe" in e for e in errs), errs)
        errs, _ = edl.screen_text(self.d / "label.mp4", 30, ["example.com"])
        self.assertFalse(any("email" in e for e in errs), errs)  # --allow skips a line on purpose
        errs, warns = edl.screen_text(self.d / "marks.mp4", 30, [])
        self.assertEqual(len(errs), 1, errs)
        self.assertIn("watermark", errs[0])  # "CapCut" alone is a watermark...
        self.assertTrue(any("an app name" in w and "made me buy" in w for w in warns), warns)  # ...a sentence is not
        self.assertTrue(any("a price" in w for w in warns), warns)

    def test_track(self):
        def truth(n):
            t = n / 30
            return (80 + 200 * t) / W, (300 + 150 * t) / H, (240 + 200 * t) / W, (460 + 150 * t) / H

        start = ",".join(f"{v:.4f}" for v in truth(0))
        rows = json.loads(sh(self.tool("track"), self.d / "square.mp4", 0, start).stdout)
        self.assertEqual([f for f, _ in rows], list(range(60)))
        for f in (30, 59):
            box, want = rows[f][1], truth(f)
            self.assertAlmostEqual((box[0] + box[2]) / 2, (want[0] + want[2]) / 2, delta=0.03, msg=f)
            self.assertAlmostEqual((box[1] + box[3]) / 2, (want[1] + want[3]) / 2, delta=0.03, msg=f)
        part = json.loads(sh(self.tool("track"), self.d / "square.mp4", 10, ",".join(f"{v:.4f}" for v in truth(10)),
                             "--to", 30).stdout)
        self.assertEqual((part[0][0], part[-1][0]), (10, 30))
        p = sh(self.tool("track"), self.d / "square.mp4", 0, "0.9,0.1,0.95,0.15")  # empty ground: lost at once
        self.assertIn("lost at frame", p.stderr)

    def test_redact_still(self):
        d = self.d
        dry = py("redact.py", d / "label.mp4", d / "x.mp4", "--dry-run", "--sheet", d / "regions.jpg")
        regions = json.loads(dry.stdout)["regions"]
        self.assertTrue(all(r["sure"] for r in regions), regions)  # clean print reads at full confidence
        self.assertGreater((d / "regions.jpg").stat().st_size, 5000)
        self.assertEqual({r["kind"] for r in regions}, {"address", "phone", "email", "barcode"})
        texts = " ".join(r["text"] for r in regions)
        self.assertIn("Jane Doe", texts)  # the name line goes with the address below it
        self.assertNotIn("Thank you", texts)
        self.assertIn("123 Main Street", dry.stderr)  # each region and what triggered it
        self.assertFalse((d / "x.mp4").exists())
        # the dry run, edited (QR dropped) and rendered as a black box: OCR does not run again
        kept = [r for r in regions if r["kind"] != "barcode"]
        (d / "edited.json").write_text(json.dumps({"regions": kept}))
        out = d / "label_box.mp4"
        py("redact.py", d / "label.mp4", out, "--regions", d / "edited.json", "--style", "box")
        self.assertEqual(frames(out), frames(d / "label.mp4"))
        street = (70, 366, 300, 30)
        self.assertLess(max(luma(out, 30, *street)), 30)  # solid black
        self.assertLess(gap(out, d / "label.mp4", 30, 70, 126, 500, 34), 3)  # "Thank you..." untouched
        self.assertLess(gap(out, d / "label.mp4", 30, 440, 820, 200, 200), 3)  # the QR, left in by the edit
        only = json.loads(py("redact.py", d / "label.mp4", d / "x.mp4", "--find", "phone", "--dry-run",
                             "--box", "0.1,0.1,0.2,0.2@0.5-1").stdout)["regions"]
        self.assertEqual([r["kind"] for r in only], ["phone", "box"])
        self.assertEqual([only[1]["keys"][0][0], only[1]["keys"][-1][0]], [15, 30])

    def test_redact_moving(self):
        d = self.d
        out = d / "moving_blur.mp4"
        p = py("redact.py", d / "moving.mp4", out, "--pad", 0)  # no pad: the box itself must follow
        self.assertIn("42 Baker Street", p.stderr)
        self.assertEqual(frames(out), frames(d / "moving.mp4"))
        for n in (0, 1, 2, 4, 5, 10, 29, 44, 58, 59):  # on samples, between them, and held at the ends
            x, y = tag_at(n)
            text = (x + 20, y + 28, 280, 28)
            before, after = spread(d / "moving.mp4", n, *text), spread(out, n, *text)
            self.assertGreater(before, 40, n)
            self.assertLess(after, min(25, before * 0.35), f"frame {n}: {after:.1f} vs {before:.1f}")
        self.assertLess(gap(out, d / "moving.mp4", 30, 60, 1100, 380, 40), 3)  # "Fresh coffee daily" stays

    def test_redact_track(self):
        d = self.d
        p = py("redact.py", d / "square.mp4", d / "x.mp4", "--find", "email", "--dry-run",
               "--track", f"{80 / W:.4f},{300 / H:.4f},{240 / W:.4f},{460 / H:.4f}@0")
        (r,) = json.loads(p.stdout)["regions"]
        self.assertEqual((r["kind"], r["keys"][0][0], r["keys"][-1][0]), ("track", 0, 59))
        self.assertAlmostEqual((r["keys"][-1][1] + r["keys"][-1][3]) / 2, (160 + 200 * 59 / 30) / W, delta=0.03)

    def test_cover(self):
        d = self.d
        out, meta, sheet = d / "cover.jpg", d / "cover.json", d / "top.jpg"
        py("cover.py", d / "softfirst.mp4", out, "--json", meta, "--top", 3, sheet)
        m = json.loads(meta.read_text())
        self.assertGreaterEqual(m["frame"], 24)  # the soft first 24 frames never win
        self.assertTrue(all(t["frame"] >= 24 for t in m["top"]), m["top"])
        self.assertEqual(m["title_box"], [0, 0.125, 1, 0.875])  # no face: the whole grid crop
        size = sh("ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", out).stdout
        self.assertEqual(size.strip(), f"{W},{H}")
        self.assertGreater(sheet.stat().st_size, 1000)
        from cover import title_box
        face = {"faces": [[0.3, 0.3, 0.7, 0.5, 0.9, 0.3, 0.3]]}  # grown: 0.22 (hair) to 0.516 (chin)
        self.assertEqual(title_box(face, [0, 0.125, 1, 0.875]), [0, 0.516, 1, 0.875])

    def test_matte_subject(self):
        d = self.d
        matte = self.tool("matte")
        everything = sh(matte, d / "subject.mp4", d / "all.mp4", "--subject", "all").stdout
        if " in 0" in everything:
            self.skipTest(f"Vision found no subject in the synthetic card: {everything.strip()}")
        apple, teddy = (40, 520, 260, 260), (400, 520, 260, 260)

        def lit(mask, n, box):
            return statistics.fmean(luma(mask, n, *box))

        self.assertEqual(frames(d / "all.mp4"), frames(d / "subject.mp4"))
        self.assertGreater(lit(d / "all.mp4", 5, apple), 60)
        self.assertGreater(lit(d / "all.mp4", 5, teddy), 60)
        self.assertLess(lit(d / "all.mp4", 25, apple), 5)  # the apple has gone
        sh(matte, d / "subject.mp4", d / "pick.mp4", "--subject", f"{170 / W:.3f},{650 / H:.3f}")
        self.assertGreater(lit(d / "pick.mp4", 5, apple), 60)
        self.assertLess(lit(d / "pick.mp4", 5, teddy), 5)  # only the instance under the point
        self.assertEqual(luma(d / "pick.mp4", 25, *apple), luma(d / "pick.mp4", 14, *apple))  # held on background
        self.assertLess(lit(d / "pick.mp4", 25, teddy), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)

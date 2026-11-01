# Render, QA and delivery

Read for steps 8 and 9: the final encode, platform limits, the checks a render must pass, and
handing it over.

## One master

Render one file and send it everywhere. Every platform re-encodes uploads, so the master carries
as much quality as the upload limits allow; a pre-shrunk copy is re-encoded twice and looks it.
Never transcode a smaller copy to fit a chat or email limit: send the master as-is, or a link.

| Setting | Value | Why |
|---|---|---|
| Size, fps | 1080x1920, 30 (or the source's 24/25/60 kept as shot) | 9:16 everywhere; never change fps mid-pipeline |
| Video | H.264 `libx264 -preset slow -crf 15`, `yuv420p`, high profile | Near-transparent; every app decodes it |
| Colour | BT.709 primaries, transfer and matrix, limited range | Untagged files shift colour in the apps |
| Audio | AAC-LC 48 kHz stereo, 320 kbps; -14 LUFS, -1 dBTP | references/audio.md |
| Container | MP4, `-movflags +faststart` | moov first: previews and uploads start at once |

- `edl.py render` writes all of this. ffmpeg 8's `-color_primaries/-color_trc/-colorspace` flags
  tag only the matrix, and `setparams` only relabels. Writing ffmpeg by hand, convert in the scale
  (`scale=...:out_color_matrix=bt709:out_range=tv`), then end the video chain with
  `setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv`.
- `scale` reads an untagged clip as BT.601. `edl.py` names the matrix for it (`in_color_matrix`:
  BT.709 at 1280 px or more, BT.601 below), so tag what you make: RGB frames (PNG, Blender) are
  encoded with the 709 matrix and tagged, as `blender_title.py` prints.
- Remotion renders: `npx remotion render --codec h264 --crf 15 --color-space bt709`, then
  `master.py mix` for the audio (it copies the video stream).
- HDR (iPhone HLG/Dolby Vision) is converted at intake (`edl.py conform`), never left for the
  platform: Reels and TikTok tone-map HDR unevenly.
- `--draft` (veryfast, CRF 23) for looking at cuts only; never hand a draft over.

## Platform limits

Check current help pages before relying on a number; these move.

| Platform | Limits that bite |
|---|---|
| Instagram Reels | API uploads: at most 25 Mbps video, 300 MB, 23-60 fps, 3 s-15 min. Reels over 3:00 are not recommended to non-followers. App uploads take larger files. |
| TikTok | 9:16 1080x1920 recommended; MP4 or MOV. Branded-content and music rules: references/audio.md |
| YouTube Shorts | Square or vertical, up to 3:00 to count as a Short. H.264 high profile, closed GOP of half the frame rate, AAC 48 kHz. |

A CRF 15 master of grainy footage can pass 25 Mbps; `edl.py qa` prints the bitrate and notes
when an API upload would refuse it (re-render that one file at CRF 17-18; never resize).

## QA

```bash
python3 scripts/edl.py qa work/edit.json renders/final.mp4 --sheet work/qa.jpg
```

`qa` fails (exit 1) on: codec, pixel format, size or fps unlike the EDL; missing BT.709 tags; a
frame count unlike the EDL's timeline; audio not AAC 48 kHz stereo; audio more than 0.05 s off the
picture; moov after mdat; loudness more than 0.5 LU off target or true peak over it
(`--no-loudness` for a voice-only draft). `--sheet` grabs the frame just after every cut,
transition and cutaway edge, plus the first and last.

On macOS it also reads the text on screen every half second (`ocr.swift`; `--no-ocr` skips it,
`--allow WORD` passes a brand's own URL or name) and measures levels. What each line means:

| Line | Level | Meaning and fix |
|---|---|---|
| `another app's watermark or credit` | error | A line reading only TikTok, CapCut or "Made with ...": re-export the source without it, or cover it |
| `an email address` / `a phone number` / `a street address` / `a postcode` / `a tracking number` on screen | error | Private details: `redact.py` (below) |
| `a barcode or QR code` | warn | A shipping label's code holds the address: blur it; a product's own code can stay |
| `a price on screen` | warn | Fine unless the project forbids prices (Amazon affiliates: never) |
| `a URL on screen` | warn | Check it is the person's or the brand's; never a link shortener |
| `an app name on screen` | warn | Fine when it is the point ("TikTok made me buy it"); a leftover watermark is not |
| `the sound pops at the cut` | warn | A step in the audio within 3 ms of a cut, at least 4 times steeper than any in the 100 ms around it: give the segment an `afade` (0.008 s is the default; 0 removes it) or move the cut into quiet with `quiet.py snap`. Listen at that second before posting |
| `highlights clip` / `shadows crush` | note | Over 20% of a segment's frames at the limits: grade.md |
| `segment N is brighter (darker, warmer, cooler) than the shot before` | note | Two takes that should match do not: `match.py` |
| `possibly ... (OCR unsure): look at the frame` | warn | Vision read it at low confidence: usually upside-down or curved print. Look; a real address still needs `redact.py` |
| `on-screen text not read` | warn | Not on macOS, or `ocr.swift` missing: read the sheet for text by eye |

## Privacy blur

`redact.py final.mp4 renders/final.redacted.mp4 --dry-run --sheet work/regions.jpg > work/regions.json`
finds addresses, phone numbers, emails, barcodes and long numbers on screen (Apple Vision OCR),
lists each with the text that triggered it and draws them on one sheet. Look at the sheet:

- A region marked `unsure` was never read with full confidence. On real footage these are usually
  upside-down packaging print and curved embroidery read as garbage that looks like a number. When
  the sheet shows every unsure region is print, render with `--sure-only`; otherwise delete the false
  ones from the JSON and render with `--regions work/regions.json`.
- On product shots use `--find address,phone,email,barcode` so the brand's URL stays readable.
- `--box x0,y0,x1,y1@T0-T1` covers what OCR missed (handwriting, sideways or tiny print, a blurred
  label), `--track x0,y0,x1,y1@T` follows a thing that moves. The address patterns are US and UK.
- `--style box` is the only cover nothing can undo; blurred or pixelated text can be read back.

Run it on the final render, then watch it: OCR misses handwriting and text under about 1.2% of the
frame height, and a fast pan needs `--step 1`.

## Cover

`cover.py work/graded.mp4 renders/cover.jpg --json work/cover.json --top 6 work/covers.jpg` scores
the graded cut before captions (a half-sentence caption on a cover reads badly), drops frames with
eyes shut or lowered or the head looking down, keeps sharp ones, ranks by Apple Vision's aesthetics,
writes the best and a sheet of the next five, and gives `title_box`: the band of the profile-grid
crop (Instagram shows the centre 3:4) clear of every face, for a cover title. Upload the picture as
the custom cover. Pick from the sheet when the top frame is not the story's moment.

Then look at the sheet, and fix in code anything that fails:

- Every cut lands on a finished word and the next shot reads as intended; no flash frames.
- Text inside the safe zone, never over a face (rerun `place.py` on the final timeline after any
  re-cut: faces move with the cut), and readable: white on a bright background needs the shadow,
  or a move.
- Captions match the words, brand names spelled the brand's way, nothing left from a dropped line.
- Hook on frame 0, CTA in the last 1.5-2.5 s, nothing cut off at the end.
- Length fits the plan; the project's compliance checks (disclosure, claims, no burned-in price
  where the project bans it) pass.

## Deliver

One best edit, with its caption text ready to paste. The person reviews and posts it; never
upload, schedule or post for them. Keep the EDL, plan and placed captions next to the render so a
fix re-renders the same edit rather than starting over.

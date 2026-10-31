# Transcribe, caption, place text

Read for step 3 (word timings) and for burned-in captions, hook and CTA text in step 6.

## Word timings

Pick by machine and privacy; default to local.

| Tool | Use when | Notes |
|---|---|---|
| WhisperX (BSD-2) | Cuts and captions on any OS | Whisper ASR, then wav2vec2 forced alignment: the edit-grade word edges. macOS runs CPU int8. Python < 3.14. Bundles pyannote VAD. |
| mlx-whisper (MIT) | Fast draft transcript on Apple Silicon | `word_timestamps=True`; decoder word times are not edit-grade, so align after |
| parakeet-mlx (Apache-2.0 code) | Fast English on Apple Silicon | Token timestamps; check the model weights' licence before shipping it |
| faster-whisper (MIT) | Linux or CUDA | `vad_filter` drops only silences over 2 s by default |
| whisper.cpp (MIT) | No Python, Metal | `-ml 1` word times are "experimental"; Remotion's wrapper needs `--dtw` |
| Deepgram, AssemblyAI (paid) | Local fails, or fillers must be found | Cloud: the person's voice leaves the machine, so ask first. Deepgram drops "uh/um" unless `filler_words=true` |

Rules that hold for every engine:

- **Spell numerals out before aligning** ("50" to "fifty", "$10" to "ten dollars") and fold them
  back for display. Aligners give no timing to digits and symbols; a word with no `start` is the
  signal. Diff the word count after alignment.
- **Fit word ends to the audio.** ASR ends drift into the next breath or stop short of a trailing
  consonant. Cut against measured quiet (`quiet.py`), never against raw ASR ends.
- Request fillers at ASR time if the edit should find them; most engines hide them by default.
- Never send transcripts of unpublished videos to git.

## Phrase captions

`captions.py WORDS.json -f json --fps 30` groups words into phrases of at most two lines and
`--max-chars` per line (32 default for 1080-wide vertical; Netflix allows 42 for 16:9), breaking at
clause boundaries and pauses, never after an article, preposition or conjunction, and never leaving
a 1-2 word top line or a stranded short word. Each phrase shows `--lead` (0.15 s) before its first
word and bridges gaps under 0.6 s, so captions do not flicker off between phrases.

| Rule | Number | Source |
|---|---|---|
| Lines per caption | at most 2, bottom-heavy | Netflix, DCMP |
| Reading speed | at most 20 characters/s (condense, never speed up) | Netflix |
| Duration | about 0.83 s minimum (single word), 6 s maximum; 1.33 s minimum for short-form pages | Netflix, DCMP |
| Gap between captions | 2 frames minimum, or at least 0.5 s | Netflix |
| Sync | in-time on the first audio frame, within 1-2 frames; showing 0.1-0.2 s early reads better on phones | Netflix, practice |
| Shot changes | snap a caption that starts within 0.5 s after a cut to the cut | Netflix |
| Numbers | spell zero to ten, numerals above; numerals for ages and prices on screen only when the project allows prices | Netflix |
| Short-form chunking | 3-5 words conversational, 4-6 calm, 2-3 high-energy; one phrase on screen at a time | practice (vendor, no study) |

Style default (override with the project's brand rules): white bold sans (TikTok Sans 700, OFL),
soft drop shadow, no outline, no box, phrase fades in over 3-4 frames, no word picked out.
A translucent box is the fix when a frame is bright behind the text (DCMP prefers one on light
backgrounds); check contrast against the brightest pixels under the caption for its whole
duration (WCAG 2.2: 4.5:1, or 3:1 for text 24 px or larger).

Fonts: all OFL and on Google Fonts; use a static instance for libass and Blender. The eight after
TikTok Sans are the ones Chockstone's phone ships; `em/char` is its line-break figure (Core Text at
weight 800, times 1.19), so line width / (font size x em/char) = characters per line.

| Font | Kind | Weight | em/char | Good for |
|---|---|---|---|---|
| TikTok Sans | sans | 700 | | Captions, hook, CTA (the default) |
| Inter | sans | 600 | 0.58 | Captions (Chockstone `clean`) |
| DM Sans | sans | 700 | 0.57 | Captions on a box (`boxed`) |
| Rubik | rounded | 700 | 0.59 | Friendly captions |
| Archivo Black | display, one weight | 400 | 0.65 | Outlined captions (`bold`), titles |
| Anton | condensed display, one weight | 400 | 0.48 | Word-pop captions (`pop`), text behind a person |
| Bebas Neue | condensed caps, one weight | 400 | 0.40 | Caps titles, text behind a person |
| Playfair Display | serif | 700 | 0.54 | Calm lifestyle titles |
| Caveat | handwriting | 700 | 0.40 | A short note or label, never a whole caption |

Display faces for titles, covers and set pieces (looks.md), never captions; set them at 80 px or more
and pair one with a plain sans for the captions. All OFL on Google Fonts:

| Font | Kind | Good for |
|---|---|---|
| Instrument Serif | condensed editorial serif, regular and italic | Calm lifestyle titles, quotes |
| DM Serif Display | high-contrast serif | Recipe and product titles |
| Fraunces | soft serif, variable | Cosy, food, home |
| Bodoni Moda | didone, 400-900 | Magazine mastheads |
| Cormorant Garamond | light classic serif | Beauty, elegant quotes |
| Gloock | heavy high-contrast serif | Bold headlines, headline wall |
| Italiana | thin fashion caps | Luxury labels |
| Syne | wide geometric sans | Fashion, art |
| Bricolage Grotesque | quirky grotesque, variable | Modern brand titles |
| Space Grotesk | technical sans | Numbers, charts |
| Unbounded | rounded wide display | Playful, tech |
| Great Vibes | formal script | One word or a signature |

Fontshare faces (Clash Display, Satoshi, General Sans) are free for commercial use under the ITF
Free Font License but are not on Google Fonts; bundle the files.

## Word highlights

The calm style picks out no word. An energetic style may light the word being said:
`PhraseCaptions highlight=` `color` (the word turns `brand.colors.highlight`), `box` (an accent
chip behind it), `pop` (the word scales up a little) or `karaoke` (it fills left to right as it is
said). It needs `captions.py --fps`, which gives each phrase its words in frames; a phrase whose
words do not match shows plain. One mode per video. Colours come from `brand.json` (looks.md);
check a highlight colour against the brightest background it crosses.

## Output formats

- `-f json`: phrases with frames, for `templates/remotion/PhraseCaptions.tsx` and `place.py`.
- `-f remotion`: `Caption[]` for `@remotion/captions` (each token carries its leading space).
- `-f srt` / `-f vtt`: sidecar files for platforms that accept uploads, and for accessibility.
- `-f ass`: styled for libass with `PlayResX/Y` = the video size.

**Burn-in path.** Check first: `ffmpeg -hide_banner -filters | grep -E ' (subtitles|ass) '`.
Homebrew's ffmpeg 8.1 has no libass (and no drawtext), so burn captions in Remotion
(`PhraseCaptions.tsx`) or in Chockstone's renderer. With a libass build:
`ffmpeg -i in.mp4 -vf "ass=caps.ass:fontsdir=fonts" ...`, using a static font instance (libass and
variable fonts are unverified). `pysubs2` (MIT) builds, retimes and converts ASS/SRT in Python.

## Safe zones (1080x1920)

What each app draws over an organic post (2026-10, from TikTok's and Meta's ad templates and
third-party measurements; no platform publishes organic numbers, and "est." marks an estimate).
Re-measure from a phone screen recording each quarter.

| Platform | Top bar ends | Right rail starts | Bottom block starts | Text box |
|---|---|---|---|---|
| TikTok | y 130 (tabs, search) | x 940, from y 840 | y 1436, higher as the caption grows | x 44-940, y 130-1436 |
| Reels | y 250 (header) | x 960, lower half | y 1600 | x 86-960, y 250-1600 |
| Shorts | y 288 (search, menu) | x 888 | about y 1450 (est.; Google's ad figure is 1248) | x 48-888, y 288-1450 |
| All three, organic | | | | x 90-890, y 290-1400 |
| All three, ads (CTA button) | | | | x 120-888, y 288-1248 |
| Instagram and Facebook Stories, Reels ads (Meta's ad guide) | y 269 (14%) | x 1015 (6% each side) | y 1248 (35%) | x 65-1015, y 269-1248 |
| Facebook Reels, organic | about y 250 (unconfirmed) | | about y 1670 (unconfirmed) | use the shared box |
| Pinterest video Pin | y 270 | x 885 | y 1130 | x 65-885, y 270-1130 |

Text goes inside the shared box unless the video targets one platform. Captions sit low in it
(bottom edge at most y 1400); hook text sits high (top edge near y 290-420). Projects record their
own measured box; prefer it. A video bound for Pinterest or Stories needs that row's tighter box.

**Grid crops.** Profile grids show the cover cut down: Instagram's grid is 3:4 since January 2025
(the centre 1080x1440, y 240-1680), a Reel in the Instagram feed shows 4:5 (y 285-1635), and
TikTok's grid is about 3:4 (centring unconfirmed for all three). Keep a cover's text and the face
inside y 300-1620 so every crop keeps them; render.md has the cover picker.

## Text off faces

```bash
swiftc -O scripts/faces.swift -o ~/.cache/video-edit/faces    # once, macOS 12+
~/.cache/video-edit/faces work/draft.mp4 3 30 > work/faces.json # every 3rd frame of the CUT
python3 scripts/captions.py work/timeline.words.json -f json --fps 30 -o work/caps.json
python3 scripts/place.py work/faces.json work/caps.json -o work/caps.placed.json
python3 scripts/place.py work/faces.json work/titles.json --kind title -o work/titles.placed.json
```

Run faces on the cut (a draft render), not the sources: cuts, zooms and cutaways move faces.
`place.py` grows each face box for hair and chin, then moves each phrase to the clear spot nearest
its usual one. Exit 1 lists phrases with no clear spot: shorten them, set them smaller, or let the
caption wait until the face moves. Never ship text on a face. Off macOS, MediaPipe Face Detector
(Apache-2.0) gives the same boxes; write them in the same JSON shape.

Measure text as the renderer sets it: `--font-size`, `--line-height` and `--em` must match the
Remotion style, and a glyph the font lacks (an emoji, a heart) counts a full em.

## Hook, CTA, titles

- Hook text: at most 7 words and 2 lines, on screen from frame 0, held at least characters/20
  seconds (a 40-character hook holds 2 s), then faded out. It holds still: no bounce, slide or pop.
- CTA: last 1.5-2.5 s, inside the safe box, off the face.
- Disclosure lines a law or platform requires go in plain words where the project's rules say,
  usually the caption text and spoken early, never hidden in a corner.

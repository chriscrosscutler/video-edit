---
name: video-edit
description: Plan, cut, caption, animate and render video with code. Use for any request to edit footage or make a video (short-form Reels, TikTok, Shorts, talking head, product demo, tutorial, explainer), to write an edit plan or EDL, choose cuts, B-roll or transitions, make captions or subtitles, titles, motion graphics or animation (Remotion, ffmpeg, Blender), mix music and loudness, set render or export settings, check a render, or edit a Chockstone post's video.
---

# video-edit

Footage in, one finished video out. The model makes the editorial calls; code does all timing,
frame-exact. Every stage reads and writes one edit decision list (EDL, `scripts/edl.py`), so
stages swap freely: cut in ffmpeg, layer in Remotion or Blender, or drive Chockstone's editor.

## Rules

1. **The model chooses, code times.** Pick lines by index and shots by id; never ask a model for
   a timestamp. Cut points come from word timings fitted to the audio, then rounded to frames.
2. **Look before planning.** `probe.py` every file, `sheet.py` every clip. A take with no speech
   is footage (a demo, B-roll), not dead air: cut it into steps or play it as an interlude.
3. **Never cut off a word.** Cuts land in measured quiet (`quiet.py snap`) and move outward, never
   inward. Spell numerals out before aligning; aligners cannot time digits. A "lands in sound"
   warning is a bug to fix (voice detector, another boundary), never a chore for the person.
4. **Story first; pace is a style choice.** A cut drops a line, shows what is said, or hides a
   fumble. Default calm: cut only dead air (a cut must save 0.6 s), no shot under 2 s, actions whole
   and in real time, shorten by dropping lines. For energy: speed ramps, punch-ins, sound effects,
   word highlights (cut.md, audio.md, captions.md). Rule 3 never bends.
5. **Text stays readable and off faces.** Inside the safe zone, never over a face (`place.py`),
   phrase captions of at most two lines shown 0.1-0.2 s early.
6. **Audio is half the video.** Clean voice, takes matched, music 15-20 dB under speech, master
   -14 LUFS and -1 dBTP with one gain and a limiter (`master.py`). Music and sound effects only under
   a licence that covers the use (references/compliance.md); an effect marks a moment on screen.
7. **Conform once, render once.** HDR to SDR, variable to constant frame rate, rotation baked, at
   intake (`edl.py conform`). Master at CRF 15 or better and hand that file over; never re-encode
   a smaller copy.
8. **QA in code, then by looking.** `edl.py check` before rendering; `edl.py qa --sheet` after
   (format, frames, sync, tags, loudness, a frame after every change). Fix in code, re-render.
9. **Hand over finished work.** One best edit unless the person asks for variants (an A/B test,
   cuts per platform), and no "listen to this spot" questions. Ask only what code cannot decide and
   that blocks delivery.

Never publish, schedule or post anything; the person posts. Sponsored and affiliate videos disclose
in the video itself, and nothing private shows on screen (references/compliance.md). Never commit
media, transcripts of unpublished videos, keys or licence files. Uploading someone's voice or face
to a cloud service needs their OK; default to local tools. Paid tools and stock need a yes first.

## Flow

| Step | Do | Read |
|---|---|---|
| 0 Shoot | Give the person the filming guide; pick the content type's recipe | references/plan.md, cookbook.md |
| 1 Organize | One folder per video: `takes/`, `broll/`, `hooks/`, `logos/`, `music/`, `work/` (cache), `renders/`. `edl.py conform` into `work/`. Read the folder's `notes.md` first; add to it before ending | references/plan.md |
| 2 Look | `probe.py --levels`, `sheet.py` per clip; note silent takes and the louder mic | references/plan.md |
| 3 Transcribe | Word timings (WhisperX or another aligner), numerals spelled out, fitted to audio | references/captions.md |
| 4 Plan | `lines.py` numbers the lines and marks retakes; story beats, lines kept and dropped by index, hook, B-roll and interludes, one best variant | references/plan.md |
| 5 Cut | Write the EDL; `quiet.py snap`; `edl.py check`; `edl.py render --draft`. Split edits, speed, two cameras, reframing, clips from long videos | references/cut.md |
| 6 Layer | Captions, titles, logos, transitions, motion graphics, set pieces, 3D | references/captions.md, transitions.md, motion.md, looks.md, blender.md |
| 7 Grade and mix | Match takes, one look; voice clean-up, music bed, master | references/grade.md, audio.md |
| 8 Render | Final render, encode, platform checks | references/render.md |
| 9 QA and deliver | Sheets at every change, loudness, length, safe zones, text on face and on-screen text; privacy blur; cover; one file handed over | references/render.md, compliance.md |
| 10 Learn | Read the posted video's retention against its EDL | references/cut.md |

Chockstone posts: its iPhone app records, cuts and renders; edit through its MCP tools instead of
ffmpeg. Read references/chockstone.md. Libraries and repos, with licences: references/sources.md.
Something looks or sounds wrong, or a term is unclear: references/troubleshooting.md.

## Scripts

`scripts/`, Python 3.10+ standard library plus ffmpeg 7+; `--help` on each gives flags and examples.
The `.swift` tools (faces, matte, ocr, track, cover) use Apple Vision and build on first use (macOS).

- Look: `probe.py`, `sheet.py`. Plan: `lines.py` (numbered lines, retakes, fillers). Cut: `quiet.py`
  (quiet, snap, room tone), `edl.py` (conform, check, words, render, qa), `sync.py` (two cameras),
  `reframe.py` (16:9 to 9:16), `clips.py` (long to short).
- Layer: `captions.py`, `place.py` (off faces), `typeon.py` (typed title and key sounds),
  `blender_title.py`, `templates/remotion/` (captions with highlights, Looks, Layouts, `brand.json`).
- Grade and mix: `match.py`, `master.py`. Deliver: `redact.py` (privacy blur), `cover.py`.
  Learn: `retention.py`.

Tests: `python3 tests/test_scripts.py`; `tests/test_vision.py` for the Apple Vision tools.

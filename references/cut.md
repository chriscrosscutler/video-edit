# Cut

Read for step 5: turning the plan into a timed EDL, snapping it to the audio, checking it and
rendering a draft. Flags are in each script's `--help`.

## What a cut is for

A cut drops a line, shows what is being said, or hides a fumble. When a cut cannot serve every
goal, give up the lower ones first (Walter Murch's order): emotion, then story, rhythm, eye trace,
screen direction, spatial continuity. Never trade emotion or story for rhythm.

The rules below are the calm house style, the default. A person or brand who wants energy gets it:
speed ramps, punch-ins, sound effects and word highlights (below, audio.md, captions.md). Never
cutting off a word holds in every style.

- **Dead air only.** Cut a pause only when the cut saves 0.6 s or more; shorter pauses are breaths
  and play. To shorten a video, drop lines; never tighten the person's pauses.
- **Shots hold.** At least 2 s of a shot between two visible changes. Long holds on a face are fine.
- **Actions play whole.** Never cut into or out of an action midway (pouring, applying, opening a
  box). If two actions inside one clip must join, use a soft 0.6 s dissolve. "Cut on motion" in
  editing books means joining two angles mid-gesture, not cutting the gesture short.
- **Real time.** Footage plays at its own speed. An action longer than the line that names it plays
  as an interlude after the line (the voice pauses, the clip runs with its own sound under it).
- **Jump cuts** inside one take are acceptable to remove dead air in a talking head; if one jars
  (head jumps across frame), cover it with a cutaway or a 0.2-0.3 s punch-in (`zoom` 1.1-1.15) on the
  second shot.

## Word timings first

Cuts come from word timings fitted to the audio (references/captions.md has the ASR choices):

1. Transcribe with word timestamps, numerals spelled out (aligners give digits no timing).
2. `_words.py` normalizes WhisperX, faster-whisper, mlx-whisper, Deepgram or Remotion output to
   `[{text, start, end}]` and fills untimed words between their neighbours.
3. Split lines with one splitter, print `index: start-end text`, and plan by those indices.

## Writing the EDL

`edl.py --help` has the schema. A segment per kept run of lines, in source seconds:

- `in` = first kept word's start, `out` = last kept word's end. Do not pad by hand; `quiet.py
  snap` moves edges out into the pause.
- Consecutive lines with less than 0.6 s between them belong to one segment.
- Held lines: `out` = last word + 0.8 s, `snap: false` if the edge must stay.
- Cutaways (`cutaways[]`) cover picture only; the voice runs on. Start and end each on a word,
  2-6 s long, never in the first 1.5 s. That is an L/J cut for free: voice continues under the
  B-roll and leads back into the face.
- Interludes are ordinary segments from the B-roll source with `gain_db: -12` and `afade: 0.25`.
- Multi-take joins: when two takes of the same set-up meet, a 16-frame `fade` transition hides the
  jump; the audio still cuts hard on the word.

## Split edits (J and L cuts)

A cutaway is already a split edit: the voice runs under it. Between two segments, `audio_lead`
(frames) starts the next segment's sound under the end of the previous picture (a J cut: the viewer
hears the next scene first), and `audio_trail` runs a segment's sound on under the next picture
(an L cut). Use one where a hard cut feels abrupt: a new place, a reaction, a laugh that carries.
6-15 frames is typical. The source needs that much room before `in` (or after `out`); `check`
says when it does not. Words follow the sound, so captions stay on the voice.

## Speed and ramps

Off in the calm style. When the style wants pace:

- `"speed": 2` plays a segment at twice speed, its voice time-stretched with pitch kept (natural up
  to about 1.5x). `0.5` is slow motion, repeating frames; add `"smooth": true` to interpolate new
  ones (slow to render). Shoot 60 fps for slow motion that holds up.
- A ramp: `"speed": [[0, 1], [0.35, 1], [0.45, 5], [0.85, 5], [1, 1]]`, keys of (position in the
  segment's source span 0-1, rate). Ramps mute the source sound (room tone fills it); lay music or an
  effect over them. Typical: real time at both ends of a process, fast through the dull middle
  (taping a box, a long pour); or a ramp down into slow motion on a reveal.
- The timeline length follows the rate (3 s at 2x is 1.5 s). Sped segments take no transition or
  split edit.

## Two cameras

1. Start both recording and clap once on camera.
2. `sync.py main.mov phone2.mov` prints phone2's offset; confidence over 1.5 is a sure match.
3. In the EDL, `"c2": {"path": "phone2.mov", "offset": 1.32}` and every segment in the main
   camera's clock. Switching angles is changing `src`; `"audio_src": "t1"` keeps the main mic under
   the other angle (words come from the audio source).
4. Match colour: `match.py main.mov phone2.mov --region 0.3,0.2,0.7,0.5` (on the face) prints a
   `grade` for c2's segments.

Switch angles on a new thought, a reaction, or to hide a jump cut; hold each angle 2 s or more.

## Reframing and clips from long videos

- `reframe.py wide.mp4 work/tall.mp4` crops 16:9 to 9:16 following the biggest face: still while
  the face stays near centre, an eased move when it shifts, a jump at a cut. A 1080p source cropped
  to vertical is 608 px wide and upscales 1.8x; shoot 4K when the edit will reframe. Two people:
  reframe each to its own file, or use a split screen (looks.md).
- `clips.py talk.words.json` lists 20-60 s stretches that start and end on sentence boundaries,
  with their first and last words; `[needs setup]` marks a start that leans on earlier context.
  Pick the ones that open on a claim, question or number and end on a payoff, then
  `--pick 3,7 --src talk.mp4 -o clips/` writes an EDL per clip to snap, trim and reframe.

## Snap, check, draft

```bash
python3 scripts/quiet.py snap edl.json -o edl.snapped.json
python3 scripts/edl.py check edl.snapped.json
python3 scripts/edl.py render edl.snapped.json work/draft.mp4 --draft
python3 scripts/sheet.py work/draft.mp4 work/draft.jpg --every 1
```

`quiet.py snap` measures quiet from the source's own loudness (integrated LUFS - 14 dB, so a quiet
mic and a hot mic both work), keeps an edge already in quiet, moves an edge in speech outward to the
nearest pause within 0.6 s without crossing a whole word, and joins same-source segments whose gap
would save under 0.6 s. It never moves an edge inward, so a kept word is never shortened.

| Message | Meaning | Fix in code or the EDL |
|---|---|---|
| `lands in sound` | No quiet within reach of an edge (run-on speech, room noise, music under voice) | Use a voice detector (pyannote, silero-vad) for "not speaking" in noise; or move the cut to another line boundary |
| `saves only` | A cut removes under 0.6 s | Join the segments |
| `shot ... lasts 1.4s (under 2.0s)` | Two changes too close | Extend the segment, move or drop a cutaway |
| `spots change more than once in 3s` | Too many changes close together | Spread the cutaways |
| `transition wants N frames, has handles for M` | Not enough source either side of the cut for the dissolve | Shorter transition, or accept the hard cut |
| `out is past the source's end` | Wrong index or file | Re-check the line numbers |
| `its sound starts N frames early but the source has M before in` | A split edit wants more source than exists | Shorter `audio_lead`/`audio_trail`, or move the edge |
| `split edit on a sped segment ignored` | Speed and split edits do not combine | Drop one |
| `sfx anchor: ...` | An effect points at a segment, word or cutaway that does not exist | Re-number after re-cutting (`edl.py words` prints word indices) |

None of these goes to the person as a question. Fix it and re-run until `check` is clean.

## Draft review

Read the 1 fps sheet of the draft and `sheet.py --at` at every cut time:

- Each cut lands between words (play the 2 s around it if unsure: `ffmpeg -ss T-1 -t 2`).
- No action cut midway; no shot under 2 s; cutaways show what the words say.
- The open: something moving at frame 0, subject visible by 1 s, hook line within the first 2 s.
- Length within the plan's target.

## After posting

`retention.py edl.json curve.csv` lines up a posted video's retention graph (seconds and percent,
read off the app) with its EDL: loss per segment, the share still watching at 3 s, and the
steepest drops with what was said and how near a cut. A drop at 0-3 s is the hook, at a cut the
cut, a slow slide the length. Use it to plan the next video, not to re-cut this one.

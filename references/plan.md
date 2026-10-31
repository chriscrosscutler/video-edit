# Organize, look, plan

Read for steps 1, 2 and 4: setting up a video's folder, reviewing footage, and writing the plan
the cut is built from. Before a shoot, give the person the filming guide (below). Recipes per
content type (haul, unboxing, get ready with me, review, comparison, tutorial): references/cookbook.md.

## Filming guide

What makes the edit possible, in the order people forget it:

- **Hold 3 s still** before speaking and after the last word of every take, and before and after
  every action. Cuts and dissolves need those frames.
- **10 s of room tone** (everyone quiet, camera rolling) at each place you film.
- **Hands-only B-roll of every product:** in the hand, opened, in use, the result. 5-10 s each,
  steady, no talking. Close-ups of a label are where the eye goes; keep addresses out of frame.
- **Lock exposure and focus** (long-press on iPhone) so the picture does not pump; face the light.
- **4K** when the edit may punch in or reframe; 60 fps for anything that may play slow.
- **One mic, close.** A lav or the phone 50 cm away beats a room mic. Do not run music while filming.
- **Stay still** for set pieces: text behind a person, a vertigo zoom and green screen all need the
  person in place and the camera locked off; green screen also needs even light on the screen and
  a step away from it.
- Two phones: start both and clap once on camera (cut.md, Two cameras).
- Film the hook three ways; it is the line most worth having options for.

## Organize

One folder per video. Raw files are never edited or renamed after intake.

```
<video-id>/            e.g. 2026-11-02-desk-cables
  takes/               talking takes, file-name order = filmed order (iPhone names are chronological)
  hooks/               hooks filmed on their own, one per variant
  broll/               cutaways and demo footage; raw/ for originals you cut steps from
  logos/ screenshots/  stills shown on a named word
  music/ sfx/          licensed files only, each with its source and licence in SOURCES.txt
  work/                cache: conformed files, transcripts, levels, faces, draft renders (disposable)
  renders/             the final master and its report
  plan.json  edl.json  the editorial decisions, then the timed cut
```

- Cache every slow step in `work/` keyed by its inputs (file mtime, settings); a re-run redoes only
  what changed. Keep a `--force` to rebuild all.
- Media, `work/` and `renders/` stay out of git. Commit code and settings, not footage or the
  transcripts of unpublished videos.
- Conform at intake (`edl.py conform takes/* broll/* -o work/conformed`): constant 30 fps, BT.709
  SDR, rotation baked. Everything after works on conformed files, so frame numbers mean one thing.

## Look

- `probe.py --levels` on every file. Act on its notes: HDR, VFR, a louder mic (use it alone;
  summing two mics combs), missing audio.
- `sheet.py clip.mp4 work/sheets/clip.jpg --every 1` for every clip, and read the sheets. A model
  sees footage only through sheets: 1 fps for planning, 3-6 frames per B-roll clip for picking.
- **Check every take for speech.** A take with no words (applying a product, packing, a demo)
  silently drops out of a transcript-driven edit. Cut it into one clip per step in `broll/`, each
  starting about 0.3 s before the step (phones wobble at tap-to-record), and keep the original in
  `broll/raw/`.
- Note where actions start and end. An action is never cut midway.

## Number the lines the way the code does

The plan names lines by index, so indices must come from the same splitter the cut uses. A splitter
that breaks at long pauses as well as punctuation numbers differently from the transcript's
periods, and a wrong index that still exists passes validation.

- Print the numbered lines (`index: start-end text`) from the splitter itself and plan from that
  printout. After any transcript edit (adding a period to split a run-on), print again: indices
  shift.
- After writing the plan, print the text of every dropped line and read it. A line naming a
  sponsor or the product must never drop silently; make code refuse it.
- When a pause splits a line in the middle of a demonstration, hold both halves so the pause plays.

## Plan

The model writes `plan.json`; code turns it into `edl.json`. The plan holds decisions only:

```json
{
  "story": "one sentence: what the viewer learns or feels",
  "keep": [0, 1, 2, 4, 5, 7], "hold": [5],
  "hooks": [{"id": "A", "text": "the mask I use every night", "open_line": 7},
            {"id": "B", "text": "...", "open_line": 2}, {"id": "C", "text": "...", "open_line": 4}],
  "best": "A", "best_why": "opens on the finished result, then the story runs in order",
  "cutaways": [{"line": 2, "clip": "broll/pour.mp4", "word": "pour"}],
  "interludes": [{"after_line": 4, "clip": "broll/packing.mp4"}],
  "logos": [{"line": 1, "word": "Acme", "file": "logos/acme.png"}],
  "cta": "full routine on my page", "music": "music/track.wav"
}
```

- `hold`: lines where something happens on camera (marking a box, a demo); their pauses play and
  the shot runs about 0.8 s past the last word.
- `cutaways` cover the voice with footage of what is being said, 2-6 s, starting and ending on
  the speaker's words; back-to-back cutaways join into one run. None in the first 1.5 s (the
  open shows the speaker or the result).
- `interludes`: footage whose action outlasts the line plays in full after it, in real time, with
  its own sound at about -12 dB; the voice resumes after. The video gets longer; that is fine.
- Write three hooks, then pick the best yourself and render only that one.

## Short-form structure

| Beat | Rule | Strength |
|---|---|---|
| Cold open | The payoff line (result, claim, surprising number) at 0:00; frame 0 already moving, showing the product, hands or face. No intro card, greeting, fade from black. | official direction, practice |
| Subject on screen | Product or subject visible by about 1 s and kept visible | official (TikTok ad study: +25% recall) |
| See and say | When a thing is named, its footage appears within about 0.3 s | official (YouTube Shorts ad guidance) |
| Hook text | At most 7 words, 2 lines, top of the safe zone | practice |
| Body | Lines in story order; each cut moves the story | practice, calm-editing rule |
| End | Cut within 0.5 s of the last payoff word; CTA as text over the last 1.5-2.5 s; loop only when it comes free | practice |
| Length | Reels 30-60 s (45-60 s led engagement in 6M brand Reels, Jan-Jun 2026); TikTok engagement peaks 15-30 s; Reels must be at most 3:00 to reach non-followers | large-sample, official |

Other formats: a tutorial runs say, show, result per step and never skips the result; an explainer
puts the answer first and the reasons after; a vlog follows time order and cuts only dead time.

## Voiceover-led videos

When the voice is recorded apart from the picture (a script read over B-roll, a slideshow, a faceless
account), the voice track is the timeline and footage fills it:

1. Record the voiceover alone, transcribe it, number its lines. Plan and cut the voice first as one
   source (`t1`), dropping fumbles and re-reads by index, as for a talking head.
2. Each line gets a shot: `cutaways[]` over the voice segments, one per line or phrase, chosen from
   sheets so the picture shows what the words name (see and say). Back-to-back cutaways are the
   whole picture; the speaker never appears.
3. Shots change on words, 2-6 s each in the calm style (shorter in an energetic one), and an action
   still plays whole: if it outlasts the line, hold the voice (an interlude) or pick another clip.
4. Music carries more of the feel; captions carry more of the meaning (many watch muted).
5. A synthetic voice needs a licence for commercial use and, on some platforms, a disclosure
   (compliance.md).

## Before cutting

- Every take checked for speech; silent ones cut into `broll/` steps.
- Lines printed from the splitter; dropped lines read back; sponsor lines kept.
- One best variant chosen, with a reason a person would accept.
- Project rules read: disclosure wording, music licence, anything the brand never shows (for
  affiliate posts: no burned-in prices, no retailer product images, no link shorteners).

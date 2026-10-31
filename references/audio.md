# Audio

Read for step 7: cleaning the voice, matching takes, the music bed, and the master. Fix audio
problems in code; never hand the person a "listen to 0:14" chore.

## Order

1. Pick the mic (`probe.py --levels`): with two channels or two mics, use the louder one alone
   (`"channel": N` in the EDL source, or `conform --channel N`). Summing two mics combs.
2. Clean the voice on the conformed source, before cutting, so cuts see the cleaned levels.
3. Cut (references/cut.md). Every segment edge gets an 8 ms fade, so no cut clicks; room tone
   fills muted and silent stretches (below).
4. Match takes: measure each take (`master.py measure`) and set `gain_db` per segment so takes sit
   within 1 dB of each other.
5. Bed, duck, master: `master.py mix`.
6. Measure the result; it must read -14 LUFS (within 0.5) and peak at or under -1 dBTP.

## Voice clean-up

| Tool | Use | Watch |
|---|---|---|
| ffmpeg `highpass=f=80` | Rumble, handling noise | Always safe on speech |
| ffmpeg `afftdn=nf=-25` | Steady hiss or hum | Too strong turns speech watery; compare before and after |
| Auphonic (paid, cloud) | Levelling, noise, hum, loudness in one pass | Keep `silence_cutter` OFF: cutting audio alone desyncs the picture. Cloud upload of the voice needs the person's OK |
| Adobe Podcast Enhance, ElevenLabs Audio Isolation (paid, cloud) | Heavy room noise, bag rustle | Read current terms first; can sound synthetic |
| A voice detector (pyannote via WhisperX, silero-vad) | Finding "not talking" where noise fills the pauses | Use for cut decisions, not for muting |

Dropped: DeepFilterNet and resemble-enhance (no release in over 18 months), pedalboard (GPL), RNNoise
models via `arnndn` (the common model repo has no licence).

## Music

- **Licensed music only.** A subscription library (Epidemic Sound and similar), or a sound the
  person adds in the platform app after export. Log the track ID and plan per video. Never bundle
  music with a tool. yt-dlp audio is a beat reference only, never in a render.
- Check the plan's terms (references/compliance.md): creator plans cover the person's own channels
  and exclude paid ads, brand promotion and client work. Business accounts on TikTok and Instagram
  get only the platforms' commercial libraries in-app.
- Level: `master.py mix --music bed.wav` sets the bed `--gap-db` (default -9) under the voice's
  integrated loudness, then a sidechain compressor pushes it about 12 dB further down while the voice
  talks, so it sits 15-20 dB under the words and breathes back up between phrases.
- Pick tempo and mood to the story, not the trend. Beat-snapped cuts only where the cut also serves
  the story; beats from `librosa` drift, so refine to onsets or use `beat_this` (MIT).
- Start the bed on frame 0 or on the first cut; end it under the CTA with a 1-2 s fade (master.py
  cuts it to the video's length; add `afade=t=out` in a custom graph when the track has no ending).

## Room tone

Digital silence under a muted segment, a silent clip or a speed ramp sounds like a dropout. Record
10 s of the empty room at every shoot; when nobody did, `quiet.py tone take.mov work/room.wav`
lifts the longest quiet stretch from a take (it refuses under 0.5 s). Then, at the EDL's top level,
`"room_tone": "work/room.wav"` (or `{"path": ..., "gain_db": -3}`) loops it under every gap with
30 ms fades.

## Sound effects

The calm house style uses none unless the person asks for one at a named moment. An energetic
style uses them to mark something on screen: a whoosh on a swipe, a pop as a sticker lands, a
riser into a reveal, a click on a screen tap. One per moment, not one per cut.

- EDL top level: `"sfx": [{"path": "sfx/pop.wav", "at": {"seg": 3}, "gain_db": -8, "align": "peak"}]`.
  `at` is timeline seconds, `{"seg": k}` (its start), `{"word": i}` (a word from `edl.py words`) or
  `{"cutaway": k}`; `offset` shifts it in seconds. `align: "peak"` puts the sound's loudest instant on
  the anchor, so a whoosh peaks on the cut. Default -8 dB; effects mix in before the master.
- Licensed or CC0 files only (references/compliance.md lists sources and their terms). Listen
  first, and log each file's source page and SHA-256 in `sfx/SOURCES.txt`.
- A synthesized sound (ffmpeg `sine`, `anoisesrc` with an envelope) needs no licence: a soft chime
  on a logo, a tick on a list item.
- **Typing.** `typeon.py "TEXT" -o work/title` writes the schedule for the `TypeOn` title (looks.md)
  and a key track on the same frames: synthesized clicks, or `--samples DIR` of recorded keys (one
  file with "space" in its name for the space bar). Add the printed `sfx` entry with `at` set to the
  title's start on the timeline; -12 dB under a voice.

## Master

- Target -14 LUFS integrated, -1 dBTP: the common convention for TikTok, Reels and Shorts (no
  platform publishes a primary figure for organic posts). A project may set its own.
- One gain plus a limiter, measured from the mix. Never `loudnorm` in dynamic mode on a finished
  mix: it pumps breaths and room tone. Two-pass `loudnorm` with `linear=true` is equivalent only
  while the target range is wide enough; it silently falls back to dynamic otherwise.
- AAC 48 kHz stereo at 192-320 kbps in the final mux.

```bash
python3 scripts/master.py mix work/draft.mp4 renders/final.mp4 --music music/bed.wav
python3 scripts/master.py measure renders/final.mp4
```

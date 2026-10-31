# Troubleshooting and glossary

Read when a render looks or sounds wrong, or for a term the other references use. Fix in code
and re-render; none of these goes to the person as a question.

## Picture

| Symptom | Cause | Fix |
|---|---|---|
| Colours shift or look washed out in the app | Untagged file, or BT.601 read as BT.709 | `edl.py conform`; check tags with `probe.py`; render.md on hand-written ffmpeg |
| iPhone footage looks grey and flat or blown out | HDR (HLG, Dolby Vision) left unconverted | `edl.py conform` tone-maps to SDR at intake |
| Stutter or doubled frames | Variable frame rate source | `edl.py conform` (constant 30 fps) |
| Sideways or upside-down clip | Rotation flag not baked | `edl.py conform` |
| Jumpy slow push | ffmpeg `zoompan` moves whole pixels | Zoom in Remotion |
| Blurry after a punch-in or reframe | Upscaling a 1080p crop | Shoot 4K; keep zooms at 1.15 or less |
| Shaky handheld | | `conform --stabilize` (crops 4%) |
| Grainy low light | | `conform --denoise light`, or `strong` (slower) |
| Text on a face | Captions placed before a re-cut | Re-run faces on the final cut, then `place.py` |
| A flash frame at a cut | An off-by-one `out` | `edl.py check`; the qa sheet shows the frame after each cut |
| Wobbly green screen edge | | Use the matte (`matte.swift --person`) and `GreenScreen`, not a chroma key |

## Sound

| Symptom | Cause | Fix |
|---|---|---|
| A word clipped at a cut | Edge in speech | `quiet.py snap`; never move an edge inward |
| A click at a cut | No fade at the edge | `edl.py render` fades every edge 8 ms; check hand-made graphs |
| Hollow, phasey voice | Two mics summed | Use the louder channel alone (`"channel": N`) |
| Sudden silence under B-roll | Muted segment with nothing under it | `room_tone` at the EDL's top level |
| Voice jumps in level between takes | Takes recorded differently | `gain_db` per segment, within 1 dB |
| Music swamps the voice | Bed too loud | `master.py mix --gap-db` lower; 15-20 dB under speech |
| Breathing, pumping level | Dynamic `loudnorm` on a mix | One gain and a limiter (`master.py`) |
| Audio drifts out of sync | VFR source, or audio cut without picture | Conform; Auphonic's `silence_cutter` off |
| A whoosh lands early | Effect aligned by its start | `"align": "peak"` |

## Pipeline

| Symptom | Cause | Fix |
|---|---|---|
| A line vanished from the edit | Wrong index; or a silent take | Print lines from the splitter; check takes for speech (plan.md) |
| Numbers mistimed in captions | Aligner cannot time digits | Spell numerals out before aligning |
| `faces`, `ocr` or `matte` will not build | No Xcode command line tools | `xcode-select --install`; off macOS use MediaPipe |
| Remotion `Cannot find module brand.json` | JSON imports off | `"resolveJsonModule": true` in tsconfig |
| Platform refuses an upload | Over its bitrate or size limit | Re-render at CRF 17-18; never resize (render.md) |
| `redact.py` covers packaging or a cap | OCR read print it could not make out (`unsure`) | `--sheet`, then `--sure-only` or edit the JSON |
| `edl.py qa` says "possibly ... (OCR unsure)" | The same: garbage read from print | Look at the frame; no fix when it is print |

## Glossary

| Term | Meaning |
|---|---|
| A-roll / B-roll | the main talking footage / footage shown over or between it. |
| Cutaway | a B-roll shot laid over the voice; picture changes, sound runs on. |
| Interlude | a clip played whole between two lines, with its own sound, while the voice pauses. |
| J cut / L cut | the next shot's sound starts before its picture / a shot's sound runs on under the next picture. |
| Jump cut | a cut inside one take that makes the subject jump; a punch-in hides it. |
| Punch-in | a small zoom (1.1-1.15) on the second half of a jump cut. |
| Speed ramp | footage that changes speed inside one shot. |
| Room tone | the sound of the empty room, laid under gaps so they never go dead silent. |
| EDL | edit decision list, the JSON every stage here reads (`edl.py --help`). |
| Conform | converting every source to one frame rate, colour space and orientation at intake. |
| Handles | spare source frames past a cut, which a dissolve uses. |
| Matte | a mask of the person, for text behind them, background blur and green screen. |
| Safe zone | the part of the frame no app button or caption covers. |
| LUFS / dBTP | loudness as heard / the highest true peak; masters sit at -14 LUFS, -1 dBTP. |
| CRF | x264's quality setting; lower is better, 15 is near-transparent. |
| BT.709 | the HD colour standard every master is tagged with. |
| Waveform / vectorscope | graphs of brightness by position / of colour, for matching shots. |
| Hook | the first line and text, which decide whether a viewer stays. |
| CTA | the call to action at the end ("full routine on my page"). |
| Cover | the frame shown on the profile grid; cropped to 3:4 or 4:5 there. |

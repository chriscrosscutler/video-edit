# video-edit

An agent skill that plans, cuts, captions, animates and renders video with code. The model picks
lines and shots by index; the scripts do all timing, frame-exact, through one edit decision list
(`scripts/edl.py`).

## Layout

| Path | What it holds |
|---|---|
| `SKILL.md` | The rules every edit follows, loaded on each use |
| `references/` | One file per stage (plan, cut, captions, audio, grade, motion, render, compliance), read when a task needs it |
| `scripts/` | Python 3.10+ (stdlib only) and Swift tools; each prints its flags with `--help` |
| `templates/remotion/` | Caption, look and layout components plus `brand.json` |
| `tests/` | `test_scripts.py` (needs ffmpeg) and `test_vision.py` (macOS, Apple Vision) |
| `guide/` | The illustrated field guide: `index.html` and its demo clips in `img/` |

## Install

The skill is linked into Claude Code's skills folder:

```bash
ln -sfn ~/Documents/GitHub/video-edit ~/.claude/skills/video-edit
```

The playbook's `skills/video-edit` is a link to this folder too, so `install.sh` keeps working.

## Requirements

- Python 3.10 or newer and ffmpeg 7 or newer on the PATH.
- macOS with Xcode command line tools for the Swift tools (`faces`, `ocr`, `track`, `matte`,
  `cover`). They build on first use into `~/.cache/video-edit/`.
- Node for the Remotion templates; Blender 5.2 LTS for `blender_title.py`
  (`references/blender.md`).

## Tests

```bash
python3 tests/test_scripts.py
```

```bash
python3 tests/test_vision.py
```

Run both before each commit. The Blender and Swift tests skip when those tools are missing.

## Guide

`guide/index.html` is the source of the published field guide. Open it in a browser from this
folder so the `img/` paths resolve. After editing, republish it to the same artifact URL.

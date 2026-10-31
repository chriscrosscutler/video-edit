# Blender

Read before making a 3D title, logo reveal or product shot. Use Remotion for anything 2D or
text-driven, `@remotion/three` for simple lit 3D in the same timeline, and Blender only for what
browser WebGL cannot do: path-traced glass and metal, HDRI product spins, volumetrics, simulations.

## Setup

- Blender 5.2 LTS (GPL-3.0; renders, .blend files and movies belong to their maker). On a Mac:
  `brew install --cask blender` (several hundred MB: ask first), then
  `/Applications/Blender.app/Contents/MacOS/Blender`. Intel Macs stop at 4.5.
- Pin one version per project and log `bpy.app.version_string`; 5.0 and 5.2 broke Python APIs.
- `bpy` from PyPI needs Python 3.13 exactly, macOS ARM64 only, about 400 MB: keep it in its own venv
  if you need it at all. The CLI is the default path.
- Scripts that use `bpy` count as part of Blender under its licence: ship them as GPL and call a
  user-installed Blender as a separate process. Get counsel before bundling Blender in a product.

## Headless renders

```bash
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
"$BLENDER" -b --factory-startup --python-exit-code 1 -P scripts/blender_title.py -- \
    --text "Acme Club" --font fonts/TikTokSans-Bold.ttf --out work/title/f_####
```

- `-b` no UI; `--factory-startup` ignores the user's prefs and add-ons; `--python-exit-code 1` makes
  a Python error fail the run instead of rendering a default scene and exiting 0.
- Everything after `--` goes to the script (`sys.argv`); parse with `parse_known_args`.
- Arguments run in order: with a .blend, put `-o`, `-s`, `-e` after it and before `-a`.
- `#` in the output path is the zero-padded frame number (`f_####` gives `f_0001.png`; ffmpeg reads
  `f_%04d.png`).
- `blender_title.py` builds a factory-clean 9:16 scene, renders RGBA PNGs and prints the ffmpeg
  line (tested on 5.2.3 LTS: about 0.3 s a frame with EEVEE on Apple Silicon). `--look flat` keeps
  exact colours; `lit` shades them, so use flat where brand colours must match. An SVG keeps its
  own fills unless `--color` is given. Flat white has no shadow: plain text over busy footage
  belongs in Remotion (`CalmText`), Blender is for depth.

## Scene rules

- 9:16: `resolution_x/y` 1080x1920, `fps` 30, `fps_base` 1. Factory defaults are 1920x1080 at
  24 fps, so a script that forgets renders landscape.
- Transparent: `render.film_transparent = True`, PNG, RGBA, 16-bit. Lights and the world still
  light the scene; only background pixels go clear.
- Colour: `view_transform = 'Standard'` for flat graphics and type that must match sRGB/BT.709
  footage. AgX or Khronos PBR Neutral for photoreal product shots (pick one per brand). Never Raw
  or Filmic (deprecated) for delivery.
- Engine: EEVEE for text and logos (id `BLENDER_EEVEE_NEXT` in 4.2-4.5, `BLENDER_EEVEE` from 5.0);
  Cycles on Metal (Apple Silicon, macOS 13+) for glossy or glass, `--cycles-device METAL` after `--`.
- Text: `bpy.data.curves.new(name, 'FONT')`; `body`, `size`, `align_x/y`, `extrude`, `bevel_depth`;
  fonts via `bpy.data.fonts.load(path)` (a static instance, not a variable font). A bevel grows
  every outline outward, so tight gaps (the eye of an "e") overlap into dark slivers: set
  `offset = -bevel_depth` on the curve.
- Fading a solid: BLENDED materials show the sides and back through the front mid-fade. Set
  `use_backface_culling = True` and `use_transparency_overlap = False`.
- SVG (`bpy.ops.import_curve.svg`): each fill becomes a material whose `diffuse_color` is already
  linear. Set extrude and bevel after scaling the import, divided by the object's scale.
- Keys: set `interpolation` and `easing` on every keyframe (QUART/EASE_OUT to land, CUBIC/EASE_IN to
  leave). Blender 5.0 removed `Action.fcurves`: use
  `bpy_extras.anim_utils.action_get_channelbag_for_slot(action, slot).fcurves`.
- Other 5.0 breaks: `scene.node_tree` became `scene.compositing_node_group`; VSE collections are
  `sequence_editor.strips` / `strips_all`.
- Calm motion still applies: fade and drift in over about 0.3 s, hold dead still, leave faster. A
  turntable loops cleanly when frame N+1 equals frame 1 (keys at 1 and N+1, render 1..N, LINEAR).

## Getting it into the edit

```bash
# ProRes 4444 keeps alpha (Blender's own ProRes output has none); BT.709 matrix, tagged
ffmpeg -framerate 30 -i work/title/f_%04d.png \
    -vf scale=out_color_matrix=bt709:out_range=tv,format=yuva444p10le,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv \
    -c:v prores_ks -profile:v 4444 -alpha_bits 16 -vendor apl0 work/title.mov
# Overlay at 1.2 s
ffmpeg -i cut.mp4 -itsoffset 1.2 -i work/title.mov \
    -filter_complex "[0][1]overlay=format=auto:eof_action=pass,format=yuv420p" -c:a copy out.mp4
```

- ffprobe shows the ProRes as `yuva444p12le`; the alpha is intact. Without the `-vf`, ffmpeg
  encodes the PNGs with the BT.601 matrix and no tag, and brand colours shift in the edit.
- VP9 alpha WebM is smaller (`-c:v libvpx-vp9 -pix_fmt yuva420p -auto-alt-ref 0`), but put
  `-c:v libvpx-vp9` before `-i` when reading it back or ffmpeg's native decoder drops the alpha.
- In an EDL render, add the .mov as a cutaway with `"fade": 0` (the alpha does the reveal; `check`
  sees the alpha and treats it as an overlay, not a cut), or in Remotion use
  `<OffthreadVideo src={staticFile('title.mov')} transparent />`.
- Place 3D titles with `place.py --kind title` like any other text: pass the placed `top` back as
  `--y`.

## Assets and MCPs

- Poly Haven HDRIs, textures and models are CC0: fine for commercial work, no attribution.
  Blender Studio assets are mostly CC BY (attribution).
- Blender MCP servers (the official Blender Lab MCP, ahujasid's MCP for Blender) run model-written
  Python with no guards. Use them only to explore a scene by hand, on localhost, with
  `BLENDER_MCP_SAFE_MODE=1` and telemetry off; never auto-approve `execute_blender_code`. Production
  renders come from a committed script run with `-b`.

# Motion graphics and animation

Read when adding titles, logos, lower thirds, animated text, stickers, explainer graphics or light
3D. For path-traced 3D read blender.md.

## Pick the tool

| Need | Tool | Licence |
|---|---|---|
| Text, captions, logos, overlays on footage, anything 2D in a React codebase | Remotion 4 | Remotion License: free for individuals, for-profits up to 3 people, non-profits; a company licence above that |
| Same, but Apache-licensed and built for agents (HTML + GSAP) | HyperFrames (heygen-com) | Apache-2.0; 0.x, pin the version |
| Programmatic 2D scenes in TypeScript generators | Revideo | MIT |
| Choreographed timelines (stagger, SplitText, MorphSVG) | GSAP via `@remotion/gsap` | GSAP Standard licence: free incl. commercial; bars a no-code animation builder |
| Designer-made vector motion (After Effects, LottieFiles) | `@remotion/lottie`, dotlottie-web | Remotion / MIT |
| Rive state-machine assets | `@remotion/rive` | Remotion / MIT runtime |
| Math and diagram explainers | Manim Community | MIT |
| Light lit 3D (spinning logo, GLTF) in the same timeline | `@remotion/three` | Remotion; needs the `angle` GL renderer |
| Path-traced glass or metal, HDRI product spins | Blender (blender.md) | GPL-3.0 app; renders belong to the creator |

Remotion licence for products: a company of more than 3 people (counting everyone involved) needs a
Company License (Creators $25 per seat per month; Automators $0.01 per render, $100 per month
minimum; Enterprise from $500 per month). A native app bundling Remotion is allowed if end users
cannot edit or upload Remotion code. Remotion 5.0 brings new terms. Check before shipping it inside
another product.

Dropped: Motion Canvas (no release since 2024-12), lightning-whisper-mlx, editly, ffmpeg-python
(stale over 18 months).

## Rules for frame-rendered motion

- **A pure function of the frame.** Drive everything from `useCurrentFrame()` with `interpolate`
  or `spring`. CSS transitions, CSS animations, Tailwind `animate-*`, `Date.now()` and unseeded
  `Math.random()` render wrong or differently each time.
- **Clamp** every `interpolate` (`extrapolateLeft/Right: 'clamp'`).
- **Calm defaults.** Fade in about 0.3 s (9 frames at 30 fps) on `Easing.bezier(0.16, 1, 0.3, 1)`;
  exit 40-50% shorter than the entrance. `spring()` bounces by default (damping 10): use
  `{damping: 200}` for no bounce. Opacity and colour never bounce.
- **A landed title is dead still.** No breathing, floating, pulsing or slow creeping scale.
- **Stagger**: letters about 1 frame, words 2-4 frames, list items 1-3 frames.
- **Size**: titles 4-9% of frame height (77-173 px at 1920), body text 2.5-4% (48-77 px).
- **Reading hold**: 0.5 s + 0.3 s per word; the last line at least 2 s.
- **Motion blur only on fast moves** (0.3-0.6 s moves): `@remotion/motion-blur`
  `HtmlInCanvasMotionBlur` (samples 8, shutterAngle 180). Calm fades have nothing to blur.
- **Beat grid**: frame of beat n = round(n x fps x 60 / BPM), never accumulated rounded beats.
  Raw `librosa.beat_track` is off by tens of milliseconds; refine to onsets or use `beat_this`.
  Cut on the beat only when the cut also serves the story.
- Fit text after the font loads: `fitText` from `@remotion/layout-utils` with
  `validateFontIsLoaded: true`.

## Remotion setup

```bash
npx remotion add @remotion/transitions    # one at a time; all @remotion/* share one exact version
npx skills add remotion-dev/skills        # official agent skills: link, don't copy (no licence stated)
```

- `<Video>` from `@remotion/media` is the recommended video component (frame-exact, `trimBefore`,
  `durationInFrames`, `effects`); `OffthreadVideo` is the fallback. `playbackRate` shifts pitch
  unless `preservePitch`; footage should play at 1x anyway.
- `@remotion/effects` (blur, glow, vignette, LUT, curves, light leak) via the `effects` prop on
  media; plain elements need `<HtmlInCanvas>`. Fast-moving API: pin and smoke-test on upgrade.
- Keep a shot's video, captions and synced overlays in one `<Sequence>`; trim once there.
- MIT helpers: `@remotion/shapes`, `paths`, `noise`, `layout-utils`, `captions`, `motion-blur`.
- Reference repos: `remotion-dev/template-tiktok` (captions), `template-overlay` (overlay on
  footage). Read for patterns; their licence is Remotion's.

## Templates in this skill

`templates/remotion/CalmText.tsx` (hook, CTA, title: fades in, holds still, fades out) and
`PhraseCaptions.tsx` (captions.py JSON, one phrase at a time, honours `place` from place.py). Copy
them into the project's Remotion `src/` and wire props from the EDL's timeline words and the plan.

```tsx
<Sequence from={0} durationInFrames={75}><CalmText text={plan.hook} size={84} top={300} /></Sequence>
<PhraseCaptions phrases={placedCaptions} lowercase />
```

## Text behind a person

A big title set behind the head: the footage, then the text, then the person cut out on top. For
the hook or a title card, not captions.

1. Matte the person on the cut (a draft render), not the sources. macOS 12+: build once with
   `swiftc -O scripts/matte.swift -o ~/.cache/video-edit/matte`, then
   `~/.cache/video-edit/matte work/draft.mp4 work/mask.mp4 --person work/person.webm` (Apple Vision
   person segmentation; a 3 s clip takes about 5 s). The mask is grey, the size and frame count of
   the cut, white where the person is. Elsewhere MediaPipe Image Segmenter (Apache-2.0); fine hair
   or several people: SAM 2 (Apache-2.0) or BiRefNet (MIT). RobustVideoMatting is GPL-3.0.
2. Composite in ffmpeg (tested on 8.1). `tmedian` stops the edge flickering, `gblur` softens it;
   convert the title to the footage's format first (`[ti]`), or ffmpeg's own conversion inside
   this graph shifts its colour:

   ```bash
   ffmpeg -i cut.mp4 -i mask.mp4 -itsoffset 0.5 -i title.mov -filter_complex \
   "[1:v]format=gray,tmedian=radius=1,gblur=sigma=1.5[m];\
   [2:v]scale=out_color_matrix=bt709:out_range=tv,format=yuva420p[ti];\
   [0:v]split[bg][fg0];[fg0][m]alphamerge[fg];[bg][ti]overlay=eof_action=pass[t];\
   [t][fg]overlay,format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv[v]" \
       -map "[v]" -map 0:a -c:v libx264 -preset slow -crf 15 -c:a copy out.mp4
   ```

   In Remotion: the cut, then `CalmText`, then `person.webm` (VP9 alpha, edge already softened)
   in `<OffthreadVideo src={staticFile('person.webm')} transparent />`.
3. A heavy display face (Anton, Bebas Neue, Archivo Black) at 10-20% of frame height in the top
   third. The head covers part of a letter or two, never a whole word, and the person holds fairly
   still while it shows (1.5-3 s). `place.py` would move this title off the face: skip it for this
   one title and check the sheet instead.

## Logos and stills

Show a logo or screenshot on the word that names it, eased in over 6-9 frames, held while the line
plays, out before the next change. Logos come from the brand's own kit; never a retailer's product
image unless the project allows it. Ken Burns on a still: ffmpeg `zoompan` with explicit `s=` and
`fps=` (defaults are 720p at 25 fps), or a Remotion `scale` interpolation of 1.0 to 1.06 over the
hold.

# Transitions

Read when choosing how two shots meet, or building a transition in ffmpeg, Remotion or a shader.

## Which one

| Join | Use | Length at 30 fps |
|---|---|---|
| Hard cut | The default. Talking head to talking head, face to B-roll, anything on a word | 0 |
| Cross dissolve (`fade`) | Two takes of one set-up; two actions inside one clip; a cut that would jump | 12-18 frames |
| Dip to black or white (`fadeblack`, `fadewhite`) | A real topic or time break, once or twice a video at most | 16-24 frames |
| Push, slide, wipe, zoom | Stylized pieces only (a list, a reveal); every one must be motivated by on-screen motion | 8-15 frames |
| Light leak, flash overlay | Brand energy on a cut without moving it (Remotion `TransitionSeries.Overlay`) | 10-20 frames |
| Shader (gl-transitions) | Rare, showy; never in a calm edit | 15-30 frames |

Rules:

- Pick 1-3 kinds per video and reuse them; the same join for the same meaning.
- A transition is centred on the cut and eats handles (extra source either side), so the timeline
  keeps its length and the audio still cuts on the word. `edl.py` does this; Remotion's
  `TransitionSeries` instead overlaps neighbours and shortens the total.
- Audio under a dissolve: cut hard on the word with an 8 ms de-click, or `acrossfade` (c1=tri:c2=tri)
  over the same frames when both sides carry room tone or music.
- Never use a transition to hide a cut that should not exist. Fix the cut.

## ffmpeg xfade

`edl.py` writes it for you: `"transition": {"type": "fade", "frames": 16}` on the segment after the
cut. `check` rejects names ffmpeg lacks. The 58 types in ffmpeg 8.1:

```
fade fadeblack fadewhite fadegrays fadefast fadeslow dissolve distance
wipeleft wiperight wipeup wipedown wipetl wipetr wipebl wipebr
slideleft slideright slideup slidedown smoothleft smoothright smoothup smoothdown
coverleft coverright coverup coverdown revealleft revealright revealup revealdown
circlecrop rectcrop circleopen circleclose vertopen vertclose horzopen horzclose radial
diagtl diagtr diagbl diagbr hlslice hrslice vuslice vdslice hlwind hrwind vuwind vdwind
squeezeh squeezev zoomin pixelize hblur
```

Writing xfade by hand:

- Both inputs need the same size, pixel format, frame rate and timebase. A 1/15360 clip meeting a
  1/90000 clip fails ("timebase do not match"): conform first, or add `settb=AVTB` per input.
- Offset of join i = sum of the first i clip lengths - i x T; output length = sum - (N-1) x T.
- Store cuts as integer frames; convert to seconds only when writing the filter.
- Easing beyond linear: `xfade-easing` (MIT) ports CSS-style easing and about 64 gl-transitions to
  xfade expressions; slow, so only for the odd stylized join.

## Remotion

```tsx
import {TransitionSeries, linearTiming, springTiming} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';

<TransitionSeries>
  <TransitionSeries.Sequence durationInFrames={90}><ShotA /></TransitionSeries.Sequence>
  <TransitionSeries.Transition presentation={fade()} timing={linearTiming({durationInFrames: 18})} />
  <TransitionSeries.Sequence durationInFrames={120}><ShotB /></TransitionSeries.Sequence>
</TransitionSeries>
```

- Total = sum of sequences - sum of transitions; compute with `timing.getDurationInFrames({fps})`.
  A transition cannot outlast either neighbour, and two transitions cannot touch.
- `springTiming({config: {damping: 200}})` is a no-bounce ease of about 23 frames at 30 fps.
- `TransitionSeries.Overlay` (4.0.415+) sits on a cut without changing the length: light leaks
  (`@remotion/effects/light-leak`, WebGL2), flashes.
- Built-in presentations (4.0.539): fade, dissolve, slide, wipe, flip, clock-wipe, iris, none,
  blur-slide, book-flip, cross-zoom, crosswarp, dreamy-zoom, film-burn, linear-blur, push-cut,
  ripple, swap, zoom-blur, zoom-in-out. Import each from `@remotion/transitions/<name>`.
- Custom presentation: a component receiving `children`, `presentationDirection` ('entering' or
  'exiting') and `presentationProgress` (0-1).
- gl-transitions in Remotion: `glTransition({name: 'CrossWarp'})` from `@gl-transitions/remotion`
  (MIT, needs Remotion 4.0.500+). Check each shader file's licence header; two are BSD.

## In Blender or a shader

gl-transitions' GLSL spec (`vec4 transition(vec2 uv)` with `getFromColor`, `getToColor`,
`progress`) ports to any GPU pipeline. In Blender, prefer rendering the moving element as alpha and
compositing it in ffmpeg or Remotion over building transitions in the VSE.

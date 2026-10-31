# Looks: zooms, title styles, set pieces

Read when a brand asks for energy or a beat needs a set piece. Each one has to show what is said:
the chart grows on the number she says, the phone holds the app she names, the cover frames the
product launch. One set piece per video, two at most, never back to back. Rule 5 still holds
(inside the safe box, off faces; the cover and orbit are the only text that goes behind a head).

All of them are components in `templates/remotion/Looks.tsx` and `Layouts.tsx` (typechecked and
rendered on Remotion 4.0.535). Frames are local, so wrap each in `<Sequence>`. `person` takes the
cutout from `matte.swift --person` (motion.md, "Text behind a person") over the same footage.

**Brand.** `templates/remotion/brand.json` holds the fonts (sans, serif, display, caption), colours
(text, accent, highlight, paper, ink, shadow), caption size, weight and case, handle and logo.
Every component reads it through `brand.ts`; a missing key keeps the default. One file per brand;
never hard-code a colour in a composition. (brand.ts imports JSON: set `"resolveJsonModule": true`
in the project's tsconfig.)

## Zooms

| Look | Component | Numbers | Use |
|---|---|---|---|
| Slow push | `Zoom keys={[[0, 1], [end, 1.06]]}` | 2-3% a second, eased | A long hold on her face; calm by default |
| Punch-in | `Zoom keys={[[0, 1.12]]}` on the second half of a jump | 1.1-1.15, face stays in frame | Hides a jump cut inside one take |
| Digital zoom | `Zoom keys={[[0, 1], [4, 1.3], [14, 1.3], [18, 1.7], [40, 1.7], [48, 1]]}` | 2 steps, 4 frames each, hold, ease back | Points at a detail she names (a label, a stitch) |
| Zoom-through cut | `ZoomThrough a b cut frames={12}` | A to 3x with 14 px blur, B lands from 1.6x | A change of place or time; origin on something dark or plain |
| Vertigo (dolly zoom) | `Vertigo background person scale={1.25}` | 1.5-3 s, room 1.25 to 1, her held at 1.25 | A realisation ("then I saw the price"); she must hold still |

- Set `origin` on what the zoom is about: her face (from `faces.swift`) or the product.
- Vertigo scales her up 1.25 and the room down to 1, never the room up: a room scaled past her
  shows a bigger copy of her around the cutout. Use footage at least 1.25x the output (4K for a
  1080 render) or accept slight softness.
- ffmpeg's `zoompan` moves in whole pixels and jitters on slow pushes; zoom in Remotion.

## Title styles

| Look | Component | Use |
|---|---|---|
| Magazine cover | `MagazineCover background person title lines issue top` | A launch, a reveal, "the issue" of a series. Didone masthead (Bodoni Moda) behind the head; set `top` so hair covers part of a letter |
| Headline wall | `HeadlineWall lines every={10}` | Press, reviews, "everyone is talking about it". Real quotes only, with the source in the caption; her claim goes last |
| Paper cut | `PaperCut text tilt={-3}` | Recipes, DIY, scrapbook, a handmade brand |
| Typed on | `TypeOn text frames font` | A search, a message, a note, a list being written. `typeon.py "TEXT" -o work/title` writes `frames` and a key-sound track from one schedule, so each click lands on its letter (audio.md); a monospace font reads as a typewriter |
| Plain calm title | `CalmText` (motion.md) | Everything else |

## Overlays

| Look | Component | Use |
|---|---|---|
| Phone mockup | `PhoneMockup scale={0.62}` | Showing an app, a page, a post or a screen recording; caption above or below the phone |
| Chart grow | `ChartGrow bars unit` | A figure she says (hours, price drop, percent); real numbers only, and no prices burned in where the project forbids them |
| Orbit | `Orbit background person words` | A tagline circling her head, 3-5 short words, one turn in 6 s |
| UI world | `UiWorld items` (note, chat, like, search) | A story about an app, a message, a search or going viral; items with `behind` sit under her |

Each holds still once it lands; nothing loops for attention except the orbit. Check every one on the
sheet (`edl.py qa --sheet`) for text on a face and for the platform UI covering it.

## Layouts

| Look | Component | Use |
|---|---|---|
| Green screen | `GreenScreen person background position scale` | Talking over a page, a product listing, a photo; `person` is the matte cutout, so no green cloth is needed |
| Split screen | `SplitScreen a b mode="side"\|"stack"\|"wipe" labels` | Before and after, this vs that, two angles; `wipe` drags a divider across one frame |
| Background blur | `BlurBackground footage person blur={24}` | A messy room, or to lift her off a busy background; eases in over `inFrames` |
| Tracked callout | `Callout track text side arrow` | A label that follows an object (`track.swift` output); fades when tracking is lost |
| List counter | `ListCounter count total corner` | "3 things...": the number rolls up at each item; `count` takes `[[frame, n], ...]` |
| Chapter card | `ChapterCard title kicker mode="lower"\|"full"` | Steps of a tutorial, parts of a long video |
| Sticker | `Sticker text mode="pop"\|"fade" at tilt` | An emoji or a word on a moment; clamped to the safe zone |

Callout, Sticker and SplitScreen labels estimate text width (0.56 em a character); check long labels
on the sheet. SplitScreen crops each pane; `focus` picks what stays.


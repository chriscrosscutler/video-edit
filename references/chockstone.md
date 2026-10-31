# Chockstone

Read when the video belongs to a Chockstone post. Chockstone's iPhone app records, cuts and
renders; its server only stores and checks the edit list. You change that list through the MCP
`edit_*` tools and the phone renders it. Nothing here publishes: never call `post_submit`,
`post_schedule` or any publish tool. The person posts.

## Loop

1. `edit_get {post_id}`: the edit list (clips cut from takes, with ids and in/out ms), its `rev`,
   length, captions as SRT, each network's checks with a ready-made fix, and render status.
   `edit` null means no cut yet: the phone makes the first cut when the person opens the editor.
2. Plan as in references/plan.md from the SRT: keep and drop lines by caption and clip id. Every
   time you send comes from `edit_get` (clip in/out, caption start/end), never a guess.
3. `edit_change {post_id, base_rev, changes}`: 1-50 changes, applied in order, all or nothing.
   Always pass `base_rev`. `EDIT_CONFLICT` means the phone saved meanwhile: `edit_get` again and
   redo the changes on the new rev.
4. Apply each failing check's fix from `edit_get` as-is; it is already a valid change.
5. `edit_render {post_id, when: "now"}` (or `"charging"` when nothing is waiting on it: it spares
   the battery). Wait until `edit_get` shows `render.state` rendered.
6. `edit_frames {post_id}`: the sheet the phone made. Check it as in references/render.md (cuts
   on finished words, captions in their band, titles off faces). `stale: true` means re-render.
7. A wrong turn: `edit_versions`, then `undo {activity_id}` (within 7 days; it comes back as a new
   rev).

## Skill rule to change

Clip and caption times are ms in the clip's take; title, image and cover times are ms on the
finished video.

| Skill rule | Change | Notes |
|---|---|---|
| Drop a line | `split` at the line's quiet edges, then `remove`; or `trim` an end | Split points from caption ends, moved out into the pause, never into a word |
| Cut dead air | `cut_pauses` with its defaults (`min_ms` 1500, `keep_ms` 400) | Keeps breaths; never `min_ms` under 1000 or `keep_ms` under 300 |
| Better take of a line | `swap_take` | Its captions follow |
| Order the story | `move` | 0 is first |
| Jump inside one take | `punch_in` 1.1-1.15 on the second part | Face stays in frame; check the sheet |
| Match takes | `look` per clip (exposure, warmth within ±0.15); `volume` per clip | Whole-edit `look` for the grade |
| Interlude, demo | Leave it at speed 1 and volume ~0.25 | Never `speed` or `freeze` unless the person asks |
| Hook, CTA, title | `text_add` (`x`, `y` = centre as frame fractions; `size` 24-160) | Hook from 0 ms; CTA the last 1.5-2.5 s |
| Logo, product shot | `image_add` (`media:<id>` from `media_list`, `w` 0.2-0.3) | On the word that names it; `track: "scene"` to stick it to the product |
| Captions | `captions` `{style: "clean", color: "#FFFFFF", accent: null, y: null, burn_in: true}` | `y: null` keeps them in the band clear of every network's buttons; `font` from the brand kit or null (fonts: references/captions.md) |
| Caption words | `caption_edit` | Brand names spelled the brand's way; fix numerals |
| Music | `music` (the person's own licensed file from `media_list`), `duck: true` | Bed 15-20 dB under the voice |
| Voice | `sound` `{clean: true}` | Cleans to -16 LUFS (the app's target, not -14); `fade_out_ms` 300-800 |
| Cover | `cover` at a frame with face and product; short `text` or null | |

- Caption styles as the phone draws them: `clean` white with a soft shadow (weight 600); `bold`
  8% larger with a black outline (800); `boxed` on a rounded black box at 72% (700); `pop` outlined,
  the spoken word in `accent` (default #FFD60A) (800). `clean` is the calm default.
- Text box for 9:16, as fractions: x 0.11-0.82, y 0.15-0.65 (the shared safe box in
  references/captions.md). The tools do not track faces: place titles where the sheet shows no
  face, and move them when it does.
- `edit_set {from_post_id}` copies another post's edit, for a series with one format; then
  `swap_take` each clip to this post's takes.
- Hook versions (another opening line or shot, for trial reels) are the list's `versions`, set
  with `edit_set`. Make them only when the person asks; the default is one best edit.

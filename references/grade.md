# Colour grading

Read before grading or matching takes. Grade the cut before captions, titles and logos go on, so
text and brand colours stay exact. Conform first (`edl.py conform`): the recipes assume BT.709-tagged
input, and untagged footage converts with the wrong matrix.

## Order

1. **Match.** Per clip, exposure and white balance until skin looks the same shot to shot.
   `match.py ref.mov take2.mov --region 0.3,0.2,0.7,0.5` measures mid-tone colour on the face in
   both and prints a `grade` for take 2's segments in the EDL (or `--apply OUT` writes the fixed
   clip). Compare with `sheet.py VIDEO OUT.jpg --at T1,T2,...`; in Chockstone, `look` per clip.
2. **Look.** One grade over the whole edit, light by default.
3. **Check.** The product must look like its listing photo (a shopper buys that colour), skin stays
   natural, highlights don't clip. Then `edl.py qa --sheet --scopes work/scopes`.

## Scopes

`edl.py qa` notes clipped highlights, crushed shadows, and neighbouring shots from different sources
whose brightness or colour jump; `--scopes DIR` writes each segment's frame beside its waveform and
vectorscope.

- **Waveform** (brightness by column): nothing flat against the top (clipped) or bottom (crushed);
  a face sits in the upper middle, about 60-70%.
- **Vectorscope** (colour): a neutral shot clusters at the centre; a cast pulls the cluster toward
  that colour. Skin of every tone falls along one line between red and yellow, near 11 o'clock.
- Two shots that should match have the same waveform height and vectorscope cluster.

## Repair

Fix at intake, before cutting: `edl.py conform ... --stabilize` (ffmpeg deshake, then a 4% crop
hides the moving edges) and `--denoise light|strong` (hqdn3d, or nlmeans: slower and cleaner, for
dim footage). Both soften the picture a little; use them only on clips that need them.

## ffmpeg looks

Tested on ffmpeg 8.1: the RGB round trip keeps colours on tagged BT.709 input.

```bash
ffmpeg -i cut.mp4 -vf "format=gbrp,LOOK,format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv" \
    -c:v libx264 -preset slow -crf 15 -c:a copy graded.mp4
```

| Look | LOOK | For |
|---|---|---|
| Clean bright | `exposure=exposure=0.25,eq=contrast=0.94:saturation=0.92,colortemperature=temperature=7000:mix=0.6` | Lifestyle, product on white |
| Warm film | `curves=all='0/0.06 0.5/0.5 1/0.95',colorbalance=rs=0.05:bs=-0.05:rh=0.04:bh=-0.03,eq=saturation=0.88,noise=alls=7:allf=t+u` | Home, food, nostalgia |
| Teal and orange | `colorbalance=rs=-0.08:bs=0.09:rm=-0.03:bm=0.04:rh=0.10:gh=0.02:bh=-0.10,eq=saturation=1.06` | Travel, outdoors; turns black clothes navy |
| Faded matte | `curves=all='0/0.14 0.6/0.58 1/0.88',eq=saturation=0.72,colorbalance=bs=0.05:bm=0.03` | Calm, moody, minimal |
| Golden hour | `colortemperature=temperature=4200:mix=0.5,eq=contrast=1.06:saturation=1.12:gamma=0.97,vignette=PI/5` | Cosy, evening |
| Black and white | `hue=s=0,curves=preset=increase_contrast` | A flashback or a quote, briefly |

- LUTs: `lut3d=file=look.cube:interp=tetrahedral` in place of LOOK. A LUT built for log footage
  (Apple Log, S-Log3) overcooks Rec.709 clips; iPhone Apple Log needs Apple's Log-to-Rec.709 LUT
  first. Check a LUT pack's licence before using it in paid work.
- Remotion: CSS `filter` on the footage (`contrast(1.05) saturate(0.9) sepia(0.08)`) is a quick
  stand-in; grade in ffmpeg when the look must match across tools.

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Blender treats scripts that use its Python API as part of Blender, so this file is GPL; the
# renders it makes belong to whoever makes them. Call Blender as a separate process; never bundle it.
"""A title or logo reveal rendered headless by Blender as a transparent RGBA PNG sequence.

Usage (Blender 4.2+ or 5.x; arguments after "--" belong to this script):
  blender -b --factory-startup --python-exit-code 1 -P blender_title.py -- \\
      --text "Acme Club" --out work/title/f_#### [options]
  blender ... -P blender_title.py -- --svg logos/acme.svg --out work/logo/f_####

  --frames 60        length; the reveal fades and rises in over 0.3 s, holds, fades out over 0.17 s
  --fps 30  --size 1080x1920
  --font PATH        a .ttf/.otf (a static instance; Blender's default font has few glyphs)
  --color HEX        text colour (default FFFFFF); for --svg, one colour for the whole logo
                     instead of its own fills
  --look flat|lit    flat: emission, exact colour, matches plain white text (default);
                     lit: shaded 3D with a sun, for extruded logos
  --height 0.07      text size as a fraction of frame height (0.04-0.09 reads as a title)
  --y 0.2            centre of the text, as a fraction of frame height from the top
  --max-width 0.71   widest the text may run, as a fraction of frame width (the shared safe box)
  --extrude 0.0  --bevel 0.0   depth in frame heights; try 0.01 and 0.002 with --look lit
  --rise 0.015       how far it drifts up while fading in (0 = dead still)
  --turn 0           degrees it turns about the vertical axis while fading in (lit logos)

Then composite the sequence (ProRes 4444 keeps alpha; Blender's own ProRes has none):
  ffmpeg -framerate 30 -i work/title/f_%04d.png -vf scale=out_color_matrix=bt709:out_range=tv,\\
format=yuva444p10le,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv \\
      -c:v prores_ks -profile:v 4444 -alpha_bits 16 -vendor apl0 work/title.mov
  ffmpeg -i cut.mp4 -itsoffset 1.2 -i work/title.mov \\
      -filter_complex "[0][1]overlay=format=auto:eof_action=pass,format=yuv420p" -c:a copy out.mp4
or play it in Remotion with <OffthreadVideo src={staticFile('title.mov')} transparent />.
Cache renders by a hash of this file plus its arguments; Blender renders are slow.
"""
import argparse
import math
import os
import sys

try:
    import bpy
except ImportError:  # plain python3: --help still works
    bpy = None

# PNGs are RGB: encode them with the BT.709 matrix and say so, or the edit reads them as BT.601.
PRORES_VF = ("scale=out_color_matrix=bt709:out_range=tv,format=yuva444p10le,"
             "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv")


def args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    what = ap.add_mutually_exclusive_group(required=True)
    what.add_argument("--text")
    what.add_argument("--svg")
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--font")
    ap.add_argument("--color")
    ap.add_argument("--look", choices=["flat", "lit"], default="flat")
    ap.add_argument("--height", type=float, default=0.07)
    ap.add_argument("--y", type=float, default=0.2)
    ap.add_argument("--max-width", type=float, default=0.71)
    ap.add_argument("--extrude", type=float, default=0.0)
    ap.add_argument("--bevel", type=float, default=0.0)
    ap.add_argument("--rise", type=float, default=0.015)
    ap.add_argument("--turn", type=float, default=0.0)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    a, unknown = ap.parse_known_args(argv)
    if unknown:
        print(f"blender_title: ignoring {unknown}", file=sys.stderr)
    return a


def set_engine(r) -> str:
    # EEVEE's id is BLENDER_EEVEE_NEXT in 4.2-4.5 and BLENDER_EEVEE again from 5.0.
    for name in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            r.engine = name
            return name
        except TypeError:
            continue
    sys.exit("blender_title: no EEVEE engine in this Blender")


def fcurves(idb) -> list:
    """F-curves of an ID's action on 4.x (action.fcurves) and 5.x (slotted channelbags)."""
    ad = idb.animation_data
    if not ad or not ad.action:
        return []
    if bpy.app.version < (5, 0, 0):
        return list(ad.action.fcurves)
    from bpy_extras import anim_utils
    bag = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    return list(bag.fcurves) if bag else []


def ease(idb, enter: int, leave: int) -> None:
    """The segment from frame `enter` lands softly (quartic ease-out); from `leave` it eases away."""
    for fc in fcurves(idb):
        for kp in fc.keyframe_points:
            f = round(kp.co.x)
            if f == enter:
                kp.interpolation, kp.easing = "QUART", "EASE_OUT"
            elif f == leave:
                kp.interpolation, kp.easing = "CUBIC", "EASE_IN"
            else:
                kp.interpolation = "LINEAR"


def linear(hex_color: str) -> tuple:
    rgb = tuple(int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb)


def material(a, lin: tuple) -> "bpy.types.Material":
    """Emission (flat) or shaded (lit) colour `lin` (linear RGB), mixed with clear by a "fade" node."""
    m = bpy.data.materials.new("title")
    if bpy.app.version < (5, 0, 0):  # node materials are always on from 5.0
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if a.look == "flat":
        surf = nt.nodes.new("ShaderNodeEmission")
        surf.inputs["Color"].default_value = (*lin, 1)
        surf.inputs["Strength"].default_value = 1.0
    else:
        surf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        surf.inputs["Base Color"].default_value = (*lin, 1)
        surf.inputs["Roughness"].default_value = 0.35
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.name = "fade"
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(surf.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    if hasattr(m, "surface_render_method"):  # EEVEE Next (4.2+)
        m.surface_render_method = "BLENDED"
    elif hasattr(m, "blend_method"):
        m.blend_method = "BLEND"
    # While it fades, show only the front surface, not the sides and back through it.
    m.use_backface_culling = True
    if hasattr(m, "use_transparency_overlap"):
        m.use_transparency_overlap = False
    elif hasattr(m, "show_transparent_back"):
        m.show_transparent_back = False
    return m


def build(a) -> None:
    W, H = (int(x) for x in a.size.lower().split("x"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    r = sc.render
    engine = set_engine(r)
    r.resolution_x, r.resolution_y, r.resolution_percentage = W, H, 100
    r.fps, r.fps_base = a.fps, 1.0
    r.film_transparent = True
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    r.image_settings.color_depth = "16"
    r.filepath = os.path.abspath(a.out)
    sc.view_settings.view_transform = "Standard"  # flat graphics must match sRGB/BT.709 footage
    sc.view_settings.look = "None"
    sc.frame_start, sc.frame_end = 1, a.frames

    # Orthographic camera whose frame is 1 unit tall: positions and sizes are frame fractions.
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type, cam.data.sensor_fit, cam.data.ortho_scale = "ORTHO", "VERTICAL", 1.0
    cam.location = (0, 0, 10)
    sc.collection.objects.link(cam)
    sc.camera = cam

    pivot = bpy.data.objects.new("pivot", None)
    sc.collection.objects.link(pivot)
    if a.text:
        cu = bpy.data.curves.new("title", "FONT")
        cu.body = a.text
        cu.align_x, cu.align_y = "CENTER", "CENTER"
        cu.size = a.height
        cu.extrude, cu.bevel_depth = a.extrude, a.bevel
        cu.offset = -a.bevel  # a bevel grows each outline outward; shrink it back so tight gaps don't overlap
        if a.font:
            cu.font = bpy.data.fonts.load(os.path.abspath(a.font))
        ob = bpy.data.objects.new("title", cu)
        mats = [material(a, linear(a.color or "FFFFFF"))]
        ob.data.materials.append(mats[0])
        sc.collection.objects.link(ob)
        ob.parent = pivot
        parts = [ob]
        bpy.context.view_layer.update()
        width = ob.dimensions.x
    else:
        from mathutils import Vector
        before = set(bpy.data.objects)
        try:
            bpy.ops.import_curve.svg(filepath=os.path.abspath(a.svg))
        except (AttributeError, RuntimeError) as e:
            sys.exit(f"blender_title: SVG import failed ({e}); enable the SVG importer or export the logo as text")
        parts = [o for o in bpy.data.objects if o not in before and o.type == "CURVE"]
        if not parts:
            sys.exit(f"blender_title: {a.svg} held no curves")
        # Keep each fill's colour (the importer stores it linear in diffuse_color) unless --color is set.
        made: dict[tuple, "bpy.types.Material"] = {}
        for o in parts:
            old = o.data.materials[0] if len(o.data.materials) else None
            lin = linear(a.color) if a.color else tuple(old.diffuse_color[:3]) if old else (1.0, 1.0, 1.0)
            key = tuple(round(c, 4) for c in lin)
            if key not in made:
                made[key] = material(a, lin)
            o.data.materials.clear()
            o.data.materials.append(made[key])
        mats = list(made.values())
        bpy.context.view_layer.update()
        pts = [o.matrix_world @ Vector(c) for o in parts for c in o.bound_box]
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        k = a.height / max(hi[1] - lo[1], 1e-6)
        for o in parts:
            o.parent = pivot
            o.location = [(o.location[i] - (lo[i] + hi[i]) / 2) * k for i in range(3)]
            o.scale = [s * k for s in o.scale]
            d = o.scale[0]  # depths are in frame heights after the fit, so divide out the object's scale
            o.data.extrude, o.data.bevel_depth, o.data.offset = a.extrude / d, a.bevel / d, -a.bevel / d
        width = (hi[0] - lo[0]) * k

    # Fit the safe column: shrink if wider than --max-width of the frame.
    limit = a.max_width * W / H
    if width > limit:
        pivot.scale = (limit / width,) * 3

    if a.look == "lit":
        sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(35), math.radians(-25), 0)
        sc.collection.objects.link(sun)
        # Grey world light fills the sides turned from the sun, which otherwise read as a dark outline.
        w = sc.world = bpy.data.worlds.new("w")
        if bpy.app.version < (5, 0, 0):
            w.use_nodes = True
        bg = w.node_tree.nodes.get("Background") if w.node_tree else None
        if bg:
            bg.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1)
        w.color = (0.5, 0.5, 0.5)

    # Keys: in over 0.3 s, hold, out over 0.17 s (exits run shorter than entrances).
    f0, f_in = 1, 1 + round(0.3 * a.fps)
    f_out, f1 = a.frames - round(0.17 * a.fps), a.frames
    if f_out <= f_in:
        sys.exit(f"blender_title: {a.frames} frames is too short for the reveal; use at least {f_in + 10}")
    y = 0.5 - a.y
    for f, alpha, dy, turn in ((f0, 0.0, -a.rise, -a.turn), (f_in, 1.0, 0, 0), (f_out, 1.0, 0, 0), (f1, 0.0, 0, 0)):
        for m in mats:
            fade = m.node_tree.nodes["fade"].inputs[0]
            fade.default_value = alpha
            fade.keyframe_insert("default_value", frame=f)
        pivot.location = (0, y + dy, 0)
        pivot.keyframe_insert("location", frame=f)
        pivot.rotation_euler = (0, math.radians(turn), 0)
        pivot.keyframe_insert("rotation_euler", frame=f)
    for m in mats:
        ease(m.node_tree, enter=f0, leave=f_out)
    ease(pivot, enter=f0, leave=f_out)
    print(f"blender_title: Blender {bpy.app.version_string}, {engine}, {W}x{H} @ {a.fps} fps, "
          f"{a.frames} frames -> {r.filepath}")


def main() -> None:
    a = args()
    if bpy is None:
        sys.exit("blender_title.py runs inside Blender: blender -b --factory-startup "
                 "--python-exit-code 1 -P blender_title.py -- --text ... --out ...")
    build(a)
    bpy.ops.render.render(animation=True)
    seq = a.out.replace("####", "%04d")
    print(f"next: ffmpeg -framerate {a.fps} -i {seq}.png -vf {PRORES_VF} -c:v prores_ks -profile:v 4444 "
          "-alpha_bits 16 -vendor apl0 title.mov")


if __name__ == "__main__":
    main()

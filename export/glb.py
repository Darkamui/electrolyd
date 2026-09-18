"""
glTF/GLB export.

    blender --background --python export/glb.py -- [--out PATH] [--no-apply]

Two modes, one script:

    (default)   the static cell, no animation — the smallest thing that still
                shows the whole pot, for a consumer that only needs to look
    --animated  the explosion rig BAKED to keyframes, so the GLB carries the
                assembly sequence as a real glTF animation. This is what the
                web viewer embeds: its slider scrubs the clip.

`--animated` is the Phase 7 delivery export and the reason it exists is blunt:
**drivers do not survive glTF.** The exporter writes node transforms and
animation tracks; a driver is neither. Exported as it stands, the rig arrives in
the browser as sixteen empties that never move and a custom property nothing
reads. `lib.explode.bake()` converts the drivers to two location keys per empty
before the export sees them, which the exporter does understand.

That also settles a divergence worth naming: with a baked animation in the file,
the web page no longer needs its own copy of the vector table. One description
of how this cell comes apart, in `spec.py`, reaching the browser through the
model rather than through a second implementation that has already drifted once.

Two things matter for a web viewer and are worth stating:

  * Modifiers are APPLIED. A bevel that only exists as a modifier is a bevel
    the browser never sees, and the booleans - the bath displaced by the
    anodes, the ramming paste with the blocks cut out - are not decoration,
    they are the geometry. Applying them costs mesh sharing, so the file is
    larger than the 74 datablocks in the .blend would suggest. For 64k
    triangles that trade is obviously worth it.
  * Object NAMES are the viewer's only handle on the model. Blender's
    exporter does not write collections as nodes, so the web page groups
    parts by the {NN}_{SUBSYSTEM}_ name prefix that lib/scene.py enforces.
    Renaming that convention breaks the viewer.

Nothing here reads a dimension. It is an I/O script.
"""

from __future__ import annotations

import argparse
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import build_all  # noqa: E402
from lib import explode  # noqa: E402


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="glb.py")
    p.add_argument("--out", default=None, help="output .glb path")
    p.add_argument(
        "--no-apply",
        action="store_true",
        help="skip modifiers; keeps mesh sharing but loses bevels and booleans",
    )
    p.add_argument(
        "--only",
        action="append",
        default=None,
        help="build only these modules (repeatable)",
    )
    p.add_argument(
        "--animated",
        action="store_true",
        help="bake the explosion rig to keyframes and export it as animation",
    )
    p.add_argument(
        "--frames",
        type=int,
        default=60,
        help="length of the baked explosion, in frames (--animated only)",
    )
    p.add_argument(
        "--decimate",
        type=float,
        default=None,
        metavar="RATIO",
        help="collapse every mesh to this fraction of its faces. Off by "
             "default, and measurement says leave it off: the model is 64k "
             "triangles against a 1.5M budget, so there is nothing to win, "
             "and collapse rounds exactly the machined edges — stub sockets, "
             "rib returns, the ledge taper — that the detail passes existed "
             "to produce. Here for a hostile target, not for this one.",
    )
    return p.parse_args(argv)


def decimate(ratio: float) -> int:
    """Add a COLLAPSE decimate to every visible mesh. Returns the count."""
    count = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.data is None or obj.hide_render:
            continue
        mod = obj.modifiers.new("EXPORT_decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        count += 1
    return count


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parse_args(argv)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = args.out or os.path.join(root, "out", "cell.glb")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    build_all.build(args.only, False)
    bpy.context.view_layer.update()

    baked = 0
    if args.animated:
        # From frame ZERO, not frame 1. The exporter times every key at its
        # absolute `frame / fps`, so a bake over 1..60 puts the assembled key at
        # 0.042 s inside a clip that starts at 0 — a dead zone at the bottom of
        # the viewer's slider, and a scrub that reads 49.2% of travel where the
        # slider says 50%. Starting at 0 makes clip time and explosion factor
        # the same number end to end.
        baked = explode.bake(0, args.frames)
        print(f"   baked {baked} rig empties to keyframes over "
              f"0..{args.frames}")

    if args.decimate is not None:
        print(f"   decimating {decimate(args.decimate)} meshes to "
              f"{args.decimate:.2f}")

    # Hidden objects are hidden for a reason - boolean cutters for the crust
    # and the ledge, which would otherwise export as solid blocks sitting in
    # the middle of the cell. use_visible drops them.
    bpy.ops.export_scene.gltf(
        filepath=out,
        export_format="GLB",
        use_visible=True,
        export_apply=not args.no_apply,
        export_yup=True,
        export_materials="EXPORT",
        export_animations=args.animated,
        export_frame_range=args.animated,
        export_optimize_animation_size=True,
        # SCENE, not the default ACTIONS. ACTIONS writes one glTF animation per
        # Blender action, and the bake leaves fifteen of them — so the file
        # arrives in a viewer as fifteen separate clips that only mean anything
        # played in lockstep, and `gltf.animations[0]` moves the shell and
        # nothing else. SCENE writes the scene's frame range as ONE clip, which
        # is what "the cell comes apart" actually is.
        export_animation_mode="SCENE",
        # ...and SCENE alone is not enough: it still splits one animation per
        # object unless this is turned off. With it off the fifteen empties
        # become fifteen channels of a single clip.
        export_anim_scene_split_object=False,
    )

    size = os.path.getsize(out)
    print("=" * 78)
    print(f"   exported {out}")
    print(f"   {size / 1048576.0:.2f} MB   modifiers "
          f"{'applied' if not args.no_apply else 'NOT applied'}"
          + (f"   animation 0..{args.frames} on {baked} nodes"
             if args.animated else "   no animation"))
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())

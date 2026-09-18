"""
Non-destructive transverse cutaway.

The user's reference is a transverse (Y–Z) cross-section, and that is the view
that proves the vertical stack: shell, refractory courses, cathode block with
its collector bars, metal pad, bath, crust, then the anode with its stubs, yoke
and stem rising to the beam. None of that is visible in a plain elevation —
the end enclosure box stands in front of the whole cell and hides it.

"Non-destructive" means exactly what it says: no mesh is edited and nothing is
deleted. Objects that straddle the cut get a named BOOLEAN modifier; objects
wholly on the cut side are merely hidden. `disable()` puts both back. The master
.blend therefore always holds the complete symmetric cell.

Why not boolean everything: an EXACT boolean on all 581 objects is slow and
most of them do not touch the plane at all. Classifying first means the solver
only runs on the handful of parts that genuinely need cutting.
"""

from __future__ import annotations

import bpy
from mathutils import Vector

import spec
from lib import build as B
from lib.scene import BuildContext
from lib.units import mm

MODIFIER_NAME = "SECTION"
CUTTER_PART = "section_cutter"
CUTTER_COLLECTION = "00_REFERENCES"

PAD_MM = 2000.0
"""
Overshoot of the cutter beyond the model on every free face.

The cutter must fully enclose the discarded half in Y and Z, or EXACT leaves a
sliver of shell wall standing in front of the section. Generous is free here —
the cutter is one box and is never rendered.
"""


def cut_plane_x(cell: spec.Cell) -> float:
    """X of the cut. Derived in spec, because render/cameras aims at it too."""
    return cell.section_plane_x


def _world_x_range(obj: bpy.types.Object) -> tuple[float, float]:
    """World-space X span, depsgraph-evaluated so arrays and mirrors count."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    mw = ev.matrix_world
    xs = [(mw @ Vector(c)).x for c in ev.bound_box]
    return min(xs), max(xs)


def _world_range(axis: int) -> tuple[float, float]:
    """World-space span of the whole model on one axis, in MILLIMETRES."""
    dg = bpy.context.evaluated_depsgraph_get()
    values: list[float] = []
    for obj in _all_meshes():
        ev = obj.evaluated_get(dg)
        mw = ev.matrix_world
        values += [(mw @ Vector(c))[axis] * 1000.0 for c in ev.bound_box]
    if not values:
        return 0.0, 0.0
    return min(values), max(values)


def _targets() -> list[bpy.types.Object]:
    """
    Every mesh the section may touch.

    Objects already hidden from render are excluded, and that exclusion is
    load-bearing: the model contains other booleans' cutters (the crust's anode
    footprints, the ledge core), which are hidden meshes spanning the whole
    cell. Adopting them would let disable() clear their hide flag and leave a
    cutter box standing in the middle of every later plate.
    """
    return [o for o in _all_meshes() if not o.hide_render]


def _all_meshes() -> list[bpy.types.Object]:
    """Every mesh except the section's own cutter, hidden or not."""
    return [
        o
        for o in bpy.context.scene.objects
        if o.type == "MESH" and o.data is not None and CUTTER_PART not in o.name
    ]


def build_cutter(ctx: BuildContext, cell: spec.Cell) -> bpy.types.Object:
    """
    The discarded half, as one box: everything at X below the cut plane.

    Lives in 00_REFERENCES because it is a construction aid, not part of the
    cell. B.boolean() hides it from viewport and render.
    """
    existing = bpy.data.objects.get(f"{CUTTER_COLLECTION}_{CUTTER_PART}_000")
    if existing is not None:
        # enable() runs once per sectioned shot. Building a second cutter would
        # collide on the name and get a ".001" suffix, which fails the naming
        # convention QA enforces.
        return existing

    plane = cut_plane_x(cell)
    lo_x = -cell.shell_outer_x / 2.0 - PAD_MM

    # Y and Z come from the MEASURED scene, not from spec. They were read off
    # the end enclosure, which is neither the tallest thing on the cell nor the
    # widest: the feeder stack tops out 1850 mm above it and the busbars reach
    # further out in Y. A cutter that stops short does not fail - it silently
    # leaves the discarded half of whatever it missed standing in the plate.
    lo_z, hi_z = _world_range(2)
    lo_y, hi_y = _world_range(1)

    size = (
        plane - lo_x,
        (hi_y - lo_y) + 2.0 * PAD_MM,
        (hi_z - lo_z) + 2.0 * PAD_MM,
    )
    centre = (
        (lo_x + plane) / 2.0,
        (lo_y + hi_y) / 2.0,
        (lo_z + hi_z) / 2.0,
    )
    cutter = B.box(ctx, CUTTER_PART, 0, size_mm=size, at_mm=centre)
    # A boolean cutter must never be visible itself. B.boolean() normally does
    # this; the modifiers here are set directly, so it has to be done here.
    cutter.hide_render = True
    cutter.hide_viewport = True
    return cutter


def enable(ctx: BuildContext, cell: spec.Cell | None = None) -> dict[str, int]:
    """
    Cut the scene. Returns a count of what was cut, hidden and left alone.

    Call after every module has built. Safe to call twice: the modifier is
    looked up by name rather than appended blindly.
    """
    cell = cell or ctx.cell
    plane_m = mm(cut_plane_x(cell))
    cutter = build_cutter(ctx.for_collection(CUTTER_COLLECTION), cell)

    bpy.context.view_layer.update()
    tally = {"cut": 0, "hidden": 0, "kept": 0}

    for obj in _targets():
        lo, hi = _world_x_range(obj)
        if hi <= plane_m:
            # Wholly in the discarded half. Hiding is cheaper than cutting
            # it away to nothing, and reversible.
            obj.hide_render = True
            obj.hide_viewport = True
            obj[MODIFIER_NAME] = "hidden"
            tally["hidden"] += 1
        elif lo >= plane_m:
            tally["kept"] += 1
        else:
            mod = obj.modifiers.get(MODIFIER_NAME)
            if mod is None:
                mod = obj.modifiers.new(MODIFIER_NAME, "BOOLEAN")
            mod.operation = "DIFFERENCE"
            mod.solver = "EXACT"
            mod.object = cutter
            mod.show_render = True
            mod.show_viewport = True
            tally["cut"] += 1

    return tally


def disable() -> None:
    """
    Restore the whole cell: unhide, and switch the cut modifiers off.

    Iterates every mesh, not _targets(), because the objects this has to undo
    are precisely the ones _targets() now filters out — the ones it hid.
    Only objects carrying the SECTION marker are unhidden, so cutters that were
    already hidden for their own reasons stay hidden.
    """
    for obj in _all_meshes():
        if obj.get(MODIFIER_NAME) == "hidden":
            obj.hide_render = False
            obj.hide_viewport = False
            del obj[MODIFIER_NAME]
        mod = obj.modifiers.get(MODIFIER_NAME)
        if mod is not None:
            mod.show_render = False
            mod.show_viewport = False

"""
Geometry primitives. The shared vocabulary every build module uses.

Design rules baked in here:

  * All sizes and positions are in MILLIMETRES. Conversion happens inside
    these helpers, never in a module.
  * Nothing depends on selection state or the active object, so modules are
    idempotent and order-independent. (The one unavoidable exception is
    auto_smooth(), which wraps an operator; it saves and restores selection.)
  * Geometry is authored with bmesh rather than bpy.ops.mesh.primitive_*,
    because the operators depend on cursor position, active collection and
    edit-mode state — all of which make results non-reproducible.
  * Every creator takes a BuildContext and links through it, so a module
    physically cannot write into another module's collection.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import bmesh
import bpy
from mathutils import Matrix, Vector

from lib.scene import BuildContext
from lib.units import mm, mm3

Vec3 = Sequence[float]


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------


def _finish(
    ctx: BuildContext,
    bm: bmesh.types.BMesh,
    part: str,
    index: int,
    at_mm: Vec3 = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    """Turn a bmesh into a named, linked object positioned at `at_mm`."""
    name = ctx.name(part, index)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.update()
    obj = bpy.data.objects.new(name, me)
    obj.location = mm3(at_mm)
    return ctx.link(obj)


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------


def box(
    ctx: BuildContext,
    part: str,
    index: int,
    size_mm: Vec3,
    at_mm: Vec3 = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    """
    Axis-aligned box, centred on its own origin, placed at `at_mm`.

    Origin at the box centre keeps mirroring and arraying predictable.
    Use box_on() when the datasheet gives you a base height instead.
    """
    sx, sy, sz = size_mm
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((mm(sx), mm(sy), mm(sz))), verts=bm.verts)
    return _finish(ctx, bm, part, index, at_mm)


def box_on(
    ctx: BuildContext,
    part: str,
    index: int,
    size_mm: Vec3,
    base_z_mm: float,
    at_xy_mm: Sequence[float] = (0.0, 0.0),
) -> bpy.types.Object:
    """
    Box sitting ON a given Z height — the way the datasheet's vertical stack is
    written (z_cathode_bottom, z_metal_top, ...). Avoids half-thickness
    arithmetic at every call site, which is a reliable source of layer gaps.
    """
    sx, sy, sz = size_mm
    x, y = at_xy_mm
    return box(ctx, part, index, size_mm, (x, y, base_z_mm + sz / 2.0))


def box_cluster(
    ctx: BuildContext,
    part: str,
    index: int,
    boxes_mm: Sequence[tuple[Vec3, Vec3]],
    at_mm: Vec3 = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    """
    One object holding many disjoint boxes, each given as (size_mm, centre_mm)
    in the object's own local space.

    Exists for boolean cutters. Subtracting 36 anode footprints from the crust
    with 36 separate BOOLEAN modifiers is both slow and fragile; one cutter and
    one modifier is the correct shape of that operation.

    DISJOINT IS A REQUIREMENT, NOT A DESCRIPTION. The boxes are welded into one
    mesh, so any two that overlap make the cutter self-intersecting, and the
    EXACT solver then returns a plausible-looking wrong result instead of an
    error. When two groups of cutters do overlap each other — collector bars
    inside cathode blocks, say — build one cluster per group and stack a
    BOOLEAN per cluster.
    """
    bm = bmesh.new()
    for size_mm, centre_mm in boxes_mm:
        sx, sy, sz = size_mm
        piece = bmesh.new()
        bmesh.ops.create_cube(piece, size=1.0)
        bmesh.ops.scale(
            piece, vec=Vector((mm(sx), mm(sy), mm(sz))), verts=piece.verts
        )
        bmesh.ops.translate(piece, vec=Vector(mm3(centre_mm)), verts=piece.verts)
        me = bpy.data.meshes.new("_tmp_cluster")
        piece.to_mesh(me)
        piece.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _finish(ctx, bm, part, index, at_mm)


def cylinder(
    ctx: BuildContext,
    part: str,
    index: int,
    diameter_mm: float,
    length_mm: float,
    at_mm: Vec3 = (0.0, 0.0, 0.0),
    axis: str = "Z",
    segments: int = 32,
) -> bpy.types.Object:
    """Cylinder centred on its origin, aligned to X, Y or Z."""
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segments,
        radius1=mm(diameter_mm / 2.0),
        radius2=mm(diameter_mm / 2.0),
        depth=mm(length_mm),
    )
    if axis.upper() == "X":
        bmesh.ops.rotate(
            bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 3, "Y")
        )
    elif axis.upper() == "Y":
        bmesh.ops.rotate(
            bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 3, "X")
        )
    elif axis.upper() != "Z":
        raise ValueError(f"axis must be X, Y or Z, got {axis!r}")
    return _finish(ctx, bm, part, index, at_mm)


def cylinder_cluster(
    ctx: BuildContext,
    part: str,
    index: int,
    cylinders_mm: Sequence[tuple[float, float, Vec3]],
    at_mm: Vec3 = (0.0, 0.0, 0.0),
    axis: str = "Z",
    segments: int = 32,
) -> bpy.types.Object:
    """
    box_cluster's round counterpart: one object holding many disjoint
    cylinders, each given as (diameter_mm, length_mm, centre_mm) in the
    object's own local space, all on the same axis.

    Exists for the same reason box_cluster does. Four stub sockets in an anode
    and five feed holes through the crust are each ONE hole pattern, and giving
    each hole its own BOOLEAN modifier makes the stack long, slow, and ordered
    — which matters, because a stack of booleans can fail differently depending
    on the order it happens to be in.

    DISJOINT IS A REQUIREMENT, exactly as for box_cluster: overlapping
    cylinders weld into a self-intersecting cutter, and EXACT answers a
    self-intersecting cutter with a plausible wrong solid rather than an error.
    """
    bm = bmesh.new()
    rotation = {
        "X": Matrix.Rotation(math.radians(90), 3, "Y"),
        "Y": Matrix.Rotation(math.radians(90), 3, "X"),
        "Z": None,
    }
    key = axis.upper()
    if key not in rotation:
        raise ValueError(f"axis must be X, Y or Z, got {axis!r}")

    for diameter_mm, length_mm, centre_mm in cylinders_mm:
        piece = bmesh.new()
        bmesh.ops.create_cone(
            piece,
            cap_ends=True,
            cap_tris=False,
            segments=segments,
            radius1=mm(diameter_mm / 2.0),
            radius2=mm(diameter_mm / 2.0),
            depth=mm(length_mm),
        )
        if rotation[key] is not None:
            bmesh.ops.rotate(piece, verts=piece.verts, matrix=rotation[key])
        bmesh.ops.translate(piece, vec=Vector(mm3(centre_mm)), verts=piece.verts)
        me = bpy.data.meshes.new("_tmp_cluster")
        piece.to_mesh(me)
        piece.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _finish(ctx, bm, part, index, at_mm)


def arc_panel(
    ctx: BuildContext,
    part: str,
    index: int,
    radius_mm: float,
    arc_deg: float,
    width_mm: float,
    at_mm: Vec3 = (0.0, 0.0, 0.0),
    segments: int = 24,
    start_deg: float = 0.0,
) -> bpy.types.Object:
    """
    Open curved panel: an arc swept in the Y-Z plane, extruded along X.

    This is the hood-panel primitive. The arc sweeps from `start_deg`
    (0 = straight up, +90 = horizontal outward in +Y), matching the way the
    real panels roll from the superstructure down and out to the shell rim.

    Produces a single-thickness surface. Give it a wall with solidify().
    """
    bm = bmesh.new()
    half_w = mm(width_mm / 2.0)
    r = mm(radius_mm)

    rings: list[list[bmesh.types.BMVert]] = []
    for x in (-half_w, half_w):
        ring = []
        for i in range(segments + 1):
            t = math.radians(start_deg + arc_deg * i / segments)
            ring.append(bm.verts.new((x, r * math.sin(t), r * math.cos(t))))
        rings.append(ring)

    bm.verts.ensure_lookup_table()
    a, b = rings
    for i in range(segments):
        bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _finish(ctx, bm, part, index, at_mm)


def loft_rings(
    ctx: BuildContext,
    part: str,
    index: int,
    rings_mm: Sequence[Sequence[Vec3]],
    at_mm: Vec3 = (0.0, 0.0, 0.0),
    cap: bool = True,
) -> bpy.types.Object:
    """
    Loft a closed solid through a stack of rings.

    Every ring must be a closed loop with the SAME number of points, ordered
    consistently. Consecutive rings are bridged with quads.

    This is the ledge primitive: the frozen-bath wedge is a rectangular ring
    whose inner contour moves inward as it descends, so it cannot be expressed
    as a box or an extrusion.
    """
    counts = {len(r) for r in rings_mm}
    if len(counts) != 1:
        raise ValueError(f"all rings must have equal point counts, got {counts}")
    if len(rings_mm) < 2:
        raise ValueError("need at least two rings to loft")

    bm = bmesh.new()
    rings = [[bm.verts.new(mm3(p)) for p in ring] for ring in rings_mm]
    bm.verts.ensure_lookup_table()

    n = len(rings[0])
    for lower, upper in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((lower[i], lower[j], upper[j], upper[i]))

    if cap:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _finish(ctx, bm, part, index, at_mm)


def rect_ring(
    half_x_mm: float, half_y_mm: float, z_mm: float
) -> list[tuple[float, float, float]]:
    """A rectangular loop at height z. Feed these to loft_rings()."""
    return [
        (-half_x_mm, -half_y_mm, z_mm),
        (half_x_mm, -half_y_mm, z_mm),
        (half_x_mm, half_y_mm, z_mm),
        (-half_x_mm, half_y_mm, z_mm),
    ]


# --- rings sampled by ANGLE -------------------------------------------------
#
# loft_rings needs equal point counts in a consistent order. The three below
# are all parametrised by the SAME angle sweep, so any of them lofts into any
# other without a twist. That is what makes a square-to-round transition — a
# rectangular mouth necking into a round collar — expressible at all; the
# four-point rect_ring above cannot bridge to a circle.


def _angles(segments: int, start_deg: float) -> list[float]:
    base = math.radians(start_deg)
    return [base + 2.0 * math.pi * i / segments for i in range(segments)]


def circle_ring(
    radius_mm: float,
    z_mm: float,
    segments: int = 32,
    start_deg: float = 0.0,
) -> list[tuple[float, float, float]]:
    """A circular loop at height z, swept counter-clockwise from +X."""
    return [
        (radius_mm * math.cos(t), radius_mm * math.sin(t), z_mm)
        for t in _angles(segments, start_deg)
    ]


def rect_ring_polar(
    half_x_mm: float,
    half_y_mm: float,
    z_mm: float,
    segments: int = 32,
    start_deg: float = 0.0,
) -> list[tuple[float, float, float]]:
    """
    A rectangular loop sampled at the angles circle_ring uses: each point is
    where the ray at that angle meets the rectangle's wall.

    Point spacing along the perimeter is therefore uneven — dense at the flats,
    sparse at the corners — which is the price of the angular correspondence,
    and the correspondence is what keeps the loft's quads from spiralling.
    """
    points: list[tuple[float, float, float]] = []
    for t in _angles(segments, start_deg):
        c, s = math.cos(t), math.sin(t)
        reach = min(
            half_x_mm / abs(c) if abs(c) > 1e-9 else math.inf,
            half_y_mm / abs(s) if abs(s) > 1e-9 else math.inf,
        )
        points.append((reach * c, reach * s, z_mm))
    return points


def saddle_ring(
    radius_mm: float,
    axis_z_mm: float,
    segments: int = 32,
    start_deg: float = 0.0,
) -> list[tuple[float, float, float]]:
    """
    The curve where a vertical collar of `radius_mm` meets the UNDERSIDE of a
    horizontal cylinder of the same radius running along Y at `axis_z_mm`.

    This is the branch-onto-header cut, and for equal radii it is exact rather
    than approximate: subtracting the two cylinder equations leaves
    (z - axis_z)^2 = y^2, so the intersection is a pair of plane ellipses and
    the lower one is simply z = axis_z - |y|.

    The collar therefore climbs from the header's underside at y = +/-r to the
    header's full width at y = 0, seating on the pipe all the way round instead
    of meeting it along a single tangent line.
    """
    return [
        (
            radius_mm * math.cos(t),
            radius_mm * math.sin(t),
            axis_z_mm - abs(radius_mm * math.sin(t)),
        )
        for t in _angles(segments, start_deg)
    ]


# ---------------------------------------------------------------------------
# repetition
# ---------------------------------------------------------------------------


def linked_copy(
    ctx: BuildContext,
    source: bpy.types.Object,
    part: str,
    index: int,
    at_mm: Vec3,
) -> bpy.types.Object:
    """
    Duplicate SHARING the source mesh datablock.

    This is how 36 anodes cost one mesh. Verified on this build: 5 objects
    sharing one mesh reports users=5. glTF preserves the sharing on export, so
    it is also the WebGL budget strategy. Never use a deep copy for a
    repeated part.
    """
    obj = bpy.data.objects.new(ctx.name(part, index), source.data)
    obj.location = mm3(at_mm)
    return ctx.link(obj)


def instance_at(
    ctx: BuildContext,
    source: bpy.types.Object,
    part: str,
    positions_mm: Iterable[Vec3],
    start_index: int = 0,
) -> list[bpy.types.Object]:
    """linked_copy over a list of positions. The repeated-part workhorse."""
    return [
        linked_copy(ctx, source, part, start_index + i, pos)
        for i, pos in enumerate(positions_mm)
    ]


# ---------------------------------------------------------------------------
# modifiers
# ---------------------------------------------------------------------------


def bevel(
    obj: bpy.types.Object,
    width_mm: float = 8.0,
    segments: int = 2,
    angle_deg: float = 30.0,
) -> bpy.types.Modifier:
    """
    Manufacturing bevel. Every real steel edge has one; without it, renders
    read as CG because perfectly sharp edges never catch a highlight.
    """
    m = obj.modifiers.new("Bevel", "BEVEL")
    m.width = mm(width_mm)
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle_deg)
    m.harden_normals = False
    return m


def solidify(
    obj: bpy.types.Object, thickness_mm: float, offset: float = -1.0
) -> bpy.types.Modifier:
    """Give a surface a wall. offset -1 thickens inward, +1 outward."""
    m = obj.modifiers.new("Solidify", "SOLIDIFY")
    m.thickness = mm(thickness_mm)
    m.offset = offset
    return m


def mirror(
    obj: bpy.types.Object, x: bool = False, y: bool = False, z: bool = False
) -> bpy.types.Modifier:
    """
    Mirror about the world origin. The cell is symmetric about X=0 and Y=0, so
    most structure is authored once and mirrored.
    """
    m = obj.modifiers.new("Mirror", "MIRROR")
    m.use_axis = (x, y, z)
    m.use_clip = True
    return m


def array(
    obj: bpy.types.Object, count: int, offset_mm: Vec3
) -> bpy.types.Modifier:
    """Constant-offset array. For evenly repeated structure like hood ribs."""
    m = obj.modifiers.new("Array", "ARRAY")
    m.count = count
    m.use_relative_offset = False
    m.use_constant_offset = True
    m.constant_offset_displace = mm3(offset_mm)
    return m


def boolean(
    obj: bpy.types.Object,
    cutter: bpy.types.Object,
    operation: str = "DIFFERENCE",
) -> bpy.types.Modifier:
    """
    Boolean with the EXACT solver. Used for collector-bar slots, the crust's
    anode footprints, and the non-destructive section cut.

    The cutter stays in the scene but should be hidden from render.
    """
    m = obj.modifiers.new("Boolean", "BOOLEAN")
    m.operation = operation
    m.object = cutter
    m.solver = "EXACT"
    cutter.hide_render = True
    cutter.hide_viewport = True
    return m


def carve(
    ctx: BuildContext,
    obj: bpy.types.Object,
    cutter: bpy.types.Object,
    operation: str = "DIFFERENCE",
) -> bpy.types.Object:
    """
    Boolean BAKED INTO THE MESH DATABLOCK, then cutter and modifier removed.

    Use this, not boolean(), for any feature that must appear on every linked
    copy of a master part: collector-bar slots in a cathode block, stub sockets
    and gas slots in an anode. A modifier lives on the OBJECT, so 35 linked
    copies of a slotted anode would show 35 unslotted blocks and one slotted
    one. Baking puts the feature in the shared mesh, where all 36 see it and
    the datablock count does not move.

    boolean() remains correct for one-off cuts on unique objects and for the
    section rig, where being reversible is the whole point.

    There is no bmesh boolean op, so this goes the long way round: evaluate the
    modifier through the depsgraph, read the result back, and write it into the
    original mesh. Three details make or break it.

      * view_layer.update() first. The cutter was very likely just created and
        positioned, and its matrix_world is stale until the depsgraph catches
        up. Evaluating against a stale cutter cuts the wrong place, silently.
      * Every OTHER modifier is muted for the bake. The depsgraph applies the
        whole stack, so carving a block that already carries a Bevel would bake
        the bevel in too — and then the still-live Bevel modifier would run a
        second time over the baked edges. Muting leaves the stack intact and
        still live afterwards.
      * The result is read into a NEW mesh and swapped in, rather than written
        over the mesh currently feeding the modifier.

    Order matters at the call site: carve BEFORE linked_copy, or the copies
    share the mesh as it was, not as it ends up.

    Returns obj, so calls chain.
    """
    muted = [m for m in obj.modifiers if m.show_viewport]
    for m in muted:
        m.show_viewport = False

    modifier = boolean(obj, cutter, operation)
    modifier.name = "CarveTemp"
    modifier.show_viewport = True

    bpy.context.view_layer.update()

    dg = bpy.context.evaluated_depsgraph_get()
    baked = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), depsgraph=dg)

    obj.modifiers.remove(modifier)
    for m in muted:
        m.show_viewport = True

    old = obj.data
    obj.data = baked
    if old.users == 0:
        name = old.name
        bpy.data.meshes.remove(old)
        baked.name = name

    ctx.discard(cutter)
    return obj


# ---------------------------------------------------------------------------
# shading
# ---------------------------------------------------------------------------


def shade_flat(obj: bpy.types.Object) -> None:
    """Flat shading. Correct default for plate steel and carbon blocks."""
    for poly in obj.data.polygons:
        poly.use_smooth = False


def auto_smooth(obj: bpy.types.Object, angle_deg: float = 30.0) -> None:
    """
    Angle-based smooth shading, for curved parts: hood panels, ducts, stubs.

    mesh.use_auto_smooth was REMOVED in Blender 4.1 (confirmed absent on this
    build). The replacement is an operator that adds a 'Smooth by Angle'
    modifier, so this is the one helper that touches selection state. It saves
    and restores it to preserve module idempotency.
    """
    view_layer = bpy.context.view_layer
    prev_active = view_layer.objects.active
    prev_selected = [o for o in bpy.context.selected_objects]

    try:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        view_layer.objects.active = obj
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle_deg))
    finally:
        bpy.ops.object.select_all(action="DESELECT")
        for o in prev_selected:
            try:
                o.select_set(True)
            except RuntimeError:
                pass
        view_layer.objects.active = prev_active

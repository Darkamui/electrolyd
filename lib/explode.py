"""
Exploded-view rig.

One float drives the whole model apart, exactly as the production prompt asks:
`Explosion` on the master empty, 0.0 assembled to 1.0 fully separated.

    CTRL (10_EXPLOSION_master_000)  ["Explosion"] = 0.0 .. 1.0
      |
      +-- 10_EXPLOSION_shell_000            <- drivers on location
      |     01_SHELL_plate_000, ...         <- parented, unmoved locally
      +-- 10_EXPLOSION_hooding_panels_000
      ...

Why empties and drivers rather than moving the objects:

  * The model is never edited. At Explosion = 0 every object sits exactly where
    its module put it, so QA's clearance assertions and the section cut measure
    the real cell, not a rigged approximation.
  * One number is the entire interface. Rendering the 0 / 25 / 50 / 100 series
    is four assignments, not four builds.
  * 723 painted objects move as nine or eleven transforms.

The rig is built AFTER every module, because it can only parent what exists.
Like the material pass it reaches across collection boundaries, and for the same
reason: a module knows what it built, not how the cell comes apart.

glTF caveat, carried from the plan: drivers do NOT export. `export/glb.py` bakes
the driven transforms to keyframes. The master .blend keeps the live drivers.
"""

from __future__ import annotations

import bpy
from mathutils import Vector

import spec
from lib.scene import BuildContext, fcurves
from lib.units import mm

MASTER = "10_EXPLOSION_master_000"
PROP = "Explosion"


def _part_token(obj: bpy.types.Object, collection: str) -> str:
    """`08_HOODING_end_box_003` -> `end_box`, given its collection."""
    return obj.name[len(collection) + 1:].rsplit("_", 1)[0]


def _groups_for(collection: str) -> tuple[tuple, ...]:
    """
    The travel groups of one subsystem.

    Most subsystems have exactly one, synthesised from EXPLOSION_VECTORS. The
    two that are built in halves declare their own in EXPLOSION_SPLITS, and
    their catch-all group inherits nothing — the split table carries its own
    direction and distance, so a split subsystem is described in one place.
    """
    if collection in spec.EXPLOSION_SPLITS:
        return spec.EXPLOSION_SPLITS[collection]
    dx, dy, dz, dist = spec.EXPLOSION_VECTORS[collection]
    return (("", None, dx, dy, dz, dist, False),)


def _dominant_axis(direction: tuple[float, float, float]) -> int:
    """Index of the axis a mirrored group separates along."""
    return max(range(3), key=lambda i: abs(direction[i]))


def _side_of(obj: bpy.types.Object, axis: int) -> float:
    """
    Which side of the cell this part is ON, along one axis.

    The centre of its geometry, NOT its origin. Origins are placed at a part's
    own logical centre or mounting face, and for a part whose mounting face is
    the cell centreline that is y = 0 for both halves of the pair. Splitting on
    the origin sent all forty collector-flex clamps to +Y, and the twenty that
    live at y = -2705 travelled 5.7 m through the cathode they were clamped
    beside. The geometry centre cannot lie about which side a part is on.
    """
    if getattr(obj, "data", None) is None or not hasattr(obj.data, "vertices"):
        return obj.matrix_world.translation[axis]
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return sum(c[axis] for c in corners) / len(corners)


def _drive(empty: bpy.types.Object, ctrl: bpy.types.Object,
           travel_m: tuple[float, float, float]) -> int:
    """
    Add one scripted driver per axis that actually travels.

    Only non-zero axes get a driver. A driver that always evaluates to zero is
    not free — it is one more thing that can go stale, show up as a red channel
    in the UI, and need explaining — and an axis with no driver is visibly, and
    correctly, an axis that does not move.
    """
    added = 0
    for axis, metres in enumerate(travel_m):
        if abs(metres) < 1e-9:
            continue
        fc = empty.driver_add("location", axis)
        drv = fc.driver
        drv.type = "SCRIPTED"
        var = drv.variables.new()
        var.name = "expl"
        var.type = "SINGLE_PROP"
        var.targets[0].id = ctrl
        var.targets[0].data_path = f'["{PROP}"]'
        drv.expression = f"expl * {metres:.6f}"
        added += 1
    return added


def build(ctx: BuildContext) -> list[bpy.types.Object]:
    """
    Create the master control and one empty per travel group, and parent every
    subsystem object to the group it belongs to.

    `ctx` must be scoped to 10_EXPLOSION.
    """
    # Resolve the transforms the modules just wrote before reading any of them.
    # `matrix_world` is a CACHE, refreshed on depsgraph evaluation, and a module
    # that sets `obj.location` leaves it stale until something asks the
    # depsgraph. Nothing had, so every part still measured as sitting at the
    # origin: the mirror split saw all forty flex clamps on the centreline and
    # sent the whole lot to +Y. The failure is silent — a stale matrix is a
    # valid matrix — and identical in kind to the lazy drivers in
    # `set_explosion` below, one step earlier in the pipeline.
    bpy.context.view_layer.update()

    ctrl = bpy.data.objects.new(ctx.name("master", 0), None)
    ctrl.empty_display_type = "PLAIN_AXES"
    ctrl.empty_display_size = mm(spec.CELL.shell_outer_x / 8.0)
    ctx.link(ctrl)
    ctrl[PROP] = 0.0
    ctrl.id_properties_ui(PROP).update(
        min=0.0, max=1.0, soft_min=0.0, soft_max=1.0,
        description="0 = assembled, 1 = fully exploded",
    )

    index = 0
    for collection, (dx, dy, dz, _dist) in spec.EXPLOSION_VECTORS.items():
        coll = bpy.data.collections.get(collection)
        if coll is None or not coll.objects:
            continue

        subsystem = collection.split("_", 1)[1].lower()
        groups = _groups_for(collection)

        # Resolve every object to a group first, so a part that matches no
        # family is a loud failure rather than a part that quietly stays behind
        # while the rest of its subsystem leaves.
        claimed = {
            fam: gi
            for gi, g in enumerate(groups)
            for fam in (g[1] or ())
        }
        members: list[list[bpy.types.Object]] = [[] for _ in groups]
        catch_all = next(i for i, g in enumerate(groups) if g[1] is None)

        for obj in coll.objects:
            # Parent only roots. Anything a module already parented travels
            # with its own parent, which is what that parenting was for.
            if obj.parent is not None:
                continue
            members[claimed.get(_part_token(obj, collection), catch_all)].append(obj)

        for gi, (suffix, _families, gdx, gdy, gdz, dist, mirror) in enumerate(groups):
            if not members[gi]:
                continue

            token = f"{subsystem}_{suffix}" if suffix else subsystem
            direction = (gdx, gdy, gdz)
            axis = _dominant_axis(direction)

            # A mirrored group is two empties travelling opposite ways, split on
            # the sign of each part's own position along the travel axis. One
            # empty cannot open a subsystem outward, and sending both halves one
            # way drives half of them back through the cell they came out of.
            sides = ((1.0, "hi"), (-1.0, "lo")) if mirror else ((1.0, ""),)

            for sign, side in sides:
                if mirror:
                    picked = [
                        o for o in members[gi]
                        if (_side_of(o, axis) >= 0.0) == (sign > 0.0)
                    ]
                else:
                    picked = members[gi]
                if not picked:
                    continue

                name = ctx.name(f"{token}_{side}" if side else token, index)
                index += 1
                empty = bpy.data.objects.new(name, None)
                empty.empty_display_type = "SINGLE_ARROW"
                empty.empty_display_size = mm(dist / 4.0) or 0.5
                ctx.link(empty)

                _drive(empty, ctrl, tuple(mm(c * dist) * sign for c in direction))

                for obj in picked:
                    obj.parent = empty
                    # The empties sit at the origin while assembled, so this is
                    # the identity today. Setting it anyway means the rig still
                    # holds if an empty is ever given a rest offset.
                    obj.matrix_parent_inverse = empty.matrix_world.inverted()

    return ctx.created


# ---------------------------------------------------------------------------


def master() -> bpy.types.Object | None:
    """The control empty, or None if the rig was not built."""
    return bpy.data.objects.get(MASTER)


def groups() -> list[bpy.types.Object]:
    """Every rig empty that actually carries drivers, master excluded."""
    return [
        o for o in bpy.data.objects
        if o.name.startswith("10_EXPLOSION_") and o.name != MASTER
        and o.animation_data is not None and o.animation_data.drivers
    ]


def bake(frame_start: int = 1, frame_end: int = 60) -> int:
    """
    Replace the rig's drivers with location keyframes. Returns the empty count.

    **Drivers do not survive glTF export.** The exporter writes node transforms
    and animation tracks; a driver is neither, and a custom property with no
    driver reading it is an inert number. Without this bake the delivery GLB is
    a permanently assembled cell carrying the one thing the whole rig exists to
    provide, disabled.

    Two things about the method are deliberate:

      * The samples come from the EVALUATED objects, not from `spec`. A driver's
        expression is the authority on where its empty goes. Re-deriving the
        travel here from the vector table would let the bake and the rig
        disagree silently — the bake would be right about the datasheet and
        wrong about the model.
      * BOTH ends are sampled before ANY driver is removed. Removing a driver
        frees the channel and leaves behind whatever value it last wrote, so an
        interleaved sample-then-remove loop reads that residue for every empty
        after the first and bakes a cell that half explodes.

    This is DESTRUCTIVE to the rig: afterwards the `Explosion` property drives
    nothing. Only ever call it in a throwaway export session, never in one that
    goes on to save `out/cell.blend`.
    """
    ctrl = master()
    if ctrl is None:
        raise RuntimeError("explosion rig not built: no " + MASTER)

    rig = groups()
    samples: dict[str, list[Vector]] = {o.name: [] for o in rig}
    for value in (0.0, 1.0):
        set_explosion(value)
        dg = bpy.context.evaluated_depsgraph_get()
        for obj in rig:
            samples[obj.name].append(
                obj.evaluated_get(dg).matrix_world.translation.copy()
            )

    set_explosion(0.0)
    for obj in rig:
        for fcurve in list(obj.animation_data.drivers):
            obj.animation_data.drivers.remove(fcurve)
        for frame, loc in zip((frame_start, frame_end), samples[obj.name]):
            obj.location = loc
            obj.keyframe_insert("location", frame=frame)

        # LINEAR, against Blender's bezier default. This clip is not a
        # performance, it is a LOOKUP TABLE: the web viewer scrubs it with a
        # 0-100 slider, so time t through the clip has to mean explosion t, the
        # same number `--explode t` renders. Bezier between two keys eases both
        # ends, and measurement put the quarter mark at 14% of travel and the
        # three-quarter mark at 84% — the page and the plates would disagree
        # about what "25%" is. The delivery MP4 keeps its easing; it is keyed
        # separately, on the control property, in render/anim.py.
        for fcurve in fcurves(obj):
            for keyframe in fcurve.keyframe_points:
                keyframe.interpolation = "LINEAR"

    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = frame_start, frame_end
    scene.frame_set(frame_start)
    return len(rig)


def set_explosion(value: float) -> float:
    """
    Set the explosion factor and force the depsgraph to catch up.

    The update is not optional. Drivers are evaluated lazily, so without it a
    render started immediately after the assignment can use the previous frame's
    transforms — which fails as an off-by-one-shot in a rendered series, the
    hardest kind of error to see in a contact sheet.
    """
    ctrl = master()
    if ctrl is None:
        raise RuntimeError("explosion rig not built: no " + MASTER)
    value = max(0.0, min(1.0, float(value)))
    ctrl[PROP] = value
    ctrl.update_tag()
    bpy.context.view_layer.update()
    return value

"""
Hooding: the curved, ribbed side hood panels with their lifting handles, the
removable centre covers over the anodes, and the tall end enclosure boxes
with their access doors.

Phase 3 detail pass. Three additions over the blockout:

  * Lifting handles. In the reference photograph these are the brightest
    thing on the cell - a row of them catching the light all down the hood
    line - and without them a panel is a piece of bent plate with no way to
    remove it. They sit at the arc's MIDPOINT, derived in spec, because that
    is where a panel balances as it comes away.
  * Centre covers. With the beams outboard at the rodding, the span between
    them was open sky over 36 anodes: the hood curved beautifully down both
    sides of a cell that was venting straight up. The covers close it, rest
    on the beams' inner ledges, and stop short of the anode stems so they can
    be lifted without unclamping a rod.
  * The end enclosures got a face. Their outer face is 4830 x 1685 mm - the
    largest single face on the cell and the foreground of both the front
    elevation and the hero - and through Phase 2 it was 86% bare plate with
    one door on it. It now carries the hood's own rib pitch, a capping plate,
    a second door, framed openings, and the pot number the Hooding docstring
    always claimed it carried.

Every dimension comes from ctx.cell / ctx.cell.hooding. The panel's radius,
arc centre and start angle are FULLY DERIVED in spec.py from the two anchors a
panel must physically touch - the anode beam above and the shell rim below -
so this module never recomputes or chooses them.

    panel(28), rib(28), handle(56+4), cover(14), end_box(2), end_cap(2),
    end_rib(2), side_rib(4), door_frame(4), door(4), number_plate(2)
        = 150 objects, 17 mesh datablocks.

The four door handles are linked copies of the hood handle, not a new part:
same shop, same stock, and therefore no extra datablock.

Panels, ribs and handles come in two families - a +Y run of 14 built directly
from cell.hood_arc_centre, and a mirrored -Y run at the same |Y| with
rotation_euler.z = pi (never a negative scale, which the QA validator flags).

Covers are the exception to shared mesh data, and deliberately so: the six a
feeder passes through are each pierced at a DIFFERENT offset from their own
centre, so they are genuinely six different parts and cannot share a
datablock with each other or with the eight plain ones. Nothing is gained by
pretending otherwise - see the loop for how they are separated.
"""

from __future__ import annotations

import math

import bpy

from lib import build as B
from lib.scene import BuildContext


def build(ctx: BuildContext) -> list[bpy.types.Object]:
    """28 panels, 28 ribs, 56 handles, 14 centre covers, 2 end boxes, 2 doors."""
    cell = ctx.cell
    h = cell.hooding
    sx = cell.shell_outer_x
    panel_w = h.panel_x(sx)
    cy, cz = cell.hood_arc_centre
    positions_x = h.panel_positions_x(sx)

    # -- 1. panel: 28 objects, 1 mesh ---------------------------------------
    # arc_panel sweeps about the object's own origin, so every panel's
    # location IS the arc centre - (cy, cz) on the +Y side, (-cy, cz) mirrored.
    panel0 = B.arc_panel(
        ctx,
        "panel",
        0,
        radius_mm=cell.hood_radius,
        arc_deg=cell.hood_arc_deg,
        width_mm=panel_w,
        at_mm=(positions_x[0], cy, cz),
        segments=h.curve_segments,
        start_deg=cell.hood_start_deg,
    )
    B.solidify(panel0, h.panel_thickness)
    B.auto_smooth(panel0)

    plus_panels = B.instance_at(
        ctx,
        panel0,
        "panel",
        [(x, cy, cz) for x in positions_x[1:]],
        start_index=1,
    )
    for obj in plus_panels:
        B.solidify(obj, h.panel_thickness)
        B.auto_smooth(obj)

    minus_panels = B.instance_at(
        ctx,
        panel0,
        "panel",
        [(x, -cy, cz) for x in positions_x],
        start_index=1 + len(plus_panels),
    )
    for obj in minus_panels:
        obj.rotation_euler.z = math.pi
        B.solidify(obj, h.panel_thickness)
        B.auto_smooth(obj)

    # -- 2. rib: 28 objects, 1 mesh ------------------------------------------
    # Ribs stand proud on the panel's OUTER face - the larger radius, since
    # the arc centre sits inboard and below. Solidify then fills inward from
    # that outer radius back down onto the panel surface at cell.hood_radius.
    n_ribs = h.ribs_per_panel(sx)
    rib_pitch = panel_w / n_ribs

    def rib_x(px: float) -> float:
        # The array grows in +X from the object, so inset the first rib by
        # half a pitch to centre the run across the panel width.
        return px - panel_w / 2.0 + rib_pitch / 2.0

    rib0 = B.arc_panel(
        ctx,
        "rib",
        0,
        radius_mm=cell.hood_radius + h.rib_depth,
        arc_deg=cell.hood_rib_arc_deg,
        width_mm=h.rib_width,
        at_mm=(rib_x(positions_x[0]), cy, cz),
        segments=h.curve_segments,
        start_deg=cell.hood_rib_start_deg,
    )
    B.solidify(rib0, h.rib_depth)
    B.array(rib0, count=n_ribs, offset_mm=(rib_pitch, 0.0, 0.0))
    B.auto_smooth(rib0)

    plus_ribs = B.instance_at(
        ctx,
        rib0,
        "rib",
        [(rib_x(x), cy, cz) for x in positions_x[1:]],
        start_index=1,
    )
    for obj in plus_ribs:
        B.solidify(obj, h.rib_depth)
        B.array(obj, count=n_ribs, offset_mm=(rib_pitch, 0.0, 0.0))

    minus_ribs = B.instance_at(
        ctx,
        rib0,
        "rib",
        [(rib_x(x), -cy, cz) for x in positions_x],
        start_index=1 + len(plus_ribs),
    )
    for obj in minus_ribs:
        obj.rotation_euler.z = math.pi
        B.solidify(obj, h.rib_depth)
        B.array(obj, count=n_ribs, offset_mm=(rib_pitch, 0.0, 0.0))

    # -- 3. handle: 56 objects, 1 mesh ---------------------------------------
    # A staple: a bar standing off the panel on two short legs. The legs run
    # RADIALLY out from the panel surface and the bar spans between their tops,
    # so the three boxes stack end to end and never overlap - cylinder_cluster
    # and box_cluster both weld without a boolean, and a self-intersecting
    # cluster returns a plausible wrong solid rather than an error.
    #
    # The mesh is authored with local +Z pointing radially outward from the
    # panel surface. Each object is then rolled about X by the handle's arc
    # angle, which is exactly the rotation that takes local +Z onto the radius
    # at that angle. Its origin sits ON the panel's outer face, so the legs
    # start at zero and the spec's handle_standoff is measured from the surface
    # it stands off, as its name says.
    t = math.radians(cell.hood_handle_deg)
    handle_r = cell.hood_radius
    leg_dx = (h.handle_length - h.handle_section) / 2.0

    handle_boxes = [
        (
            (h.handle_length, h.handle_section, h.handle_section),
            (0.0, 0.0, h.handle_standoff + h.handle_section / 2.0),
        ),
        (
            (h.handle_section, h.handle_section, h.handle_standoff),
            (-leg_dx, 0.0, h.handle_standoff / 2.0),
        ),
        (
            (h.handle_section, h.handle_section, h.handle_standoff),
            (leg_dx, 0.0, h.handle_standoff / 2.0),
        ),
    ]

    n_handles = h.handle_per_panel
    handle_offsets = [
        -panel_w / 2.0 + (i + 0.5) * panel_w / n_handles for i in range(n_handles)
    ]
    handle_y = cy + handle_r * math.sin(t)
    handle_z = cz + handle_r * math.cos(t)

    handle_stations = [
        (px + offset, sign)
        for sign in (1.0, -1.0)
        for px in positions_x
        for offset in handle_offsets
    ]

    handle0 = B.box_cluster(
        ctx,
        "handle",
        0,
        handle_boxes,
        at_mm=(handle_stations[0][0], handle_y, handle_z),
    )
    handle0.rotation_euler.x = -t
    B.shade_flat(handle0)
    B.bevel(handle0, h.handle_bevel)

    for index, (hx, sign) in enumerate(handle_stations[1:], start=1):
        obj = B.linked_copy(
            ctx, handle0, "handle", index, (hx, sign * handle_y, handle_z)
        )
        # Rolling about X puts the staple on the radius; the extra half turn
        # about Z carries it to the -Y run, exactly as the panels and ribs are
        # carried there.
        obj.rotation_euler.x = -t
        if sign < 0.0:
            obj.rotation_euler.z = math.pi
        B.bevel(obj, h.handle_bevel)

    # -- 4. cover: 14 objects, 7 meshes --------------------------------------
    # One cover per panel bay, tiling exactly the run the panels tile. A cover
    # a feeder passes through is pierced where it passes; a cover no feeder
    # reaches is plain, and those eight share one datablock.
    #
    # The hole is carved into the mesh rather than left as a BOOLEAN modifier
    # for the usual reason - but here the reason is inverted and worth stating:
    # these covers must NOT share data, so carving is what keeps each one's
    # hole in its own place instead of stamping one cover's hole through all
    # fourteen.
    cover_w = h.centre_cover_x(sx)
    cover_size = (cover_w, 2.0 * cell.centre_cover_half_y, h.centre_cover_thickness)
    cover_centre_z = cell.z_centre_cover + h.centre_cover_thickness / 2.0
    hole_d = cell.centre_cover_hole_diameter
    # Overshoot above and below, so no cutter cap is coplanar with the thin
    # face it cuts. A 6 mm cover is exactly the thickness at which a coplanar
    # cap turns into non-manifold edges rather than a hole.
    hole_h = h.centre_cover_thickness * 3.0

    feed_xs = cell.feeder_positions_x()
    plain_master: bpy.types.Object | None = None

    for i, cover_x in enumerate(h.centre_cover_positions_x(sx)):
        holes = [
            fx - cover_x
            for fx in feed_xs
            if abs(fx - cover_x) < (cover_w + hole_d) / 2.0
        ]

        if not holes and plain_master is not None:
            B.linked_copy(ctx, plain_master, "cover", i, (cover_x, 0.0, cover_centre_z))
            continue

        cover = B.box_on(
            ctx,
            "cover",
            i,
            size_mm=cover_size,
            base_z_mm=cell.z_centre_cover,
            at_xy_mm=(cover_x, 0.0),
        )
        B.shade_flat(cover)

        if holes:
            B.carve(
                ctx,
                cover,
                B.cylinder_cluster(
                    ctx,
                    "cover_hole",
                    i,
                    [(hole_d, hole_h, (dx, 0.0, cover_centre_z)) for dx in holes],
                    at_mm=(cover_x, 0.0, 0.0),
                ),
            )
        else:
            plain_master = cover

    # -- 5. end_box: 2 objects, 1 mesh ---------------------------------------
    box_height = h.end_box_top_z - cell.shell_outer_z
    box_x = h.end_box_centre_x(sx)
    box_centre_z = cell.shell_outer_z + box_height / 2.0
    face_x = sx / 2.0  # outer face of the +X box; the -X box mirrors it

    end_box0 = B.box_on(
        ctx,
        "end_box",
        0,
        size_mm=(h.end_box_x, cell.shell_outer_y, box_height),
        base_z_mm=cell.shell_outer_z,
        at_xy_mm=(box_x, 0.0),
    )
    B.shade_flat(end_box0)

    B.instance_at(
        ctx, end_box0, "end_box", [(-box_x, 0.0, box_centre_z)], start_index=1
    )

    # -- 6. end_cap: 2 objects, 1 mesh ---------------------------------------
    # A capping plate over the roof, overhanging all round. It is what the gas
    # offtake throat stands on - spec derives z_end_box_roof from it, so the
    # throat cannot drift off the box - and it gives the face a top edge, which
    # a bare 1685 mm plate running straight into the sky did not have.
    cap_size = (
        h.end_box_x + 2.0 * h.end_box_cap_grow,
        cell.shell_outer_y + 2.0 * h.end_box_cap_grow,
        h.end_box_cap_t,
    )
    cap_centre_z = h.end_box_top_z + h.end_box_cap_t / 2.0

    cap0 = B.box_on(
        ctx,
        "end_cap",
        0,
        size_mm=cap_size,
        base_z_mm=h.end_box_top_z,
        at_xy_mm=(box_x, 0.0),
    )
    B.shade_flat(cap0)
    B.bevel(cap0, h.panel_thickness)
    B.bevel(
        B.linked_copy(ctx, cap0, "end_cap", 1, (-box_x, 0.0, cap_centre_z)),
        h.panel_thickness,
    )

    # -- 7. end_rib: 2 objects, 1 mesh / side_rib: 4 objects, 1 mesh ----------
    # The end enclosure's outer face is 4830 x 1685 mm - the largest single
    # face on the cell, the foreground of both the front elevation and the
    # hero - and through Phase 2 it carried one 700 mm door and nothing else:
    # 86% bare plate. Its side faces were the same. These are panels from the
    # same shop as the hood, so they get the hood's own rib pitch.
    #
    # Two masters rather than one rotated master, because the section is not
    # square: a rib projects rib_depth away from the face it stiffens and
    # spreads rib_width across it, and those are different axes on the two
    # faces. Each master carries the ARRAY; the copies re-declare it, since a
    # modifier lives on the object and the mesh is what stays shared.
    n_end = h.end_ribs_across(cell.shell_outer_y)
    end_pitch = cell.shell_outer_y / n_end
    end_rib_y0 = -cell.shell_outer_y / 2.0 + end_pitch / 2.0

    end_rib0 = B.box_on(
        ctx,
        "end_rib",
        0,
        size_mm=(h.rib_depth, h.rib_width, box_height),
        base_z_mm=cell.shell_outer_z,
        at_xy_mm=(face_x + h.rib_depth / 2.0, end_rib_y0),
    )
    B.shade_flat(end_rib0)
    B.array(end_rib0, count=n_end, offset_mm=(0.0, end_pitch, 0.0))

    end_rib1 = B.linked_copy(
        ctx,
        end_rib0,
        "end_rib",
        1,
        (-(face_x + h.rib_depth / 2.0), end_rib_y0, box_centre_z),
    )
    B.array(end_rib1, count=n_end, offset_mm=(0.0, end_pitch, 0.0))

    n_side = h.end_ribs_along()
    side_pitch = h.end_box_x / n_side
    side_rib_x0 = box_x - h.end_box_x / 2.0 + side_pitch / 2.0
    side_face_y = cell.shell_outer_y / 2.0 + h.rib_depth / 2.0

    side_rib0 = B.box_on(
        ctx,
        "side_rib",
        0,
        size_mm=(h.rib_width, h.rib_depth, box_height),
        base_z_mm=cell.shell_outer_z,
        at_xy_mm=(side_rib_x0, side_face_y),
    )
    B.shade_flat(side_rib0)
    B.array(side_rib0, count=n_side, offset_mm=(side_pitch, 0.0, 0.0))

    for index, (sign_x, sign_y) in enumerate(
        ((1.0, -1.0), (-1.0, 1.0), (-1.0, -1.0)), start=1
    ):
        obj = B.linked_copy(
            ctx,
            side_rib0,
            "side_rib",
            index,
            (sign_x * side_rib_x0, sign_y * side_face_y, box_centre_z),
        )
        B.array(obj, count=n_side, offset_mm=(sign_x * side_pitch, 0.0, 0.0))

    # -- 8. door_frame: 4 objects, 1 mesh ------------------------------------
    # Two doors per face now, not one. The frame is the reason the doorway
    # reads as an opening rather than a plate stuck on: it stands proud of the
    # ribs (spec derives end_box_frame_t from rib_depth for exactly that), so
    # the rib run visibly stops at the frame instead of running through it.
    door_ys = h.end_box_door_positions_y(cell.shell_outer_y)
    frame_h = h.end_box_door_h + h.end_box_frame_grow
    frame_centre_z = cell.shell_outer_z + frame_h / 2.0
    frame_x = face_x + h.end_box_frame_t / 2.0

    frame_stations = [
        (sign * frame_x, y) for sign in (1.0, -1.0) for y in door_ys
    ]
    frame0 = B.box_on(
        ctx,
        "door_frame",
        0,
        size_mm=(
            h.end_box_frame_t,
            h.end_box_door_w + 2.0 * h.end_box_frame_grow,
            frame_h,
        ),
        base_z_mm=cell.shell_outer_z,
        at_xy_mm=frame_stations[0],
    )
    B.shade_flat(frame0)
    B.bevel(frame0, h.panel_thickness)
    for index, (fx, fy) in enumerate(frame_stations[1:], start=1):
        B.bevel(
            B.linked_copy(ctx, frame0, "door_frame", index, (fx, fy, frame_centre_z)),
            h.panel_thickness,
        )

    # -- 9. door: 4 objects, 1 mesh -------------------------------------------
    door_x = face_x + h.end_box_door_t / 2.0
    door_centre_z = cell.shell_outer_z + h.end_box_door_h / 2.0
    door_stations = [(sign * door_x, y) for sign in (1.0, -1.0) for y in door_ys]

    door0 = B.box_on(
        ctx,
        "door",
        0,
        size_mm=(h.end_box_door_t, h.end_box_door_w, h.end_box_door_h),
        base_z_mm=cell.shell_outer_z,
        at_xy_mm=door_stations[0],
    )
    B.shade_flat(door0)
    B.bevel(door0, h.panel_thickness)
    for index, (dx, dy) in enumerate(door_stations[1:], start=1):
        B.bevel(
            B.linked_copy(ctx, door0, "door", index, (dx, dy, door_centre_z)),
            h.panel_thickness,
        )

    # -- 10. door_handle: 4 objects, 0 new meshes -----------------------------
    # The SAME staple as the hood panels carry - same shop, same stock - so
    # these are linked copies of handle0 and cost no datablock. Its mesh is
    # authored with local +Z as the outward normal and the bar along local X,
    # so a quarter turn about Y stands it on a vertical face with the bar
    # upright; the -X face adds the usual half turn about Z.
    handle_x = face_x + h.end_box_door_t
    handle_z = cell.shell_outer_z + h.end_box_door_h / 2.0
    handle_stations_door = [
        (sign, y + h.end_box_door_w / 2.0 - h.handle_length / 2.0)
        for sign in (1.0, -1.0)
        for y in door_ys
    ]
    for index, (sign, hy) in enumerate(
        handle_stations_door, start=len(handle_stations)
    ):
        obj = B.linked_copy(
            ctx, handle0, "handle", index, (sign * handle_x, hy, handle_z)
        )
        obj.rotation_euler.y = math.pi / 2.0
        if sign < 0.0:
            obj.rotation_euler.z = math.pi
        B.bevel(obj, h.handle_bevel)

    # -- 11. number_plate: 2 objects, 1 mesh ----------------------------------
    # The docstring on Hooding has always said these boxes carry the pot
    # number. They never did. It goes in the bay BETWEEN the two doors - with a
    # 1600 mm door on a 1685 mm face there is no band above them to use - and
    # it stands proud of the ribs for the same reason the door frame does.
    plate_centre_z = cell.shell_outer_z + box_height / 2.0
    plate_x = face_x + h.end_box_plate_t / 2.0

    plate0 = B.box(
        ctx,
        "number_plate",
        0,
        size_mm=(h.end_box_plate_t, h.end_box_plate_w, h.end_box_plate_h),
        at_mm=(plate_x, 0.0, plate_centre_z),
    )
    B.shade_flat(plate0)
    B.bevel(plate0, h.panel_thickness)
    B.bevel(
        B.linked_copy(
            ctx, plate0, "number_plate", 1, (-plate_x, 0.0, plate_centre_z)
        ),
        h.panel_thickness,
    )

    return ctx.created

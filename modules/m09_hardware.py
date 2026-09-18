"""
Connection hardware: the screw jacks that actually carry the anode beam, the
base plates and gussets that land the columns on the cradles, and the clamp
plates that grip the flexible connectors to the collector bar tips.

Justified hardware ONLY. Every part here closes a load path that the earlier
modules left implied; nothing is here to raise the polygon count.

The one that matters is the jacks. Through Phase 2 the anode beam carried all
36 anode assemblies and hung from NOTHING - the portal ties pass 350 mm above
it and the columns stand 1090 mm outboard. The jacks are simultaneously the
missing support and the real mechanism, because raising the beam is how the
anodes are lowered as they burn back. They stand where a tie already crosses
a beam, which is the only place the load has anywhere to go.

Five parts, each built once and repeated as linked copies:
    jack_cap(12), jack(12), base_plate(12), gusset(24), flex_clamp(48)
        = 108 objects, 5 mesh datablocks.

Every dimension comes from ctx.cell. Nothing here chooses a length: a jack is
as long as the gap between the beam cap and the tie, a gusset reaches exactly
to the edge of its own base plate, and a clamp rests on whichever part of the
joint it laps stands taller. All three of those are derived in spec.
"""

from __future__ import annotations

import math

import bpy

from lib import build as B
from lib.scene import BuildContext


def build(ctx: BuildContext) -> list[bpy.types.Object]:
    """Beam jacks with their cap plates, column base plates and gussets,
    and flexible-connector clamp plates."""
    cell = ctx.cell
    hw = cell.hardware
    s = cell.superstructure

    column_xs = cell.column_positions_x()

    # Jacks and caps share one set of stations: every column X, on both beams.
    # The beam line, not the column line - a jack bears on the beam.
    jack_stations = [
        (x, sign * cell.beam_centre_y) for x in column_xs for sign in (1.0, -1.0)
    ]

    # -- 1. jack_cap: 12 objects, 1 mesh -------------------------------------
    # A bearing plate spreading the jack's point load into the beam's top
    # flange. Without it a 260 mm cylinder stands on a beam and the load path
    # is a drawn circle.
    cap_size = (hw.jack_cap_x, hw.jack_cap_y, hw.jack_cap_t)
    cap_centre_z = cell.beam_top_z + hw.jack_cap_t / 2.0

    cap0 = B.box_on(
        ctx,
        "jack_cap",
        0,
        size_mm=cap_size,
        base_z_mm=cell.beam_top_z,
        at_xy_mm=jack_stations[0],
    )
    B.shade_flat(cap0)
    B.bevel(cap0, s.edge_bevel)

    for index, (x, y) in enumerate(jack_stations[1:], start=1):
        B.bevel(
            B.linked_copy(ctx, cap0, "jack_cap", index, (x, y, cap_centre_z)),
            s.edge_bevel,
        )

    # -- 2. jack: 12 objects, 1 mesh -----------------------------------------
    # Body casting below, exposed screw above. The two are STACKED, not
    # overlapped, because cylinder_cluster welds without a boolean and a
    # self-intersecting cluster returns a plausible wrong solid rather than an
    # error.
    #
    # Authored at true world height, like the anode stub, because a stepped
    # solid has no centre that means anything. Its copies therefore sit at
    # z = 0 and carry no offset.
    body_z = cell.z_jack_base + cell.jack_body_length / 2.0
    screw_z = cell.z_jack_base + cell.jack_body_length + cell.jack_screw_length / 2.0

    jack0 = B.cylinder_cluster(
        ctx,
        "jack",
        0,
        [
            (hw.jack_body_diameter, cell.jack_body_length, (0.0, 0.0, body_z)),
            (hw.jack_screw_diameter, cell.jack_screw_length, (0.0, 0.0, screw_z)),
        ],
        at_mm=(jack_stations[0][0], jack_stations[0][1], 0.0),
    )
    B.auto_smooth(jack0)

    B.instance_at(
        ctx,
        jack0,
        "jack",
        [(x, y, 0.0) for x, y in jack_stations[1:]],
        start_index=1,
    )

    # -- 3. base_plate: 12 objects, 1 mesh -----------------------------------
    # Column to cradle. A 400 mm box section landing directly on a 25 mm cradle
    # web is not a joint. The plate's width across the cell is the column's own
    # section with no margin at all - spec has the reason, which is that the
    # column already spans the entire cradle band exactly, and a plate grown
    # that way clipped the hood panel's bottom edge.
    plate_size = (cell.base_plate_x, cell.base_plate_y, hw.base_plate_t)
    plate_centre_z = cell.shell.rim_z + hw.base_plate_t / 2.0

    plate_stations = [
        (x, sign * cell.column_centre_y) for x in column_xs for sign in (1.0, -1.0)
    ]

    plate0 = B.box_on(
        ctx,
        "base_plate",
        0,
        size_mm=plate_size,
        base_z_mm=cell.shell.rim_z,
        at_xy_mm=plate_stations[0],
    )
    B.shade_flat(plate0)
    B.bevel(plate0, s.edge_bevel)

    for index, (x, y) in enumerate(plate_stations[1:], start=1):
        B.bevel(
            B.linked_copy(ctx, plate0, "base_plate", index, (x, y, plate_centre_z)),
            s.edge_bevel,
        )

    # -- 4. gusset: 24 objects, 1 mesh ---------------------------------------
    # A triangular bracket from the column face out to the edge of its own base
    # plate. Two per column, on the +X and -X faces only: there is no land in Y
    # to reach out to, because the plate has no margin that way.
    #
    # Built as a three-point loft rather than a box, which is the whole point -
    # a rectangular bracket would bear on nothing at its outer top corner.
    # Local origin sits at the column's +X face on the plate's top surface,
    # with the run going +X and the rise going +Z.
    run = hw.gusset_run
    rise = hw.gusset_rise
    half_t = hw.gusset_t / 2.0
    triangle = [(0.0, 0.0, 0.0), (run, 0.0, 0.0), (0.0, 0.0, rise)]

    # Every gusset's own position, so the master is simply the first of them and
    # no float comparison is needed to skip it.
    gusset_stations = [
        (x + face_sign * s.column_section / 2.0, y, face_sign)
        for x, y in plate_stations
        for face_sign in (1.0, -1.0)
    ]

    gusset0 = B.loft_rings(
        ctx,
        "gusset",
        0,
        [
            [(gx, -half_t, gz) for gx, _, gz in triangle],
            [(gx, half_t, gz) for gx, _, gz in triangle],
        ],
        at_mm=(gusset_stations[0][0], gusset_stations[0][1], cell.z_column_base),
    )
    B.shade_flat(gusset0)
    B.bevel(gusset0, s.edge_bevel)

    # The -X gusset is the same mesh given a half turn about Z, which sends its
    # run to -X. A negative scale would do it too, and the QA validator flags
    # negative scale precisely because it inverts normals.
    for index, (gx, gy, face_sign) in enumerate(gusset_stations[1:], start=1):
        obj = B.linked_copy(
            ctx, gusset0, "gusset", index, (gx, gy, cell.z_column_base)
        )
        if face_sign < 0.0:
            obj.rotation_euler.z = math.pi
        B.bevel(obj, s.edge_bevel)

    # -- 5. flex_clamp: 48 objects, 1 mesh -----------------------------------
    # The plate that bolts the laminate stack down onto the collector bar tip.
    # Without it the flexible connector meets the bar in a butt joint, which is
    # the one place in the whole current path where a butt joint cannot be
    # what is really there.
    #
    # It straddles the joint plane by the clamp margin each side, and its
    # underside is derived: it rests on the collector bar, which stands proud
    # of the laminate stack it grips.
    clamp_size = (cell.flex_clamp_x, cell.flex_clamp_y, hw.flex_clamp_t)
    clamp_centre_z = cell.z_flex_clamp_base + hw.flex_clamp_t / 2.0

    clamp_stations = [
        (x, sign * cell.bar_tip_y)
        for x in cell.cathode.block_positions_x()
        for sign in (1.0, -1.0)
    ]

    clamp0 = B.box_on(
        ctx,
        "flex_clamp",
        0,
        size_mm=clamp_size,
        base_z_mm=cell.z_flex_clamp_base,
        at_xy_mm=clamp_stations[0],
    )
    B.shade_flat(clamp0)
    B.bevel(clamp0, s.edge_bevel)

    for index, (x, y) in enumerate(clamp_stations[1:], start=1):
        B.bevel(
            B.linked_copy(ctx, clamp0, "flex_clamp", index, (x, y, clamp_centre_z)),
            s.edge_bevel,
        )

    return ctx.created

"""
Busbar blockout for an ISOLATED cell (not a potline): flexible connectors
bridging the collector bar tips to longitudinal collector busbars on both
+/-Y sides, and risers carrying current from the +Y collector busbar up to
the anode beam.

Phase 3 detail pass. Two changes over the blockout:

  * The flexible connector is a STACK of laminates, not a solid bar. That is
    the entire reason it is flexible, and the blockout's billet was therefore
    a rigid connector that read as one.
  * The risers reach the anode beam. Each now rises to the beam's TOP and laps
    over it on an arm; through Phase 2 they stopped 1240 mm outboard of the
    beam's outer face in a bare cut face, connected to nothing. Their X
    stations are derived from the portal BAYS so the arms have somewhere to
    cross the column line.

Every dimension comes from ctx.cell. Repeated parts (48 flex stubs, 4 risers,
4 arms) each share a single mesh datablock via B.linked_copy / B.instance_at;
a Bevel is a modifier and lives on the OBJECT, so copies are beveled
individually and the mesh stays shared.

Busbars still terminate in clean stubs at the cell boundary -- nothing reaches
toward a neighbouring cell.
"""

from __future__ import annotations

import bpy

from lib import build as B
from lib.scene import BuildContext


def build(ctx: BuildContext) -> list[bpy.types.Object]:
    """Riser busbars, collector busbars and flexible connector stubs."""
    cell = ctx.cell
    bb = cell.busbars

    xs = cell.cathode.block_positions_x()

    # Y positions, derived in order: bar tip -> flex centre -> busbar centre.
    # The tip is a Cell property, not a local sum: m09 clamps the flexible
    # connector down onto that same tip and the two must not drift apart.
    bar_tip_y = cell.bar_tip_y
    flex_centre_y = bar_tip_y + bb.flex_length / 2.0
    busbar_y = bar_tip_y + bb.flex_length + bb.riser_t / 2.0

    # -- 1. flexible connector stubs, one per collector bar tip -------------
    # A flexible connector is a STACK of thin laminates with air between them.
    # That is the entire reason it is flexible, and the blockout's solid bar
    # was therefore not a flexible connector at all — it was a rigid one, and
    # it read as one.
    #
    # The laminate thickness is what is left of the connector's section once
    # the gaps have taken their share, so the stack always fills exactly the
    # envelope the solid bar occupied however the lamination count changes.
    gaps = (bb.flex_laminates - 1) * bb.flex_laminate_gap
    laminate_t = (bb.flex_section - gaps) / bb.flex_laminates
    pitch = laminate_t + bb.flex_laminate_gap

    flex0 = B.box_cluster(
        ctx,
        "flex",
        0,
        [
            (
                (bb.flex_section, bb.flex_length, laminate_t),
                (
                    0.0,
                    0.0,
                    -bb.flex_section / 2.0 + laminate_t / 2.0 + i * pitch,
                ),
            )
            for i in range(bb.flex_laminates)
        ],
        at_mm=(xs[0], flex_centre_y, cell.bar_z_centre),
    )
    B.shade_flat(flex0)

    flex_positions: list[tuple[float, float, float, int]] = []
    for i, x in enumerate(xs):
        plus_index = 2 * i
        minus_index = 2 * i + 1
        if plus_index != 0:
            flex_positions.append((x, flex_centre_y, cell.bar_z_centre, plus_index))
        flex_positions.append((x, -flex_centre_y, cell.bar_z_centre, minus_index))

    for x, y, z, index in flex_positions:
        B.linked_copy(ctx, flex0, "flex", index, (x, y, z))

    # -- 2. collector busbars, one down each side ---------------------------
    collector_size = (cell.cathode.run_x, bb.riser_t, bb.riser_t)

    collector0 = B.box(
        ctx,
        "collector",
        0,
        size_mm=collector_size,
        at_mm=(0, busbar_y, cell.bar_z_centre),
    )
    B.shade_flat(collector0)
    B.bevel(collector0, bb.busbar_bevel)

    B.bevel(
        B.linked_copy(
            ctx, collector0, "collector", 1, (0, -busbar_y, cell.bar_z_centre)
        ),
        bb.busbar_bevel,
    )

    # -- 3. risers, +Y side only, standing in the portal bays ---------------
    # Height and X stations are both derived now, and both were wrong before.
    # The blockout spread four risers evenly over the cathode run and stopped
    # them at a chosen 2100 - level with the anode beam's underside but 1240 mm
    # outboard of its outer face. They rose out of the collector busbar, carried
    # nothing, and ended in bare cut faces. A riser that does not reach the beam
    # is not a riser, it is a post.
    riser_xs = cell.riser_positions_x()
    riser_size = (bb.riser_w, bb.riser_t, cell.z_riser_top)

    riser0 = B.box_on(
        ctx,
        "riser",
        0,
        size_mm=riser_size,
        base_z_mm=0,
        at_xy_mm=(riser_xs[0], busbar_y),
    )
    B.shade_flat(riser0)
    B.bevel(riser0, bb.busbar_bevel)

    riser_centre_z = cell.z_riser_top / 2.0
    for index, x in enumerate(riser_xs[1:], start=1):
        B.bevel(
            B.linked_copy(ctx, riser0, "riser", index, (x, busbar_y, riser_centre_z)),
            bb.busbar_bevel,
        )

    # -- 4. riser arms, one per riser ----------------------------------------
    # The arm is what makes a riser one: it runs inboard OVER the top of the
    # anode beam and laps half its width, which is the joint a real riser head
    # makes. Over the top rather than alongside, because the hood panels anchor
    # on the beam's outer face along the whole cell - an arm at beam height
    # would drive straight through the panel run.
    #
    # It crosses the portal column line on the way, which is why the riser
    # stations are derived from the column BAYS rather than chosen; spec's
    # _self_check holds the clearance.
    arm_inner_y = cell.beam_centre_y
    arm_outer_y = busbar_y + bb.riser_t / 2.0
    arm_length = arm_outer_y - arm_inner_y
    arm_centre_y = (arm_outer_y + arm_inner_y) / 2.0

    arm0 = B.box_on(
        ctx,
        "arm",
        0,
        size_mm=(bb.riser_w, arm_length, bb.arm_t),
        base_z_mm=cell.z_riser_top,
        at_xy_mm=(riser_xs[0], arm_centre_y),
    )
    B.shade_flat(arm0)
    B.bevel(arm0, bb.busbar_bevel)

    arm_centre_z = cell.z_riser_top + bb.arm_t / 2.0
    for index, x in enumerate(riser_xs[1:], start=1):
        B.bevel(
            B.linked_copy(ctx, arm0, "arm", index, (x, arm_centre_y, arm_centre_z)),
            bb.busbar_bevel,
        )

    return ctx.created

"""
Cathode blockout: graphitised carbon blocks laid transversely, plus the steel
collector bars that exit through the shell on both +Y and -Y sides.

Primitive massing only. No slots, no bevels. Every dimension comes from
ctx.cell. Repeated parts (24 blocks, 48 bars) each share a single mesh
datablock via B.linked_copy / B.instance_at.
"""

from __future__ import annotations

import bpy

from lib import build as B
from lib.scene import BuildContext


def build(ctx: BuildContext) -> list[bpy.types.Object]:
    """Cathode blocks + collector bars blockout."""
    cell = ctx.cell
    cathode = cell.cathode

    xs = cathode.block_positions_x()

    # -- A. cathode blocks, laid transversely (long axis along Y) ----------
    block_size = (cathode.block_x, cathode.block_y, cathode.block_z)
    block_centre_z = cell.z_cathode_bottom + cathode.block_z / 2.0

    block0 = B.box_on(
        ctx,
        "block",
        0,
        size_mm=block_size,
        base_z_mm=cell.z_cathode_bottom,
        at_xy_mm=(xs[0], 0),
    )
    B.shade_flat(block0)

    bar_size = (cathode.bar_w, cell.bar_half_length, cathode.bar_h)
    bar_y = cathode.bar_centre_gap / 2.0 + cell.bar_half_length / 2.0

    # A collector bar does not sit on top of a cathode block, it sits IN it,
    # in a slot cut along the block's underside and sealed with cast iron.
    # The blockout had the bars simply coinciding with solid carbon, which
    # reads as two objects fighting over the same space in any section.
    #
    # Carved, not booleaned: the slot has to live in the mesh DATABLOCK so all
    # 24 blocks show it while still sharing one mesh. And carved BEFORE the
    # linked copies are made, or they share the block as it was.
    # The slot is the bar's own footprint, dropped so its floor falls BELOW the
    # block. The bar's underside is flush with the block's (both at z=280), and
    # a cutter face coplanar with the face it cuts is exactly the case EXACT
    # resolves into non-manifold edges — the same trap the ramming paste below
    # had to be pushed clear of. There is nothing under the block in this
    # collection for the overshoot to touch.
    #
    # In Y the slot stops where the bar stops, at |y| = bar_centre_gap/2, which
    # leaves the blind inner end a real slot end rather than a hole punched
    # through to the block's far side.
    slot_size = (cathode.bar_w, cell.bar_half_length, cathode.bar_h * 2.0)
    slot_z = cell.bar_z_centre + cathode.bar_h / 2.0 - cathode.bar_h
    B.carve(
        ctx,
        block0,
        B.box_cluster(
            ctx,
            "block_slot",
            0,
            [(slot_size, (0.0, sign * bar_y, slot_z)) for sign in (1.0, -1.0)],
            at_mm=(xs[0], 0.0, 0.0),
        ),
    )

    block_positions = [(x, 0, block_centre_z) for x in xs[1:]]
    B.instance_at(ctx, block0, "block", block_positions, start_index=1)

    # -- B. collector bars, run along Y, protrude past the shell both ways -

    bar0 = B.box(
        ctx,
        "bar",
        0,
        size_mm=bar_size,
        at_mm=(xs[0], bar_y, cell.bar_z_centre),
    )
    B.shade_flat(bar0)

    bar_positions: list[tuple[float, float, float, int]] = []
    for i, x in enumerate(xs):
        plus_index = 2 * i
        minus_index = 2 * i + 1
        if plus_index != 0:
            bar_positions.append((x, bar_y, cell.bar_z_centre, plus_index))
        bar_positions.append((x, -bar_y, cell.bar_z_centre, minus_index))

    # instance_at assigns indices sequentially from start_index, so drive it
    # one call per bar to keep the +Y/-Y index convention exact.
    for x, y, z, index in bar_positions:
        B.linked_copy(ctx, bar0, "bar", index, (x, y, z))

    # -- C. rammed carbon paste filling every void around the blocks --------
    # The Phase 2 section exposed a 450 x 450 mm channel running the full
    # length of the cell down both sides, plus the same at both ends and a
    # 40 mm slot at each of the 23 inter-block seams. In a real pot none of
    # that is void: it is rammed paste, and it is what seals the cathode
    # periphery and carries the ledge above it.
    #
    # Built as the whole cathode band with the blocks and bars cut out of it,
    # rather than as three separate fillers. That is how it is actually
    # rammed, it needs no gap arithmetic, and it cannot drift out of step with
    # the blocks the way three independently-placed fillers would.
    paste = B.box_on(
        ctx,
        "ramming",
        0,
        size_mm=(cell.cavity_x, cell.cavity_y, cathode.block_z),
        base_z_mm=cell.z_cathode_bottom,
    )
    B.shade_flat(paste)

    # The blocks fill the paste band exactly, so their top and bottom faces are
    # coplanar with the paste's — the case EXACT resolves into non-manifold
    # edges. Cutting with a taller box pushes those faces clear; there is
    # nothing above or below the band for the overshoot to touch.
    tall_block = (cathode.block_x, cathode.block_y, cathode.block_z * 3.0)
    block_voids = [(tall_block, (x, 0.0, block_centre_z)) for x in xs]

    # Blocks and bars go in SEPARATE cutters. box_cluster welds its boxes into
    # one mesh, and the bars sit inside the blocks, so a combined cutter would
    # be self-intersecting — EXACT then returns nonsense rather than failing.
    # Within each cutter the boxes are disjoint: blocks are 600 at 640 pitch,
    # and the two bars of a block are held apart by bar_centre_gap.
    bar_voids = [
        (bar_size, (x, y, cell.bar_z_centre)) for x, y, _, _ in bar_positions
    ]
    bar_voids.append((bar_size, (xs[0], bar_y, cell.bar_z_centre)))  # bar_000

    for index, (part, voids) in enumerate(
        (("ramming_cut_blocks", block_voids), ("ramming_cut_bars", bar_voids))
    ):
        B.boolean(paste, B.box_cluster(ctx, part, index, voids), "DIFFERENCE")

    return ctx.created

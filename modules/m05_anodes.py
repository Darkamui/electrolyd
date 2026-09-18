"""
Anode assemblies: 36 prebaked carbon anodes with their rodding — cast-iron
stubs, aluminium yoke and stem, and the beam clamp.

Phase 3 detail pass. Three changes over the blockout:

  * The clamp is bolted to the anode beam's INNER FACE, not centred on the
    beam. Centred, it sat bodily inside the beam. Both the clamp's position
    and the beam's are now derived in spec from where a rod is actually
    gripped, so this module reads cell.clamp_centre_y and never the row line.
  * Stubs sit in sockets. A stub is grouted into a cast socket, not driven
    into solid carbon, and the socket is the most recognisable feature of a
    spent anode — which is what the exploded view will show.
  * The working face carries gas slots. Without them the CO2 has nowhere to
    go, and an anode with an unbroken flat underside is the detail an
    aluminium engineer notices first.

Every dimension comes from ctx.cell. Five distinct parts (block, stub, yoke,
stem, clamp) are each built once at anode index 0 and every repeat is a linked
copy sharing that one mesh datablock, so 36 anodes cost 5 mesh datablocks
total. Features carved into a master must therefore be carved BEFORE its
copies are taken.
"""

from __future__ import annotations

import math

import bpy

from lib import build as B
from lib.scene import BuildContext


def build(ctx: BuildContext) -> list[bpy.types.Object]:
    """36 anode assemblies: carbon block, stubs, yoke, stem, clamp."""
    cell = ctx.cell
    a = cell.anodes

    positions = a.positions()
    ax0, ay0 = positions[0]

    # -- vertical layout, derived once from spec ---------------------------
    # The rodding heights are derived in spec.Cell, not recomputed here, so the
    # stem always meets the anode beam if the beam moves.
    # The stub's mesh is authored at true world height rather than centred on
    # its own origin, because it is a stepped solid and there is no one "centre"
    # that means anything. Its copies therefore sit at z=0 and carry no offset.
    yoke_base_z = cell.yoke_base_z
    stem_base_z = cell.stem_base_z

    # -- A. carbon block, index 0 via box_on, 1..35 as linked copies -------
    block_size = (a.block_x, a.block_y, a.block_z)
    block_centre_z = cell.z_anode_bottom + a.block_z / 2.0

    block0 = B.box_on(
        ctx,
        "block",
        0,
        size_mm=block_size,
        base_z_mm=cell.z_anode_bottom,
        at_xy_mm=(ax0, ay0),
    )
    B.shade_flat(block0)

    n = a.stubs_per_anode
    stub_dy = [
        -a.yoke_length / 2.0 + i * a.yoke_length / (n - 1) for i in range(n)
    ]

    # -- A1. stub sockets, carved into the master block ---------------------
    # Carved, not booleaned, so the sockets live in the shared mesh datablock
    # and all 36 blocks show them for the cost of one.
    #
    # The socket runs from the block's top face down by the stub's embedded
    # depth, and the cutter is pushed up clear of that top face — a cutter cap
    # coplanar with the face it cuts is what EXACT turns into non-manifold
    # edges. Its floor is left inside the carbon, which is what a blind socket
    # is.
    socket_d = a.stub_diameter + 2.0 * a.stub_socket_clearance
    socket_h = a.stub_embed_depth * 2.0
    socket_z = cell.z_anode_top - a.stub_embed_depth + socket_h / 2.0
    B.carve(
        ctx,
        block0,
        B.cylinder_cluster(
            ctx,
            "block_socket",
            0,
            [(socket_d, socket_h, (0.0, dy, socket_z)) for dy in stub_dy],
            at_mm=(ax0, ay0, 0.0),
        ),
    )

    # -- A2. gas slots, carved into the master block ------------------------
    # Vertical slots cut up into the working face, running the full width of
    # the block so the CO2 generated under the anode can escape sideways into
    # the channels instead of blanketing the face.
    #
    # Overshoot BELOW the working face for the same coplanarity reason, and
    # run past the block in Y so the slots are open at both ends rather than
    # being blind pockets.
    slot_xs = [
        -a.block_x / 2.0 + (i + 0.5) * a.block_x / a.slot_count
        for i in range(a.slot_count)
    ]
    B.carve(
        ctx,
        block0,
        B.box_cluster(
            ctx,
            "block_slot",
            0,
            [
                (
                    (a.slot_width, a.block_y * 2.0, a.slot_depth * 2.0),
                    (sx, 0.0, cell.z_anode_bottom),
                )
                for sx in slot_xs
            ],
            at_mm=(ax0, ay0, 0.0),
        ),
    )

    block_positions = [(x, y, block_centre_z) for x, y in positions[1:]]
    B.instance_at(ctx, block0, "block", block_positions, start_index=1)

    # -- B. cast-iron stubs, 4 per anode, one master + 143 linked copies ----
    # A stepped cylinder, not a plain one: over its embedded length the stub is
    # the socket's full diameter, because what fills the socket is the cast
    # iron grouted around the stub, and modelling that as a separate part would
    # double the object count to show a 10 mm annulus. Above the block it steps
    # down to the stub's own diameter.
    #
    # The two cylinders are stacked rather than overlapped, so the cluster
    # stays a clean single mesh.
    stub0 = B.cylinder_cluster(
        ctx,
        "stub",
        0,
        [
            (
                socket_d,
                a.stub_embed_depth,
                (0.0, 0.0, cell.z_anode_top - a.stub_embed_depth / 2.0),
            ),
            (
                a.stub_diameter,
                a.stub_free_height,
                (0.0, 0.0, cell.z_anode_top + a.stub_free_height / 2.0),
            ),
        ],
        at_mm=(ax0, ay0 + stub_dy[0], 0.0),
    )
    B.shade_flat(stub0)

    stub_positions: list[tuple[float, float, float]] = []
    for ax, ay in positions:
        for dy in stub_dy:
            stub_positions.append((ax, ay + dy, 0.0))
    # skip the very first stub position — it is stub0 itself, already built
    B.instance_at(ctx, stub0, "stub", stub_positions[1:], start_index=1)

    # -- C. yoke, index 0 via box_on, 1..35 as linked copies ----------------
    yoke_size = (a.yoke_section, a.yoke_length, a.yoke_section)
    yoke_centre_z = yoke_base_z + a.yoke_section / 2.0

    yoke0 = B.box_on(
        ctx,
        "yoke",
        0,
        size_mm=yoke_size,
        base_z_mm=yoke_base_z,
        at_xy_mm=(ax0, ay0),
    )
    B.shade_flat(yoke0)

    yoke_positions = [(x, y, yoke_centre_z) for x, y in positions[1:]]
    B.instance_at(ctx, yoke0, "yoke", yoke_positions, start_index=1)

    # -- D. stem, index 0 via box_on, 1..35 as linked copies ----------------
    stem_size = (a.stem_section, a.stem_section, cell.stem_height)
    stem_centre_z = stem_base_z + cell.stem_height / 2.0

    stem0 = B.box_on(
        ctx,
        "stem",
        0,
        size_mm=stem_size,
        base_z_mm=stem_base_z,
        at_xy_mm=(ax0, ay0),
    )
    B.shade_flat(stem0)

    stem_positions = [(x, y, stem_centre_z) for x, y in positions[1:]]
    B.instance_at(ctx, stem0, "stem", stem_positions, start_index=1)

    # -- E. clamp, index 0 via box_on, 1..35 as linked copies ---------------
    # A jaw straddling the joint between the rod and the beam's inner face:
    # half of it grips the stem, half laps onto the beam. Both halves of that
    # sentence are derived in spec — clamp_centre_y sits on the stem's outer
    # face, and the beam's own centreline is derived so its inner face lands
    # there too — so this module must not reach for the anode row line, which
    # is what put the clamp inside the beam in the blockout.
    #
    # Vertically it is centred on the beam's section, so the jaw grips the
    # middle of the beam rather than hanging off its top or bottom edge.
    clamp_size = (a.clamp_x, a.clamp_y, a.clamp_z)
    clamp_centre_z = cell.z_clamp_base + a.clamp_z / 2.0

    def clamp_y(anode_y: float) -> float:
        """Mirror the clamp onto whichever row its anode belongs to."""
        return math.copysign(cell.clamp_centre_y, anode_y)

    clamp0 = B.box_on(
        ctx,
        "clamp",
        0,
        size_mm=clamp_size,
        base_z_mm=cell.z_clamp_base,
        at_xy_mm=(ax0, clamp_y(ay0)),
    )
    B.shade_flat(clamp0)

    clamp_positions = [
        (x, clamp_y(y), clamp_centre_z) for x, y in positions[1:]
    ]
    B.instance_at(ctx, clamp0, "clamp", clamp_positions, start_index=1)

    return ctx.created

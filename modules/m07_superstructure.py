"""
Superstructure: the portal frame straddling the cell, the feeder deck, the
point-feeder assemblies (hopper, chute, breaker, chisel) and the gas offtake
duct.

Phase 3 detail pass. Four changes over the blockout:

  * The anode beams stand on cell.beam_centre_y, not on the anode row line.
    The beam's position is derived in spec from where a rod is actually
    gripped; m05 already clamps to that face, and until now the beam was not
    there to be clamped to.
  * The hoppers neck down to their chutes. A box sitting on a pipe is a box
    sitting on a pipe - alumina would bridge in the corners and the feeder
    would not feed. This is the one part of a point feeder that has a shape.
  * The duct ends in flanges. The agreed scope stops it in a stub rather than
    running it to a gas treatment centre; a bare cut cylinder reads as
    geometry that was clipped, a flange reads as a pipe that ends here.
  * The duct now STANDS ON a square-to-round throat instead of lying tangent
    on the end enclosure roof. The blockout gave the hood plenum no gas path
    at all, which is the one thing a gas offtake has to have.
  * Every frame member carries a rolled edge. Perfectly sharp steel catches no
    highlight, which is most of why an unbeveled frame reads as CG.

Every dimension comes from ctx.cell. Repeated parts share one mesh datablock
each. A Bevel is a modifier and therefore lives on the OBJECT, so copies are
beveled individually - the mesh stays shared, which is the whole point.

The frame is deliberately OPEN along the centreline: each transverse tie is
a PAIR of half-ties (part "cross"), one per side, stopping short of y=0, so
the alumina feeders can descend and a crane can reach in to change anodes.
Only one height was chosen anywhere in the frame (superstructure.beam_z);
everything above it is read from derived Cell properties, never recomputed
here.
"""

from __future__ import annotations

import bpy

from lib import build as B
from lib.scene import BuildContext


def build(ctx: BuildContext) -> list[bpy.types.Object]:
    """Portal frame, feeder deck, point feeders and gas duct."""
    cell = ctx.cell
    s = cell.superstructure
    f = cell.feeder

    def rolled(master: bpy.types.Object, copies: list[bpy.types.Object]) -> None:
        """Bevel a master and each of its linked copies.

        The modifier cannot ride on the shared mesh, so every object needs its
        own. Beveling only the master leaves one crisp member in a frame of
        eleven razor-sharp ones, which is more obviously wrong than no bevel.
        """
        B.bevel(master, s.edge_bevel)
        for obj in copies:
            B.bevel(obj, s.edge_bevel)

    # -- 1. beam: 2 objects, 1 mesh -----------------------------------------
    # beam_centre_y, NOT the anode row: the beam's inner face is derived to
    # land where a rod is gripped, and m05 places its clamps against that face.
    beam_size = (cell.beam_length, s.beam_y, s.beam_z_section)
    beam_centre_z = s.beam_z + s.beam_z_section / 2.0

    beam0 = B.box_on(
        ctx,
        "beam",
        0,
        size_mm=beam_size,
        base_z_mm=s.beam_z,
        at_xy_mm=(0.0, cell.beam_centre_y),
    )
    B.shade_flat(beam0)
    beams = B.instance_at(
        ctx,
        beam0,
        "beam",
        [(0.0, -cell.beam_centre_y, beam_centre_z)],
        start_index=1,
    )
    rolled(beam0, beams)

    # -- 2. column: 12 objects, 1 mesh --------------------------------------
    column_height = cell.z_column_top - cell.z_column_base
    column_size = (s.column_section, s.column_section, column_height)
    column_centre_z = cell.z_column_base + column_height / 2.0

    column_xs = cell.column_positions_x()
    column0 = B.box_on(
        ctx,
        "column",
        0,
        size_mm=column_size,
        base_z_mm=cell.z_column_base,
        at_xy_mm=(column_xs[0], cell.column_centre_y),
    )
    B.shade_flat(column0)

    column_positions: list[tuple[float, float, float]] = []
    for x in column_xs:
        for sign in (1.0, -1.0):
            column_positions.append((x, sign * cell.column_centre_y, column_centre_z))
    columns = B.instance_at(ctx, column0, "column", column_positions[1:], start_index=1)
    rolled(column0, columns)

    # -- 3. cross: 12 objects, 1 mesh ---------------------------------------
    inner_y = cell.cross_inner_y
    outer_y = cell.column_centre_y + s.column_section / 2.0
    cross_y_length = outer_y - inner_y
    cross_y_centre = (outer_y + inner_y) / 2.0
    cross_size = (s.cross_section, cross_y_length, s.cross_section)

    cross0 = B.box_on(
        ctx,
        "cross",
        0,
        size_mm=cross_size,
        base_z_mm=cell.z_cross_base,
        at_xy_mm=(column_xs[0], cross_y_centre),
    )
    B.shade_flat(cross0)

    cross_centre_z = cell.z_cross_base + s.cross_section / 2.0
    cross_positions: list[tuple[float, float, float]] = []
    for x in column_xs:
        for sign in (1.0, -1.0):
            cross_positions.append((x, sign * cross_y_centre, cross_centre_z))
    crosses = B.instance_at(ctx, cross0, "cross", cross_positions[1:], start_index=1)
    rolled(cross0, crosses)

    # -- 4. deck_rail: 2 objects, 1 mesh -------------------------------------
    rail_size = (cell.deck_rail_length, s.deck_rail_section, s.deck_rail_section)
    rail_centre_z = cell.z_column_top + s.deck_rail_section / 2.0

    rail0 = B.box_on(
        ctx,
        "deck_rail",
        0,
        size_mm=rail_size,
        base_z_mm=cell.z_column_top,
        at_xy_mm=(0.0, cell.deck_rail_centre_y),
    )
    B.shade_flat(rail0)
    rails = B.instance_at(
        ctx,
        rail0,
        "deck_rail",
        [(0.0, -cell.deck_rail_centre_y, rail_centre_z)],
        start_index=1,
    )
    rolled(rail0, rails)

    # -- 5. hopper: 5 objects, 1 mesh ----------------------------------------
    # A parallel-walled prism over a taper that necks down to the chute. Both
    # heights and the outlet are derived in spec; the only free quantity there
    # is what share of the height tapers.
    #
    # The rings are authored at TRUE world height rather than centred on the
    # object's own origin, because a tapered solid has no centre that means
    # anything. Its copies therefore sit at z=0 and carry no offset - the same
    # convention m05 uses for the stepped stub.
    hopper_xs = cell.feeder_positions_x()
    z_outlet = cell.z_hopper_base
    z_shoulder = z_outlet + f.hopper_taper_z
    z_top = z_outlet + f.hopper_z

    hopper0 = B.loft_rings(
        ctx,
        "hopper",
        0,
        [
            B.rect_ring(f.hopper_outlet / 2.0, f.hopper_outlet / 2.0, z_outlet),
            B.rect_ring(f.hopper_x / 2.0, f.hopper_y / 2.0, z_shoulder),
            B.rect_ring(f.hopper_x / 2.0, f.hopper_y / 2.0, z_top),
        ],
        at_mm=(hopper_xs[0], 0.0, 0.0),
    )
    B.shade_flat(hopper0)

    hopper_positions = [(x, 0.0, 0.0) for x in hopper_xs[1:]]
    hoppers = B.instance_at(ctx, hopper0, "hopper", hopper_positions, start_index=1)
    rolled(hopper0, hoppers)

    # -- 6. chute: 5 objects, 1 mesh ------------------------------------------
    chute_top = cell.z_hopper_base
    chute_bottom = cell.z_cover_top
    chute_length = chute_top - chute_bottom
    chute_centre_z = (chute_top + chute_bottom) / 2.0

    chute0 = B.cylinder(
        ctx,
        "chute",
        0,
        diameter_mm=f.chute_diameter,
        length_mm=chute_length,
        at_mm=(hopper_xs[0], 0.0, chute_centre_z),
        axis="Z",
    )
    B.auto_smooth(chute0)

    chute_positions = [(x, 0.0, chute_centre_z) for x in hopper_xs[1:]]
    B.instance_at(ctx, chute0, "chute", chute_positions, start_index=1)

    # -- 7. breaker: 5 objects, 1 mesh ---------------------------------------
    breaker_centre_z = cell.z_breaker_base + f.cylinder_length / 2.0

    breaker0 = B.cylinder(
        ctx,
        "breaker",
        0,
        diameter_mm=f.cylinder_diameter,
        length_mm=f.cylinder_length,
        at_mm=(hopper_xs[0], 0.0, breaker_centre_z),
        axis="Z",
    )
    B.auto_smooth(breaker0)

    breaker_positions = [(x, 0.0, breaker_centre_z) for x in hopper_xs[1:]]
    B.instance_at(ctx, breaker0, "breaker", breaker_positions, start_index=1)

    # -- 8. chisel: 5 objects, 1 mesh -----------------------------------------
    # The chisel stops at the crust surface, where m04 has opened a hole for it.
    chisel_top = cell.z_breaker_base
    chisel_bottom = cell.z_crust_top
    chisel_length = chisel_top - chisel_bottom
    chisel_centre_z = (chisel_top + chisel_bottom) / 2.0

    chisel0 = B.cylinder(
        ctx,
        "chisel",
        0,
        diameter_mm=f.chisel_diameter,
        length_mm=chisel_length,
        at_mm=(hopper_xs[0], 0.0, chisel_centre_z),
        axis="Z",
    )
    B.auto_smooth(chisel0)

    chisel_positions = [(x, 0.0, chisel_centre_z) for x in hopper_xs[1:]]
    B.instance_at(ctx, chisel0, "chisel", chisel_positions, start_index=1)

    # -- 9. duct: 1 object, 1 mesh --------------------------------------------
    # Pipe plus a terminating flange at each stub end, as one cluster. The pipe
    # is SHORTENED by the two flange thicknesses rather than the flanges being
    # laid over its ends: cylinder_cluster welds without a boolean, so its
    # members must be disjoint or the result is a plausible wrong solid.
    duct_x = cell.hooding.end_box_centre_x(cell.shell_outer_x)
    flange_t = s.duct_flange_t
    pipe_length = cell.duct_length - 2.0 * flange_t
    flange_y = cell.duct_length / 2.0 - flange_t / 2.0

    duct0 = B.cylinder_cluster(
        ctx,
        "duct",
        0,
        [
            (s.duct_flange_diameter, flange_t, (0.0, -flange_y, 0.0)),
            (s.duct_diameter, pipe_length, (0.0, 0.0, 0.0)),
            (s.duct_flange_diameter, flange_t, (0.0, flange_y, 0.0)),
        ],
        at_mm=(duct_x, 0.0, cell.z_duct_centre),
        axis="Y",
        segments=s.duct_segments,
    )
    B.auto_smooth(duct0)

    # -- 10. throat: 1 object, 1 mesh -----------------------------------------
    # The part the blockout was missing. Through Phase 2 the header lay tangent
    # on the end enclosure roof with no opening anywhere: 6 m of pipe resting on
    # a closed box, and a hood plenum underneath it that vented nowhere. It read
    # as exactly what it was - a pipe left lying on a roof.
    #
    # A square-to-round transition is the real part, and it does two jobs at
    # once: it takes gas out of the plenum, and it is what holds the header up.
    # So the header no longer touches the roof at all - duct_throat_rise is now
    # what separates them, and z_duct_centre is derived from it.
    #
    # The top ring is a SADDLE, not a circle. A horizontal circle at the
    # header's underside touches it along one tangent line and leaves daylight
    # either side; the saddle is the actual branch-onto-header cut and seats on
    # the pipe all the way round. Both rings are sampled at the same angles, so
    # the loft bridges a rectangle to a round mouth without spiralling.
    radius = s.duct_diameter / 2.0
    throat0 = B.loft_rings(
        ctx,
        "throat",
        0,
        [
            B.rect_ring_polar(
                cell.duct_throat_mouth_x / 2.0,
                cell.duct_throat_mouth_y / 2.0,
                cell.z_end_box_roof,
                segments=s.duct_segments,
            ),
            B.saddle_ring(
                radius, cell.z_duct_centre, segments=s.duct_segments
            ),
        ],
        at_mm=(duct_x, 0.0, 0.0),
    )
    B.shade_flat(throat0)

    return ctx.created

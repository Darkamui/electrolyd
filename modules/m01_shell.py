"""
Steel shell: bottom plate, four walls, 28 side cradles, 8 end cradles, two
rim flanges.

Phase 3 detail pass. Two changes over the blockout:

  * A cradle is an I-section rib, not a flat plate — broad foot, slender web,
    bearing flange flush with the rim. The flange is what the portal column's
    base plate actually lands on, so the blockout's plain 25 mm plate left the
    column bearing on a knife edge.
  * Every plate edge carries a manufacturing bevel. Perfectly sharp steel does
    not exist and does not catch a highlight, which is most of why an unbeveled
    clay render reads as CG.

Every dimension comes from ctx.cell.
"""

from __future__ import annotations

import math

import bpy

from lib import build as B
from lib.scene import BuildContext


def build(ctx: BuildContext) -> list[bpy.types.Object]:
    """Steel shell blockout."""
    cell = ctx.cell
    shell = cell.shell

    # -- 1. bottom plate -----------------------------------------------
    # Top face lands exactly on Z = 0, so the box sits on -plate.
    plate = B.box_on(
        ctx,
        "plate",
        0,
        size_mm=(cell.shell_outer_x, cell.shell_outer_y, shell.plate),
        base_z_mm=-shell.plate,
    )
    B.bevel(plate, shell.edge_bevel)
    B.shade_flat(plate)

    # -- 2. long side walls ----------------------------------------------
    side_y = cell.shell_inner_y / 2.0 + shell.plate / 2.0
    for index, sign in enumerate((1.0, -1.0)):
        wall = B.box_on(
            ctx,
            "wall_side",
            index,
            size_mm=(cell.shell_outer_x, shell.plate, shell.rim_z),
            base_z_mm=0,
            at_xy_mm=(0, sign * side_y),
        )
        B.bevel(wall, shell.edge_bevel)
        B.shade_flat(wall)

    # -- 3. end walls, tucked between the side walls ----------------------
    end_x = cell.shell_inner_x / 2.0 + shell.plate / 2.0
    for index, sign in enumerate((1.0, -1.0)):
        wall = B.box_on(
            ctx,
            "wall_end",
            index,
            size_mm=(shell.plate, cell.shell_inner_y, shell.rim_z),
            base_z_mm=0,
            at_xy_mm=(sign * end_x, 0),
        )
        B.bevel(wall, shell.edge_bevel)
        B.shade_flat(wall)

    # -- 4. cradles, one mesh shared across all 28 ------------------------
    # An I-section in elevation: foot, web, bearing flange, stacked so the
    # three boxes are DISJOINT. box_cluster welds without a boolean, so
    # stacking rather than overlapping keeps the single mesh clean — and it is
    # the honest section anyway, since a real rib's web runs BETWEEN its
    # flanges rather than through them.
    #
    # The flange finishes flush with the rim because that is the surface the
    # column base plate bears on. Anything else and the load path from the
    # portal frame down to the potroom floor has a step in it.
    cradle_y = cell.shell_outer_y / 2.0 + shell.cradle_depth / 2.0
    positions_x = cell.cradle_positions_x()
    depth = shell.cradle_depth

    web_z = shell.rim_z - shell.cradle_foot_t - shell.cradle_flange_t
    cradle_boxes = (
        # foot: spreads the rib onto the floor
        ((shell.cradle_foot_x, depth, shell.cradle_foot_t),
         (0.0, 0.0, shell.cradle_foot_t / 2.0)),
        # web: the slender part, all the rib's height
        ((shell.cradle_thickness, depth, web_z),
         (0.0, 0.0, shell.cradle_foot_t + web_z / 2.0)),
        # flange: bearing surface, top face flush with the rim
        ((shell.cradle_flange_x, depth, shell.cradle_flange_t),
         (0.0, 0.0, shell.rim_z - shell.cradle_flange_t / 2.0)),
    )

    first = B.box_cluster(
        ctx, "cradle", 0, cradle_boxes, at_mm=(positions_x[0], cradle_y, 0.0)
    )
    B.bevel(first, shell.edge_bevel)
    B.shade_flat(first)

    remaining: list[tuple[float, float, float]] = [
        (x, cradle_y, 0.0) for x in positions_x[1:]
    ] + [(x, -cradle_y, 0.0) for x in positions_x]

    copies = B.instance_at(ctx, first, "cradle", remaining, start_index=1)
    for obj in copies:
        B.bevel(obj, shell.edge_bevel)
        B.shade_flat(obj)

    # -- 4b. end cradles, the SAME mesh turned a quarter turn ---------------
    # The end wall had nothing on it: 4800 x 1500 of dead plate, and in a
    # transverse elevation that is the largest surface in the picture. The
    # stiffening ran the whole length of the cell and then stopped at the
    # corner.
    #
    # These are linked copies of the side cradle, not a second section. The
    # cluster is authored symmetric about its own local X and Y, so a quarter
    # turn about Z is all it takes: the 320 mm foot that ran along the cell now
    # runs across it, and the 400 mm depth projects outward in X instead of Y.
    # A rotation, never a negative scale — QA flags those, and rightly.
    end_cradle_x = cell.end_cradle_centre_x
    end_positions: list[tuple[float, float, float]] = [
        (sign * end_cradle_x, y, 0.0)
        for sign in (1.0, -1.0)
        for y in cell.end_cradle_positions_y()
    ]
    end_copies = B.instance_at(
        ctx, first, "end_cradle", end_positions, start_index=0
    )
    for obj in end_copies:
        obj.rotation_euler.z = math.pi / 2.0
        B.bevel(obj, shell.edge_bevel)
        B.shade_flat(obj)

    # -- 5. rim flanges -----------------------------------------------------
    flange_y = cell.shell_inner_y / 2.0 + shell.plate / 2.0
    for index, sign in enumerate((1.0, -1.0)):
        flange = B.box_on(
            ctx,
            "flange",
            index,
            size_mm=(cell.shell_outer_x, shell.flange_width, shell.flange_thickness),
            base_z_mm=shell.rim_z,
            at_xy_mm=(0, sign * flange_y),
        )
        B.bevel(flange, shell.edge_bevel)
        B.shade_flat(flange)

    return ctx.created

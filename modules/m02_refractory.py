"""
Refractory lining + frozen-bath ledge blockout: bottom lining slabs, side/end
lining walls, and the ledge (solid block minus a lofted taper).

Primitive massing only. No bricks, no bevels. Every dimension comes from
ctx.cell.
"""

from __future__ import annotations

import bpy

from lib import build as B
from lib.scene import BuildContext


def build(ctx: BuildContext) -> list[bpy.types.Object]:
    """Refractory lining + ledge blockout."""
    cell = ctx.cell
    lining = cell.lining

    # -- A. bottom lining layers, stacked with no gap and no overlap -------
    insulation = B.box_on(
        ctx,
        "insulation",
        0,
        size_mm=(cell.shell_inner_x, cell.shell_inner_y, lining.insulation),
        base_z_mm=0,
    )
    B.shade_flat(insulation)

    # The firebrick is TWO courses, and they are modelled as two objects rather
    # than one 130 mm slab. The historic sectional plate the user supplied draws
    # them as separate labelled courses for a reason: they are laid as separate
    # courses, and the joint between them is visible in any section — which is
    # the plate this model is finally judged on.
    for course in range(lining.firebrick_courses):
        brick = B.box_on(
            ctx,
            "firebrick",
            course,
            size_mm=(cell.shell_inner_x, cell.shell_inner_y, lining.firebrick_course),
            base_z_mm=lining.z_insulation_top + course * lining.firebrick_course,
        )
        B.shade_flat(brick)

    bedding = B.box_on(
        ctx,
        "bedding",
        0,
        size_mm=(cell.shell_inner_x, cell.shell_inner_y, lining.bedding),
        base_z_mm=lining.z_firebrick_top,
    )
    B.shade_flat(bedding)

    # -- B. side lining walls, bedding top to shell rim ---------------------
    # Two distinct materials, not one 250 mm wall: a silicon carbide block
    # facing the cavity, and refractory backing behind it against the shell.
    # They are the only two lining layers that differ in what they do — the SiC
    # is there because it survives contact with cryolite, the backing is there
    # because it insulates — so collapsing them into one solid loses the thing
    # a section drawing of a sidewall exists to show.
    #
    # Offsets are cumulative outward from the cavity face, so the two courses
    # cannot drift apart or overlap however the thicknesses change.
    side_height = cell.shell.rim_z - lining.z_bedding_top
    courses = (
        ("sic", lining.side_sic, 0.0),
        ("backing", lining.side_backing, lining.side_sic),
    )

    for material, thickness, offset in courses:
        side_y = cell.cavity_y / 2.0 + offset + thickness / 2.0
        for index, sign in enumerate((1.0, -1.0)):
            wall = B.box_on(
                ctx,
                f"side_{material}",
                index,
                size_mm=(cell.shell_inner_x, thickness, side_height),
                base_z_mm=lining.z_bedding_top,
                at_xy_mm=(0, sign * side_y),
            )
            B.shade_flat(wall)

        end_x = cell.cavity_x / 2.0 + offset + thickness / 2.0
        for index, sign in enumerate((1.0, -1.0)):
            wall = B.box_on(
                ctx,
                f"end_{material}",
                index,
                size_mm=(thickness, cell.cavity_y, side_height),
                base_z_mm=lining.z_bedding_top,
                at_xy_mm=(sign * end_x, 0),
            )
            B.shade_flat(wall)

    # -- C. the ledge - solid block minus a lofted taper ---------------------
    hx, hy = cell.cavity_x / 2.0, cell.cavity_y / 2.0
    lg = cell.ledge
    levels = [
        (cell.z_cathode_top, lg.intrusion_at_metal),
        (cell.z_metal_top, lg.intrusion_at_metal),
        ((cell.z_metal_top + cell.z_bath_top) / 2.0, lg.intrusion_at_bath_mid),
        (cell.z_bath_top, lg.intrusion_at_bath_top),
        (cell.z_crust_top, lg.intrusion_at_bath_top - lg.top_overhang),
    ]
    rings = [B.rect_ring(hx - inset, hy - inset, z) for z, inset in levels]
    core = B.loft_rings(ctx, "ledge_core", 0, rings)

    outer = B.box_on(
        ctx,
        "ledge",
        0,
        size_mm=(cell.cavity_x, cell.cavity_y, cell.z_crust_top - cell.z_cathode_top),
        base_z_mm=cell.z_cathode_top,
    )
    B.boolean(outer, core, "DIFFERENCE")
    B.shade_flat(outer)
    B.shade_flat(core)

    return ctx.created

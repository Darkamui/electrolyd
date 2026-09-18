"""
Process layers blockout: molten metal pad, cryolite bath, frozen crust and
alumina cover blanket.

Primitive massing only. No bevels, no materials. Every dimension comes from
ctx.cell. The metal pad and bath must stay clear of the frozen-bath ledge
built by m02_refractory, so their footprints are derived from the same
ledge intrusion values that module uses.
"""

from __future__ import annotations

import bpy

from lib import build as B
from lib.scene import BuildContext


def build(ctx: BuildContext) -> list[bpy.types.Object]:
    """Metal pad, bath, crust and alumina cover blockout."""
    cell = ctx.cell
    lg = cell.ledge

    # -- 1. metal pad - sits on the cathode, inset by the ledge's metal-band
    #       intrusion (constant across this Z band, so a box is exact) -------
    metal = B.box_on(
        ctx,
        "metal",
        0,
        size_mm=(
            cell.cavity_x - 2.0 * lg.intrusion_at_metal,
            cell.cavity_y - 2.0 * lg.intrusion_at_metal,
            cell.process.metal_pad_depth,
        ),
        base_z_mm=cell.z_cathode_top,
    )
    B.shade_flat(metal)

    # -- 2. bath - tapers outward with height, following the ledge inner
    #       face, so it is lofted through three rings rather than boxed -----
    hx, hy = cell.cavity_x / 2.0, cell.cavity_y / 2.0
    bath_levels = [
        (cell.z_metal_top, lg.intrusion_at_metal),
        ((cell.z_metal_top + cell.z_bath_top) / 2.0, lg.intrusion_at_bath_mid),
        (cell.z_bath_top, lg.intrusion_at_bath_top),
    ]
    bath_rings = [B.rect_ring(hx - inset, hy - inset, z) for z, inset in bath_levels]
    bath = B.loft_rings(ctx, "bath", 0, bath_rings)
    B.shade_flat(bath)

    # -- 3. anode-footprint cutter - one object holding all 36 anode
    #       footprints. Extents come from spec, which has the reasoning for
    #       why it overshoots at the top and stops dead at the bottom. -------
    a = cell.anodes
    cut_bottom = cell.anode_cut_bottom_z
    cut_top = cell.anode_cut_top_z
    cut_h = cut_top - cut_bottom
    cut_z = cut_bottom + cut_h / 2.0
    boxes = [
        ((a.block_x, a.block_y, cut_h), (x, y, cut_z)) for x, y in a.positions()
    ]
    cutter = B.box_cluster(ctx, "anode_cut", 0, boxes)
    B.shade_flat(cutter)

    # The bath gets the same cutter. 36 anodes are immersed 155 mm into it and
    # the blockout left every one of them sharing that 155 mm with solid
    # electrolyte. One object may be the cutter for several BOOLEANs, so this
    # is a second modifier, not a second cutter.
    B.boolean(bath, cutter, "DIFFERENCE")

    # -- 4. crust - frozen bath skin on the bath surface, pierced by the
    #       anode footprints ------------------------------------------------
    crust_inset = lg.intrusion_at_bath_top - lg.top_overhang
    crust = B.box_on(
        ctx,
        "crust",
        0,
        size_mm=(
            cell.cavity_x - 2.0 * crust_inset,
            cell.cavity_y - 2.0 * crust_inset,
            cell.process.crust_thickness,
        ),
        base_z_mm=cell.z_bath_top,
    )
    B.boolean(crust, cutter, "DIFFERENCE")
    B.shade_flat(crust)

    # -- 5. alumina cover - powder blanket on the crust, same footprint,
    #       same cutter reused (do not build a second one) ------------------
    cover = B.box_on(
        ctx,
        "cover",
        0,
        size_mm=(
            cell.cavity_x - 2.0 * crust_inset,
            cell.cavity_y - 2.0 * crust_inset,
            cell.process.alumina_cover,
        ),
        base_z_mm=cell.z_crust_top,
    )
    B.boolean(cover, cutter, "DIFFERENCE")
    B.shade_flat(cover)

    # -- 6. feed holes - where the crust breakers have been through ----------
    # The blockout ran each chisel into an unbroken slab, which reads as a rod
    # welded to the ice rather than as a breaker that has done its job. A point
    # feeder's whole purpose is that there is a hole under it.
    #
    # The hole is wider than the chisel because the bath melts back around the
    # opening; how much wider is feeder.crust_hole_clearance, and spec asserts
    # the result still fits between the two anode rows.
    #
    # One cluster serves both crust and cover, and runs the full height of both
    # plus an overshoot at each end so no cutter cap lands on a face it cuts.
    f = cell.feeder
    hole_bottom = cell.z_bath_top - cell.process.crust_thickness
    hole_top = cell.z_cover_top + cell.process.crust_thickness
    hole_h = hole_top - hole_bottom
    holes = B.cylinder_cluster(
        ctx,
        "feed_hole",
        0,
        [
            (cell.crust_feed_hole_diameter, hole_h, (x, 0.0, hole_bottom + hole_h / 2.0))
            for x in cell.feeder_positions_x()
        ],
    )
    B.shade_flat(holes)
    B.boolean(crust, holes, "DIFFERENCE")
    B.boolean(cover, holes, "DIFFERENCE")

    return ctx.created

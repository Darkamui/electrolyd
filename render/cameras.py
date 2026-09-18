"""
Camera rig. Framing is COMPUTED from the datasheet, never hardcoded, so the
plates stay correctly framed when a dimension changes.

Shots provided:
    ortho_front    looking along +X   -> transverse view (matches the FR section)
    ortho_side     looking along +Y   -> longitudinal view
    ortho_top      looking down -Z    -> plan view
    hero           3/4 perspective    -> matches the potroom photograph angle
    section        as ortho_front, paired with the section cut
    detail_anode   close perspective on one anode assembly
"""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

import spec
from lib.scene import BuildContext
from lib.units import mm

MARGIN = 1.15
"""Framing headroom around the computed extent."""

SENSOR_MM = 36.0
"""Blender's default horizontal sensor size; the lens maths below assumes it."""


def _aim(location_m: Vector, target_m: Vector) -> tuple[float, float, float]:
    """
    Euler that points a camera from location at target.

    Blender cameras look down local -Z with +Y up, so the track quaternion is
    the honest way to do this. Hand-written eulers are how hero shots end up
    cropping the subject.
    """
    return (target_m - location_m).to_track_quat("-Z", "Y").to_euler()[:]


def _fit_distance(
    radius_m: float, lens_mm: float, margin: float, aspect: float = 1.0
) -> float:
    """
    Distance at which a bounding sphere of `radius_m` fits the frame.

    `aspect` is the SHORT frame edge over the long one. Blender's sensor fit is
    AUTO, so SENSOR_MM spans the longer edge and the shorter one sees a
    proportionally narrower field — on 16:9, only 9/16 of it. Fitting the sphere
    to the horizontal field alone therefore overflows the frame vertically,
    which is what cropped the shell off the bottom of the exploded hero. It is
    the same mistake Revision 4 fixed for `ortho_scale`, in its perspective
    form: the fit must be made against whichever field is NARROWER.
    """
    half_fov = math.atan(SENSOR_MM * min(1.0, aspect) / 2.0 / lens_mm)
    return radius_m * margin / math.sin(half_fov)


def _overall_extent(cell: spec.Cell) -> tuple[float, float, float]:
    """
    Overall bounding extent in mm, including superstructure and hooding.

    Every term is a real outermost part, not an estimate. The widest thing in Y
    is whichever of the gas duct, the portal columns or the busbar run reaches
    furthest; the tallest is the crust breaker standing on its hopper — NOT the
    columns, which the feeder deck now rises well above.
    """
    x = cell.shell_outer_x
    y = max(
        cell.duct_length,
        2.0 * (cell.column_centre_y + cell.superstructure.column_section / 2.0),
        cell.shell_outer_y + 2.0 * cell.busbars.riser_w,
    )
    z = max(
        cell.hooding.end_box_top_z,
        cell.z_breaker_base + cell.feeder.cylinder_length,
    )
    return x, y, z


def _new_camera(
    ctx: BuildContext,
    part: str,
    index: int,
    ortho: bool,
    location_m: tuple[float, float, float],
    rotation: tuple[float, float, float],
    ortho_scale_m: float = 1.0,
    lens_mm: float = 50.0,
) -> bpy.types.Object:
    name = ctx.name(part, index)
    data = bpy.data.cameras.new(name)
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = ortho_scale_m
    else:
        data.type = "PERSP"
        data.lens = lens_mm
    data.clip_start = 0.1
    data.clip_end = 500.0
    obj = bpy.data.objects.new(name, data)
    obj.location = location_m
    obj.rotation_euler = rotation
    return ctx.link(obj)


def build(ctx: BuildContext) -> dict[str, bpy.types.Object]:
    """Create every camera. Returns a shot-name -> camera map."""
    cell = ctx.cell
    ex, ey, ez = _overall_extent(cell)
    mid_z = mm(ez / 2.0)
    dist = mm(max(ex, ey, ez) * 2.0)

    cams: dict[str, bpy.types.Object] = {}

    # Transverse: camera on -X looking toward +X.
    cams["ortho_front"] = _new_camera(
        ctx,
        "ortho_front",
        0,
        ortho=True,
        location_m=(-dist, 0.0, mid_z),
        rotation=(math.radians(90), 0.0, math.radians(-90)),
        ortho_scale_m=mm(max(ey, ez) * MARGIN),
    )

    # Longitudinal: camera on -Y looking toward +Y.
    cams["ortho_side"] = _new_camera(
        ctx,
        "ortho_side",
        0,
        ortho=True,
        location_m=(0.0, -dist, mid_z),
        rotation=(math.radians(90), 0.0, 0.0),
        ortho_scale_m=mm(max(ex, ez) * MARGIN),
    )

    # Plan: straight down.
    cams["ortho_top"] = _new_camera(
        ctx,
        "ortho_top",
        0,
        ortho=True,
        location_m=(0.0, 0.0, dist),
        rotation=(0.0, 0.0, 0.0),
        ortho_scale_m=mm(max(ex, ey) * MARGIN),
    )

    # Hero 3/4, echoing the reference photograph: off one corner, looking down
    # the length. Position is derived from the bounding sphere so the whole
    # cell stays framed no matter how the datasheet moves.
    hero_lens = 42.0
    # Frame on the cell's vertical mid-height, not the world origin, or the
    # subject sits high and the plate is half empty floor.
    target = Vector((0.0, 0.0, mm(ez / 2.0)))
    radius = mm(math.sqrt(ex**2 + ey**2 + ez**2) / 2.0)
    fit = _fit_distance(radius, hero_lens, MARGIN)

    # Azimuth off the long axis, elevation above the horizon: the potroom
    # photograph's viewpoint, expressed as angles rather than coordinates.
    azimuth, elevation = math.radians(147.0), math.radians(26.0)
    hero_loc = target + Vector((
        math.cos(elevation) * math.cos(azimuth),
        math.cos(elevation) * math.sin(azimuth),
        math.sin(elevation),
    )) * fit
    cams["hero"] = _new_camera(
        ctx,
        "hero",
        0,
        ortho=False,
        location_m=hero_loc[:],
        rotation=_aim(hero_loc, target),
        lens_mm=hero_lens,
    )
    # The hero is the one perspective shot that frames the WHOLE model, so it
    # is the one that must refit when the model changes size. At Explosion 1.0
    # the superstructure stands 7 m clear and the hooding opens 5 m either side;
    # a camera placed from the assembled bounding sphere crops all of it. The
    # close-ups below deliberately frame a small region and must NOT refit,
    # which is why this is an opt-in flag rather than a rule for perspective.
    cams["hero"]["frame_scene"] = 1.0

    # Section shares the transverse framing.
    cams["section"] = _new_camera(
        ctx,
        "section",
        0,
        ortho=True,
        location_m=(-dist, 0.0, mid_z),
        rotation=(math.radians(90), 0.0, math.radians(-90)),
        ortho_scale_m=mm(max(ey, ez) * 1.05),
    )
    # The section is a study plate, not a presentation one — crop it tighter
    # than the elevations. activate() reads this back when it refits.
    cams["section"]["frame_margin"] = 1.05

    # Close on the anode assembly the SECTION cuts through — the shot is
    # rendered with the cutaway on, so the camera must stand on the discarded
    # side and look into the opened cell. Aimed anywhere else it frames shell
    # plate, which is what the first version of this shot delivered: a
    # perspective close-up of a sealed pot from the outside.
    #
    # Framed on the whole assembly, not the block. A detail plate of an anode
    # that omits the stubs, yoke, stem and clamp is a plate of a carbon brick,
    # and those four parts are the entire Phase 3 detail pass on this subsystem.
    ax = cell.section_plane_x
    ay = cell.anodes.row_centre_y
    detail_lens = 80.0
    detail_low, detail_high = cell.z_anode_bottom, cell.z_stem_top
    detail_target = Vector((mm(ax), mm(ay), mm((detail_low + detail_high) / 2.0)))
    detail_radius = mm((detail_high - detail_low) / 2.0) * 1.25
    # Azimuth just off the cut plane's normal: square enough that the cutaway
    # face reads, oblique enough that the assembly still has depth.
    detail_loc = detail_target + Vector((
        math.cos(math.radians(14.0)) * math.cos(math.radians(-152.0)),
        math.cos(math.radians(14.0)) * math.sin(math.radians(-152.0)),
        math.sin(math.radians(14.0)),
    )) * _fit_distance(detail_radius, detail_lens, 1.1)
    cams["detail_anode"] = _new_camera(
        ctx,
        "detail_anode",
        0,
        ortho=False,
        location_m=detail_loc[:],
        rotation=_aim(detail_loc, detail_target),
        lens_mm=detail_lens,
    )

    # -- Phase 5 material validation close-ups ------------------------------
    #
    # Three plates, chosen so that between them every one of the seventeen
    # materials appears at close range against a material it has to be told
    # apart from. A close-up that shows one material alone proves nothing —
    # the question a material plate answers is "does cast iron read as cast
    # iron NEXT TO carbon", not "is this grey".
    #
    #   mat_lining   sectioned. Floor and sidewall stack: insulation board,
    #                firebrick, alumina bedding, SiC, ramming paste, graphite
    #                cathode, steel collector bar, molten metal, bath, ledge,
    #                crust, alumina cover. Twelve of the seventeen.
    #   mat_busbar   aluminium riser against copper flex laminates against
    #                steel clamp plate and oxidised shell — the conductor
    #                trio, which is where a wrong metallic value shows worst.
    #   mat_shell    outside: galvanised hood, oxidised cradle, painted end
    #                box and its number plate.

    def _close(part: str, target: Vector, radius_m: float,
               azimuth_deg: float, elevation_deg: float, lens: float = 80.0):
        az, el = math.radians(azimuth_deg), math.radians(elevation_deg)
        loc = target + Vector((
            math.cos(el) * math.cos(az),
            math.cos(el) * math.sin(az),
            math.sin(el),
        )) * _fit_distance(radius_m, lens, 1.1)
        return _new_camera(
            ctx, part, 0, ortho=False,
            location_m=loc[:], rotation=_aim(loc, target), lens_mm=lens,
        )

    # The lining stack, cut open. The camera stands on the discarded -X side
    # of the section plane and looks very nearly along its normal, so the whole
    # sightline is through opened cell rather than through shell plate.
    lin_y = cell.shell_inner_y / 2.0 - cell.lining.side_total / 2.0
    lin_low, lin_high = 0.0, cell.z_cover_top
    lin_target = Vector((
        mm(cell.section_plane_x), mm(lin_y), mm((lin_low + lin_high) / 2.0)
    ))
    # Nearly square on to the cut face, and nearly level with it. A lining
    # section read from 17 degrees above and 21 off the normal turns every
    # layer into a foreshortened wedge and the courses stop reading as courses;
    # the whole point of the plate is that the bands are legible as bands.
    cams["mat_lining"] = _close(
        "mat_lining", lin_target,
        mm((lin_high - lin_low) / 2.0) * 1.15,
        azimuth_deg=193.0, elevation_deg=8.0, lens=70.0,
    )

    # The riser / flex / clamp joint on the upstream (+Y) side, at the first
    # riser station clear of centre.
    riser_x = cell.riser_positions_x()[0]
    bus_low, bus_high = cell.bar_z_centre, cell.z_riser_top
    bus_target = Vector((
        mm(riser_x),
        mm(cell.shell_outer_y / 2.0 + cell.busbars.riser_t),
        mm((bus_low + bus_high) / 2.0),
    ))
    cams["mat_busbar"] = _close(
        "mat_busbar", bus_target,
        mm((bus_high - bus_low) / 2.0) * 1.3,
        azimuth_deg=58.0, elevation_deg=16.0, lens=65.0,
    )

    # Outside, downstream (-Y) side, over the end enclosure: hood arc, cradles,
    # painted box. Framed on the run between the hood apex and the shell foot.
    shl_low, shl_high = 0.0, cell.hooding.end_box_top_z
    shl_target = Vector((
        mm(cell.shell_outer_x * 0.32),
        mm(-cell.shell_outer_y / 2.0),
        mm((shl_low + shl_high) / 2.0),
    ))
    cams["mat_shell"] = _close(
        "mat_shell", shl_target,
        mm((shl_high - shl_low) / 2.0) * 1.45,
        azimuth_deg=-118.0, elevation_deg=12.0, lens=60.0,
    )

    return cams


def scene_bounds() -> tuple[Vector, Vector] | None:
    """
    World-space bounds of every mesh actually in the scene, depsgraph-evaluated.

    For FRAMING the evaluated box is the right one — solidify, array and mirror
    results are all things the camera has to fit. This is the opposite of what
    qa.validate._mesh_bounds wants, which measures the authored surface.
    """
    dg = bpy.context.evaluated_depsgraph_get()
    lo = hi = None
    for obj in bpy.context.scene.objects:
        # hide_render covers boolean cutters and the half a section discards.
        # Framing what will not appear is how a plate ends up off-centre.
        if obj.type != "MESH" or obj.data is None or obj.hide_render:
            continue
        ev = obj.evaluated_get(dg)
        mw = ev.matrix_world
        for corner in ev.bound_box:
            p = mw @ Vector(corner)
            if lo is None:
                lo, hi = p.copy(), p.copy()
            else:
                for i in range(3):
                    lo[i] = min(lo[i], p[i])
                    hi[i] = max(hi[i], p[i])
    return None if lo is None else (lo, hi)


def scene_corners() -> list[Vector]:
    """
    Every visible object's eight evaluated bounding-box corners, in world space.

    Framing wants these, not the scene AABB's own corners. On an exploded model
    the AABB's corners are phantoms: nothing occupies +11 m along X and +12 m up
    at the same time — the end enclosures are low and the superstructure is
    narrow — so fitting them pushed the camera back far enough to leave the cell
    at 60% of frame height in a sea of grey. Roughly 6000 points; the cost is
    nothing next to a Cycles frame.
    """
    dg = bpy.context.evaluated_depsgraph_get()
    points: list[Vector] = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.data is None or obj.hide_render:
            continue
        ev = obj.evaluated_get(dg)
        mw = ev.matrix_world
        points.extend(mw @ Vector(c) for c in ev.bound_box)
    return points


def _reframe_ortho(cam: bpy.types.Object, lo: Vector, hi: Vector) -> None:
    """
    Fit an orthographic camera to the measured scene, in the camera's own
    screen axes.

    Two things this exists to prevent, both of which shipped cropped plates:

    1. `ortho_scale` spans the LARGER render dimension, not the width. On a
       16:9 frame the vertical span is only 9/16 of it, so a transverse view of
       a cell 4.8 m wide and 5.0 m tall silently lost its top and bottom.
    2. The extent was predicted from spec rather than measured, so anything the
       prediction forgot — the crust breaker, a rib standing proud — fell
       outside the frame with nothing to report it.

    Projecting the measured box onto the camera's right/up axes handles all
    three ortho shots with no per-shot special-casing.
    """
    scene = bpy.context.scene
    basis = cam.matrix_world.to_3x3()
    right = (basis @ Vector((1.0, 0.0, 0.0))).normalized()
    up = (basis @ Vector((0.0, 1.0, 0.0))).normalized()

    corners = [
        Vector((x, y, z))
        for x in (lo.x, hi.x)
        for y in (lo.y, hi.y)
        for z in (lo.z, hi.z)
    ]
    rs = [c.dot(right) for c in corners]
    us = [c.dot(up) for c in corners]
    width, height = max(rs) - min(rs), max(us) - min(us)

    aspect = (
        scene.render.resolution_x * scene.render.pixel_aspect_x
    ) / (scene.render.resolution_y * scene.render.pixel_aspect_y)
    # ortho_scale covers the longer sensor edge; the shorter one gets
    # scale/aspect (or scale*aspect for a portrait frame).
    fit = max(width, height * aspect) if aspect >= 1.0 else max(height, width / aspect)

    margin = cam.get("frame_margin", MARGIN)
    cam.data.ortho_scale = fit * margin

    # Slide the camera across its own screen plane so the subject centres.
    # The view direction is untouched, so the shot stays a true elevation.
    loc = cam.matrix_world.translation.copy()
    loc += right * ((max(rs) + min(rs)) / 2.0 - loc.dot(right))
    loc += up * ((max(us) + min(us)) / 2.0 - loc.dot(up))
    cam.location = loc


def required_distance(
    cam: bpy.types.Object, centre: Vector, corners: list[Vector] | None = None
) -> float:
    """
    How far back along its own view axis `cam` must sit for `corners` to fit.

    Closed-form and exact. With the camera at `centre - forward * d` a point's
    depth is its offset along forward plus d, so each point states the d it
    demands and the answer is the largest of them.

    Public because the turntable needs the same number the hero does, and a
    turntable whose framing rule differs from the stills is a turntable that
    crops something the stills showed.
    """
    basis = cam.matrix_world.to_3x3()
    forward = (basis @ Vector((0.0, 0.0, -1.0))).normalized()
    right = (basis @ Vector((1.0, 0.0, 0.0))).normalized()
    up = (basis @ Vector((0.0, 1.0, 0.0))).normalized()

    # Sensor fit is AUTO: SENSOR_MM spans the LONGER frame edge, and the shorter
    # edge sees a proportionally narrower field. Both half-angles are needed,
    # because which one binds depends on how the subject lies in frame.
    res = bpy.context.scene.render
    long_edge = max(res.resolution_x, res.resolution_y)
    sensor_x = SENSOR_MM * res.resolution_x / long_edge
    sensor_y = SENSOR_MM * res.resolution_y / long_edge
    margin = cam.get("frame_margin", MARGIN)
    tan_h = sensor_x / 2.0 / cam.data.lens / margin
    tan_v = sensor_y / 2.0 / cam.data.lens / margin

    distance = 0.0
    for point in scene_corners() if corners is None else corners:
        corner = point - centre
        depth = corner.dot(forward)
        distance = max(
            distance,
            abs(corner.dot(right)) / tan_h - depth,
            abs(corner.dot(up)) / tan_v - depth,
        )
    return distance


def _reframe_persp(cam: bpy.types.Object, lo: Vector, hi: Vector) -> None:
    """
    Slide a perspective camera along its own view axis until the measured scene
    fits, keeping both its direction and the point it looks at.

    Only the distance changes. Recomputing the position from angles instead
    would re-derive the shot every time the model's extent moved, and the hero's
    azimuth and elevation are a deliberate choice — they echo the potroom
    photograph. A camera that reframes itself should not also recompose itself.

    The fit is against the eight measured CORNERS projected onto the camera's
    own screen axes, not against a bounding sphere. A sphere is the safe fit for
    a compact subject and a bad one for this: an exploded cell is a long thin
    diagonal 22 m across, so its sphere has a 16.5 m radius while its projection
    is nothing like that wide, and fitting the sphere left the model sitting in
    a third of the frame surrounded by grey. Corners cost eight dot products and
    are exact. `_reframe_ortho` has measured them since Revision 4; this is the
    perspective equivalent.
    """
    centre = (lo + hi) / 2.0
    if (hi - lo).length <= 0.0:
        return
    forward = (cam.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
    distance = required_distance(cam, centre)

    radius = (hi - lo).length / 2.0
    cam.location = centre - forward * distance
    # The far plane is fixed at 500 m; an exploded model pushes the camera back
    # far enough that it is worth making sure the subject is still inside it.
    cam.data.clip_end = max(cam.data.clip_end, (centre - cam.location).length + radius * 2.0)


def activate(name: str) -> bpy.types.Object:
    """
    Make a named shot's camera the scene camera, refitting it to what is
    actually in the scene.

    Called at render time, not build time, because the render resolution — and
    therefore the frame aspect — is only known once a preset has been applied.
    """
    obj = bpy.data.objects.get(f"11_CAMERAS_{name}_000")
    if obj is None:
        raise KeyError(f"no camera for shot {name!r}")
    bpy.context.scene.camera = obj

    refit = obj.data.type == "ORTHO" or obj.get("frame_scene")
    if refit:
        # matrix_world is stale until the depsgraph has been evaluated, and a
        # stale one silently yields the wrong screen axes.
        bpy.context.view_layer.update()
        bounds = scene_bounds()
        if bounds is not None:
            if obj.data.type == "ORTHO":
                _reframe_ortho(obj, *bounds)
            else:
                _reframe_persp(obj, *bounds)
    return obj

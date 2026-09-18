"""
The two Phase 7 motion deliverables: a turntable and an exploded assembly.

    turntable   orbit at fixed elevation, assembled, one full revolution
    explosion   fixed hero viewpoint, Explosion 1 -> 0: the cell assembling

Both write H.264 MP4 through Blender's own ffmpeg, so there is no external
dependency and no PNG sequence to clean up afterwards.

The one rule that governs both, and the reason this is a module rather than two
loops in the orchestrator: **the camera is framed ONCE, for the worst frame, and
then held.** `cameras.activate()` refits per shot, which is right for a still
and wrong for a sequence — a camera that refits every frame breathes in and out
as the subject's projection changes, and on the explode that breathing is larger
than the motion being shown. So each animation measures every frame it is about
to render, takes the distance the hungriest one demands, and does not move
again. The subject drifts within a stable frame, which is what reads as a camera
on a tripod.
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector

from lib import explode
from lib.scene import fcurves
from render import cameras, shots

FPS = 30


def _use_video(path: str, fps: int = FPS) -> str:
    """
    Point the scene at an MP4. Returns the filepath STEM, not the final name.

    Blender appends the container extension itself when `use_file_extension` is
    on, so the filepath handed to it carries no suffix — passing one produces
    `turntable.mp4.mp4`. It also stamps the rendered frame range onto the name.
    `_finish` deals with that; this function cannot, because it runs before the
    range is rendered.
    """
    scene = bpy.context.scene
    scene.render.fps = fps
    scene.render.filepath = os.path.splitext(path)[0]
    scene.render.use_file_extension = True
    # `media_type` is new in Blender 5.x and gates the enum below: FFMPEG is
    # simply not among the file_format options until the media type is VIDEO,
    # and assigning it first raises rather than being ignored.
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    ff = scene.render.ffmpeg
    ff.format = "MPEG4"
    ff.codec = "H264"
    ff.constant_rate_factor = "HIGH"
    ff.ffmpeg_preset = "GOOD"
    ff.gopsize = 12
    ff.audio_codec = "NONE"

    # H.264 refuses odd dimensions. Every preset here is even, but a future
    # SHOT_ASPECT reshape rounds to whatever it rounds to, and the failure mode
    # is an encoder error at the end of a long render rather than at the start.
    for axis in ("resolution_x", "resolution_y"):
        value = getattr(scene.render, axis)
        if value % 2:
            setattr(scene.render, axis, value + 1)
    return scene.render.filepath


def _finish(base: str, start: int, end: int) -> str:
    """
    Rename Blender's frame-stamped video to the clean name. Returns the result.

    Blender writes `turntable0001-0120.mp4`, not `turntable.mp4` — sensible for
    a sequence of takes, wrong for a deliverable whose name is referenced from a
    plan and a web page. The stamped name is derived rather than guessed: it is
    exactly the range the scene was told to render.
    """
    stamped, final = f"{base}{start:04d}-{end:04d}.mp4", f"{base}.mp4"
    if os.path.exists(stamped):
        os.replace(stamped, final)
    return final


def _unwrap(eulers: list[Vector]) -> list[Vector]:
    """
    Make a per-frame euler track continuous.

    `to_track_quat().to_euler()` returns each rotation in its own principal
    range, so somewhere in a 360 degree orbit a channel steps from +pi to -pi.
    Keyframed as-is that step is interpolated, and the camera whips through a
    full reverse revolution between two frames. Adding the multiple of 2pi that
    keeps each value within pi of its predecessor costs nothing and removes the
    whole class of problem.
    """
    out = [eulers[0]]
    for e in eulers[1:]:
        prev = out[-1]
        out.append(Vector(tuple(
            v + round((prev[i] - v) / (2.0 * math.pi)) * 2.0 * math.pi
            for i, v in enumerate(e)
        )))
    return out


def _keyframe_camera(
    cam: bpy.types.Object,
    track: list[tuple[int, Vector, Vector]],
) -> None:
    """Write one location + rotation key per frame, linearly interpolated."""
    for frame, loc, rot in track:
        cam.location = loc
        cam.rotation_euler = rot
        cam.keyframe_insert("location", frame=frame)
        cam.keyframe_insert("rotation_euler", frame=frame)

    # LINEAR, not the default bezier. A bezier through per-frame keys eases
    # between every pair of them, which on a constant-rate orbit is a stutter
    # thirty times a second.
    for fcurve in fcurves(cam):
        for kp in fcurve.keyframe_points:
            kp.interpolation = "LINEAR"


# ---------------------------------------------------------------------------


def turntable(
    frames: int = 240,
    elevation_deg: float = 22.0,
    at: float = 0.0,
    subdir: str = "",
) -> str:
    """
    One revolution about the cell's own vertical axis, at a fixed elevation.

    `frames` covers 360 degrees exclusive: the key at `frames + 1` is the full
    turn, and rendering 1..frames stops one step short of repeating frame 1. A
    turntable that renders the closing duplicate visibly hitches on loop.

    240 frames is 8 seconds at 30 fps, i.e. 45 degrees per second. The first cut
    ran 120 and measured 4.000 s exactly — a 90 deg/s revolution, which is fine
    for a teapot and much too fast for a 16.4 m pot: an end-on to broadside
    transition passes in under a second, and the eye is still finding the anode
    rows when the cell has turned away. Render time is linear in the count and
    the machine is otherwise idle, so the slow version is nearly free.

    The orbit radius is the largest any azimuth demands. The cell is 16.4 m long
    and 4.8 m wide, so the distance that frames it end-on is roughly three times
    the one that frames it broadside; holding the larger means the broadside
    view sits small, and that is the correct trade. The alternative — a radius
    that varies with azimuth — is a camera that dollies in and out twice per
    revolution, which reads as a mistake even when it is deliberate.
    """
    explode.set_explosion(at)
    cam = cameras.activate("hero")
    bpy.context.view_layer.update()

    bounds = cameras.scene_bounds()
    if bounds is None:
        raise RuntimeError("nothing to orbit: the scene has no visible meshes")
    lo, hi = bounds
    centre = (lo + hi) / 2.0
    corners = cameras.scene_corners()

    elevation = math.radians(elevation_deg)
    azimuths = [2.0 * math.pi * i / frames for i in range(frames + 1)]
    directions = [
        Vector((
            math.cos(elevation) * math.cos(a),
            math.cos(elevation) * math.sin(a),
            math.sin(elevation),
        ))
        for a in azimuths
    ]

    # Pass one: ask every azimuth what distance it needs. `required_distance`
    # reads the camera's own orientation, so the camera has to be pointed the
    # right way before each question — hence placing it at a throwaway distance
    # first. The answer does not depend on that distance, only on the direction.
    radius = 0.0
    probe = (hi - lo).length
    for direction in directions:
        cam.location = centre + direction * probe
        cam.rotation_euler = cameras._aim(cam.location, centre)
        bpy.context.view_layer.update()
        radius = max(radius, cameras.required_distance(cam, centre, corners))

    # Pass two: the real track, all at that one radius.
    locations = [centre + d * radius for d in directions]
    rotations = _unwrap([
        Vector(cameras._aim(loc, centre)) for loc in locations
    ])
    cam.animation_data_clear()
    _keyframe_camera(
        cam, list(zip(range(1, frames + 2), locations, rotations))
    )
    cam.data.clip_end = max(cam.data.clip_end, radius + (hi - lo).length)

    scene = bpy.context.scene
    scene.camera = cam
    scene.frame_start, scene.frame_end = 1, frames
    base = _use_video(os.path.join(shots.OUT_DIR, subdir, "turntable"))
    os.makedirs(os.path.dirname(base), exist_ok=True)
    bpy.ops.render.render(animation=True)
    return _finish(base, 1, frames)


def explosion(
    frames: int = 150,
    hold: int = 15,
    subdir: str = "",
) -> str:
    """
    The assembly sequence: apart, together, from the fixed hero viewpoint.

    Runs 1 -> 0, not 0 -> 1. An exploded diagram answers "what is in there";
    an assembly animation answers "how does it go together", and the second is
    the more useful of the two from the same keyframes. `hold` frames of
    stillness at each end stop the loop from snapping.

    The camera is framed at Explosion 1.0 — the widest the model ever is — and
    then held for the whole sequence. Framed at 0 instead, the first two thirds
    of the shot would play out beyond the edges of the frame.
    """
    explode.set_explosion(1.0)
    cam = cameras.activate("hero")   # refits against the fully exploded model
    bpy.context.view_layer.update()

    ctrl = explode.master()
    if ctrl is None:
        raise RuntimeError("explosion rig not built")

    # Keyed on the control property, so the drivers do the work and the rig
    # stays the single description of how this cell comes apart.
    ctrl.animation_data_clear()
    schedule = (
        (1, 1.0),
        (1 + hold, 1.0),
        (frames - hold, 0.0),
        (frames, 0.0),
    )
    for frame, value in schedule:
        ctrl[explode.PROP] = value
        ctrl.keyframe_insert(f'["{explode.PROP}"]', frame=frame)

    # Bezier between the two moving keys is wanted here — it eases the parts
    # into place instead of stopping them dead — but the two holds must be flat,
    # or the interpolator overshoots past 1.0 and past 0.0 and the subsystems
    # visibly bounce at both ends.
    for fcurve in fcurves(ctrl):
        for kp in fcurve.keyframe_points:
            kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"

    scene = bpy.context.scene
    scene.camera = cam
    scene.frame_start, scene.frame_end = 1, frames
    base = _use_video(os.path.join(shots.OUT_DIR, subdir, "explosion"))
    os.makedirs(os.path.dirname(base), exist_ok=True)
    bpy.ops.render.render(animation=True)

    ctrl.animation_data_clear()
    explode.set_explosion(0.0)
    return _finish(base, 1, frames)


SEQUENCES = {"turntable": turntable, "explosion": explosion}

"""
Render presets.

Two tiers, following the Phase 0 findings:

    preview  EEVEE, low res           -> the iterate/critique loop
    hero     Cycles on OPTIX GPU      -> QA and final plates

Cycles defaults to CPU on this machine, so the GPU must be opted into
explicitly. See tools/API_NOTES.md.
"""

from __future__ import annotations

import math
import os

import bpy

from render import cameras

OUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "out")
)

ALL_SHOTS = (
    "ortho_front",
    "ortho_side",
    "ortho_top",
    "hero",
    "section",
    "detail_anode",
)

BLOCKOUT_SHOTS = ("ortho_front", "ortho_side", "ortho_top", "hero", "section")

MATERIAL_SHOTS = ("mat_lining", "mat_busbar", "mat_shell", "detail_anode")

EXPLODED_SHOTS = ("hero", "ortho_front", "ortho_side")
"""
Phase 6 validation set, rendered once per explosion step.

The hero carries the plate; the two elevations are what make it CHECKABLE. An
exploded 3/4 view can hide a subsystem travelling the wrong way behind one that
travels the right way, and the transverse elevation cannot — every group's
motion is a straight line across the frame. The plan view is left out: nothing
in EXPLOSION_VECTORS travels along X except the end enclosures.
"""
"""
Phase 5 validation set. `detail_anode` is reused rather than duplicated: it
already frames carbon against cast iron against aluminium, which is the one
material adjacency the three new plates do not cover.
"""

SECTIONED_SHOTS = frozenset({"section", "detail_anode", "mat_lining"})
"""
Shots that only make sense with the cutaway applied.

Both look at things sealed inside a closed pot. `detail_anode` was originally
rendered without the cut and returned a perspective close-up of blank shell
plate — the anode it was aimed at was behind 15 mm of steel and a hood panel.
"""

SHOT_ASPECT = {
    "ortho_front": 1.0,
    "section": 1.0,
    # The lining stack and the busbar joint are both tall and narrow; a
    # widescreen frame spends its pixels on the air beside them.
    "mat_lining": 1.0,
    "mat_busbar": 1.0,
}
"""
Frame shape per shot, where the default 16:9 wastes the plate.

The cell is ~16.4 m long but only 4.8 m wide and 5.0 m tall. Looking down the
length, a widescreen frame spends most of its pixels on empty air either side
while the camera pulls back to fit the height. A square frame puts roughly
twice the resolution on the subject for the same pixel budget. The longitudinal
and plan views really are wide, so they keep 16:9.
"""

_BASE_RES = (1280, 720)
"""Pixel budget set by the last preset; SHOT_ASPECT reshapes it per shot."""


CLAY_NAME = "MAT_blockout_clay"


def blockout_clay() -> bpy.types.Material:
    """
    Mid-grey clay for blockout plates.

    Blender's default surface is 0.8 albedo, which clips to paper-white under
    any usable key light and hides exactly the form we are trying to judge.
    0.32 leaves headroom for both the lit and shadowed sides to read.
    """
    mat = bpy.data.materials.get(CLAY_NAME)
    if mat is None:
        mat = bpy.data.materials.new(CLAY_NAME)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.32, 0.32, 0.33, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.62
        bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def apply_blockout_clay() -> int:
    """Give every un-materialled mesh the clay. Never overrides a real material."""
    mat = blockout_clay()
    count = 0
    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.data is None:
            continue
        if len(obj.data.materials) == 0:
            obj.data.materials.append(mat)
            count += 1
    return count


def _grade(scene: bpy.types.Scene) -> None:
    """Pin the colour pipeline so exposure is reproducible run to run."""
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "None"
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0
    except (AttributeError, TypeError):
        pass


def use_preview(resolution: tuple[int, int] = (1280, 720)) -> None:
    """Fast EEVEE. Engine id is BLENDER_EEVEE on 5.2.1, not _NEXT."""
    global _BASE_RES
    _BASE_RES = resolution
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    _grade(scene)
    apply_blockout_clay()
    try:
        scene.eevee.taa_render_samples = 32
    except AttributeError:
        pass


def use_hero(
    resolution: tuple[int, int] = (2560, 1440), samples: int = 256
) -> str:
    """
    Cycles on GPU. Returns the device actually engaged so the caller can
    report it rather than assume.
    """
    global _BASE_RES
    _BASE_RES = resolution
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True

    device = "CPU"
    prefs = bpy.context.preferences.addons.get("cycles")
    if prefs is not None:
        cprefs = prefs.preferences
        for backend in ("OPTIX", "CUDA"):
            try:
                cprefs.compute_device_type = backend
                devs = [
                    d for d in cprefs.get_devices_for_type(backend) if "GPU" in d.name
                ] or list(cprefs.get_devices_for_type(backend))
                if devs:
                    for d in cprefs.get_devices_for_type(backend):
                        d.use = True
                    scene.cycles.device = "GPU"
                    device = f"{backend}:{devs[0].name}"
                    break
            except (TypeError, AttributeError):
                continue
    return device


def use_motion(
    resolution: tuple[int, int] = (1440, 1080), samples: int = 64
) -> str:
    """
    Cycles for SEQUENCES. Same engine and lighting as the hero stills, sized for
    two or three hundred frames instead of twelve.

    A still is looked at for a minute and a frame of video for a thirtieth of a
    second, so the sample count that a plate needs is waste here — 64 samples
    with the denoiser on is indistinguishable in motion and renders four times
    faster. The resolution drops for the same reason: 1080p is the delivery
    format for a turntable, and at 1440p a 270-frame set is an overnight job for
    pixels nobody will see.

    **4:3, not 16:9, and the reason is measured.** An exploded cell is a tall
    near-square diagonal — its own bounding box is about 1.03:1 — so on a 16:9
    frame it used only 46.6% of the width at its widest while filling 80.6% of
    the height. More than half the frame was grey in every frame of both
    sequences. Rendering the governing frames of each sequence on a transparent
    film and counting alpha pixels, at three aspects:

        subject as % of frame AREA      16:9    4:3     1:1
        explosion, at Explosion 1.0     16.5   21.4    27.9
        explosion, at Explosion 0.0      6.1    7.9    10.2
        turntable, end-on               13.9   17.4    16.8
        turntable, broadside            18.7   22.3    20.9

    1:1 is the best frame the explosion could have and the WRONG one for the
    turntable: a turntable subject changes aspect continuously, from roughly
    0.7:1 end-on to 2.6:1 broadside, and squaring the frame makes broadside the
    binding constraint — the worst azimuth jumps from 195 deg to 55 and the
    radius stops shrinking usefully. 4:3 is the one aspect that improves BOTH
    (+30% subject area on the explosion, +19% on the turntable), so the delivery
    set stays one shape. Pass `resolution` to override; `--anim-aspect` on the
    orchestrator does it from the command line.
    """
    device = use_hero(resolution=resolution, samples=samples)
    # Denoising matters more here than on a still. At 64 samples the raw frame
    # is noisy, and film grain that is DIFFERENT every frame is the one artifact
    # video compression cannot hide — it eats the bitrate and the motion with it.
    bpy.context.scene.cycles.use_denoising = True
    return device


def _apply_resolution(scene: bpy.types.Scene, shot: str) -> None:
    """Reshape the frame for this shot, keeping the preset's pixel budget."""
    base_w, base_h = _BASE_RES
    aspect = SHOT_ASPECT.get(shot)
    if aspect is None:
        scene.render.resolution_x, scene.render.resolution_y = base_w, base_h
        return
    height = round(math.sqrt(base_w * base_h / aspect))
    scene.render.resolution_x = round(height * aspect)
    scene.render.resolution_y = height


def render(shot: str, suffix: str = "", subdir: str = "") -> str:
    """Render one named shot to out/. Returns the written path."""
    # Resolution first: activate() fits the ortho cameras to the frame aspect,
    # so changing the aspect afterwards would crop what it just fitted.
    _apply_resolution(bpy.context.scene, shot)
    cameras.activate(shot)
    directory = os.path.join(OUT_DIR, subdir) if subdir else OUT_DIR
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{shot}{suffix}.png")

    scene = bpy.context.scene
    scene.render.filepath = path
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    return path


def render_many(
    shots: tuple[str, ...] = BLOCKOUT_SHOTS, suffix: str = "", subdir: str = ""
) -> list[str]:
    return [render(s, suffix, subdir) for s in shots]

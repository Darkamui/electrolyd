"""
Lighting rig.

No HDRI is available offline, so this is a built three-point studio setup plus
a gradient world. Deliberately neutral: the job of these renders is to expose
geometry problems, not to flatter them. Warm/dramatic grading belongs in the
Phase 7 hero pass, after the model is correct.

Sizes scale off the datasheet so the rig stays proportionate to the cell.
"""

from __future__ import annotations

import math

import bpy

from lib.scene import BuildContext
from lib.units import mm


def _area(
    ctx: BuildContext,
    part: str,
    index: int,
    energy_w: float,
    size_m: float,
    location_m: tuple[float, float, float],
    rotation: tuple[float, float, float],
    color: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> bpy.types.Object:
    name = ctx.name(part, index)
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy_w
    data.size = size_m
    data.color = color
    obj = bpy.data.objects.new(name, data)
    obj.location = location_m
    obj.rotation_euler = rotation
    return ctx.link(obj)


def build_world(strength: float = 0.55) -> bpy.types.World:
    """
    Neutral gradient world. Provides ambient fill so unlit sides read as form
    rather than black holes - the failure visible in the Phase 0 smoke render.

    THREE stops, not two, and the lower one is not black. This was rewritten in
    Phase 5 and the reason is worth keeping, because the two-stop version was
    not wrong for what it was built for.

    A clay model is entirely diffuse: it needs fill and nothing else, and what
    the lower hemisphere contains is invisible. Once the cell is made of metal
    that stops being true. A `metallic = 1.0` surface does not have a colour of
    its own - it returns what is around it - so a world whose bottom stop is
    0.037 makes every downward-facing or downward-curving metal surface BLACK.
    In the first materialled hero the Ø900 gas duct, the jack screws and the
    breaker cylinders all read as holes cut in the image, and the materials
    were not at fault: there was simply nothing for them to reflect.

    So the ramp now runs floor bounce -> horizon -> sky. The bottom stop is a
    concrete potroom floor, which is what is actually under this cell, and the
    top is daylight through a roof vent. Metal now has somewhere to look.
    """
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    grad = nt.nodes.new("ShaderNodeTexGradient")
    mapping = nt.nodes.new("ShaderNodeMapping")
    tex_co = nt.nodes.new("ShaderNodeTexCoord")
    ramp = nt.nodes.new("ShaderNodeValToRGB")

    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.150, 0.146, 0.140, 1.0)  # floor
    ramp.color_ramp.elements[1].position = 0.52
    ramp.color_ramp.elements[1].color = (0.310, 0.330, 0.370, 1.0)  # horizon
    sky = ramp.color_ramp.elements.new(1.0)
    sky.color = (0.600, 0.660, 0.760, 1.0)                          # zenith

    mapping.inputs["Rotation"].default_value = (math.radians(90), 0.0, 0.0)
    bg.inputs["Strength"].default_value = strength

    nt.links.new(tex_co.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], grad.inputs["Vector"])
    nt.links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    bpy.context.scene.world = world
    return world


def build(ctx: BuildContext) -> list[bpy.types.Object]:
    """Three-point rig scaled to the cell."""
    cell = ctx.cell
    length = cell.shell_outer_x
    width = cell.shell_outer_y
    height = cell.hooding.end_box_top_z

    build_world()

    lights = [
        # Key: high, off the front-left corner.
        _area(
            ctx,
            "key",
            0,
            energy_w=3_200.0,
            size_m=mm(length * 0.55),
            location_m=(mm(length * 0.35), mm(-width * 2.2), mm(height * 2.6)),
            rotation=(math.radians(52), 0.0, math.radians(28)),
            color=(1.0, 0.97, 0.92),
        ),
        # Fill: opposite side, soft and cool, kills the black-side failure.
        _area(
            ctx,
            "fill",
            0,
            energy_w=1_300.0,
            size_m=mm(length * 0.8),
            location_m=(mm(-length * 0.3), mm(width * 2.4), mm(height * 1.6)),
            rotation=(math.radians(70), 0.0, math.radians(-150)),
            color=(0.88, 0.92, 1.0),
        ),
        # Rim: behind and high, separates the silhouette from the background.
        _area(
            ctx,
            "rim",
            0,
            energy_w=2_000.0,
            size_m=mm(width * 1.5),
            location_m=(mm(-length * 0.75), mm(width * 0.6), mm(height * 2.2)),
            rotation=(math.radians(58), 0.0, math.radians(-118)),
            color=(1.0, 0.95, 0.88),
        ),
    ]
    return lights

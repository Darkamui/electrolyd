"""
Blender API probe. Run BEFORE writing any build module.

    blender --background --python tools/smoke_test.py

Purpose: this project targets Blender 5.2.1, which postdates the assistant's
reliable bpy knowledge. Rather than guess at 4.x idioms and discover breakage
across eight modules, this script exercises every API the build depends on and
REPORTS what the installed build actually exposes.

Every probe is isolated. One failure never aborts the run, so a single
execution yields a complete capability report.

Known cross-version hazards this deliberately checks:
  * Principled BSDF socket names were renamed in 4.0
    ("Specular" -> "Specular IOR Level", "Emission" -> "Emission Color", ...)
  * mesh.use_auto_smooth was REMOVED in 4.1, replaced by a modifier/operator
  * Node group interfaces moved to node_tree.interface in 4.0
  * EEVEE was renamed BLENDER_EEVEE_NEXT in 4.2
  * glTF exporter keyword arguments drift between releases
"""

import sys
import traceback

import bpy

RESULTS: list[tuple[str, bool, str]] = []


def probe(label: str):
    """Decorator: run a probe, capture its outcome, never raise."""

    def wrap(fn):
        try:
            detail = fn()
            RESULTS.append((label, True, str(detail) if detail else "ok"))
        except Exception as exc:  # noqa: BLE001 - a probe must never abort the run
            tb = traceback.format_exc().strip().splitlines()[-1]
            RESULTS.append((label, False, f"{type(exc).__name__}: {exc} | {tb}"))
        return fn

    return wrap


def reset() -> None:
    """Wipe the scene to a known empty state."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


@probe("version")
def _version():
    return f"{bpy.app.version_string} (bpy {bpy.app.version})"


@probe("python")
def _python():
    return sys.version.split()[0]


@probe("render engines available")
def _engines():
    """
    NOTE: the static bl_rna enum lists only built-in engines. Cycles registers
    dynamically as an add-on, so it does NOT appear here even when available.
    Assignability is the real test - see the 'cycles available' probe.
    """
    prop = bpy.types.RenderSettings.bl_rna.properties["engine"]
    static = [e.identifier for e in prop.enum_items]
    registered = [
        getattr(c, "bl_idname", c.__name__)
        for c in bpy.types.RenderEngine.__subclasses__()
    ]
    return f"static={static} dynamically_registered={registered}"


@probe("cycles available (assignability test)")
def _cycles_available():
    reset()
    scene = bpy.context.scene
    try:
        scene.render.engine = "CYCLES"
    except TypeError as exc:
        raise RuntimeError(f"CYCLES not assignable: {exc}") from exc
    if scene.render.engine != "CYCLES":
        raise RuntimeError(f"engine did not stick, got {scene.render.engine}")
    has_cycles_props = hasattr(scene, "cycles")
    addon = "cycles" in bpy.context.preferences.addons
    return f"assigned=CYCLES scene.cycles={has_cycles_props} addon_enabled={addon}"


@probe("cycles GPU compute devices")
def _cycles_gpu():
    reset()
    bpy.context.scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons.get("cycles")
    if prefs is None:
        raise RuntimeError("cycles addon not in preferences")
    cprefs = prefs.preferences
    backends = []
    for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            cprefs.compute_device_type = backend
            devs = cprefs.get_devices_for_type(backend)
            if devs:
                backends.append(f"{backend}:{[d.name for d in devs]}")
        except (TypeError, AttributeError):
            continue
    return f"usable={backends or 'NONE - CPU only'}"


@probe("unit settings")
def _units():
    reset()
    u = bpy.context.scene.unit_settings
    u.system = "METRIC"
    u.length_unit = "METERS"
    u.scale_length = 1.0
    return f"system={u.system} length={u.length_unit} scale={u.scale_length}"


# ---------------------------------------------------------------------------
# Geometry creation
# ---------------------------------------------------------------------------


@probe("mesh from_pydata")
def _from_pydata():
    reset()
    me = bpy.data.meshes.new("probe_mesh")
    verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    faces = [(0, 1, 2, 3)]
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new("probe_obj", me)
    bpy.context.scene.collection.objects.link(ob)
    return f"verts={len(me.vertices)} polys={len(me.polygons)}"


@probe("bmesh box + transform")
def _bmesh():
    import bmesh
    from mathutils import Matrix

    reset()
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.transform(bm, matrix=Matrix.Scale(2.0, 4), verts=bm.verts)
    me = bpy.data.meshes.new("probe_bm")
    bm.to_mesh(me)
    bm.free()
    return f"verts={len(me.vertices)} polys={len(me.polygons)}"


@probe("collection create + link + nest")
def _collections():
    reset()
    parent = bpy.data.collections.new("01_SHELL")
    bpy.context.scene.collection.children.link(parent)
    child = bpy.data.collections.new("01_SHELL_sub")
    parent.children.link(child)
    me = bpy.data.meshes.new("m")
    ob = bpy.data.objects.new("01_SHELL_plate_000", me)
    child.objects.link(ob)
    return f"nested ok, obj in {ob.users_collection[0].name}"


@probe("linked duplicate shares mesh data")
def _linked_dupe():
    reset()
    me = bpy.data.meshes.new("shared")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0)], [], [(0, 1, 2)])
    me.update()
    obs = []
    for i in range(5):
        ob = bpy.data.objects.new(f"dupe_{i:03d}", me)
        bpy.context.scene.collection.objects.link(ob)
        obs.append(ob)
    shared = len({o.data.name for o in obs}) == 1
    return f"5 objects share 1 mesh: {shared} (users={me.users})"


# ---------------------------------------------------------------------------
# Modifiers
# ---------------------------------------------------------------------------


@probe("modifiers: bevel/solidify/mirror/array/boolean")
def _modifiers():
    reset()
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    ob = bpy.context.active_object
    out = []

    b = ob.modifiers.new("Bevel", "BEVEL")
    b.width = 0.02
    b.segments = 2
    b.limit_method = "ANGLE"
    b.angle_limit = 0.5236
    out.append("BEVEL")

    s = ob.modifiers.new("Solidify", "SOLIDIFY")
    s.thickness = 0.015
    s.offset = -1.0
    out.append("SOLIDIFY")

    m = ob.modifiers.new("Mirror", "MIRROR")
    m.use_axis = (True, True, False)
    out.append("MIRROR")

    a = ob.modifiers.new("Array", "ARRAY")
    a.count = 18
    a.use_relative_offset = False
    a.use_constant_offset = True
    a.constant_offset_displace[0] = 0.85
    out.append("ARRAY")

    bpy.ops.mesh.primitive_cube_add(size=1.0)
    cutter = bpy.context.active_object
    bo = ob.modifiers.new("Boolean", "BOOLEAN")
    bo.operation = "DIFFERENCE"
    bo.object = cutter
    bo.solver = "EXACT"
    out.append("BOOLEAN")

    return f"{len(ob.modifiers)} added: {', '.join(out)}"


@probe("smooth shading mechanism (auto_smooth removed in 4.1)")
def _smooth():
    reset()
    bpy.ops.mesh.primitive_cylinder_add(vertices=32)
    ob = bpy.context.active_object
    has_legacy = hasattr(ob.data, "use_auto_smooth")
    notes = [f"mesh.use_auto_smooth exists={has_legacy}"]
    bpy.ops.object.shade_smooth()
    notes.append("shade_smooth() ok")
    if hasattr(bpy.ops.object, "shade_auto_smooth"):
        bpy.ops.object.shade_auto_smooth(angle=0.5236)
        notes.append("shade_auto_smooth(angle=) ok -> USE THIS")
    else:
        notes.append("shade_auto_smooth MISSING")
    return "; ".join(notes)


# ---------------------------------------------------------------------------
# Drivers - the explosion rig depends entirely on these
# ---------------------------------------------------------------------------


@probe("custom property + UI range")
def _custom_prop():
    reset()
    empty = bpy.data.objects.new("CTRL_MASTER", None)
    bpy.context.scene.collection.objects.link(empty)
    empty["Explosion"] = 0.0
    ui = empty.id_properties_ui("Explosion")
    ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description="0=assembled")
    return f"value={empty['Explosion']} ui_configured=True"


@probe("driver: scripted expression reading a custom prop")
def _driver():
    reset()
    ctrl = bpy.data.objects.new("CTRL_MASTER", None)
    bpy.context.scene.collection.objects.link(ctrl)
    ctrl["Explosion"] = 1.0
    ctrl.id_properties_ui("Explosion").update(min=0.0, max=1.0)

    target = bpy.data.objects.new("EXPL_05_ANODES", None)
    bpy.context.scene.collection.objects.link(target)

    fc = target.driver_add("location", 2)  # Z
    drv = fc.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "expl"
    var.type = "SINGLE_PROP"
    var.targets[0].id = ctrl
    var.targets[0].data_path = '["Explosion"]'
    drv.expression = "expl * 4.2"

    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    z = target.evaluated_get(dg).location.z
    if abs(z - 4.2) > 1e-4:
        raise RuntimeError(f"driver did not evaluate: Z={z}")
    return f"driven Z={z:.4f} (expected 4.2) is_valid={drv.is_valid}"


# ---------------------------------------------------------------------------
# Materials - socket names are the classic breakage point
# ---------------------------------------------------------------------------


@probe("Principled BSDF socket names")
def _principled():
    reset()
    mat = bpy.data.materials.new("probe_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        raise RuntimeError("no node named 'Principled BSDF'")
    return [s.name for s in bsdf.inputs]


@probe("set common Principled inputs")
def _principled_set():
    reset()
    mat = bpy.data.materials.new("probe_mat2")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    applied = []
    for name, val in (
        ("Base Color", (0.5, 0.5, 0.5, 1.0)),
        ("Metallic", 1.0),
        ("Roughness", 0.4),
        ("IOR", 1.45),
    ):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = val
            applied.append(name)
    emissive = [n for n in bsdf.inputs.keys() if "Emission" in n]
    return f"set={applied} emission_sockets={emissive}"


# ---------------------------------------------------------------------------
# Camera and render
# ---------------------------------------------------------------------------


@probe("orthographic camera")
def _camera():
    reset()
    cam_data = bpy.data.cameras.new("CAM_ortho")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 20.0
    cam = bpy.data.objects.new("11_CAMERAS_ortho_front", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return f"type={cam_data.type} ortho_scale={cam_data.ortho_scale}"


@probe("EEVEE render to PNG")
def _render_eevee():
    import os

    reset()
    scene = bpy.context.scene
    engines = [
        e.identifier
        for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    ]
    eevee = next((e for e in engines if "EEVEE" in e), None)
    if not eevee:
        raise RuntimeError(f"no EEVEE engine in {engines}")
    scene.render.engine = eevee

    bpy.ops.mesh.primitive_cube_add(size=2.0)
    cam_data = bpy.data.cameras.new("c")
    cam = bpy.data.objects.new("c", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (6, -6, 4)
    cam.rotation_euler = (1.1, 0.0, 0.785)
    scene.camera = cam
    light_data = bpy.data.lights.new("l", type="SUN")
    light = bpy.data.objects.new("l", light_data)
    bpy.context.scene.collection.objects.link(light)

    out = os.path.join(os.path.dirname(__file__), "..", "out", "smoke_eevee.png")
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    scene.render.resolution_x = 320
    scene.render.resolution_y = 240
    scene.render.filepath = out
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    size = os.path.getsize(out) if os.path.exists(out) else 0
    return f"engine={eevee} wrote {size} bytes"


@probe("Cycles configurable")
def _cycles():
    reset()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    cy = scene.cycles
    cy.samples = 64
    cy.use_denoising = True
    return f"samples={cy.samples} denoise={cy.use_denoising} device={cy.device}"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@probe("glTF exporter present + accepted kwargs")
def _gltf():
    op = getattr(bpy.ops.export_scene, "gltf", None)
    if op is None:
        raise RuntimeError("bpy.ops.export_scene.gltf missing")
    props = op.get_rna_type().properties
    wanted = [
        "filepath",
        "export_format",
        "use_selection",
        "use_visible",
        "export_apply",
        "export_materials",
        "export_yup",
        "export_animations",
        "export_draco_mesh_compression_enable",
    ]
    present = [w for w in wanted if w in props]
    missing = [w for w in wanted if w not in props]
    return f"present={present} MISSING={missing}"


@probe("glTF actual export")
def _gltf_export():
    import os

    reset()
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    out = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "out", "smoke.glb")
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
    size = os.path.getsize(out) if os.path.exists(out) else 0
    return f"wrote {size} bytes"


@probe("save .blend")
def _save():
    import os

    out = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "out", "smoke.blend")
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    return f"wrote {os.path.getsize(out)} bytes"


# ---------------------------------------------------------------------------


def main() -> int:
    width = 46
    print("\n" + "=" * 78)
    print("  BLENDER API PROBE")
    print("=" * 78)
    failed = 0
    for label, ok, detail in RESULTS:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  [{mark}] {label:<{width}} {detail}")
    print("=" * 78)
    print(f"  {len(RESULTS) - failed}/{len(RESULTS)} passed")
    print("=" * 78 + "\n")
    return failed


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)

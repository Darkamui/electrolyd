"""
Exercise lib/ inside Blender. Run before delegating any module.

    blender --background --python tools/lib_test.py

Verifies that the helpers modules will be told to use actually work, and that
the guard rails actually refuse bad input. A library handed to a delegated task
without this is a library that fails eight times in eight modules.
"""

from __future__ import annotations

import os
import sys

# Blender does not put the script's project root on sys.path.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402

import spec  # noqa: E402
from lib import build as B  # noqa: E402
from lib.scene import new_context  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(label: str, fn) -> None:
    try:
        RESULTS.append((label, True, str(fn() or "ok")))
    except Exception as exc:  # noqa: BLE001
        RESULTS.append((label, False, f"{type(exc).__name__}: {exc}"))


def expect_raises(label: str, exc_type, fn) -> None:
    """A guard rail that does not fire is a guard rail that is not there."""
    try:
        fn()
    except exc_type as exc:
        RESULTS.append((label, True, f"correctly refused: {exc}"))
        return
    except Exception as exc:  # noqa: BLE001
        RESULTS.append((label, False, f"wrong exception {type(exc).__name__}: {exc}"))
        return
    RESULTS.append((label, False, "NO EXCEPTION - guard rail is missing"))


# ---------------------------------------------------------------------------

root = new_context()
cell = spec.CELL

check(
    "collection tree",
    lambda: f"{len(root.collections)} collections, "
    f"{len(bpy.context.scene.collection.children)} linked to scene",
)

shell = root.for_collection("01_SHELL")
check(
    "box at datasheet size",
    lambda: B.box(
        shell, "plate", 0, (cell.shell_outer_x, cell.shell_outer_y, 50)
    ).name,
)


def _box_on():
    o = B.box_on(shell, "plate", 1, (1000, 1000, 200), base_z_mm=cell.z_cathode_top)
    expected_centre = (cell.z_cathode_top + 100) * 0.001
    # float32 storage: Blender keeps transforms in single precision, so 0.830
    # reads back as 0.8299999833. Never assert tighter than ~1e-6 on a
    # transform. QA clearance checks must use the same tolerance.
    assert abs(o.location.z - expected_centre) < 1e-6, o.location.z
    return f"centre Z={o.location.z:.6f} m from base {cell.z_cathode_top} mm"


check("box_on sits on a datasheet height", _box_on)

check(
    "cylinder X/Y/Z",
    lambda: ", ".join(
        B.cylinder(shell, "stub", 10 + i, 180, 900, axis=ax).name[-14:]
        for i, ax in enumerate("XYZ")
    ),
)

# -- hood panel: the curved primitive ---------------------------------------

hood = root.for_collection("08_HOODING")
h = cell.hooding


def _arc():
    p = B.arc_panel(
        hood,
        "panel",
        0,
        radius_mm=cell.hood_radius,
        arc_deg=cell.hood_arc_deg,
        width_mm=h.panel_x(cell.shell_outer_x),
        segments=h.curve_segments,
    )
    B.solidify(p, h.panel_thickness)
    B.auto_smooth(p, 40)
    return f"{len(p.data.vertices)} verts, {len(p.data.polygons)} faces, {len(p.modifiers)} mods"


check("arc_panel + solidify + auto_smooth", _arc)

# -- ledge: loft, then subtract, proving the primitives compose -------------

refrac = root.for_collection("02_REFRACTORY")


def _ledge():
    """
    The ledge is (cavity block) MINUS (inward-tapering lofted solid).
    This is the composition the ledge module will use, so prove it here.
    """
    lg = cell.ledge
    hx, hy = cell.cavity_x / 2.0, cell.cavity_y / 2.0
    levels = [
        (cell.z_cathode_top, lg.intrusion_at_metal),
        (cell.z_metal_top, lg.intrusion_at_metal),
        ((cell.z_metal_top + cell.z_bath_top) / 2.0, lg.intrusion_at_bath_mid),
        (cell.z_bath_top, lg.intrusion_at_bath_top),
        (cell.z_crust_top, lg.intrusion_at_bath_top - lg.top_overhang),
    ]
    rings = [B.rect_ring(hx - inset, hy - inset, z) for z, inset in levels]
    inner = B.loft_rings(refrac, "ledge_core", 0, rings)

    outer = B.box_on(
        refrac,
        "ledge",
        0,
        (cell.cavity_x, cell.cavity_y, cell.z_crust_top - cell.z_cathode_top),
        base_z_mm=cell.z_cathode_top,
    )
    B.boolean(outer, inner, "DIFFERENCE")

    # link_faces is a bmesh attribute; bpy.types.MeshEdge has no such thing.
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(inner.data)
    manifold = all(len(e.link_faces) == 2 for e in bm.edges)
    bm.free()
    return (
        f"loft {len(inner.data.vertices)}v/{len(inner.data.polygons)}f "
        f"manifold={manifold}; boolean attached to {outer.name}"
    )


check("ledge = box - lofted taper", _ledge)

# -- repetition: the 36-anode budget strategy -------------------------------

anodes = root.for_collection("05_ANODES")


def _instancing():
    a = cell.anodes
    master = B.box(anodes, "block", 0, (a.block_x, a.block_y, a.block_z))
    positions = [(x, y, cell.z_anode_bottom + a.block_z / 2.0) for x, y in a.positions()]
    copies = B.instance_at(anodes, master, "block", positions[1:], start_index=1)
    meshes = {o.data.name for o in [master, *copies]}
    assert len(meshes) == 1, f"instancing broke: {len(meshes)} meshes"
    return (
        f"{len(copies) + 1} anodes share {len(meshes)} mesh "
        f"(users={master.data.users})"
    )


check("36 anodes share one mesh", _instancing)

check(
    "modifier helpers",
    lambda: ", ".join(
        m.type
        for m in [
            B.bevel(bpy.data.objects["01_SHELL_plate_000"], 8, 2),
            B.mirror(bpy.data.objects["01_SHELL_plate_000"], x=True, y=True),
            B.array(bpy.data.objects["08_HOODING_panel_000"], 5, (0, 0, 150)),
        ]
    ),
)

# -- guard rails ------------------------------------------------------------

expect_raises(
    "reject malformed part name",
    ValueError,
    lambda: shell.name("Bad Name With Spaces", 0),
)

expect_raises(
    "reject unknown collection",
    KeyError,
    lambda: root.for_collection("99_NOPE"),
)


def _cross_link():
    """An object named for one collection must not enter another."""
    obj = bpy.data.objects.new("01_SHELL_plate_900", bpy.data.meshes.new("x"))
    hood.link(obj)


expect_raises("reject cross-collection link", ValueError, _cross_link)


def _unscoped():
    from lib.scene import BuildContext

    BuildContext(collections=root.collections).name("plate", 0)


expect_raises("reject unscoped context", RuntimeError, _unscoped)

# -- does it render ---------------------------------------------------------


def _render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    cam_data = bpy.data.cameras.new("c")
    cam = bpy.data.objects.new("c", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (mm_(24000), mm_(-20000), mm_(12000))
    cam.rotation_euler = (1.15, 0.0, 0.87)
    scene.camera = cam
    sun = bpy.data.objects.new("s", bpy.data.lights.new("s", type="SUN"))
    scene.collection.objects.link(sun)
    sun.rotation_euler = (0.6, 0.2, 0.8)

    out = os.path.join(ROOT, "out", "lib_test.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    scene.render.resolution_x, scene.render.resolution_y = 800, 450
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    return f"wrote {os.path.getsize(out)} bytes"


def mm_(v):
    return v * 0.001


check("render the exercised scene", _render)

# ---------------------------------------------------------------------------

print("\n" + "=" * 78)
print("  LIB EXERCISE")
print("=" * 78)
failed = sum(1 for _, ok, _ in RESULTS if not ok)
for label, ok, detail in RESULTS:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label:<34} {detail}")
print("=" * 78)
print(f"  {len(RESULTS) - failed}/{len(RESULTS)} passed")
print("=" * 78 + "\n")
sys.exit(1 if failed else 0)

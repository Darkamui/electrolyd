"""
Automated model validation.

    blender --background --python qa/validate.py
    blender --background --python qa/validate.py -- --phase blockout

Every check is independent and reports rather than aborts, so one failure never
hides the rest — the same isolation pattern as tools/smoke_test.py. Findings are
ranked CRITICAL / MAJOR / MINOR, which is the order they should be fixed in.

TOLERANCE: Blender stores object transforms in float32, so a box placed at
830 mm reads back as 0.8299999833106995. Every positional assertion here uses
TOL = 1e-6 m (0.001 mm) — four orders of magnitude finer than any dimension in
the datasheet, and the tightest bound that does not produce permanent false
failures. See tools/API_NOTES.md #5.
"""

from __future__ import annotations

import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import spec  # noqa: E402
from lib.scene import NAME_RE, owning_collection  # noqa: E402

TOL = 1e-6
"""Metres. Governs every clearance assertion. Do not tighten."""

CRITICAL, MAJOR, MINOR = "CRITICAL", "MAJOR", "MINOR"
_RANK = {CRITICAL: 0, MAJOR: 1, MINOR: 2}

_findings: list[tuple[str, str, str]] = []
_checks_run: list[str] = []


def finding(severity: str, check: str, message: str) -> None:
    _findings.append((severity, check, message))


def check(label: str):
    """Run a check in isolation; an exception inside it is itself a finding."""

    def decorate(fn):
        def wrapped(*args, **kwargs):
            _checks_run.append(label)
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                finding(CRITICAL, label, f"check itself raised {type(exc).__name__}: {exc}")
                return None

        return wrapped

    return decorate


# ---------------------------------------------------------------------------
# hygiene
# ---------------------------------------------------------------------------


def _tree_objects() -> list[bpy.types.Object]:
    out: list[bpy.types.Object] = []
    for name in spec.COLLECTIONS:
        coll = bpy.data.collections.get(name)
        if coll:
            out.extend(coll.objects)
    return out


@check("naming")
def check_naming() -> None:
    for obj in _tree_objects():
        if not NAME_RE.match(obj.name):
            finding(MAJOR, "naming", f"{obj.name!r} does not match the convention")
        if ".00" in obj.name:
            finding(MAJOR, "naming", f"{obj.name!r} looks like Blender duplicate leakage")


@check("transforms")
def check_transforms() -> None:
    for obj in _tree_objects():
        for axis, value in zip("xyz", obj.location):
            if math.isnan(value) or math.isinf(value):
                finding(CRITICAL, "transforms", f"{obj.name} location.{axis} is {value}")
        for axis, value in zip("xyz", obj.scale):
            if abs(value - 1.0) > 1e-4:
                finding(
                    MINOR,
                    "transforms",
                    f"{obj.name} has non-unit scale.{axis}={value:.4f}; "
                    "bake it into the mesh so modifiers behave",
                )


@check("orphans")
def check_orphans() -> None:
    in_tree = {o.name for o in _tree_objects()}
    for obj in bpy.data.objects:
        if obj.name not in in_tree:
            finding(MAJOR, "orphans", f"{obj.name} is outside the collection tree")
    for mesh in bpy.data.meshes:
        if mesh.users == 0:
            finding(MINOR, "orphans", f"mesh datablock {mesh.name} has no users")


@check("mesh_sharing")
def check_mesh_sharing() -> None:
    """Repeated parts must share one datablock. This is the WebGL budget."""
    expectations = (
        ("05_ANODES", "block", spec.CELL.anodes.count),
        ("03_CATHODE", "block", spec.CELL.cathode.block_count),
        ("01_SHELL", "cradle", spec.CELL.shell.cradle_pairs * 2),
        (
            "01_SHELL",
            "end_cradle",
            len(spec.CELL.end_cradle_positions_y()) * 2,
        ),
    )
    for coll_name, part, expected_count in expectations:
        coll = bpy.data.collections.get(coll_name)
        if not coll:
            continue
        # Exact part match, not a substring: the naming convention is
        # {NN}_{SUBSYSTEM}_{part}_{index}, so "_cradle_" also matches
        # "_end_cradle_" and the side cradles counted 36 against an expected 28.
        # Splitting the index off makes the comparison say what it means.
        prefix = f"{coll_name}_{part}"
        objs = [o for o in coll.objects if o.name.rsplit("_", 1)[0] == prefix]
        if not objs:
            continue
        if len(objs) != expected_count:
            finding(
                MAJOR,
                "mesh_sharing",
                f"{coll_name}/{part}: {len(objs)} objects, expected {expected_count}",
            )
        datablocks = {o.data.name for o in objs if o.data}
        if len(datablocks) > 1:
            finding(
                MAJOR,
                "mesh_sharing",
                f"{coll_name}/{part}: {len(objs)} objects use {len(datablocks)} "
                "mesh datablocks; they must share exactly 1",
            )


@check("manifold")
def check_manifold() -> None:
    """
    Structural meshes should be closed.

    Checked on the EVALUATED mesh, not obj.data. Several parts are authored as
    open surfaces that a modifier closes: a hood panel is a bare arc until
    SOLIDIFY gives it a wall, and the crust is a slab until BOOLEAN perforates
    it. Reading the pre-modifier mesh reported 56 false non-manifold findings on
    the hooding alone, which is worse than no check at all — it trains you to
    ignore the category. What matters is whether the thing that renders is
    closed.
    """
    dg = bpy.context.evaluated_depsgraph_get()
    for obj in _tree_objects():
        if obj.type != "MESH" or not obj.data.polygons:
            continue
        evaluated = obj.evaluated_get(dg)
        me = evaluated.to_mesh()
        if me is None or not me.polygons:
            evaluated.to_mesh_clear()
            continue
        bm = bmesh.new()
        bm.from_mesh(me)
        open_edges = [e for e in bm.edges if len(e.link_faces) != 2]
        bm.free()
        evaluated.to_mesh_clear()
        if open_edges:
            finding(
                MINOR,
                "manifold",
                f"{obj.name} has {len(open_edges)} non-manifold edges "
                "after modifiers",
            )


# ---------------------------------------------------------------------------
# clearances read straight off the datasheet
# ---------------------------------------------------------------------------


def _world_bounds(obj: bpy.types.Object) -> tuple[list[float], list[float]]:
    """
    World-space min/max corner, in metres.

    Uses the object's own bound_box, which is PRE-modifier. Every clearance
    checked here is on unmodified primitives, so that is correct and cheap;
    a booleaned part would need depsgraph evaluation instead.
    """
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = [min(c[i] for c in corners) for i in range(3)]
    hi = [max(c[i] for c in corners) for i in range(3)]
    return lo, hi


def _mesh_bounds(obj: bpy.types.Object) -> tuple[list[float], list[float]]:
    """
    World-space min/max of the AUTHORED vertices, ignoring modifiers.

    Object.bound_box is depsgraph-evaluated, so it silently includes SOLIDIFY.
    For a hood panel that matters: the authored arc is the panel's OUTER face,
    which is the surface that lands on the shell rim, while the solidified
    inner face's cut corner hangs ~2 mm below it. Measuring the evaluated box
    reports that overhang as a missed anchor.
    """
    mw = obj.matrix_world
    corners = [mw @ v.co for v in obj.data.vertices]
    lo = [min(c[i] for c in corners) for i in range(3)]
    hi = [max(c[i] for c in corners) for i in range(3)]
    return lo, hi


def _find(name: str) -> bpy.types.Object | None:
    return bpy.data.objects.get(name)


@check("datasheet_consistency")
def check_datasheet() -> None:
    """The spec must agree with itself before geometry is even worth checking."""
    cell = spec.CELL
    if cell.anode_immersion <= 0:
        finding(CRITICAL, "datasheet_consistency",
                f"anode immersion is {cell.anode_immersion} mm; anodes are not in the bath")
    if cell.freeboard <= 0:
        finding(CRITICAL, "datasheet_consistency",
                f"freeboard is {cell.freeboard} mm; the process stack overtops the shell")
    if cell.cathode_end_gap <= 0:
        finding(CRITICAL, "datasheet_consistency",
                f"cathode end gap is {cell.cathode_end_gap} mm; blocks overrun the cavity")
    if cell.cathode_side_gap <= 0:
        finding(CRITICAL, "datasheet_consistency",
                f"cathode side gap is {cell.cathode_side_gap} mm")
    panel_x = cell.hooding.panel_x(cell.shell_outer_x)
    if panel_x <= 0:
        finding(CRITICAL, "datasheet_consistency",
                f"derived hood panel width is {panel_x} mm; end boxes overrun the shell")


@check("acd")
def check_acd() -> None:
    """The 45 mm anode-cathode distance is the defining dimension of the cell."""
    cell = spec.CELL
    anode = _find("05_ANODES_block_000")
    metal = _find("04_PROCESS_metal_000")
    if anode is None or metal is None:
        return
    anode_lo, _ = _world_bounds(anode)
    _, metal_hi = _world_bounds(metal)
    gap_mm = (anode_lo[2] - metal_hi[2]) * 1000.0
    if abs(gap_mm - cell.process.acd) > TOL * 1000.0:
        finding(
            CRITICAL,
            "acd",
            f"ACD measures {gap_mm:.4f} mm, datasheet says {cell.process.acd} mm",
        )


@check("anode_ledge_clearance")
def check_anode_ledge() -> None:
    """Anodes must not be buried in the frozen ledge."""
    cell = spec.CELL
    ledge_inner_y = cell.cavity_y / 2.0 - cell.ledge.intrusion_at_bath_top
    anode_outer_y = cell.anodes.row_centre_y + cell.anodes.block_y / 2.0
    if anode_outer_y > ledge_inner_y:
        finding(
            CRITICAL,
            "anode_ledge_clearance",
            f"anode row reaches |y|={anode_outer_y:.1f} mm but the ledge inner "
            f"face is at {ledge_inner_y:.1f} mm; they interpenetrate",
        )


@check("collector_bar_reach")
def check_collector_bars() -> None:
    cell = spec.CELL
    expected_tip = cell.shell_outer_y / 2.0 + cell.cathode.bar_protrusion
    bar = _find("03_CATHODE_bar_000")
    if bar is None:
        return
    _, hi = _world_bounds(bar)
    tip_mm = hi[1] * 1000.0
    if abs(tip_mm - expected_tip) > TOL * 1000.0:
        finding(
            MAJOR,
            "collector_bar_reach",
            f"collector bar tip at {tip_mm:.3f} mm, expected {expected_tip:.3f} mm",
        )


@check("hood_anchors")
def check_hood_anchors() -> None:
    """
    A hood panel must touch BOTH the things it spans between: the anode beam
    above and the shell's top outer edge below. Its radius is derived from
    exactly that span, so if either anchor misses, the derivation or the
    placement is wrong and the panel is a floating shape rather than a hood.

    Measured on the authored arc, which IS the panel's outer face — see
    _mesh_bounds. The crest allows for chord sag, because a 24-segment polyline
    inscribed in the arc always falls slightly inside it; that is tessellation,
    not misplacement.
    """
    cell = spec.CELL
    panel = _find("08_HOODING_panel_000")
    if panel is None:
        return
    lo, hi = _mesh_bounds(panel)

    h = cell.hooding
    sag = cell.hood_radius * (
        1.0 - math.cos(math.radians(cell.hood_arc_deg / h.curve_segments / 2.0))
    )

    landing_y = hi[1] * 1000.0
    if abs(landing_y - cell.shell_outer_y / 2.0) > TOL * 1000.0:
        finding(
            CRITICAL,
            "hood_anchors",
            f"panel reaches |y|={landing_y:.3f} mm but the shell edge is at "
            f"{cell.shell_outer_y / 2.0:.3f} mm; it misses its landing",
        )

    landing_z = lo[2] * 1000.0
    if abs(landing_z - cell.shell_outer_z) > TOL * 1000.0:
        finding(
            CRITICAL,
            "hood_anchors",
            f"panel bottoms out at z={landing_z:.3f} mm, shell rim is at "
            f"{cell.shell_outer_z:.3f} mm",
        )

    crest_z = hi[2] * 1000.0
    if not (cell.hood_apex_z - sag <= crest_z <= cell.hood_apex_z + TOL * 1000.0):
        finding(
            MAJOR,
            "hood_anchors",
            f"panel crest {crest_z:.3f} mm, derived apex "
            f"{cell.hood_apex_z:.3f} mm (sag allowance {sag:.3f} mm)",
        )
    if crest_z > cell.z_cross_base:
        finding(
            CRITICAL,
            "hood_anchors",
            f"panel crest {crest_z:.1f} mm fouls the portal tie at "
            f"{cell.z_cross_base:.1f} mm",
        )


@check("superstructure_clearance")
def check_superstructure() -> None:
    """
    The portal frame must pass OVER the rodding and stand OUTSIDE the hood.
    Both were live collisions before the frame heights were derived, so both
    are worth asserting on the built geometry and not just in the datasheet.
    """
    cell = spec.CELL
    cross = _find("07_SUPERSTRUCTURE_cross_000")
    stem = _find("05_ANODES_stem_000")
    if cross is not None and stem is not None:
        tie_base = _world_bounds(cross)[0][2] * 1000.0
        stem_top = _world_bounds(stem)[1][2] * 1000.0
        if tie_base < stem_top - TOL * 1000.0:
            finding(
                CRITICAL,
                "superstructure_clearance",
                f"portal tie starts at {tie_base:.1f} mm, below the stem tops "
                f"at {stem_top:.1f} mm; they interpenetrate",
            )

    column = _find("07_SUPERSTRUCTURE_column_000")
    if column is not None:
        lo, hi = _world_bounds(column)
        inner_y = min(abs(lo[1]), abs(hi[1])) * 1000.0
        if inner_y < cell.shell_outer_y / 2.0 - TOL * 1000.0:
            finding(
                CRITICAL,
                "superstructure_clearance",
                f"column inner face at |y|={inner_y:.1f} mm is inside the shell "
                f"edge at {cell.shell_outer_y / 2.0:.1f} mm; it grows through "
                "the hood",
            )

    # The feeder must have a clear shaft all the way down the open centreline.
    chute = _find("07_SUPERSTRUCTURE_chute_000")
    if chute is not None:
        half_w = cell.feeder.chute_diameter / 2.0
        if half_w > cell.cross_inner_y:
            finding(
                CRITICAL,
                "superstructure_clearance",
                f"chute half-width {half_w:.1f} mm exceeds the tie opening "
                f"{cell.cross_inner_y:.1f} mm",
            )


@check("materials")
def check_materials() -> None:
    """Every visible mesh carries exactly one material.

    A boolean cutter is exempt and must STAY exempt: a cutter carrying a
    material hands that material to the faces it cuts, so painting one is a
    defect in the opposite direction.
    """
    from lib import materials as matlib

    bare: list[str] = []
    multi: list[str] = []
    painted_cutters: list[str] = []
    seen: set[str] = set()

    for obj in _tree_objects():
        if obj.type != "MESH" or obj.data is None:
            continue
        slots = [s for s in obj.data.materials if s is not None]
        if matlib.family(obj) in matlib.UNPAINTED:
            if slots and obj.data.name not in seen:
                painted_cutters.append(obj.name)
            continue
        if obj.data.name in seen:
            continue
        seen.add(obj.data.name)
        if not slots:
            bare.append(obj.name)
        elif len(slots) > 1:
            multi.append(f"{obj.name} ({len(slots)})")

    if bare:
        finding(
            MAJOR, "materials",
            f"{len(bare)} mesh datablock(s) carry no material: "
            + ", ".join(sorted(bare)[:6]),
        )
    if multi:
        finding(
            MINOR, "materials",
            "more than one material slot: " + ", ".join(sorted(multi)[:6]),
        )
    if painted_cutters:
        finding(
            MAJOR, "materials",
            "boolean cutter carries a material, which it will hand to the "
            "faces it cuts: " + ", ".join(sorted(painted_cutters)[:6]),
        )
    print(
        f"   materials: {len(bpy.data.materials)} in file, "
        f"{len(seen)} mesh datablocks painted"
    )


@check("explosion")
def check_explosion() -> None:
    """
    Every movable object is on the rig, the rig moves it, and it is home.

    Three distinct failures, all silent in a render:

    * A part with no rig parent stays behind while its subsystem leaves. In a
      3/4 hero that reads as an artistic choice rather than a bug.
    * A driver that failed to build, or went stale, leaves its group assembled
      and nothing says so.
    * A non-zero Explosion at QA time invalidates every clearance check in this
      file — the ACD would be measured on a cell that has been pulled apart.
      This check runs first among the three so the others' results can be
      trusted.
    """
    from lib import explode

    ctrl = explode.master()
    if ctrl is None:
        finding(MAJOR, "explosion", "no explosion rig: " + explode.MASTER)
        return

    value = float(ctrl[explode.PROP])
    if abs(value) > 1e-6:
        finding(
            MAJOR, "explosion",
            f"Explosion is {value:.2f}, not 0; every clearance check in this "
            f"file measured a model that is pulled apart",
        )

    rig = {o.name for o in bpy.data.collections["10_EXPLOSION"].objects}
    orphans: list[str] = []
    for obj in _tree_objects():
        if obj.type != "MESH" or obj.name in rig:
            continue
        coll = owning_collection(obj.name)
        if coll not in spec.EXPLOSION_VECTORS:
            continue
        # A parented child travels with its parent; only roots need the rig.
        root = obj
        while root.parent is not None:
            root = root.parent
        if root.name not in rig:
            orphans.append(obj.name)

    if orphans:
        finding(
            MAJOR, "explosion",
            f"{len(orphans)} objects are not on the rig and will stay behind: "
            + ", ".join(sorted(orphans)[:6]),
        )

    # Drivers are the whole mechanism; a stale one is a group that does not move.
    dead = [
        f"{o.name}[{fc.array_index}]"
        for o in bpy.data.collections["10_EXPLOSION"].objects
        if o.animation_data
        for fc in o.animation_data.drivers
        if not fc.driver.is_valid
    ]
    if dead:
        finding(MAJOR, "explosion", "invalid drivers: " + ", ".join(dead[:6]))

    driven = sum(
        len(o.animation_data.drivers)
        for o in bpy.data.collections["10_EXPLOSION"].objects
        if o.animation_data
    )
    print(
        f"   explosion: {len(rig) - 1} groups, {driven} drivers, "
        f"Explosion={value:.2f}"
    )


@check("triangle_budget")
def check_budget() -> None:
    """
    Count what actually ships, which is the EVALUATED mesh.

    This check used to fan out `obj.data.polygons` — the authored cage, before
    the booleans, bevels, solidifies and arrays that make the model what it is.
    That undercounts by more than half: 64 388 authored against 140 556 in the
    exported GLB, because `export/glb.py` applies modifiers and the browser gets
    the result. A budget check that measures something other than the delivered
    file is a budget check that can pass while the delivery fails. Both numbers
    are printed, since the gap between them is the cost of the modifier stack
    and worth watching.
    """
    dg = bpy.context.evaluated_depsgraph_get()
    authored = evaluated = 0
    for obj in _tree_objects():
        if obj.type != "MESH":
            continue
        authored += sum(max(len(p.vertices) - 2, 0) for p in obj.data.polygons)
        if obj.hide_render:
            continue          # cutters; `use_visible=True` drops them too
        mesh = obj.evaluated_get(dg).data
        evaluated += sum(max(len(p.vertices) - 2, 0) for p in mesh.polygons)
    budget = spec.GLB_TRIANGLE_BUDGET
    if evaluated > budget:
        finding(
            MINOR,
            "triangle_budget",
            f"{evaluated} triangles against a {budget} budget; "
            f"the GLB path must decimate",
        )
    print(f"   triangles: {evaluated} evaluated (what the GLB carries) / "
          f"{budget} budget; {authored} authored")


# ---------------------------------------------------------------------------


def run() -> int:
    _findings.clear()
    _checks_run.clear()

    # Objects built this session have a stale matrix_world until the depsgraph
    # is evaluated, so bound_box corners come back in LOCAL space and every
    # clearance silently measures the wrong thing. Without this line the ACD
    # check reports -400 mm instead of 45 mm.
    bpy.context.view_layer.update()

    check_datasheet()
    check_naming()
    check_transforms()
    check_orphans()
    check_mesh_sharing()
    check_manifold()
    check_acd()
    check_anode_ledge()
    check_collector_bars()
    check_hood_anchors()
    check_superstructure()
    check_materials()
    check_explosion()
    check_budget()

    print("\n" + "=" * 78)
    print("  QA REPORT")
    print("=" * 78)
    print(f"   checks run: {len(_checks_run)}   objects in tree: {len(_tree_objects())}")

    if not _findings:
        print("   no defects found.")
        print("=" * 78 + "\n")
        return 0

    _findings.sort(key=lambda f: _RANK[f[0]])
    for severity, name, message in _findings:
        print(f"  [{severity:<8}] {name:<24} {message}")

    counts = {s: sum(1 for f in _findings if f[0] == s) for s in (CRITICAL, MAJOR, MINOR)}
    print("-" * 78)
    print(f"   {counts[CRITICAL]} critical, {counts[MAJOR]} major, {counts[MINOR]} minor")
    print("=" * 78 + "\n")
    return counts[CRITICAL]


if __name__ == "__main__":
    import build_all

    only = None
    argv = sys.argv
    if "--" in argv:
        rest = argv[argv.index("--") + 1:]
        if "--only" in rest:
            only = [rest[rest.index("--only") + 1]]
    build_all.build(only, strict=False)
    sys.exit(min(run(), 1))

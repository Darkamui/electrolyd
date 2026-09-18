"""
Orchestrator. The single entry point for building, rendering and exporting.

    blender --background --python build_all.py
    blender --background --python build_all.py -- --render all
    blender --background --python build_all.py -- --only m01_shell --render ortho_front
    blender --background --python build_all.py -- --hero --render hero
    blender --background --python build_all.py -- --save

Arguments after the bare `--` are ours; everything before belongs to Blender.

The build is deterministic and always runs from an empty scene, so any run
reproduces the whole model from the datasheet alone.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
import time
import traceback

ROOT = os.path.abspath(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402

import spec  # noqa: E402
from lib import explode, materials, section  # noqa: E402
from lib.scene import new_context  # noqa: E402
from render import anim, cameras, lighting, shots  # noqa: E402

# Module -> the one collection it owns. Strictly 1:1; a module that needs to
# touch two collections is a module that should be split.
REGISTRY: tuple[tuple[str, str], ...] = (
    ("modules.m01_shell", "01_SHELL"),
    ("modules.m02_refractory", "02_REFRACTORY"),
    ("modules.m03_cathode", "03_CATHODE"),
    ("modules.m04_process", "04_PROCESS"),
    ("modules.m05_anodes", "05_ANODES"),
    ("modules.m06_busbars", "06_BUSBARS"),
    ("modules.m07_superstructure", "07_SUPERSTRUCTURE"),
    ("modules.m08_hooding", "08_HOODING"),
    ("modules.m09_hardware", "09_HARDWARE"),
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    args = argv[argv.index("--") + 1 :] if "--" in argv else []
    p = argparse.ArgumentParser(prog="build_all")
    p.add_argument("--only", action="append", default=None,
                   help="build only these modules, e.g. --only m01_shell")
    p.add_argument("--render", default=None,
                   help="'all', 'blockout', 'materials', 'exploded', "
                        "or a shot name (comma-separated; groups expand)")
    p.add_argument("--hero", action="store_true",
                   help="Cycles GPU instead of EEVEE preview")
    p.add_argument("--samples", type=int, default=256)
    p.add_argument("--suffix", default="")
    p.add_argument("--subdir", default="")
    p.add_argument("--save", action="store_true", help="write out/cell.blend")
    p.add_argument("--section", action="store_true",
                   help="apply the transverse cutaway to every rendered shot")
    p.add_argument("--clay", action="store_true",
                   help="skip the material pass; leave the model unpainted")
    p.add_argument("--explode", default=None,
                   help="explosion factor 0..1, or a comma series such as "
                        "0,0.25,0.5,1 to render every shot once per value")
    p.add_argument("--anim", default=None,
                   help="'all', 'turntable' or 'explosion' (comma-separated); "
                        "renders MP4 rather than stills")
    p.add_argument("--anim-frames", type=int, default=None,
                   help="override each sequence's own frame count")
    p.add_argument("--anim-aspect", default="4:3",
                   choices=("4:3", "16:9", "1:1"),
                   help="delivery frame shape for --anim (default 4:3; see "
                        "shots.use_motion for the measurements behind it)")
    p.add_argument("--strict", action="store_true",
                   help="fail the run if any module is missing or errors")
    return p.parse_args(args)


def build(
    only: list[str] | None, strict: bool, clay: bool = False
) -> tuple[object, dict]:
    """Build the model. `clay` skips the material pass.

    `clay` is defaulted because export/glb.py and the probe scripts call this
    positionally with two arguments.
    """
    root = new_context()
    report: dict[str, str] = {}

    for mod_name, coll in REGISTRY:
        short = mod_name.split(".")[-1]
        if only and short not in only:
            continue

        try:
            module = importlib.import_module(mod_name)
            importlib.reload(module)
        except ModuleNotFoundError:
            report[short] = "not written yet"
            if strict:
                raise
            continue
        except Exception as exc:  # noqa: BLE001
            report[short] = f"IMPORT FAILED: {type(exc).__name__}: {exc}"
            traceback.print_exc()
            if strict:
                raise
            continue

        t0 = time.perf_counter()
        try:
            ctx = root.for_collection(coll)
            module.build(ctx)
            dt = time.perf_counter() - t0
            tris = sum(
                len(o.data.polygons) for o in ctx.created if getattr(o, "data", None)
                and hasattr(o.data, "polygons")
            )
            report[short] = f"{len(ctx.created)} objects, {tris} faces, {dt:.2f}s"
        except Exception as exc:  # noqa: BLE001
            report[short] = f"BUILD FAILED: {type(exc).__name__}: {exc}"
            traceback.print_exc()
            if strict:
                raise

    # Materials run once, over whatever got built, rather than inside each
    # module: a module knows what it built, not what the cell is made of.
    if clay:
        report["materials"] = "skipped (--clay)"
    else:
        t0 = time.perf_counter()
        try:
            counts = materials.apply(strict=strict)
            used = sum(1 for n in counts.values() if n)
            report["materials"] = (
                f"{len(counts)} materials ({used} used), "
                f"{sum(counts.values())} objects painted, "
                f"{time.perf_counter() - t0:.2f}s"
            )
        except Exception as exc:  # noqa: BLE001
            report["materials"] = f"BUILD FAILED: {type(exc).__name__}: {exc}"
            traceback.print_exc()
            if strict:
                raise

    # The rig parents what the modules built, so it can only run once they all
    # have. It leaves the model where it stands: at Explosion 0 nothing moves,
    # which is what lets QA and the section cut measure the real cell.
    t0 = time.perf_counter()
    try:
        rig = explode.build(root.for_collection("10_EXPLOSION"))
        parented = sum(
            1 for c in bpy.data.collections
            if c.name in spec.COLLECTIONS
            for o in c.objects if o.parent is not None
        )
        report["explosion"] = (
            f"{len(rig)} empties, {parented} objects parented, "
            f"{time.perf_counter() - t0:.2f}s"
        )
    except Exception as exc:  # noqa: BLE001
        report["explosion"] = f"BUILD FAILED: {type(exc).__name__}: {exc}"
        traceback.print_exc()
        if strict:
            raise

    # Scene furniture always builds, so a partial model is still renderable.
    cameras.build(root.for_collection("11_CAMERAS"))
    lighting.build(root.for_collection("12_LIGHTING"))
    return root, report


def main() -> int:
    args = parse_args(sys.argv)
    root, report = build(args.only, args.strict, args.clay)

    print("\n" + "=" * 78)
    print("  BUILD REPORT")
    print("=" * 78)
    for mod, status in report.items():
        flag = "  " if "FAILED" not in status else "!!"
        print(f"{flag} {mod:<24} {status}")

    total_objs = sum(
        len(c.objects) for c in bpy.data.collections if c.name in spec.COLLECTIONS
    )
    print("-" * 78)
    print(f"   total objects in tree: {total_objs}")
    print(f"   mesh datablocks:       {len(bpy.data.meshes)}")

    if args.render:
        device = "EEVEE"
        if args.hero:
            device = shots.use_hero(samples=args.samples)
        else:
            shots.use_preview()

        # Group names expand in place, so they compose with individual shots in
        # one comma list. Without this, `--render materials,hero` asked for a
        # camera literally called "materials" and the run died at the first
        # shot; a group name only worked when it stood alone.
        groups = {
            "all": shots.ALL_SHOTS,
            "blockout": shots.BLOCKOUT_SHOTS,
            "materials": shots.MATERIAL_SHOTS,
            "exploded": shots.EXPLODED_SHOTS,
        }
        seen: list[str] = []
        for token in args.render.split(","):
            for shot in groups.get(token, (token,)):
                if shot not in seen:
                    seen.append(shot)
        targets = tuple(seen)

        # One value or a series. A series renders the whole shot list once per
        # value and stamps the factor into the filename, so a contact sheet
        # sorts into explosion order on its own.
        steps = (
            [float(v) for v in args.explode.split(",")]
            if args.explode else [None]
        )

        print("-" * 78)
        print(f"   rendering {len(targets)} shot(s) x {len(steps)} step(s) "
              f"with {device}")
        for step in steps:
            suffix = args.suffix
            if step is not None:
                actual = explode.set_explosion(step)
                suffix = f"{args.suffix}_x{int(round(actual * 100)):03d}"
                print(f"   explosion = {actual:.2f}")
            _render_shots(root, targets, args, suffix)

    if args.anim:
        # --hero means Cycles, but the sequence preset rather than the plate
        # preset: 1080p at 64 samples, not 1440p at 256. --samples still wins
        # if it was given explicitly.
        if args.hero:
            # Height is held at 1080 and the width follows the aspect, so the
            # choice changes the shape of the frame and not its class. H.264
            # refuses odd dimensions; every width here is even.
            width = {"4:3": 1440, "16:9": 1920, "1:1": 1080}[args.anim_aspect]
            device = shots.use_motion(
                resolution=(width, 1080),
                samples=args.samples if args.samples != 256 else 64,
            )
        else:
            device = "EEVEE"
            shots.use_preview()
        names = (
            tuple(anim.SEQUENCES) if args.anim == "all"
            else tuple(args.anim.split(","))
        )
        print("-" * 78)
        for name in names:
            sequence = anim.SEQUENCES.get(name)
            if sequence is None:
                print(f"!! unknown sequence {name!r}; "
                      f"have {', '.join(anim.SEQUENCES)}")
                continue
            kwargs = {"subdir": args.subdir}
            if args.anim_frames:
                kwargs["frames"] = args.anim_frames
            t0 = time.perf_counter()
            path = sequence(**kwargs)
            size = os.path.getsize(path) if os.path.exists(path) else 0
            print(f"   {name} [{device}]  {os.path.relpath(path, ROOT)}  "
                  f"({size // 1024} KB, {time.perf_counter() - t0:.1f}s)")

    if args.save:
        out = os.path.join(ROOT, "out", "cell.blend")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=out)
        print(f"   saved {os.path.relpath(out, ROOT)}")

    print("=" * 78 + "\n")
    return sum(1 for s in report.values() if "FAILED" in s)


def _render_shots(root, targets: tuple[str, ...], args, suffix: str) -> None:
    """Render every target shot once, applying the cutaway where it belongs."""
    for shot in targets:
        # Only the shots that look inside a sealed pot need the cutaway, and it
        # is switched off again afterwards so the following plates show the
        # whole cell. --section forces it on for every shot.
        cut = args.section or shot in shots.SECTIONED_SHOTS
        if cut:
            tally = section.enable(root)
            print(
                f"   section cut at x={section.cut_plane_x(root.cell):.0f} mm: "
                f"{tally['cut']} cut, {tally['hidden']} hidden, "
                f"{tally['kept']} kept"
            )
        path = shots.render(shot, suffix, args.subdir)
        if cut:
            section.disable()
        size = os.path.getsize(path) if os.path.exists(path) else 0
        print(f"   {os.path.relpath(path, ROOT)}  ({size // 1024} KB)")


if __name__ == "__main__":
    sys.exit(min(main(), 1))

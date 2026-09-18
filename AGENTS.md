# Orientation for the next agent

Read this before touching anything. It exists because most of what will bite you
in this repository is **invisible** — silently wrong output, not an error — and
the traps are listed in §7.

---

## 1. What this is

A **parametric 3D model of a single aluminium electrolysis cell** (*cuve
d'électrolyse*) — a 400 kA modern prebake Hall-Héroult reduction pot, "Marc-400"
class — built as a suite of Python `bpy` scripts executed by headless Blender.

Running one command from an empty scene reproduces the entire cell
deterministically: 757 objects, 74 mesh datablocks, 17 materials, 140 556
evaluated triangles. From there it renders orthographic plates, a hero, a
sectioned cutaway, an exploded series, two MP4 sequences, a GLB, and a
single-file interactive web viewer.

**One cell, not a row.** The user was explicit about this. Busbars and the gas
duct terminate in clean stubs; there is no potroom, no adjacent cell, no crane,
no gas treatment plant.

## 2. Who, when, why

- **Owner:** the repo owner (GitHub `Darkamui`). They gate the work at phase
  boundaries and approve before the next phase starts.
- **When:** built 13–18 September 2026. Phases 0 through 7 are **complete and
  approved**. The project is at final delivery.
- **Why it is scripts and not a `.blend`:** the job started as
  [`astra_blender_electrolysis_cell_production_prompt.md`](astra_blender_electrolysis_cell_production_prompt.md)
  (kept in the repo root, unmodified), which asks for an interactive
  Blender-MCP modelling session. That was unexecutable — no Blender, no MCP
  server, no reference images on the machine. It was re-architected as a script
  suite, which turned out to be the better fit for the actual goal:

  > *"You are the high-level 3d model architectural maker, you need to be ultra
  > clear and specific so the proper gruntwork itself can be passed to a Sonnet
  > model."* — the user, setting the working model for this repo

  So: **one agent authors `spec.py` and the contracts; module bodies are
  delegable gruntwork.** A delegated task is given its file path, the exact
  `spec` fields it may read, exact object names and target collection, a
  geometric description in millimetres with the datum restated, acceptance
  criteria, and the command to self-check. A delegate never chooses a dimension,
  never edits `spec.py`, and never touches another module.

## 3. Where — the machine this was built on

| | |
|---|---|
| Blender | `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` (5.2.1 LTS) |
| Python | `C:\Python314\python.exe` (for the non-`bpy` tools only) |
| GPU | `OPTIX:NVIDIA GeForce RTX 5060 Laptop GPU` — Cycles defaults to CPU and must be opted into explicitly |

**Absent, and load-bearing on how things get verified:** no `ffprobe` (MP4s are
checked by parsing `ftyp`/`moov`/`mvhd`/`stsd`/`stsz` boxes directly), no Chrome
(so the devtools and Playwright MCP servers both fail — the web viewer has never
been looked at in a browser, only loaded in Node), and the GitHub MCP server
fails to connect (`gh` CLI works fine).

## 4. Current state

All fourteen QA checks pass with no defects at `Explosion=0.00`, and
`spec.py`'s `_self_check` passes.

Deliverables live in `out/`, which is **gitignored** — it is 156 MB of
accumulated renders from every phase. Everything in it regenerates from source;
see §6. The delivered set was:

| file | what it is |
|---|---|
| `out/cell.blend` | the master — live drivers, no baked actions, saved assembled |
| `out/cell.glb` / `out/cell_anim.glb` | static / one "Scene" clip, 15 channels, LINEAR, frame-0 start |
| `out/cuve400.html` | 4.59 MB single file, GLB embedded as base64, opens with no server |
| `out/p7final/turntable.mp4` | avc1 1440×1080, 240 frames, 8.000 s, 45°/s |
| `out/p7final/explosion.mp4` | avc1 1440×1080, 150 frames, 5.000 s |

The viewer is also published as a live artifact at
<https://claude.ai/artifact/5uZipx9LKUcU2XjZsZWing>.

## 5. Repository map

```
spec.py            THE DATASHEET. Frozen dataclasses, all millimetres, no bpy
                   import, ~2600 lines with its own _self_check(). The single
                   source of every dimension in the project.
build_all.py       Orchestrator and the only entry point you normally need.
lib/
  units.py         mm() -> metres
  scene.py         scene reset, collection tree, NAME_RE enforcement, fcurves()
  build.py         box(), plate(), box_cluster(), profile_extrude(), bevel()
  materials.py     17 materials + the central part-family ASSIGNMENT table
  explode.py       the rig: one float, empties, drivers; and bake()
  section.py       reversible transverse cutaway (booleans + hiding)
modules/m01..m09   the nine subsystems, one collection each, strictly 1:1
render/
  cameras.py       framing, incl. required_distance() and perspective refit
  lighting.py      three-point + world ramp
  shots.py         render presets: use_preview / use_hero / use_motion
  anim.py          turntable + explosion sequences -> MP4
export/glb.py      GLB export, static or baked-animation
qa/validate.py     14 independent checks, CRITICAL / MAJOR / MINOR
tools/
  API_NOTES.md     REAL Blender 5.2 API signatures, confirmed by introspection
  smoke_test.py    environment smoke test
  lib_test.py      lib/ unit tests
  embed_glb.py     re-embed a GLB into the single-file viewer
docs/
  DESIGN_HISTORY.md  the full nine-revision record. READ IT (see §9).
```

## 6. How to run it

Arguments after the bare `--` belong to the scripts; everything before belongs
to Blender.

```bash
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"

# build only
"$B" --background --python build_all.py

# build, render every shot, save the master
"$B" --background --python build_all.py -- --render all --hero --save

# one module, one plate, fast
"$B" --background --python build_all.py -- --only m01_shell --render ortho_front

# the exploded series
"$B" --background --python build_all.py -- --explode 0,0.25,0.5,1 --render exploded

# the two MP4 sequences (4:3 is the measured default; --anim-aspect overrides)
"$B" --background --python build_all.py -- --anim all --hero --subdir p7final

# QA — has its own __main__; there is NO --qa flag on build_all
"$B" --background --python qa/validate.py

# exports
"$B" --background --python export/glb.py -- --animated --out out/cell_anim.glb
"/c/Python314/python.exe" tools/embed_glb.py    # re-embed into the viewer page
```

Other flags: `--clay` (skip materials), `--section` (force the cutaway on every
shot), `--samples`, `--suffix`, `--subdir`, `--strict` (fail the run on any
module error — use it).

## 7. The traps

Every one of these produced output that looked correct. None raised an error.

**Depsgraph laziness, two forms.** Blender evaluates lazily and both symptoms
are silence:

1. `matrix_world` is a **cache**, refreshed only on depsgraph evaluation.
   Reading a transform you did not just write requires an explicit
   `bpy.context.view_layer.update()`. Without it, `explode.build()` measured
   every part as sitting at the origin and sent all forty flex clamps the wrong
   way.
2. Assigning an ID **custom property does not flag the depsgraph**, so drivers
   reading it are never re-evaluated. Writing a value drivers depend on requires
   an explicit `obj.update_tag()`. `explode.set_explosion()` does this; a probe
   that omitted it reported fifteen dead drivers in a file that was fine.

**`action.fcurves` does not exist on Blender 5.2.** 4.4 replaced the flat list
with *slotted actions*: action → layers → strips → one channelbag per slot. The
route is `strip.channelbag(animation_data.action_slot).fcurves`, centralised in
`lib/scene.fcurves()`.

**`image_settings.media_type` gates the format enum.** `FFMPEG` is not among the
`file_format` options until `media_type` is `VIDEO`, and assigning it first
raises rather than being ignored.

**Blender stamps the frame range onto video filenames** (`turntable0001-0240.mp4`).
`anim._finish()` renames; derive the stamped name from the range the scene was
told to render, never guess it.

**Drivers do not survive glTF.** The exporter writes node transforms and
animation tracks; a driver is neither. `lib.explode.bake()` converts them to
keyframes first — and it must **sample both ends before removing any driver**,
because removing one frees the channel and leaves its last value as residue.

**One glTF clip, not fifteen.** `export_animation_mode="SCENE"` alone is not
enough; `export_anim_scene_split_object=False` is the other half. Without it you
get one animation per empty, and the file loads without complaint.

**The bake is LINEAR and starts at frame 0.** The web slider scrubs the clip as
a lookup table, so time *t* must mean explosion *t*. Under Blender's default
bezier the quarter mark measured at 14% of travel. Starting at frame 1 puts the
first key at 0.042 s inside a clip that starts at 0, creating a dead zone.

**Scrubbing a `THREE.AnimationMixer`:** `mixer.setTime()` does **nothing** to a
paused action, and unpaused, `setTime(duration)` lands on a `LoopRepeat` loop
point and wraps to zero. Set `action.time` directly, then `mixer.update(0)`.

**Materials go on the MESH, not the object,** so linked duplicates share one
slot. **Boolean cutters stay unpainted** — a cutter carrying a material hands it
to the faces it cuts; QA treats a painted cutter as a MAJOR defect.

**`box_cluster()` welds its boxes into one mesh.** Overlapping boxes in one
cluster self-intersect, and a boolean EXACT solve against them returns a
plausible *wrong* solid. Use a separate cluster per non-overlapping group.

**A sequence camera is framed ONCE, for the worst frame, and then held.**
`cameras.activate()` refits per shot, which is right for a still and wrong for a
sequence. Both sequences ask every frame what distance it needs, take the
maximum, and never move again.

**QA's triangle budget must count the EVALUATED mesh.** Counting
`obj.data.polygons` measures the authored cage before booleans, bevels,
solidifies and arrays — 64 388 authored against 140 556 actually delivered.

## 8. Rules that hold the design together

1. **No numeric literal in a module.** Every dimension comes from `spec`.
   Delegates never edit `spec.py`.
2. **Derived over chosen.** Any quantity that must *fit inside* another is
   computed from it, never picked independently. Revision 3 found four chosen
   values that were really collisions waiting for a detail render; Revision 2
   found hood panels overrunning the shell by 3.8 m.
3. **One module owns exactly one collection.** A module that needs two is a
   module that should be split. Cross-cutting passes (materials, the explosion
   rig) run centrally, after every module — a module knows what it built, not
   what the cell is made of or how it comes apart.
4. **Naming:** `{NN}_{SUBSYSTEM}_{part}_{index:03d}`, matching
   `^\d{2}_[A-Z_]+_[a-z0-9_]+_\d{3}$`, enforced by `lib/scene.py`. The rig obeys
   it too.
5. **Repeated parts share mesh data.** 36 anodes, one block datablock.
6. **The model is never moved to explode it.** At `Explosion = 0` every object
   sits exactly where its module put it, so QA's clearance assertions measure
   the real cell.
7. **Idempotent builds.** No reliance on selection state or the active object.

## 9. Method — the thing that actually mattered

**Measure; do not assert, and do not validate by eye.** Nearly every claim in
this project's history that was reasoned rather than measured turned out wrong
in some degree: a "67% of frame" fill that was really 6% (a distance ratio
quoted where a frame area was meant), a 3:1 azimuth ratio that measured 1.36:1,
an anode geometry "correction" derived from generic ranges that the published
400 kA column flatly contradicted.

The inverse is just as important: **three alarming findings were defects in the
measurement, not the model** — fifteen "dead" drivers (a missing `update_tag()`),
100% frame coverage (keying off a background whose gradient runs along world Z,
so its iso-lines are not image rows — fixed by rendering on a transparent film
and using alpha as an exact mask), and a "CROPS" verdict from a strict
inequality applied to two numbers designed to be exactly equal. Do not accept
the first plausible explanation for an alarming result; test it.

**`docs/DESIGN_HISTORY.md` is the full record** — nine revisions covering every
defect found, what caused it, and why each fix is the way it is. Several entries
exist specifically to stop a later reader "fixing" something back. Read it
before making a structural change; it will save you rediscovering something at
your own expense.

## 10. Open work

Nothing is broken and nothing is half-finished. If work continues, in the order
the last review ranked it:

1. **Source the superstructure and hooding.** The pot itself descends from a
   published 400 kA datasheet (Dupuis, *Thermo-Electric Design of a 740 kA Cell*,
   Table 1, 400 kA column, cited in `spec.py`). Everything above the shell rim —
   portal frame, anode beam, hood geometry, end enclosures, gas offtake, feeder
   stack, busbar sections — is plausible-class and marked `# ASSUMED`. This is
   the real remaining fidelity gap.
2. **The 150 mm rod slot**, currently accepted-with-reason (it is a genuine
   feature of a real pot and the known fugitive-emission path), could be closed
   with per-rod sliding plates.
3. **Stills at 4:3.** The sequences were re-framed to 4:3 on measurement; the
   still plates are still a mix of 16:9 and square per shot.

**Known and accepted, recorded so they are not re-found as bugs:** the roof
opening under the gas throat is deliberately not carved; `detail_anode`'s cut
anode shows dark stub sockets because the section plane falls on the stub
centreline; the inside-potshell width diverges from the cited source by 450 mm
to pass the feeder chutes the user's reference section requires. All three are
explained in `docs/DESIGN_HISTORY.md`.

> **What this document is.** The living design record for this repository,
> written as the model was built and revised nine times. It is not a plan to be
> executed — Phases 0 through 7 are complete. It is the record of every defect
> found, what caused it, and why each fix is the way it is.
>
> Read it before making a structural change. Several entries exist specifically
> to stop a later reader "fixing" something back: the deliberate divergences
> from the cited source, the accepted artifacts, and the measurements that
> contradict what the geometry looks like it should need. `AGENTS.md` is the
> orientation document; this is the reasoning behind it.

# Parametric Aluminium Electrolysis Cell — Build Architecture

## Context

`astra_blender_electrolysis_cell_production_prompt.md` asks for a professional, exploded-view Blender model of an aluminium reduction cell (*cuve d'électrolyse*), built through an iterative human-gated workflow using Blender MCP.

**That prompt cannot be executed as written.** Verified on this machine:

- No Blender installed (checked Program Files, LOCALAPPDATA\Programs, PATH, winget list — absent)
- No Blender MCP server configured (checked `.claude.json`, `settings.json`, project `.mcp.json`)
- No reference images — the project folder contains only the prompt file
- Python 3.14 present at `C:\Python314\python.exe`

The prompt's core loop ("model → render → critique → fix") presumes live interactive Blender. Its Phase 1 presumes references to analyse. Neither exists.

**The intended outcome** is the same deliverable, reached by a different and better-suited route: the cell is built as a **parametric `bpy` script suite** executed headlessly. This is not a downgrade — it is the right architecture for the stated goal of delegating gruntwork to Sonnet models:

| Interactive Blender | Script suite |
|---|---|
| Manual ops, not reproducible | Deterministic, re-runnable from zero |
| Changes are invisible | Every change is a reviewable diff |
| Hard to delegate | Sonnet writes modules against a numeric contract |
| Explosion hand-animated | Explosion is one float driving the whole rig |
| Dimensions drift | One frozen datasheet, no magic numbers |

Renders come from `blender --background --python`, written to PNG, and read back for visual critique — so the prompt's mandatory review loop is preserved, not lost.

### Decisions locked with the user

| Decision | Choice |
|---|---|
| Blender | Install 5.2.1 via winget (`BlenderFoundation.Blender`, confirmed available) |
| Dimensional basis | Datasheet authored from published literature |
| Deliverable | Heavy Cycles master **+** separate optimized GLB export path |
| Internals | Full symmetric cell, non-destructive toggleable section |
| Scope edge | Isolated cell; busbars terminate in clean stubs |
| Review gates | Stop at phase boundaries; self-critique with renders inside phases |
| Annotations | None — clean renders |
| Cell class | ~400 kA modern prebake, Marc-400 class |

### Standing risk

Blender 5.2.1 postdates my reliable `bpy` knowledge. **Task 0 is an API smoke test.** No module is written until the real API surface is confirmed on the installed build. Assume nothing about 4.x idioms — particularly node group interfaces, `bmesh` ops, and glTF exporter kwargs, which are the usual breakage points across major versions.

---

## The datasheet — single source of truth

Lives in `spec.py` as frozen dataclasses. **No module may contain a literal dimension.** Every number below is in millimetres; a `mm()` helper converts to Blender metres at build time.

Anchor figures (Marc-400 class) are self-consistent and verifiable: 36 anodes × 1700 × 800 mm = 48.96 m²; 400 000 A ÷ 48.96 m² = 0.817 A/cm², matching the published anodic current density.

### Coordinate datum

- **+X** = longitudinal (cell length) · **+Y** = transverse (width) · **+Z** = up
- **Origin** at cell centre in X/Y; **Z = 0 at the shell's inner floor** (top face of bottom plate)
- Cell is symmetric about both X=0 and Y=0 — exploit with Mirror modifiers

### Process / electrical

| Parameter | Value |
|---|---|
| Line current | 400 kA |
| Anode count | 36 (2 rows × 18) |
| Anodic current density | 0.817 A/cm² |
| ACD (anode–cathode distance) | 45 |
| Metal pad depth | 200 |
| Bath depth above metal | 200 |
| Anode immersion into bath | 150 |

### Vertical stack (from Z=0 upward)

| Layer | Thickness | Top at Z |
|---|---|---|
| Insulating board (calcium silicate) | 100 | 100 |
| Refractory firebrick (2 courses × 65) | 130 | 230 |
| Dry barrier / alumina bedding | 50 | 280 |
| Cathode block | 450 | 730 |
| Metal pad (molten Al) | 200 | 930 |
| Bath (cryolite electrolyte) | 200 | 1130 |
| Freeboard to shell rim | 270 | **1400 (rim)** |

Derived: anode bottom face = metal top + ACD = **975**; anode top = 975 + 600 = **1575** (protrudes above rim into superstructure — correct).

### Plan dimensions

| Parameter | Value |
|---|---|
| Anode block | 1700 (Y) × 800 (X) × 600 (Z) |
| Inter-anode gap (X) | 50 |
| Centre channel between anode rows (Y) | 200 |
| Side channel, anode edge → ledge (Y) | 250 |
| End channel, anode → end lining (X) | 300 |
| Anode array extent (X) | 18×800 + 17×50 = 15 250 |
| Cavity interior | 15 850 (X) × 4 100 (Y) |
| Side lining: SiC block | 100 |
| Side lining: refractory backing | 150 |
| Shell plate thickness | 15 |
| **Shell external** | **~16 380 (X) × 4 630 (Y) × 1 415 (Z)** |

### Cathode assembly

| Parameter | Value |
|---|---|
| Cathode block | 3 400 (Y) × 600 (X) × 450 (Z) |
| Block count | 24, laid transversely |
| Ramming paste seam between blocks | 40 |
| Collector bar section | 120 (W) × 150 (H) |
| Collector bars per block | 2 (exit both ±Y faces) |
| Bar protrusion beyond shell | 250 (flexible connector stub) |

### Anode assembly (×36, one master, linked duplicates)

| Component | Spec |
|---|---|
| Carbon block | 1700 × 800 × 600 |
| Stubs (cast iron, into block) | 4 per anode, Ø180, 100 embedded |
| Yoke (aluminium) | Horizontal bar 1400 × 160 × 160 |
| Stem / rod (aluminium) | 150 × 150 section, 1 800 tall |
| Clamp at anode beam | Simple jaw block, 300 × 250 × 200 |

### Shell & superstructure

| Component | Spec |
|---|---|
| Cradles (external ribs) | 14 pairs, 1 200 pitch, 400 (H) × 25 (T) |
| Anode beam | 2 longitudinal aluminium beams, 800 × 300 section, at Z = 2 100 |
| Superstructure columns | 6 pairs, 400 × 400 box section |
| Hood panels | 18 per side, 900 (X) × 1 400 (H), removable group |
| Riser busbars | 4 on upstream (+Y) side, 800 × 200 section |
| Gas duct | Ø900, one end, terminating in stub |

> Figures beyond the Marc-400 anchors are plausible-class values, not sourced per-part. Each is an explicit, tunable assumption in `spec.py` — flagged there with a `# ASSUMED` comment so they can be corrected wholesale if references arrive later.

---

### Revision 1 — user reference section (transverse Y–Z cut)

The user supplied an annotated FR/EN cross-section. It **confirmed** the overall
architecture (shell → refractory → cathode + collector bars → metal pad →
electrolyte → two anode rows → rods → anodic beam → hoods) and **corrected**
four things, now applied to `spec.py`:

| Change | Reason |
|---|---|
| Added **crust** (`croûte`, 120 mm) + alumina cover blanket (100 mm) | In the reference, absent from the first datasheet |
| Added **ledge** (`gelée`) as a tapered sidewall solid, 300 mm at metal → 120 mm at bath surface | In the reference; it defines the cavity profile at bath level |
| Added **alumina feeder** (`alimentation en alumine`): 5 point feeders, hopper + chute + crust breaker | In the reference, entirely missing before |
| Centre channel 200 → **400 mm**; shell rim 1400 → **1500 mm** | A 250 mm feeder chute could not fit a 200 mm channel; the crust+cover stack left only 50 mm of freeboard |

Resulting cell: **16 380 × 4 830 × 1 515 mm** — inside the published 8–25 m ×
3–5 m range for industrial Hall-Héroult pots.

`04_PROCESS` now carries metal/bath/crust/cover; ledge builds with `02_REFRACTORY`
(it forms against the lining); the feeder builds with `07_SUPERSTRUCTURE`.

**Modelling note for the crust:** it forms only in the channels *around and
between* anodes, never beneath one. It must be built as bath-surface geometry
with the 36 anode footprints subtracted, not as a flat slab.

---

### Revision 2 — historic plate, potroom photograph, process diagram

| Ref | Value | Applied |
|---|---|---|
| Historic FR plate (*Coupe Longitudinale* / *½ Coupe Transversale* / *Vue Générale*) | Confirms construction logic: anodes in a row, continuous cathode block run, **two distinct brick courses** — *Briques Réfractaires* over *Briques Kieselguhr* | Validates the existing 2-course `Lining`. **Dimensions NOT adopted** — this is a much older, smaller cell than Marc-400 |
| **Potroom photograph** | Hooding is **curved and heavily ribbed** bright metal, not flat plate; substantial **end enclosure boxes** with access doors rise above the hood line | Major `Hooding` rewrite (below) |
| Process flow diagram (CTG, silos, casting) | Plant context; confirms duct → gas treatment centre | No geometry change; duct still terminates in a stub per agreed scope |

**Hooding rewritten.** The first draft had flat 8 mm plates. The photograph shows
the curve-plus-rib rhythm is the dominant visual signature of the cell, so it is
now modelled explicitly: quarter-cylinder sweep (R1250, 85°), ribs at 150 mm
pitch, lifting handles, plus end boxes (1800 mm long, rising to 3200 mm).

**Panel width is now DERIVED, not chosen.** Hardcoding 18 × 900 mm panels
overran the shell by 3.8 m — caught by `_self_check` before any geometry
existed. The run is now sized to exactly fill the gap between the end boxes:
14 panels × 894 mm, closing on 12 780 mm.

> Precedent worth keeping: any quantity that must *fit inside* another is
> derived from it, never independently chosen. Same rule already applies to
> `anode_immersion`, `freeboard`, and the cathode gaps.

---

### Revision 3 — blockout self-critique (Phase 2)

Four chosen values were found to be quantities that something else already
determines. Each had a real geometric consequence, and three of them were
collisions that would have been invisible until a detail-phase render.

| Was chosen | Now derived from | What it actually did wrong |
|---|---|---|
| `anodes.stem_height` = 1800 | `beam_top_z + stem_above_beam` | Left **1335 mm of bare rod** above the anode beam — the hero render read as a forest of spikes. Stem is now 815 mm, topping out at 2750. |
| `superstructure.column_top_z` = 2600 | `z_stem_top + cross_section` | Put the transverse tie **straight through the 2750 mm stem tops**. |
| `feeder.hopper_base_z` = 2600 | `z_deck_top` | Floated the hopper with nothing under it once the frame moved. |
| `hooding.curve_radius` = 1250 | chord between the two anchors | An 85° arc of R1250 needs a **1689 mm chord**; the span from anode beam to shell rim is **1128 mm**. The panel could not touch both anchors and crested at 2656 mm, up through the superstructure. Derived R = **835 mm**. |

Two further structural corrections, from working the collisions through:

- **The portal frame is open along the centreline.** A full-width transverse
  tie blocks the feeder chutes at y=0. Each tie is now a *pair* of half-ties
  stopping at `cross_inner_y`. This is not a simplification — it is how a
  prebake superstructure is built, because the feeders descend through that
  gap and the crane reaches in there to change anodes.
- **Columns stand on the cradles**, at `|Y| = shell_outer_y/2 + section/2`, so
  their inner face is flush with the shell side. Any further inboard and the
  column grows through the hood envelope. Their X stations are derived as the
  cradle positions that fall clear of the end enclosures, spread evenly —
  giving a real load path rather than six arbitrary positions.

Resulting superstructure stack, with **one** chosen height (`beam_z` = 2100)
and everything above it derived: beam top 2400 → stem tops 2750 → portal tie
2750–3150 → feeder deck 3150–3350 → hopper 3350–4150 → breaker 4150–5050.

Thirteen new `_self_check` assertions now hold each of these relationships, so
none can silently regress.

**Known issue, deferred to Phase 3:** the anode clamp is centred on the beam
rather than bolted to its side face, so it interpenetrates the beam. It is a
mounting detail, not a proportion error, and does not affect the blockout gate.

---

## Repository structure

```
electrolyd/
  spec.py                  # datasheet, frozen dataclasses, NO bpy import
  build_all.py             # orchestrator; --phase, --render, --explode flags
  lib/
    units.py               # mm(), consistent float conversion
    scene.py               # clear_scene(), collection tree, naming enforcement
    build.py               # box(), plate(), profile_extrude(), bevel(), solidify()
    materials.py           # material library, one function per material
    explode.py             # explosion rig + drivers
    section.py             # non-destructive cutaway boolean, toggleable
  modules/
    m01_shell.py           m05_anodes.py
    m02_refractory.py      m06_busbars.py
    m03_cathode.py         m07_superstructure.py
    m04_process.py         m08_hardware.py
  render/
    cameras.py  lighting.py  shots.py
  export/
    glb.py                 # decimate + bake path, master untouched
  qa/
    validate.py            # automated assertions
  out/                     # renders, .blend, .glb  (gitignored)
```

### Module contract — every `modules/m*.py` obeys this

```python
def build(ctx: BuildContext) -> list[bpy.types.Object]:
    """Create this subsystem. Returns all created objects."""
```

Non-negotiable rules for module authors:

1. **Read dimensions only from `spec`.** A numeric literal in a module is a defect, except for counts already in `spec` and trivial factors like `0.5`.
2. **Link objects only into the module's own collection.** Never touch another module's objects.
3. **Naming:** `{NN}_{SUBSYSTEM}_{part}_{index:03d}` — e.g. `05_ANODES_block_017`. Enforced by `scene.py`.
4. **Origins** at the part's own logical centre or mounting face, never at world origin.
5. **Idempotent:** running `build()` twice on a clean scene gives identical output. No reliance on selection state or the active object.
6. **Repeated parts share mesh data** (linked duplicates), never independent copies — this is what makes 36 anodes cheap in both Blender and glTF.

---

## Collection tree

Matches the original prompt's hierarchy:

```
00_REFERENCES   01_SHELL        02_REFRACTORY   03_CATHODE
04_PROCESS      05_ANODES       06_BUSBARS      07_SUPERSTRUCTURE
08_HOODING      09_HARDWARE     10_EXPLOSION    11_CAMERAS   12_LIGHTING
```

---

## Explosion system

Controlled by a single float, exactly as the prompt requires (`0.0` assembled → `1.0` fully exploded).

- One empty `CTRL_MASTER` carries a custom property `Explosion` (0.0–1.0, soft-limited).
- Each subsystem collection is parented to its own empty, `EXPL_{subsystem}`.
- Each `EXPL_*` empty has **drivers** on `location`, evaluating `Explosion × direction × distance`, with direction and distance read from `spec.EXPLOSION_VECTORS`.
- Movement is axis-sensible per the prompt: lining layers separate on **+Z**, anodes lift **+Z** far, hoods **±Y** outward, collector bars **±Y**, superstructure **+Z** furthest. No radial scattering.

**glTF caveat:** drivers do not export. `export/glb.py` bakes the driven transforms to keyframes before export. The master `.blend` keeps live drivers.

---

## Execution phases and gates

Each phase ends with renders written to `out/` which I inspect and critique before presenting to you. **I stop for your approval at every phase boundary.**

### Phase 0 — Environment (no geometry)
Install Blender 5.2.1 via winget. Run the API smoke test: confirm headless launch, `bpy` version, mesh creation, modifier stack, driver creation, Cycles render to PNG, and glTF export kwargs. **Record the real API signatures.** Write `spec.py`, `lib/units.py`, `lib/scene.py`, `lib/build.py`.
*Gate: smoke-test render exists and API notes are captured.*

### Phase 1 — Reference & inventory
Original Phase 1, adapted: with no images, the datasheet **is** the reference. Produce the component inventory and a written known-vs-assumed split. Every `# ASSUMED` in `spec.py` is listed.
*Gate: you confirm the inventory and dimensional assumptions.*

### Phase 2 — Blockout
All eight modules produce primitive-only massing at correct dimensions. No detail. Render the five views the prompt demands: front ortho, side ortho, top ortho, 3/4 hero, longitudinal section.
*Gate: proportions and silhouette approved. This gate matters most — errors here propagate.*

### Phase 3 — Subsystem detail passes
One module at a time, in prompt order: shell → refractory → cathode → process → anodes → busbars → superstructure/hooding → hardware. Per module: build, render, self-critique against the 5-largest-problems rule, fix, re-render.
*Gate: at the end of the group, not per module (your choice).*

### Phase 4 — QA
Run `qa/validate.py`. Ranked defect list, Critical → Major → Minor. Fix in order.
*Gate: defect list and after-renders.*

### Phase 5 — Materials
Ten materials per the prompt. Close-up validation renders.
*Gate: material close-ups.*

### Phase 6 — Exploded view
Build the rig; render assembled, 25%, 50%, 100%, and a hero exploded view.
*Gate: the exploded set.*

### Phase 7 — Polish & export
Cleanup, turntable, exploded animation, GLB export via the separate optimized path.
*Gate: final delivery.*

---

## How Sonnet work is dispatched

I author the spec and contracts; Sonnet writes module bodies. Each delegated task is self-contained and includes, without exception:

1. **The module file path** and its `build(ctx)` signature
2. **The exact `spec` fields it may read** — named explicitly, so nothing is invented
3. **Exact object names and the target collection**
4. **A geometric description in millimetres** with the datum restated
5. **Acceptance criteria** — object count, bounding box within tolerance, named modifiers present
6. **The self-check command** to run and the render to inspect:
   ```
   blender --background --python build_all.py -- --phase m0X --render ortho_front
   ```

A task is complete only when its render and `qa/validate.py` both pass. Sonnet never chooses dimensions, never edits `spec.py`, and never touches another module.

---

## Verification

**Automated** — `qa/validate.py`, run every phase:
- No object has NaN/inf in its transform; no unintended non-uniform scale
- All names match the convention; no `Cube.001` leakage
- No objects outside the collection tree; no orphaned mesh data
- Manifold check and consistent outward normals on structural meshes
- **Clearance assertions from `spec`**: ACD = 45 mm; anode bottom clears metal pad; collector bars intersect cathode blocks but not shell plate; no anode–hood interpenetration
- Repeated parts share mesh data (36 anodes → 1 block mesh datablock)
- Triangle count reported against the GLB budget

**Visual** — headless renders to `out/`, inspected directly:
```
blender --background --python build_all.py -- --render all
blender --background --python build_all.py -- --explode 0.5 --render hero
```

**End-to-end** — from an empty scene, `build_all.py` reproduces the entire model deterministically; GLB loads in a glTF viewer with the master `.blend` unmodified.

---

## What I am explicitly not doing

- No potroom floor, adjacent cells, cranes, or gas treatment plant — busbars and duct end in stubs
- No 3D callouts or leader lines
- No Søderberg variant
- No modification of `spec.py` by delegated tasks

---

### Revision 4 — Phase 2 plate critique

The first five plates were rendered, inspected, and four defects fixed. Two of
the four were invisible in the renders and only showed up under measurement,
which is why the diagnostic tooling below is now permanent.

| Defect | Cause | Fix |
|---|---|---|
| Transverse plates cropped top and bottom | `ortho_scale` spans the **larger** render dimension; on 16:9 the vertical span is only 9/16 of it, and the framing was *predicted* from spec rather than measured | `cameras.activate()` now measures the evaluated scene, projects it onto the camera's own screen axes, and corrects for frame aspect. `ortho_front` and `section` render square. |
| `section` plate was a duplicate of `ortho_front` | no section cut existed; the end enclosure box stands in front of the whole cell | new `lib/section.py` — a reversible transverse cut at the anode column nearest centre |
| A 450 × 450 mm void ran the full length of **both** sides of the cathode, plus both ends and all 23 inter-block seams | the rammed carbon paste was simply never modelled | `m03` now builds the paste as the whole cathode band with blocks and bars subtracted |
| The paste first came out as a slab *above* the cathode | `box_cluster` welds its boxes into one mesh; the bar boxes sit inside the block boxes, so the cutter self-intersected and EXACT returned a plausible wrong solid | separate cluster per non-overlapping group; the requirement is now stated in `box_cluster`'s docstring |

**`lib/section.py`.** Non-destructive in the literal sense: objects straddling
the plane get a named BOOLEAN, objects wholly on the discarded side are only
hidden, and `disable()` restores both. Verified by round-trip — two enable /
disable cycles return the scene to exactly 570 visible objects and 24 346
evaluated faces, with one cutter and no naming violations. Objects already
hidden for their own reasons (the crust and ledge cutters) are excluded, or
`disable()` would unhide them into the middle of every later plate.

**Diagnostic worth keeping:** ray-casting a grid across the section plane and
printing what each sample hits. The 450 mm void was legible as "the ray flew
8 m down the cell and hit the far end wall" long before it was legible as a
grey square in a clay render.

**Carried into Phase 3:**

- anode clamp is centred on the anode beam instead of bolted to its side face
- hood ribs stand 24 mm proud of the panel's landing edge, so a panel would
  rock on its stiffeners rather than seat on the shell rim
- the bath solid is not displaced by the immersed anodes (155 mm of overlap);
  the crust already handles this with `anode_cut`, the bath does not
- `m09_hardware` not yet written

---

### Revision 5 — Phase 3 detail passes

All nine modules detailed and critiqued. Four defects found and fixed; three
carried items from Phase 2 turned out to be already correct under measurement;
two findings were accepted with a stated reason rather than fixed.

**Fixed**

| Defect | What it actually did wrong | Fix |
|---|---|---|
| Gas offtake had **no gas path** | The header lay tangent on the end enclosure roof — 6 m of pipe resting on a closed box, with the hood plenum underneath venting nowhere | New square-to-round **throat** rises out of the plenum and carries the header. `z_duct_centre` is now derived from `duct_throat_rise`, so the pipe no longer touches the roof at all |
| End enclosure face was **86% bare plate** | Two doors on a blank 4.8 × 1.7 m box | 32 ribs at the hood's own pitch, framed openings, capping plate, side ribs, pot-number plaque → **29% bare** |
| Risers **ended in bare cut faces** | `riser_top_z` was *chosen* at 2100 and labelled "meets the anode beam"; it stopped level with the beam's underside but 1240 mm outboard of its outer face, connected to nothing | `z_riser_top` derived = `beam_top_z`; X stations derived from the portal **bays**; each riser laps over the beam top on an **arm** |
| Shell **end wall was dead plate** | 4800 × 1500 mm blank — the largest single surface in a transverse elevation. The cradles stopped at the side walls, so the stiffening rhythm ran the length of the cell and ended at the corner | **End cradles**: linked copies of the side cradle turned a quarter turn, at the side wall's own derived pitch. Zero new mesh datablocks |

Two supporting fixes found while doing the above:

- **`lib/section.py` sized its cutter from `end_box_top_z`**, which no longer
  bounds the model — the feeder stack tops out 1850 mm above it and the busbars
  reach further out in Y. A cutter that stops short does not fail, it silently
  leaves the discarded half of whatever it missed standing in the plate. It now
  measures the evaluated scene on both axes.
- **`qa/validate.py` matched part families by substring**, so `_cradle_` also
  caught `_end_cradle_` and reported 36 objects against an expected 28. The
  match is now exact on the part token.

**Carried from Phase 2, measured, already correct**

- *Anode clamp vs beam* — the clamp laps 125 mm of its 250 mm depth onto the
  beam's inner face. A clamp must overlap what it grips; this is a jaw, not an
  interpenetration.
- *Hood rib inset* — ribs no longer stand proud of the panel's landing edge.
- *Bath not displaced by the immersed anodes* — **this was a probe artifact, not
  a defect.** `m04` already applies the anode cutter to the bath. Three separate
  measurement errors nearly produced a false Critical: reading `obj.data.vertices`
  (the authored slab) when the cut is a BOOLEAN *modifier* and only exists on the
  evaluated mesh; a footprint window set *narrower* than the block, which excluded
  the very vertices the cut created; and then being fooled by the bath loft's own
  corner vertices. Settled by BVHTree ray-crossing parity up the centreline of a
  **middle** anode: bath occupies exactly (930, 975), the ACD is bath-filled, and
  nothing stands above the anode working face.

**Accepted with reason, not fixed**

- **The 150 mm rod slot.** The hood top cover stops at y=975; the anode beam's
  inner face is at y=1125, leaving a 150 mm slot open for ~700 mm between every
  pair of stems — 34 openings. This is a real feature of a real pot: the anode
  rods pass through exactly such a slot, pots are not gas-tight there, and it is
  the known fugitive-emission path. Closing it would mean per-rod sliding plates,
  which is past the agreed scope.
- **Empty-looking stub sockets in `detail_anode`.** A framing artifact of the
  clay pass, not geometry. The section plane at x=425 falls dead on the stub
  centreline (stub centre x = block centre x, all four stubs in one row along Y),
  so the cut-away half of each stub leaves a face coplanar with the socket bore.
  In a single clay colour that reads as a hole. Stubs measure correctly seated —
  z 1475..1775 against a block top of 1575, exactly the 100 mm embedment — and
  cast iron against carbon in Phase 5 will separate them.

**Deliberate omission, recorded so it is not re-found:** the roof opening under
the throat is *not* carved. Carving it would split the two end boxes onto
separate mesh datablocks (the far box would get a hole with nothing above it),
z-fight with the throat's own bottom cap, and it is not visible from any camera —
the section plane is at x=425 and the end box at x=7290.

**State at the Phase 3 gate:** 801 objects, 74 mesh datablocks, 79 396 triangles
against a 1 500 000 budget. `spec.py` `_self_check` PASSES. `qa/validate.py`
reports **no defects** across 12 checks. Six plates in `out/p3gate/`.

---

### Revision 6 â€” external sourcing pass

Every previous check in this project was **circular**: `spec._self_check` and
`qa/validate.py` both read `spec.CELL`, so they prove the model is consistent
with the datasheet and say nothing about whether the datasheet is right. The
audit that prompted this pass counted **119 `# ASSUMED` values against 37
`DERIVED` markers**. This pass went outside the project for the first time.

**The primary source, found.** M. Dupuis, *"Thermo-Electric Design of a 740 kA
Cell, Is There a Size Limit?"* carries a six-column table comparing 300 / 265 /
350 / 400 / 500 / 740 kA designs, descending from his *"Thermo-Electric Design
of a 400 kA Cell Using Mathematical Models: A Tutorial"* (TMS Light Metals
2000). The 400 kA column is a complete datasheet for exactly the cell modelled
here. It is now cited as `[1]` in `spec.py`'s header, with ICSOBA 2017 as `[2]`.

**The big question, answered â€” and my own previous finding was wrong.**

Before this pass I reported that the cell was mis-shaped: that published anode
blocks are 400-600 x 1200-1500 mm against my 1700 x 800, that the anode count
should rise from 36 to ~48, and that the cell should be ~20 m rather than 16.4.
That was reasoning from *generic ranges* across all cell sizes, and it was
wrong. `[1]` gives, for 400 kA specifically:

> 36 anodes Â· 1.7 m x 0.8 m Â· inside potshell 16.1 x 4.35 m

â€” and describes how that cell is arrived at: the 350 kA design in a 14.4 m
potshell, stretched to 16.1 m to take four more anodes. The geometry already in
the model is the published geometry. **No reshape. The blockout gate stands.**

Worth keeping as a lesson: a range that spans every cell from 100 to 740 kA
will not tell you whether one 400 kA cell is right. Find the column, not the
range.

**Corrections applied to `spec.py`**

| Field | Was | Now | Source |
|---|---|---|---|
| `process.acd` | 45 | **40** | `[1]` 4 cm, for every design 350-740 kA. ICSOBA gives 4.0-4.5 |
| `anodes.stubs_per_anode` | 4 | **3** | `[1]`. Four belongs to the 1.95 m anodes of 500 kA+ cells |
| `anodes.stub_diameter` | 180 | **190** | `[1]` "19 cm" |
| `cathode.block_count` | 24 | **20** | `[1]`. The 1.7 m stretch added two blocks, not four |
| `cathode.block_y` | 3400 | **3670** | `[1]` "3.67 m" |
| `cathode.block_x` | 600 | **730** | follows from n=20 filling the same cavity |
| `cathode.bar_w` x `bar_h` | 120 x 150 | **100 x 230** | `[2]`. A collector bar is tall and narrow; current practice supersedes 65x180 and 65x240 |

The cathode correction is the interesting one. It is not a cosmetic swap of
numbers: twenty fatter blocks is a *different construction* from twenty-four
narrower ones, and the 3670 mm block length shrinks the side ramming-paste band
from a frankly absurd 450 mm to 315.

**Confirmed correct, no change**

Anode block 1700 x 800 x 600 Â· 36 anodes in 2 rows Â· 0.817 A/cmÂ² (published band
0.65-1.3) Â· bath depth 200 (150-300) Â· alumina cover 100 (`[1]` "10 cm") Â·
5 centre point feeders Â· **stiffeners on the end walls as well as the sides**,
which independently vindicates the end cradles added in Revision 5.

A cross-check that does not come from the geometry at all: Faraday's law at
0.3356 g/(AÂ·h) gives 400 kA Ã— 24 h Ã— 93.4% CE = **3.01 t/cell-day**, which is
exactly the published figure for a real 400 kA pot (SY400, ICSOBA Table 2).
Two independent routes to the same cell.

**Known divergences from `[1]`, deliberate, now recorded in `spec.py`**

- **Inside potshell width 4800 against 4350.** `[1]` is a thermal model with no
  feeder geometry in it; the user's reference section has feeders descending the
  centre channel. That channel was widened 200 â†’ 400 in Revision 1 to pass a
  250 mm chute, and the side channel is 250 rather than ~125. Those two account
  for the whole 450 mm difference.
- **Inside potshell length 16350 against 16100.** Identical anode array (15250)
  either way; the difference is a more generous end channel plus lining.

Both are stated in the datasheet header so neither gets "corrected" later by
someone who has read `[1]` and not the reasoning.

**Still unsourced, and honestly so:** the entire superstructure and hooding â€”
portal frame, anode beam section, hood panel geometry, end enclosures, gas
offtake, feeder stack, busbar sections. `[1]` is a thermal model of the pot and
stops at the shell rim. These remain plausible-class values and are marked
`ASSUMED`.

**State after the revision:** 737 objects (down from 801: 36 fewer stubs, four
fewer cathode blocks and their bars), 74 mesh datablocks, 64 388 triangles
against the 1 500 000 budget. `spec.py` `_self_check` PASSES. `qa/validate.py`
reports **no defects** across 12 checks. Six plates re-rendered to `out/p3rev/`.

One visible improvement worth noting: `detail_anode` now reads correctly. The
cut anode shows three stub sockets across the block instead of four, and the
socket row no longer sits dead on the section plane in the way that made
Revision 5's plate look like it had empty holes in it.


---

### Revision 7 — Phase 5 materials

Seventeen materials, not the prompt's ten. The extra seven are not decoration:
`cast_iron` vs `structural_steel` vs `oxidized_steel` vs `galvanised_steel` vs
`painted_steel` are five different steels because they are five different
surface *states*, and a plate that renders them all as one grey cannot show
whether a part is a cast stub, a mill-scaled bracket, or a zinc-coated hood.

**Central assignment, not per-module.** `lib/materials.py` owns a single
`ASSIGNMENT` table mapping all 56 part families to materials, applied once by
the orchestrator after every module has built. A module knows what it built; it
does not know what the cell is made of. The pass runs under `--strict`, where an
unassigned family is a hard error — so adding a part without deciding what it is
made of fails the build rather than shipping a grey object.

Two rules the code states in its own comments because both are easy to "fix"
back:

- **Materials go on the MESH, not the object.** Linked duplicates then share one
  slot — safe only while a datablock belongs to one part family, which `apply()`
  verifies and raises on.
- **Boolean cutters stay unpainted.** A cutter carrying a material hands that
  material to the faces it cuts. Five cutters are listed in `UNPAINTED`, and the
  new QA check treats a *painted* cutter as a MAJOR defect — a defect in the
  opposite direction from a bare mesh.

**The 13th QA check.** `check_materials()`: every visible mesh carries exactly
one material; cutters carry none. Deduplicates by datablock, so 36 anodes count
once. Reports 17 materials in file, 69 mesh datablocks painted — 69 + 5 cutters
= 74, complete coverage.

**Three new close-up cameras** (`mat_lining`, `mat_busbar`, `mat_shell`), plus
`detail_anode` reused rather than duplicated. The framing principle is recorded
in `cameras.py`: *a close-up that shows one material alone proves nothing — the
question a material plate answers is "does cast iron read as cast iron NEXT TO
carbon", not "is this grey".* Every plate frames an adjacency.

**Four material corrections, from reading the first plates**

| Material | Was | Now | Why |
|---|---|---|---|
| `carbon_anode` | #1E1C1B | **#2C2926** | 1.2% linear; under AgX the block crushed to a flat silhouette with no form in it. Carbon is dark, not black |
| `cast_iron` | #4A4744, metallic 0.90 | **#6E675E, 0.55** | The stubs vanished into the carbon — the exact artifact Revision 5 expected materials to resolve. Cast iron out of a mould is SCALED, not polished, and scale is a dielectric skin over the metal |
| `structural_steel` | metallic 1.00, rough 0.42 | **0.72 / 0.55** | A mirror in a sparse scene is a coin toss on facing direction (below) |
| `molten_aluminium` / `electrolyte` emission | 2.2 / 3.4 | **0.9 / 1.5** | Above ~1.5 AgX's shoulder desaturates every hue toward white: pad and bath came out the same pale peach and could not be told apart, defeating the reason for lighting them |

**The largest finding: the black objects were an ENVIRONMENT defect, not a
material defect.** In the first materialled hero the Ø900 gas duct, the jack
screws and the breaker cylinders rendered pure black. The diagnosis came from a
probe, not a guess: all five `07_SUPERSTRUCTURE_breaker_*` are identical objects
sharing one material at one Z, yet one rendered as steel and four as holes.
Nothing about the parts differed — only which way they happened to face.

A `metallic = 1.0` surface has no colour of its own; it returns what is around
it. The world was a two-stop gradient bottoming at 0.037 — near black. Every
downward-facing metal surface was faithfully reflecting nothing.

The two-stop world was **not wrong for what it was built for.** A clay model is
entirely diffuse: it needs fill, and what the lower hemisphere contains is
invisible. That stops being true the moment the cell is made of metal. The ramp
now runs floor bounce (0.150) → horizon (0.310) → sky (0.600), strength 0.55:
the bottom stop is a concrete potroom floor, which is what is actually under
this cell, and the top is daylight through a roof vent. Metal has somewhere to
look. Both this and the `structural_steel` change are defensible independently,
and both are documented in place so neither gets reverted.

**Orchestrator changes.** `--clay` skips the material pass (the blockout plates
remain reproducible). `--render` group names now expand *in place* inside the
comma list — previously `--render materials,hero` asked for a camera literally
named "materials" and killed the run at the first shot; a group name only worked
standing alone.

**Viewer.** GLB re-exported with materials (3.25 MB) and the page carries a
"Real materials" switch, defaulting on, with the flat subsystem palette retained
as the second mode — a flat per-subsystem colour is what makes the layer toggles
legible, so neither replaces the other. One non-obvious fix: changing the
*count* of clipping planes requires `needsUpdate` on every material in use, the
GLB's included, or the section cut silently stops clipping the real materials.

**Accepted, unchanged:** `detail_anode`'s cut-block sockets still read as dark
cavities. The section plane falls on the stub centreline and the near half of
each stub is discarded with it — the Revision 5 accepted artifact. The
improvement is visible on the *un-cut* neighbouring anode, where cast iron now
separates from carbon clearly.

**State at the Phase 5 gate:** 737 objects, 74 mesh datablocks, 17 materials
(17 used), 723 objects painted, 64 388 triangles against the 1 500 000 budget.
`spec.py` `_self_check` PASSES. `qa/validate.py` reports **no defects** across
13 checks. Six plates in `out/p5gate/`.

---

### Revision 8 — Phase 6 exploded-view rig

One float, `Explosion` on `10_EXPLOSION_master_000`, 0 assembled to 1 apart.
Sixteen group empties carry fifteen scripted drivers; 728 objects are parented
and **nothing is ever moved**, so at Explosion 0 the model is bit-identical to
the Phase 5 cell and QA's clearance assertions still measure the real pot.

**The plan's rig names were illegal.** `CTRL_MASTER` and `EXPL_{subsystem}` fail
`lib/scene.py`'s `NAME_RE`, which every other object in the file obeys. The rig
uses conforming names (`10_EXPLOSION_hooding_panels_hi_000`) — no less readable,
and they pass `check_naming()` like everything else.

**Three subsystems do not travel as one, and the split table is MEASURED.** The
plan assumed one empty per collection. Probing the built scene showed that holds
for six of nine:

| Subsystem | What the measurement showed | Motions |
|---|---|---|
| `06_BUSBARS` | 29 parts one side of the centreline, 21 the other — the risers stand on the upstream face but the collector flexes exit BOTH ±Y faces | risers + flexes out, mirrored |
| `08_HOODING` | 22 of 150 parts straddle Y=0: the 14 top `cover`s and the `end_box`/`end_cap`/`end_rib`/`number_plate` of the two end enclosures | covers lift, panels swing out, end boxes withdraw along X |
| `09_HARDWARE` | not a subsystem at all — a bag of fasteners with three different hosts: 40 `flex_clamp` at Z 510, 36 base plates and gussets on the shell rim at Z 1500, 24 jacks on the anode beam at Z 2400 | clamps ride the busbars, the rest lifts |

The hardware case is the one worth keeping. Sent +Z as a single group, the forty
clamps flew off the forty flexes they grip while those flexes travelled ±Y — an
exploded view that is confidently wrong about how the cell comes apart. The
clamps now take the busbar vector exactly, and their 80 mm overlap with the bars
is the grip, not a defect.

`mirror` is the general rule behind all three: the direction flips for parts on
the negative side of the group's own dominant axis, so a mirrored subsystem
opens like a book instead of sliding sideways.

**Every distance is now derived from measurement, not chosen.** The first set
was chosen, and a pair-overlap audit at Explosion 1 found four subsystems still
solid-intersecting each other — a part cannot read as removed while it is still
inside its neighbour. Distances are now set from the evaluated bounding boxes,
walking outward from the cathode datum with a 600 mm reading gap at each step
(600 because the exploded diagram is 17 m tall; 200 mm at that scale is one
pixel and reads as contact):

| | was | now | |
|---|---|---|---|
| `01_SHELL` | 2500 | **4700** | cleared the refractory by 220 mm — i.e. did not |
| `02_REFRACTORY` | 1200 | **2400** | its ledge still stood 470 mm inside the cathode |
| `04_PROCESS` | 1800 | **1200** | *reduced*: it belongs below the hardware, not through it |
| `05_ANODES` | 4200 | **4400** | |
| `06_BUSBARS` | 3500 | **3000** | |
| `07_SUPERSTRUCTURE` | 7000 | **7400** | |
| `08_HOODING` panels | 5000 | **6100** | riser and panel envelopes overlap by 2488 mm while assembled, so the difference from the busbars must exceed it; 3100 does |
| `08_HOODING` covers / ends | — | **5800 / 3000** | |
| `09_HARDWARE` frame | 2000 | **1900** | |

The audit now reports exactly one overlapping pair at 1.0, the clamp gripping
its bar. Everything else is clear.

**Two silent bugs, both the same bug.** `matrix_world` is a *cache*, refreshed on
depsgraph evaluation, and a module that sets `obj.location` leaves it stale until
something asks the depsgraph. Nothing had — so at rig-build time every part
measured as sitting at the origin, the mirror split saw all forty flex clamps on
the centreline, and sent the lot to +Y. A stale matrix is a valid matrix; there
is no error. `explode.build()` now calls `view_layer.update()` before reading a
single transform. This is the same hazard as the lazy drivers that `set_explosion`
already guards, one step earlier in the pipeline — worth stating as a rule: **in
this codebase, reading a transform you did not just write requires an explicit
depsgraph update.**

**Framing: the hero had to learn to refit, then to refit properly.** Only ORTHO
cameras measured the scene, so the perspective hero cropped the shell off the
bottom at Explosion 1. Perspective refit is now opt-in via a `frame_scene`
property, set on `hero` alone — the Phase 5 close-ups frame a deliberate small
region and must never refit. Getting it right took three passes, and the two
wrong ones are both instructive:

1. Fitting the bounding sphere against the **horizontal** field. On a 16:9 frame
   the vertical field is 9/16 as wide, so the sphere overflowed top and bottom.
   This is Revision 4's `ortho_scale` defect in its perspective form.
2. Fitting the sphere against the narrower field. Correct, and far too loose —
   an exploded cell is a long thin diagonal whose bounding sphere has a 16.5 m
   radius, and the model sat in a third of the frame.
3. Fitting the **actual geometry corners** projected onto the camera's own screen
   axes, closed-form. The scene AABB's corners are phantoms — nothing occupies
   +11 m along X and +12 m up at the same time — so the fit measures ~6000 real
   bounding-box corners instead. The cell now fills 82% of frame height.

`_reframe_ortho` has measured corners since Revision 4. This is finally its
perspective equivalent.

**The 14th QA check.** `check_explosion()` names three silent failures: a part
with no rig parent stays behind (in a 3/4 hero that reads as an artistic choice,
not a bug); a stale or failed driver leaves its group assembled; and a non-zero
`Explosion` at QA time invalidates every clearance assertion in the file. It
walks `obj.parent` to the root, since a child parented by its own module travels
with its parent legitimately.

**Orchestrator.** `--explode` takes one value or a series (`0,0.25,0.5,1`),
rendering every shot once per value and stamping the factor into the filename so
a contact sheet sorts itself. Extracting `_render_shots()` exposed a latent bug:
the loop passed `args.suffix` rather than its own `suffix`, which would have made
every step of a series overwrite the same three files.

**Still true, and now load-bearing:** drivers do NOT export to glTF. Phase 7's
`export/glb.py` must bake the driven transforms to keyframes.

**Known divergence, deferred:** the web viewer carries its own JS explosion built
from the old `EXPLOSION_VECTORS` converted to Y-up. It now disagrees with the
Blender rig on seven distances and knows nothing of the split groups, so its
hooding and busbars still move as single blocks. Re-export and republish belongs
with the Phase 7 GLB work.

**State at the Phase 6 gate:** 757 objects (737 model + 16 rig empties + cameras
and lights), 74 mesh datablocks, 17 materials, 64 388 triangles against the
1 500 000 budget. `spec.py` `_self_check` PASSES. `qa/validate.py` reports **no
defects** across 14 checks, with `Explosion=0.00`. Twelve Cycles plates in
`out/p6gate/` — hero, transverse and longitudinal elevations at 0 / 25 / 50 /
100%.

---

### Revision 9 — Phase 7 polish, motion and delivery export

Three deliverables: two rendered sequences, an animated GLB, and a web viewer
that no longer describes the explosion for itself. Every defect found in this
phase was **invisible in the output** — the files loaded, played and looked
right — and every one of them was caught by measurement.

**The bake, and its two deliberate method choices.** `lib/explode.bake()`
replaces the rig's fifteen drivers with two location keys per empty, because
**drivers do not survive glTF**: the exporter writes node transforms and
animation tracks, and a driver is neither. Two things about how it does that are
load-bearing:

- The samples come from the **evaluated** objects, not re-derived from `spec`. A
  driver's expression is the authority on where its empty goes; computing the
  travel a second time here would let the bake and the rig disagree silently.
- **Both ends are sampled before any driver is removed.** Removing a driver
  frees the channel and leaves whatever value it last wrote, so an interleaved
  sample-then-remove loop reads that residue for every empty after the first and
  bakes a cell that half explodes.

It is destructive to the rig, so it runs only in the export process, never in
one that goes on to save `out/cell.blend`.

**Fifteen clips where there should have been one.** The first animated GLB
carried fifteen glTF animations, one per empty — a file where `animations[0]`
moves the steel shell and nothing else, and which only means anything if a
consumer knows to play all fifteen in lockstep. It loads without complaint.
`export_animation_mode="SCENE"` alone did **not** fix it (it only dropped the
"Action" suffix from the names); `export_anim_scene_split_object=False` is the
other half. Verified by decoding the GLB's JSON and BIN chunks directly: **one
clip named "Scene", fifteen channels**, every travel matching `spec` — anodes
+4400 Z, busbars ∓3000 Y, hooding covers +5800 Z, panels ∓6100 Y, ends ±3000 X,
superstructure +7400 Z, shell −4700 Z, refractory −2400 Z, process +1200 Z,
hardware frame +1900 Z with the flex clamps taking the busbars' ∓3000 Y — and
**no cathode channel**, correct, because it is the datum.

**Two Blender-5 API breaks, both resolved by introspecting the installed build
rather than assuming 4.x idioms** — which is the standing risk Task 0 named:

- `action.fcurves` **does not exist** on 5.2. Blender 4.4 replaced the flat list
  with SLOTTED actions: action → layers → strips → one channelbag per slot. The
  route is `strip.channelbag(animation_data.action_slot).fcurves`. It now lives
  once, in `lib/scene.fcurves()`, because both the bake and the camera tracks
  need it and `lib` may not import `render`.
- `image_settings.media_type` is new in 5.x and **gates the format enum**:
  `FFMPEG` is not among the `file_format` options until the media type is
  `VIDEO`, and assigning it first raises rather than being ignored.

**Blender stamps the rendered frame range onto video filenames** —
`turntable0001-0120.mp4`, not `turntable.mp4`. Sensible for a sequence of takes,
wrong for a deliverable whose name is referenced from a plan and a web page.
`_finish()` derives the stamped name from the range the scene was actually told
to render rather than guessing it.

**The rule that governs both sequences: the camera is framed ONCE, for the worst
frame, and then held.** `cameras.activate()` refits per shot, which is right for
a still and wrong for a sequence — a camera that refits every frame breathes in
and out as the subject's projection changes, and on the explode that breathing is
larger than the motion being shown. So `cameras.required_distance()` was made
public (a turntable whose framing rule differs from the stills is one that crops
what the stills showed), and each sequence asks every frame it is about to render
what distance it needs, takes the maximum, and does not move again.

- **Turntable, two passes.** Pass one puts the camera at each azimuth and asks;
  pass two lays the real track at the single largest answer. A radius that varies
  with azimuth is a camera that dollies in and out twice per revolution, which
  reads as a mistake even when deliberate.

  **Two corrections to what this paragraph used to claim**, both from asking pass
  one its own question at 15° steps rather than reasoning from the shell
  dimensions:

  - It said end-on needs "roughly three times" the distance broadside does,
    reasoning from 16.4 m long against 4.8 m wide. Measured, it is **33.51 m
    against 24.72 m — a factor of 1.36, not 3**. Required distance is not
    proportional to the longest dimension: the cell's own 5.06 m height and the
    22° camera elevation put a floor under the broadside figure that the plan
    aspect ratio knows nothing about. The *direction* was right — end-on is the
    hungry azimuth, and holding its radius means broadside sits smaller than it
    could — but the magnitude was invented.
  - The bounding box being orbited is **17.18 × 6.53 × 5.06 m**, not the
    16.38 × 4.83 × 1.52 m shell: busbars, superstructure and gas offtake all
    stand outside the steel.

  And the finding that justifies the two passes existing at all: the largest
  answer comes from **azimuth 195°, at 34.10 m** — not from 180°, which needs
  33.51 m. The cell is not symmetric in plan (risers on the upstream face, the
  offtake at one end), so the hungriest viewpoint is not one a person would have
  guessed and picked by hand. A shortcut that framed on the end-on azimuth would
  have under-framed the real worst case by 0.6 m.

  Verified from the delivered track by re-rendering four azimuths on a
  transparent film: 0° and 180° measure 27.7% of frame width × 67.6% of height,
  90° and 270° measure 61.5% × 41.7%, and **all four are clear of every frame
  edge** — which is the thing the two-pass radius exists to guarantee.
- **`_unwrap()`.** `to_track_quat().to_euler()` returns each rotation in its own
  principal range, so somewhere in a revolution a channel steps from +π to −π.
  Keyframed as-is, that step interpolates and the camera whips through a full
  reverse revolution between two frames. Measured after the fix: the largest
  euler step between consecutive frames is exactly one orbit step.
- **The explosion runs 1 → 0, not 0 → 1.** An exploded diagram answers "what is
  in there"; an assembly animation answers "how does it go together", and the
  second is the more useful of the two from the same keyframes. Holds at both
  ends use `AUTO_CLAMPED` handles, or the interpolator overshoots past 1.0 and
  past 0.0 and every subsystem visibly bounces.
- **Accepted cost, and a correction to how it was stated.** An earlier draft of
  this revision said the assembled cell "fills 67% of the frame" at the end of
  the sequence. That number was a **distance ratio** — required distance over
  held distance — and a distance ratio flatters, because it is linear where
  frame area is quadratic. Measured properly instead, by re-rendering five
  frames of the exact sequence setup on a transparent film and counting alpha
  pixels:

  | frame | Explosion | bbox, % of frame W × H | subject, % of frame area |
  |---|---|---|---|
  | 1 | 1.000 | 46.6 × **80.6** | 16.5 |
  | 40 | 0.894 | 44.5 × 76.3 | 15.3 |
  | 75 | 0.506 | 36.6 × 61.5 | 11.2 |
  | 110 | 0.114 | 28.8 × 46.7 | 7.2 |
  | 150 | 0.000 | 27.5 × **42.2** | 6.1 |

  So the framing rule does what Revision 8 claimed at the wide end — 80.6% of
  frame height at Explosion 1.0, against the 82% measured for the hero still —
  and the assembled cell ends at **42% of frame height, 6% of frame area**, not
  67% of anything. That is the real cost of framing once and holding.

  Two separate things are visible in that table and only one is a trade:

  - The **height** falling 80.6 → 42.2% is the trade, and it is the right one
    for an assembly shot: it shows parts converging on a place, where a camera
    pushing in as the model contracts would double the apparent motion.
  - The **width** is waste, not a trade. Even at its widest the subject uses
    46.6% of a 16:9 frame — more than half the width is grey in every frame of
    the sequence, because an exploded cell is a tall diagonal and the fit is
    height-limited throughout. A squarer delivery frame recovers that directly,
    and is the one change to these sequences worth offering.

  Keying the subject off the background was tried first and was wrong: the world
  ramp runs along world Z, so its iso-lines are not image rows and a per-row
  median is not the background — it reported every frame as 100% × 100%.
  Transparent film needs no key and no threshold.

**`shots.use_motion()`** — Cycles at 1080p/64 samples with denoising forced on,
against the hero plate's 1440p/256. A still is looked at for a minute and a frame
of video for a thirtieth of a second; more to the point, per-frame noise is the
one artifact video compression cannot hide, because it is different every frame
and eats the bitrate and the motion with it.

**Not decimating, and why.** `--decimate RATIO` exists and is off. The model is
140 556 triangles against a 1 500 000 budget, so there is nothing to win, and
COLLAPSE rounds exactly the machined edges — stub sockets, rib returns, the ledge
taper — that the Phase 3 detail passes existed to produce.

**The QA triangle budget was measuring the wrong mesh.** It fanned out
`obj.data.polygons` — the authored cage, before the booleans, bevels, solidifies
and arrays. That undercounts by more than half: **64 388 authored against 140 556
in the exported GLB**, because the export applies modifiers and the browser gets
the result. A budget check that measures something other than the delivered file
can pass while the delivery fails. It now counts the evaluated mesh and prints
both. The corrected figure was confirmed independently from the other end —
loading the delivered page in Node and counting its geometry gave 140 556 exactly.

**The turntable was twice as fast as it should be.** Measured from the MP4
container rather than watched: avc1, 1920×1080, 120 samples, 4.000 s — a 90°/s
revolution. On a 16.4 m pot the end-on to broadside transition passes in under a
second. The default is now **240 frames / 8 s / 45° per second**. Render time is
linear in the count and the machine is otherwise idle.

Re-rendered and re-measured from the container: **avc1, 1920×1080, 240 samples,
8.000 s — 30.000 fps, 45.0° per second.** `_finish()` renamed
`turntable0001-0240.mp4` correctly.

#### The viewer, resynced

The page carried its own JS explosion, built from a converted copy of
`EXPLOSION_VECTORS`. By the Phase 6 gate it disagreed with the model on seven
distances and knew nothing of the three subsystems that split into more than one
motion, so its hooding, busbars and hardware still moved as single blocks. That
table is **deleted**. The page now embeds the animated GLB and its slider scrubs
the baked clip, so `spec.py` is the single description of how this cell comes
apart and it reaches the browser through the model.

**Scrubbing an `AnimationMixer` has two silent traps, both measured in Node
against the real file before either could ship:**

- **`mixer.setTime()` does nothing at all to a PAUSED action.** Pausing sets the
  effective time scale to zero, so the delta is multiplied away and the action
  never leaves the first frame. This was my first implementation, and it is
  perfectly inert: the page loads, the slider moves, the readout updates, and the
  cell simply never comes apart.
- Unpaused, **`setTime(duration)` lands exactly on the loop point** of a
  `LoopRepeat` action and wraps to zero — so the far end of the slider snaps back
  to assembled.

Writing `action.time` directly and updating by a zero delta sidesteps both: no
time scale is applied to zero, and no loop boundary is crossed. Four candidate
recipes were tested side by side against a probe anode; two were wrong in exactly
the two ways above.

**The bake is LINEAR, against Blender's bezier default.** This clip is not a
performance, it is a **lookup table**: the slider scrubs it, so time *t* through
the clip has to mean explosion *t* — the same number `--explode t` renders. Under
the default bezier, measurement put the quarter mark at **14%** of travel and the
three-quarter mark at **84%**, so the page and the plates would have disagreed
about what "25%" means. The delivery MP4 keeps its easing; it is keyed
separately, on the control property, in `render/anim.py`.

**The bake starts at frame 0, not frame 1**, because the exporter times every key
at its absolute `frame / fps`: over 1..60 the assembled key lands at 0.042 s
inside a clip that starts at 0, giving a dead zone at the bottom of the slider
and 49.2% of travel where the slider reads 50%. From frame 0 the mapping is exact
— measured 0 → 1100 → 2200 → 3300 → 4400 mm across the anode travel.

**`tools/embed_glb.py`** replaces the page's base64 payload, locating it by its
`const b64 = "` prefix rather than by line number. The viewer is deliberately one
file with the model inside it, so it opens from the filesystem with no server and
no CORS — which makes republishing a mechanical edit of one 4.5 MB line, exactly
the kind of edit that gets done by hand correctly once and never again.

**The delivered page was verified end to end**, not the source GLB: the base64
was pulled back out of the html, parsed with the same loader the page uses, and
scrubbed with the exact recipe the page now contains. 723 parts, **0 meshes
unmatched** by the subsystem grouping, 0 without a material, 140 556 triangles;
every subsystem moves at Explosion 1 except the cathode datum, and all three
split subsystems mirror — hooding spanning 3000..6100 mm and hardware
1900..3000 mm, matching the Revision 8 table exactly.

**Still true and still deferred:** no browser exists on this machine (Chrome is
absent, so both the devtools and Playwright MCP servers fail), so the page has
been verified by loading its payload in Node, not by looking at it.

**The delivered `.blend` was opened, not assumed.** Every other check in this
phase ran against a freshly built scene. `out/cell.blend` is a different
artefact: written by one process, opened by another, and the two failures that
would make it worthless — drivers saved dead, or the file saved mid-explosion so
that every clearance assertion in it measures a cell that is flying apart — are
both invisible until someone opens it. Opened: **757 objects (728 mesh, 17
empty), 74 mesh datablocks, 17 materials, 13 collections, 15 driver channels all
of which fire, `Explosion` saved at 0.0, zero empties off-origin, and zero
actions** — the rig in the master file is drivers, as intended, and the bake
exists only in the export process.

That check found its own defect first, and it is the Revision 8 hazard wearing a
different hat: the probe reported **fifteen dead drivers**. Assigning an ID
custom property does **not** flag the depsgraph, so the drivers reading it are
never re-evaluated and every empty reports its previous position. No error, no
warning — a perfectly confident false Critical against a file that was fine.
`lib/explode.set_explosion()` has called `update_tag()` since it was written;
the probe had to learn it too. **The rule generalises: in this codebase, writing
a value that drivers depend on requires an explicit `update_tag()`, exactly as
reading a transform you did not just write requires an explicit depsgraph
update.**

#### Correction to the Revision 8 state figures

Revision 8 records "16 rig empties". The object count it reports, 757, is right;
the description is not. `10_EXPLOSION` holds **17** empties: one master carrying
the `Explosion` property plus **16** group empties, of which **15** carry
drivers. The sixteenth group is the cathode, which is the explosion datum and
correctly has no driver — that is why the glTF clip has fifteen channels and not
sixteen. Recorded here rather than edited into Revision 8, which describes what
was measured at its own gate.

#### State at the Phase 7 gate

| | |
|---|---|
| objects in tree | 757 (728 mesh + 17 rig empties, plus cameras and lights) |
| mesh datablocks | 74 |
| materials | 17 in file, 17 used, 723 objects painted |
| parented to the rig | 728 |
| triangles | **140 556 evaluated** (what the GLB carries) / 64 388 authored, against a 1 500 000 budget |
| `spec.py` `_self_check` | PASSES |
| `qa/validate.py` | **no defects** across 14 checks, at `Explosion=0.00` |

Delivery artefacts:

| file | what it is |
|---|---|
| `out/cell.blend` | 222 KB — the master. Live drivers, no baked actions, saved assembled |
| `out/cell.glb` | 3.25 MB — static, materials, no animation |
| `out/cell_anim.glb` | 3.27 MB — one "Scene" clip, 15 channels, linear, frame 0 start |
| `out/cuve400.html` | 4.59 MB — single file, model embedded, opens with no server |
| `out/p7gate/turntable.mp4` | 3.94 MB — avc1 1920×1080, 240 frames, 8.000 s, 45°/s |
| `out/p7gate/explosion.mp4` | 4.72 MB — avc1 1920×1080, 150 frames, 5.000 s |

Both sequences rendered on `OPTIX:NVIDIA GeForce RTX 5060 Laptop GPU`, and both
were verified twice over: once from the MP4 container, which is the only witness
to what was encoded on a machine with no ffprobe and no player, and once by
re-rendering frames of the identical setup as stills — because a container says
nothing about whether the camera was pointed at the cell.

#### The delivery frame — 4:3, measured rather than chosen

The 16:9 finding above (46.6% of frame width at the widest moment, so more than
half the frame grey in every frame of both sequences) is real, but "make it
squarer" does not follow from it on its own. The two sequences have different
subjects: the explosion holds one shape for five seconds, while the turntable's
subject changes aspect continuously through the revolution and its single held
radius is set by the worst case. A frame that suits one can starve the other.

So the three candidates were rendered rather than argued about — the governing
frames of each sequence, on a transparent film, alpha bounding box counted:

| subject as % of frame **area** | 16:9 | 4:3 | 1:1 |
|---|---|---|---|
| explosion, at Explosion 1.0 | 16.5 | 21.4 | **27.9** |
| explosion, at Explosion 0.0 | 6.1 | 7.9 | **10.2** |
| turntable, end-on | 13.9 | **17.4** | 16.8 |
| turntable, broadside | 18.7 | **22.3** | 20.9 |

**1:1 is the best frame the explosion could have and the wrong one for the
turntable.** The explosion's own bounding box is about 1.03:1, so a square frame
nearly doubles its subject area against 16:9 while costing three points of
height. The turntable runs from roughly 0.7:1 end-on to 2.6:1 broadside, and
squaring the frame makes **broadside** the binding constraint instead of end-on:
the worst azimuth jumps from 195° to 55° and the radius stops shrinking usefully,
so 1:1 comes out *worse than 4:3* at both viewpoints.

**4:3 is the one aspect that improves both** — +30% subject area on the
explosion, +19% on the turntable — so the delivery set stays a single shape
rather than shipping two videos of different proportions to make one of them
optimal. `shots.use_motion()` now defaults to 1440 × 1080 and carries the table;
`--anim-aspect {4:3,16:9,1:1}` overrides it. Height is held at 1080 and width
follows, so the choice changes the frame's shape and not its class.

Recorded because it is the obvious thing to "fix" later: someone reading only
the first finding will square the frame, improve the explosion, quietly degrade
the turntable, and have no way of knowing they did.

#### The 4:3 delivery set, verified the same two ways

Re-rendered to `out/p7final/`; `out/p7gate/` keeps the 16:9 pair so the change is
comparable rather than asserted. Containers, read from the boxes:

| | `turntable.mp4` | `explosion.mp4` |
|---|---|---|
| | avc1 **1440 × 1080** | avc1 **1440 × 1080** |
| | 240 frames, 8.000 s, 30.000 fps | 150 frames, 5.000 s, 30.000 fps |
| | 45.0°/s | — |
| | 3.48 MB | 3.96 MB |

And the content, re-rendered from the identical setup on a transparent film:

- **Turntable** — 0° and 180° measure 36.4% W × 65.2% H, 90° and 270° measure
  77.8% × 39.3%, all four **clear of every frame edge**. The single held radius
  survives the reshape, which is the one thing squaring a frame could have
  broken: the aspect change moves which azimuth is hungriest.
- **Explosion** — 21.4% of frame area at Explosion 1.0 and 7.9% at 0.0, matching
  the predicted 4:3 column exactly. Alpha margins at frame 1 are L 151, R 132,
  B 34, T 79 px of 720 × 540.

**A probe defect worth recording, because it cried Critical on a good file.**
The framing probe classifies a frame by `need > have + 1e-6`. At explosion frame
1 the camera is at *precisely* the distance Explosion 1.0 demands — that is what
"framed once for the worst frame" means — so `need` and `have` are the same
number to within float error and the test tipped to `CROPS` at 44.52 m of
44.52 m. The rendered pixels say otherwise on all four edges. **A strict
inequality is the wrong test for a quantity that is designed to be exactly
equal**; the tolerance belongs in the probe, and the delivery was never at risk.
Third time this phase that an alarming finding was a defect in the measurement
rather than in the model — after the background-median key and the missing
`update_tag()`.

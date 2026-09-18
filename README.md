# Cuve 400 — a parametric 400 kA aluminium electrolysis cell

A complete 3D model of a single **modern prebake Hall-Héroult aluminium
reduction cell** ("Marc-400" class, 400 kA), built as a suite of parametric
Python `bpy` scripts rather than as a hand-modelled `.blend`.

One command rebuilds the whole cell from an empty scene, deterministically:
**757 objects, 74 mesh datablocks, 17 materials, 140 556 triangles.** Every
dimension comes from one frozen datasheet — `spec.py` — and no module contains a
numeric literal.

From that single source it produces orthographic plates, a hero render, a
reversible transverse cutaway, an exploded series driven by one float, two MP4
sequences, a glTF export with the assembly baked to a real animation clip, and a
single-file interactive web viewer that opens with no server.

The pot itself is dimensioned from published literature (Dupuis,
*Thermo-Electric Design of a 740 kA Cell*, Table 1, 400 kA column); the
superstructure and hooding above the shell rim are plausible-class and marked
`# ASSUMED` in the datasheet. It cross-checks: Faraday's law at 400 kA and 93.4%
current efficiency gives 3.01 t/cell-day, the published figure for a real pot of
this class.

## Getting started

```bash
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"

"$B" --background --python build_all.py                      # build
"$B" --background --python build_all.py -- --render all --hero --save
"$B" --background --python qa/validate.py                    # 14 checks
```

## Documentation

| | |
|---|---|
| **[AGENTS.md](AGENTS.md)** | **Start here.** What this is, how to run it, the architecture rules, and the traps that produce silently wrong output rather than errors. |
| [docs/DESIGN_HISTORY.md](docs/DESIGN_HISTORY.md) | The nine-revision design record: every defect found, its cause, and why each fix is the way it is. |
| [tools/API_NOTES.md](tools/API_NOTES.md) | Real Blender 5.2 API signatures, confirmed by introspection rather than assumed from 4.x. |
| [astra_blender_electrolysis_cell_production_prompt.md](astra_blender_electrolysis_cell_production_prompt.md) | The original brief, kept unmodified for provenance. |

Build output goes to `out/`, which is gitignored — it regenerates from source.

## Scope

One cell, not a row. Busbars and the gas duct terminate in clean stubs; there is
no potroom, adjacent cell, crane, or gas treatment plant.

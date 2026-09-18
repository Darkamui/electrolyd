# CLAUDE.md

Read [AGENTS.md](AGENTS.md) first — it is the orientation document for this
repository and covers what the project is, who it is for, how to run it, and the
traps that produce silently wrong output rather than errors.

Then read [docs/DESIGN_HISTORY.md](docs/DESIGN_HISTORY.md) before making any
structural change. It records every defect found across the build and why each
fix is the way it is; several entries exist specifically to stop a later reader
"fixing" something back.

Two habits this repository runs on, stated here because they are easy to skip:

- **Measure, don't assert.** Do not validate geometry, framing or output by eye
  or by proxy. Nearly every claim in this project's history that was reasoned
  rather than measured turned out wrong.
- **Never put a numeric dimension in a module.** `spec.py` is the single source
  of every dimension, and any quantity that must fit inside another is derived
  from it rather than chosen.

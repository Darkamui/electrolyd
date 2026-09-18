"""
Re-embed a GLB into the single-file web viewer.

    python tools/embed_glb.py [--glb out/cell_anim.glb] [--page out/cuve400.html]

The viewer is deliberately ONE file with the model inside it as base64, so it
opens from the filesystem with no server and no CORS. That makes re-publishing
after a model change a mechanical edit of one very long line, which is exactly
the kind of edit that gets done by hand once and then never again correctly.

The line is located by its `const b64 = "` prefix rather than by number, and the
old payload is never parsed — only replaced. Nothing else in the page is touched.
"""

from __future__ import annotations

import argparse
import base64
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = 'const b64 = "'


def main() -> int:
    p = argparse.ArgumentParser(prog="embed_glb")
    p.add_argument("--glb", default=os.path.join(ROOT, "out", "cell_anim.glb"))
    p.add_argument("--page", default=os.path.join(ROOT, "out", "cuve400.html"))
    args = p.parse_args()

    with open(args.glb, "rb") as fh:
        payload = base64.b64encode(fh.read()).decode("ascii")

    with open(args.page, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    hits = [i for i, line in enumerate(lines) if line.lstrip().startswith(PREFIX)]
    if len(hits) != 1:
        raise SystemExit(
            f"expected exactly one {PREFIX!r} line in {args.page}, found {len(hits)}"
        )

    index = hits[0]
    was = len(lines[index])
    lines[index] = f'{PREFIX}{payload}";\n'
    with open(args.page, "w", encoding="utf-8") as fh:
        fh.writelines(lines)

    print(f"   {os.path.relpath(args.glb, ROOT)} "
          f"({os.path.getsize(args.glb) / 1048576.0:.2f} MB) "
          f"-> {os.path.relpath(args.page, ROOT)} line {index + 1}")
    print(f"   payload {was} -> {len(lines[index])} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

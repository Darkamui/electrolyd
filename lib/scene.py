"""
Scene skeleton: collection tree, naming discipline, and the BuildContext that
every module receives.

Naming convention, enforced here and asserted by QA:

    {NN}_{SUBSYSTEM}_{part}_{index:03d}

    01_SHELL_plate_000        03_CATHODE_block_017
    05_ANODES_stem_004        08_HOODING_panel_011

Rationale: the numeric prefix sorts the outliner into build order, the
subsystem token lets QA attribute every object to exactly one owner, and the
zero-padded index keeps repeated parts adjacent and sortable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import bpy

import spec

NAME_RE = re.compile(r"^\d{2}_[A-Z_]+_[a-z0-9_]+_\d{3}$")


# ---------------------------------------------------------------------------


def clear_scene() -> None:
    """
    Reset to a genuinely empty scene.

    Uses read_factory_settings rather than deleting objects, because deletion
    leaves orphaned meshes, materials and collections behind. QA asserts on
    orphan counts, so a half-clean scene produces false failures.
    """
    bpy.ops.wm.read_factory_settings(use_empty=True)

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0


def build_collection_tree() -> dict[str, bpy.types.Collection]:
    """
    Create the 13 top-level collections from spec.COLLECTIONS.

    Idempotent: returns existing collections if already present.
    """
    root = bpy.context.scene.collection
    out: dict[str, bpy.types.Collection] = {}
    for name in spec.COLLECTIONS:
        coll = bpy.data.collections.get(name)
        if coll is None:
            coll = bpy.data.collections.new(name)
        if coll.name not in {c.name for c in root.children}:
            root.children.link(coll)
        out[name] = coll
    return out


def part_name(collection: str, part: str, index: int = 0) -> str:
    """
    Build a conforming object name.

        part_name("03_CATHODE", "block", 17) -> "03_CATHODE_block_017"

    `collection` is the full collection name including its numeric prefix, so
    the object name and its owning collection can never disagree.
    """
    name = f"{collection}_{part}_{index:03d}"
    if not NAME_RE.match(name):
        raise ValueError(
            f"name {name!r} violates the convention "
            f"{{NN}}_{{SUBSYSTEM}}_{{part}}_{{index:03d}}"
        )
    return name


def owning_collection(obj_name: str) -> str:
    """Recover the collection an object claims, from its name prefix."""
    m = re.match(r"^(\d{2}_[A-Z_]+?)_[a-z0-9_]+_\d{3}$", obj_name)
    if not m:
        raise ValueError(f"unparseable object name {obj_name!r}")
    return m.group(1)


def fcurves(obj: bpy.types.Object) -> list[bpy.types.FCurve]:
    """
    Every F-curve of an object's active action.

    Blender 4.4 replaced the flat `action.fcurves` list with SLOTTED actions —
    an action holds layers, a layer holds strips, and a strip holds one
    channelbag per slot. `action.fcurves` does not exist at all on 5.2, so the
    old one-liner raises AttributeError rather than degrading. The route through
    `animation_data.action_slot` is the supported one; the fallback is kept for
    a legacy action, which `keyframe_insert` will not create here but a loaded
    .blend might.

    It lives in `scene` rather than beside either caller because both the
    explosion bake and the camera tracks need it, and `lib` may not import
    `render`.
    """
    ad = obj.animation_data
    if ad is None or ad.action is None:
        return []
    action = ad.action
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    out: list[bpy.types.FCurve] = []
    for layer in action.layers:
        for strip in layer.strips:
            bag = strip.channelbag(ad.action_slot)
            if bag is not None:
                out.extend(bag.fcurves)
    return out


# ---------------------------------------------------------------------------


@dataclass
class BuildContext:
    """
    Handed to every module's build(). The module's single window onto the
    scene and the datasheet.

    A module must:
      * read dimensions ONLY from ctx.cell
      * link objects ONLY into its own collection, via ctx.link()
      * name objects ONLY via ctx.name()
    """

    cell: spec.Cell = field(default_factory=lambda: spec.CELL)
    collections: dict[str, bpy.types.Collection] = field(default_factory=dict)
    collection: str = ""
    """The collection the currently-building module owns."""

    created: list[bpy.types.Object] = field(default_factory=list)

    # -- scoping -----------------------------------------------------------

    def for_collection(self, name: str) -> "BuildContext":
        """Return a context scoped to one collection. Modules get this."""
        if name not in self.collections:
            raise KeyError(f"unknown collection {name!r}")
        return BuildContext(
            cell=self.cell,
            collections=self.collections,
            collection=name,
            created=[],
        )

    # -- the two operations a module is allowed --------------------------

    def name(self, part: str, index: int = 0) -> str:
        """Conforming name inside the owned collection."""
        if not self.collection:
            raise RuntimeError("BuildContext is not scoped to a collection")
        return part_name(self.collection, part, index)

    def link(self, obj: bpy.types.Object) -> bpy.types.Object:
        """
        Link an object into the owned collection, unlinking it from anywhere
        else. Guards against a module leaking objects into another's space.
        """
        if not self.collection:
            raise RuntimeError("BuildContext is not scoped to a collection")

        claimed = owning_collection(obj.name)
        if claimed != self.collection:
            raise ValueError(
                f"object {obj.name!r} claims collection {claimed!r} but is "
                f"being linked into {self.collection!r}"
            )

        for coll in list(obj.users_collection):
            coll.objects.unlink(obj)
        self.collections[self.collection].objects.link(obj)
        self.created.append(obj)
        return obj

    def discard(self, obj: bpy.types.Object) -> None:
        """
        Delete an object created through this context, and forget it.

        For scaffolding that has done its job — chiefly a cutter whose boolean
        build.carve() has already baked into a mesh. Leaving it linked would
        put an invisible box in the outliner and in the object count; removing
        it without this would leave a dead reference in `created`, and the next
        module to touch that list would get a ReferenceError rather than
        anything that names the cause.
        """
        me = obj.data if obj.type == "MESH" else None
        try:
            self.created.remove(obj)
        except ValueError:
            pass
        for coll in list(obj.users_collection):
            coll.objects.unlink(obj)
        bpy.data.objects.remove(obj)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def new_context() -> BuildContext:
    """Fresh scene + collection tree + root context."""
    clear_scene()
    colls = build_collection_tree()
    return BuildContext(cell=spec.CELL, collections=colls)

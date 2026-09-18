"""
Material library and assignment.

Phase 5. Materials are kept strictly separate from geometry: no module builds
a material, and no module names one. Everything lives here, in two tables:

    SPECS       material name -> Principled BSDF values
    ASSIGNMENT  part family   -> material name

A "part family" is an object name with its index stripped, so
`05_ANODES_stub_107` belongs to the family `05_ANODES_stub`. Assignment
therefore rides on the naming convention that lib/scene.py already enforces,
which means a new part cannot quietly arrive unpainted: `apply()` raises on
any family it has never been told about.

WHY A CENTRAL TABLE RATHER THAN PER-MODULE ASSIGNMENT
    A module knows what it built; it does not know what the cell is made of.
    Putting the whole mapping in one place makes "what is this pot made of?"
    a single readable file, lets a reviewer check it without opening nine
    modules, and keeps materials out of the delegated module contract.

THE PROMPT'S TEN, AND WHAT WAS ADDED
    The production prompt asks for ten materials. All ten are here. Seven more
    were added, each because two parts that are genuinely different substances
    were otherwise going to render identically and the construction would read
    wrong:

      painted / oxidized steel   split in two. The prompt lists these as one
                                 item, but a heat-stained pot shell and a
                                 painted portal frame are not the same object
                                 in a photograph, and the shell is the larger
                                 surface.
      galvanised steel           the hooding. The user's potroom reference is
                                 bright ribbed metal, not paint; Revision 2
                                 called that the cell's dominant signature.
      cast iron                  the anode stubs. Revision 5 deferred exactly
                                 this: "cast iron against carbon in Phase 5
                                 will separate them."
      graphite                   graphitised cathode block, against the baked
                                 carbon of the anode. Different process,
                                 different look, and the section shows both.
      ramming paste              the seams between cathode blocks. A whole
                                 band of it reads in section.
      silicon carbide            the sidewall blocks, against firebrick.
      alumina                    the cover blanket and the dry barrier. White
                                 powder; nothing else in the cell looks it.

    The ledge deliberately shares the crust material. Both are frozen bath -
    the same substance, one against the wall and one on the surface - and
    showing them as one material is itself explanatory.

COLOUR
    Every colour below is written as an sRGB hex string because that is what
    a human can read and check. Blender wants LINEAR, so `_srgb()` converts.
    Hex straight into a socket is the classic washed-out-material bug.

API NOTE (Blender 5.2.1)
    Principled BSDF socket names follow the 4.x scheme, probed on this build:
    'Emission Color' and 'Emission Strength' (not 'Emission'), 'Specular IOR
    Level' (not 'Specular'), 'Transmission Weight' (not 'Transmission').
    `Material.use_nodes` is deprecated for removal in Blender 6.0, so it is
    only touched when a material somehow arrives without a node tree.
"""

from __future__ import annotations

import bpy

# ---------------------------------------------------------------------------
# Material definitions
# ---------------------------------------------------------------------------

# Keys map onto Principled BSDF sockets. `emit`/`emit_strength` are a
# convenience pair for 'Emission Color' / 'Emission Strength'.
SPECS: dict[str, dict] = {
    # -- steels -------------------------------------------------------------
    # metallic 1.0 / roughness 0.42 made this a mirror, and a mirror in a
    # scene with no surroundings is a coin toss: of the five IDENTICAL breaker
    # cylinders in the hero, one caught the key's specular sweep and read as
    # steel while the other four read as black holes. Nothing about the parts
    # differed - only which way they happened to face.
    #
    # Bare mild steel in a potroom is not a mirror anyway. It carries mill
    # scale and alumina dust, which is an oxide skin over the metal: hence the
    # lower metallic and the broader highlight. The material now reads the
    # same from every direction, which is what a validation plate needs.
    "structural_steel": dict(
        color="#797E83", metallic=0.72, roughness=0.55,
        note="collector bars, hardware, feeder mechanism",
    ),
    "oxidized_steel": dict(
        color="#5A4F47", metallic=0.85, roughness=0.74,
        note="pot shell - heat-stained, never painted, runs hot all its life",
    ),
    "painted_steel": dict(
        color="#5D6F73", metallic=0.0, roughness=0.55, coat=0.18,
        coat_roughness=0.35,
        note="portal frame and feeder stack - works cool enough to hold paint",
    ),
    "galvanised_steel": dict(
        color="#A7ADB1", metallic=1.0, roughness=0.30,
        note="hooding - bright ribbed sheet, the cell's dominant signature",
    ),
    # Lightened and de-metallised from the first draft after the mat plates.
    # At #4A4744 / metallic 0.9 the stubs vanished into the carbon: a metal
    # that dark returns almost nothing from a dark environment, so the sockets
    # read as empty holes - exactly the artifact Revision 5 expected materials
    # to resolve. Cast iron out of a mould is SCALED, not polished; the scale
    # is a dielectric skin over the metal, which is what the lower metallic
    # says. It now separates from the block at every light level.
    "cast_iron": dict(
        color="#6E675E", metallic=0.55, roughness=0.68,
        note="anode stubs, cast into the block's sockets",
    ),
    # -- conductors ---------------------------------------------------------
    "aluminium": dict(
        color="#C4C6C8", metallic=1.0, roughness=0.30,
        note="anode rods, yokes, clamps, busbars, the anode beam itself",
    ),
    "copper": dict(
        color="#9C5B3C", metallic=1.0, roughness=0.36,
        note="flexible connectors, collector bar to collector busbar",
    ),
    # -- carbon -------------------------------------------------------------
    # #1E1C1B is 1.2% linear - under AgX the whole block crushed to a flat
    # silhouette with no form in it, and a plate that cannot show the form of
    # the part is not a validation plate. Carbon is dark, not black.
    "carbon_anode": dict(
        color="#2C2926", metallic=0.0, roughness=0.80,
        note="prebaked anode block - matte, slightly open-pored",
    ),
    "graphite": dict(
        color="#26282A", metallic=0.35, roughness=0.42,
        note="graphitised cathode block - denser and glossier than the anode",
    ),
    "ramming_paste": dict(
        color="#2A2523", metallic=0.0, roughness=0.94,
        note="seams between cathode blocks and the perimeter band",
    ),
    # -- lining -------------------------------------------------------------
    "refractory_brick": dict(
        color="#A8724A", metallic=0.0, roughness=0.90,
        note="firebrick courses and the backing behind the SiC",
    ),
    "silicon_carbide": dict(
        color="#3C4247", metallic=0.10, roughness=0.62,
        note="sidewall blocks - dense, dark, nothing like firebrick",
    ),
    "insulation_board": dict(
        color="#D8CFBE", metallic=0.0, roughness=0.96,
        note="calcium silicate, the bottom-most course",
    ),
    "alumina": dict(
        color="#E2E0DA", metallic=0.0, roughness=0.97,
        note="cover blanket and dry barrier - white powder, reads as powder",
    ),
    # -- process ------------------------------------------------------------
    # The pot runs near 960 C. Emission is not decoration here: an unlit
    # metal pad reads as a grey slab, which is exactly what it is not.
    #
    # Strengths cut from 2.2 / 3.4 after the mat plates. Emission above ~1.5
    # runs past AgX's shoulder, where every hue desaturates toward white: the
    # metal pad and the bath both came out the same pale peach and could not
    # be told apart, which defeats the reason for lighting them at all. Below
    # the shoulder the two hues survive, and the bath stays the brighter of
    # the pair - which is correct, it is the hotter, thinner layer.
    "molten_aluminium": dict(
        color="#E8E2D8", metallic=0.75, roughness=0.20,
        emit="#FF9A40", emit_strength=0.9,
        note="the metal pad, tapped daily",
    ),
    "electrolyte": dict(
        color="#E8913C", metallic=0.0, roughness=0.34,
        emit="#FF7A1E", emit_strength=1.5,
        note="molten cryolite bath",
    ),
    "crust": dict(
        color="#8E8478", metallic=0.0, roughness=0.95,
        note="frozen bath - the top crust AND the sidewall ledge, same stuff",
    ),
}

# ---------------------------------------------------------------------------
# Part family -> material
# ---------------------------------------------------------------------------

ASSIGNMENT: dict[str, str] = {
    # -- 01 shell: hot, unpainted, stained -----------------------------------
    "01_SHELL_plate": "oxidized_steel",
    "01_SHELL_wall_side": "oxidized_steel",
    "01_SHELL_wall_end": "oxidized_steel",
    "01_SHELL_cradle": "oxidized_steel",
    "01_SHELL_end_cradle": "oxidized_steel",
    "01_SHELL_flange": "oxidized_steel",

    # -- 02 refractory: the lining, coldest at the bottom ---------------------
    "02_REFRACTORY_insulation": "insulation_board",
    "02_REFRACTORY_firebrick": "refractory_brick",
    "02_REFRACTORY_side_backing": "refractory_brick",
    "02_REFRACTORY_end_backing": "refractory_brick",
    "02_REFRACTORY_side_sic": "silicon_carbide",
    "02_REFRACTORY_end_sic": "silicon_carbide",
    "02_REFRACTORY_bedding": "alumina",
    "02_REFRACTORY_ledge": "crust",

    # -- 03 cathode -----------------------------------------------------------
    "03_CATHODE_block": "graphite",
    "03_CATHODE_bar": "structural_steel",
    "03_CATHODE_ramming": "ramming_paste",

    # -- 04 process -----------------------------------------------------------
    "04_PROCESS_metal": "molten_aluminium",
    "04_PROCESS_bath": "electrolyte",
    "04_PROCESS_crust": "crust",
    "04_PROCESS_cover": "alumina",

    # -- 05 anodes: three substances in one assembly --------------------------
    "05_ANODES_block": "carbon_anode",
    "05_ANODES_stub": "cast_iron",
    "05_ANODES_yoke": "aluminium",
    "05_ANODES_stem": "aluminium",
    "05_ANODES_clamp": "aluminium",

    # -- 06 busbars -----------------------------------------------------------
    "06_BUSBARS_riser": "aluminium",
    "06_BUSBARS_arm": "aluminium",
    "06_BUSBARS_collector": "aluminium",
    "06_BUSBARS_flex": "copper",

    # -- 07 superstructure ----------------------------------------------------
    # The anode beam is a conductor, not structure - it is the busbar every
    # anode clamps onto. Painting it would say the opposite.
    "07_SUPERSTRUCTURE_beam": "aluminium",
    "07_SUPERSTRUCTURE_column": "painted_steel",
    "07_SUPERSTRUCTURE_cross": "painted_steel",
    "07_SUPERSTRUCTURE_deck_rail": "painted_steel",
    "07_SUPERSTRUCTURE_hopper": "painted_steel",
    "07_SUPERSTRUCTURE_chute": "structural_steel",
    "07_SUPERSTRUCTURE_breaker": "structural_steel",
    "07_SUPERSTRUCTURE_chisel": "structural_steel",
    "07_SUPERSTRUCTURE_duct": "galvanised_steel",
    "07_SUPERSTRUCTURE_throat": "galvanised_steel",

    # -- 08 hooding -----------------------------------------------------------
    "08_HOODING_panel": "galvanised_steel",
    "08_HOODING_rib": "galvanised_steel",
    "08_HOODING_cover": "galvanised_steel",
    "08_HOODING_end_box": "galvanised_steel",
    "08_HOODING_end_rib": "galvanised_steel",
    "08_HOODING_side_rib": "galvanised_steel",
    "08_HOODING_end_cap": "galvanised_steel",
    "08_HOODING_door": "galvanised_steel",
    "08_HOODING_door_frame": "galvanised_steel",
    "08_HOODING_handle": "structural_steel",
    "08_HOODING_number_plate": "painted_steel",

    # -- 09 hardware ----------------------------------------------------------
    "09_HARDWARE_base_plate": "structural_steel",
    "09_HARDWARE_gusset": "structural_steel",
    "09_HARDWARE_jack": "structural_steel",
    "09_HARDWARE_jack_cap": "structural_steel",
    "09_HARDWARE_flex_clamp": "structural_steel",
}

# Boolean operands. They are hidden from every render and exist only to be
# subtracted, so they get no material ON PURPOSE - a cutter carrying its own
# material would hand that material to the new faces it cuts.
UNPAINTED: frozenset[str] = frozenset({
    "02_REFRACTORY_ledge_core",
    "03_CATHODE_ramming_cut_bars",
    "03_CATHODE_ramming_cut_blocks",
    "04_PROCESS_anode_cut",
    "04_PROCESS_feed_hole",
})


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def _srgb(hex_colour: str) -> tuple[float, float, float, float]:
    """sRGB hex -> linear RGBA, which is what a Blender colour socket wants."""
    h = hex_colour.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)


def _principled(mat: bpy.types.Material) -> bpy.types.Node:
    if mat.node_tree is None:  # pragma: no cover - defensive, 6.0-proofing
        mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    if node is None:
        raise RuntimeError(f"{mat.name}: no Principled BSDF to drive")
    return node


def _set(node: bpy.types.Node, socket: str, value) -> None:
    if socket not in node.inputs:
        raise RuntimeError(f"Principled BSDF has no socket {socket!r}")
    node.inputs[socket].default_value = value


def build_library() -> dict[str, bpy.types.Material]:
    """Create every material in SPECS. Idempotent within a fresh scene."""
    made: dict[str, bpy.types.Material] = {}

    for name, s in SPECS.items():
        mat = bpy.data.materials.new(name)
        node = _principled(mat)

        _set(node, "Base Color", _srgb(s["color"]))
        _set(node, "Metallic", s["metallic"])
        _set(node, "Roughness", s["roughness"])

        if "coat" in s:
            _set(node, "Coat Weight", s["coat"])
            _set(node, "Coat Roughness", s.get("coat_roughness", 0.3))
        if "emit" in s:
            _set(node, "Emission Color", _srgb(s["emit"]))
            _set(node, "Emission Strength", s["emit_strength"])

        # Viewport colour, so the material also reads in the solid-shaded
        # .blend the user opens - not only in a render.
        mat.diffuse_color = _srgb(s["color"])
        mat.metallic = s["metallic"]
        mat.roughness = s["roughness"]

        made[name] = mat

    return made


def family(obj: bpy.types.Object) -> str:
    """`05_ANODES_stub_107` -> `05_ANODES_stub`."""
    return obj.name.rsplit("_", 1)[0]


def apply(strict: bool = True) -> dict[str, int]:
    """
    Paint the whole scene. Returns material name -> objects painted.

    Materials go on the MESH, not the object, so the 36 anode blocks sharing
    one datablock also share one material slot. That only holds while a
    datablock belongs to a single family; if two families ever share a mesh
    AND disagree about its material, that is a real modelling error and this
    raises rather than letting the last writer win.
    """
    lib = build_library()
    counts: dict[str, int] = {name: 0 for name in lib}
    claimed: dict[str, tuple[str, str]] = {}   # mesh name -> (material, family)
    unknown: list[str] = []

    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.data is None:
            continue

        fam = family(obj)
        if fam in UNPAINTED:
            continue

        mat_name = ASSIGNMENT.get(fam)
        if mat_name is None:
            if fam not in unknown:
                unknown.append(fam)
            continue

        prior = claimed.get(obj.data.name)
        if prior and prior[0] != mat_name:
            raise RuntimeError(
                f"mesh {obj.data.name!r} is shared by {prior[1]!r} "
                f"({prior[0]}) and {fam!r} ({mat_name}) - two materials on "
                f"one datablock. Split the mesh or align the materials."
            )

        if prior is None:
            obj.data.materials.clear()
            obj.data.materials.append(lib[mat_name])
            claimed[obj.data.name] = (mat_name, fam)

        counts[mat_name] += 1

    if unknown:
        message = (
            f"{len(unknown)} part family/families have no material: "
            + ", ".join(sorted(unknown))
            + ". Add them to lib.materials.ASSIGNMENT, or to UNPAINTED if "
              "they are boolean cutters."
        )
        if strict:
            raise RuntimeError(message)
        print("   WARNING: " + message)

    return counts

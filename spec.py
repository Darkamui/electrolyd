"""
Datasheet for a ~400 kA modern prebake Hall-Heroult aluminium reduction cell.

SINGLE SOURCE OF TRUTH. This module is the only place in the project where a
dimension may appear as a literal. Every build module reads from here.

    !! NO MODULE MAY CONTAIN A LITERAL DIMENSION. !!
    !! DELEGATED TASKS MAY READ THIS FILE BUT NEVER EDIT IT. !!

UNITS
    Every length is in MILLIMETRES (int or float). Angles in degrees.
    Conversion to Blender metres happens exactly once, at build time, via
    lib.units.mm(). Never divide by 1000 by hand in a module.

DATUM
    +X  longitudinal, along the cell length
    +Y  transverse, across the cell width
    +Z  up
    Origin at the cell centre in X and Y.
    Z = 0 at the SHELL INNER FLOOR (the top face of the bottom plate).
    The cell is symmetric about both the X=0 and Y=0 planes.

SOURCING
    Values marked SOURCED are published figures, cited by bracket number
    against the list below. Values marked ASSUMED are plausible-class
    engineering values chosen for visual and structural coherence; they are
    not per-part sourced. Correct them here and the whole model follows.

    [1] M. Dupuis, "Thermo-Electric Design of a 740 kA Cell, Is There a Size
        Limit?", Table 1 - a six-column comparison of 300 / 265 / 350 / 400 /
        500 / 740 kA cell designs, descending from his 400 kA tutorial (TMS
        Light Metals 2000, 297-302). This is the primary datasheet for the
        cell modelled here; the 400 kA column reads:

            36 anodes, 1.7 m x 0.8 m      3 studs/anode, 19 cm dia
            20 cathode blocks, 3.67 m     inside potshell 16.1 x 4.35 m
            ACD 4 cm                      anode cover 10 cm

        Chain of consistency, which is why these figures are trusted:
            36 x 1700 x 800   = 48.96 m^2 total anode area
            400 000 A / 48.96 = 0.817 A/cm^2, inside the published
                                0.65-1.3 A/cm^2 band
        and independently, by Faraday at 0.3356 g/(A.h):
            400 kA x 24 h x 93.4% CE = 3.01 t/cell-day, which is exactly the
            published figure for a real 400 kA pot (SY400).

    [2] "History and Recent Developments in Aluminum Smelting in China",
        ICSOBA 2017 - SY400/NEUI400 KPIs, and the collector bar section:
        current practice 100 x 230 mm, superseding 65 x 180 / 65 x 240.

    KNOWN DIVERGENCE FROM [1], deliberate, with reasons:
      * Inside potshell width 4800 here against 4350 in [1]. [1] is a thermal
        model and has no feeder geometry in it; the user's reference section
        does. The centre channel was widened 200 -> 400 to pass a 250 mm
        feeder chute, and the side channel is 250 rather than ~125. Those two
        account for the whole 450 mm.
      * Inside potshell length 16350 here against 16100 in [1]. Same anode
        array (15250 mm) either way; the difference is a more generous end
        channel plus lining.

This module must never import bpy. It is plain Python so it can be unit
tested and imported by tooling outside Blender.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Process and electrical
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Process:
    """Operating parameters. Drive the vertical stack and clearances."""

    line_current_ka: float = 400.0  # SOURCED
    anodic_current_density_a_cm2: float = 0.817  # SOURCED

    # Dupuis [1] gives 4 cm for every design from 350 kA up to 740 kA; ICSOBA
    # gives 4.0-4.5 cm for modern Chinese pots. 40 is the figure both agree on.
    acd: float = 40.0  # SOURCED [1] Table 1, 400 kA column
    metal_pad_depth: float = 200.0  # ASSUMED (lit. range 150-250)
    bath_depth: float = 200.0  # ASSUMED (lit. range 180-220)

    # Top crust ("croute") - solidified bath over the electrolyte surface,
    # confirmed by the user's transverse-section reference. Forms in the
    # channels around and between the anodes, never under an anode.
    crust_thickness: float = 120.0  # ASSUMED
    alumina_cover: float = 100.0  # ASSUMED  powder blanket over the crust

    def anode_area_m2(self, anodes: "Anodes") -> float:
        """Total anode working area, m^2. Used to verify current density."""
        return anodes.count * (anodes.block_y / 1000.0) * (anodes.block_x / 1000.0)

    def current_density_check(self, anodes: "Anodes") -> float:
        """Derived A/cm^2. Must agree with the SOURCED value within 1%."""
        area_cm2 = self.anode_area_m2(anodes) * 10_000.0
        return (self.line_current_ka * 1000.0) / area_cm2


# ---------------------------------------------------------------------------
# Anodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Anodes:
    """36 prebaked carbon anode assemblies in two longitudinal rows."""

    count: int = 36  # SOURCED
    rows: int = 2  # SOURCED

    block_y: float = 1700.0  # SOURCED  long axis, transverse
    block_x: float = 800.0  # SOURCED  short axis, longitudinal
    block_z: float = 600.0  # ASSUMED

    gap_x: float = 50.0  # ASSUMED  inter-anode gap along the row
    # Centre channel must clear the feeder chute and breaker rod. Widened from
    # 200 after the reference section showed the alumina feeder descending here.
    centre_channel: float = 400.0  # ASSUMED
    side_channel: float = 250.0  # ASSUMED  anode edge to sidewall ledge
    end_channel: float = 300.0  # ASSUMED  end anode to end lining

    # Rodding assembly
    # Three studs, not four. Four is common on the 1.95 m anodes of 500 kA+
    # cells; for a 1.7 m anode at 400 kA the sourced design is 3 per anode.
    stubs_per_anode: int = 3  # SOURCED [1] Table 1, 400 kA column
    stub_diameter: float = 190.0  # SOURCED [1] Table 1 ("19 cm")
    stub_embed_depth: float = 100.0  # ASSUMED  into the carbon block
    stub_free_height: float = 200.0  # ASSUMED  block top to yoke underside

    yoke_length: float = 1400.0  # ASSUMED  spans the stub pairs
    yoke_section: float = 160.0  # ASSUMED  square

    stem_section: float = 150.0  # ASSUMED  square aluminium rod
    # Stem LENGTH is derived, not chosen - see Cell.stem_height. A chosen
    # 1800 mm left 1335 mm of bare rod standing above the anode beam, which
    # read as a forest of spikes in the blockout hero. What is actually
    # specifiable is how far the stem clears the beam; the length follows.
    stem_above_beam: float = 350.0  # ASSUMED  stem top above the beam's top face

    clamp_x: float = 300.0  # ASSUMED
    clamp_y: float = 250.0  # ASSUMED
    clamp_z: float = 200.0  # ASSUMED

    # -- detail pass (Phase 3) ------------------------------------------------

    # Stub sockets. A stub is not driven into solid carbon: the block is cast
    # with a socket and the stub is grouted into it. Modelled because the
    # transverse section cuts straight through four of them.
    stub_socket_clearance: float = 10.0  # ASSUMED  radial, stub to carbon

    # Gas slots. A horizontal slot cut up into the anode's working face, which
    # lets the CO2 film escape sideways instead of blanketing the face. Real,
    # functional, and the section plane exposes it.
    slot_count: int = 2  # ASSUMED  per anode, spaced across the block's X
    slot_width: float = 15.0  # ASSUMED  along X
    slot_depth: float = 250.0  # ASSUMED  up from the working face

    @property
    def per_row(self) -> int:
        return self.count // self.rows

    @property
    def array_x(self) -> float:
        """Longitudinal extent of one anode row, outer face to outer face."""
        return self.per_row * self.block_x + (self.per_row - 1) * self.gap_x

    @property
    def row_pitch_x(self) -> float:
        return self.block_x + self.gap_x

    @property
    def row_centre_y(self) -> float:
        """|Y| of each row's centreline."""
        return self.centre_channel / 2.0 + self.block_y / 2.0

    def positions(self) -> list[tuple[float, float]]:
        """(x, y) centre of every anode block. Length == count."""
        x0 = -self.array_x / 2.0 + self.block_x / 2.0
        out: list[tuple[float, float]] = []
        for row in range(self.rows):
            y = self.row_centre_y * (1.0 if row == 0 else -1.0)
            for i in range(self.per_row):
                out.append((x0 + i * self.row_pitch_x, y))
        return out


# ---------------------------------------------------------------------------
# Vertical lining stack, measured upward from Z = 0
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Lining:
    """Bottom lining layers. Ordered bottom to top."""

    insulation: float = 100.0  # ASSUMED  calcium silicate board
    firebrick_course: float = 65.0  # ASSUMED
    firebrick_courses: int = 2  # ASSUMED
    bedding: float = 50.0  # ASSUMED  dry barrier / alumina

    side_sic: float = 100.0  # ASSUMED  silicon carbide side block
    side_backing: float = 150.0  # ASSUMED  refractory behind the SiC

    @property
    def firebrick(self) -> float:
        return self.firebrick_course * self.firebrick_courses

    @property
    def side_total(self) -> float:
        """Total side lining thickness, cavity face to shell plate."""
        return self.side_sic + self.side_backing

    @property
    def z_insulation_top(self) -> float:
        return self.insulation

    @property
    def z_firebrick_top(self) -> float:
        return self.z_insulation_top + self.firebrick

    @property
    def z_bedding_top(self) -> float:
        return self.z_firebrick_top + self.bedding


# ---------------------------------------------------------------------------
# Ledge ("gelee") - frozen bath against the cooled sidewalls
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Ledge:
    """
    Solidified bath forming a wedge on the inner sidewalls, confirmed by the
    user's reference section. Thickest around the metal/bath interface and
    tapering upward, so it narrows the cavity exactly where the anodes sit.

    Profile is defined by inward intrusion at three heights, measured from the
    SiC sidewall face toward the cell centreline. Built as a lofted/tapered
    solid running the full cavity perimeter.
    """

    toe_z_offset: float = 0.0  # ASSUMED  base sits at cathode top level
    intrusion_at_metal: float = 300.0  # ASSUMED  widest, at the metal pad
    intrusion_at_bath_mid: float = 220.0  # ASSUMED
    intrusion_at_bath_top: float = 120.0  # ASSUMED  thinnest, at bath surface
    top_overhang: float = 60.0  # ASSUMED  lip above the bath into the crust


# ---------------------------------------------------------------------------
# Alumina feeder ("alimentation en alumine") + crust breaker
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Feeder:
    """
    Point feeder assembly in the centre channel: a hopper on the
    superstructure, a chute descending between the anode rows, and a pneumatic
    crust breaker whose chisel punches through the crust. All ASSUMED.
    """

    count: int = 5  # point feeders along the centre channel
    hopper_x: float = 900.0
    hopper_y: float = 700.0
    hopper_z: float = 800.0
    # Hopper BASE height is derived, not chosen - see Cell.z_hopper_base. The
    # hopper rests on the feeder deck, and the deck sits on the portal tie,
    # which itself clears the stems. Choosing a height here just guarantees it
    # floats above or sinks into whatever the superstructure actually resolves to.

    chute_diameter: float = 250.0
    cylinder_diameter: float = 300.0
    cylinder_length: float = 900.0
    chisel_diameter: float = 120.0
    chisel_travel: float = 400.0  # stroke below the crust surface

    # -- detail pass (Phase 3) ------------------------------------------------
    # The chisel has been through the crust, so there is a hole. Blockout ran
    # the chisel straight into an unbroken slab, which reads as a rod welded to
    # the ice rather than a breaker that has done its job.
    crust_hole_clearance: float = 100.0  # ASSUMED  radial, chisel to crust edge

    # A hopper necks down to its outlet. A box sitting on a pipe is a box
    # sitting on a pipe - alumina would bridge in the corners and the feeder
    # would not feed. The taper is the part of the hopper that does the work,
    # so the only free quantity is how much of the height it takes.
    hopper_taper_fraction: float = 0.55  # ASSUMED  share of hopper_z that necks

    @property
    def hopper_outlet(self) -> float:
        """
        Square side of the hopper's outlet. DERIVED - it is the chute.

        The chute is inscribed in the outlet, so its wall meets the outlet at
        the four midpoints and the transition is clean. Choosing an outlet
        independently means the chute either rattles inside a hole too big for
        it or is throttled by one too small.
        """
        return self.chute_diameter

    @property
    def hopper_taper_z(self) -> float:
        """Height of the necked-down portion. DERIVED from the fraction."""
        return self.hopper_z * self.hopper_taper_fraction

    @property
    def hopper_prism_z(self) -> float:
        """Height of the parallel-walled portion above the taper. DERIVED."""
        return self.hopper_z - self.hopper_taper_z

    @property
    def widest_component(self) -> float:
        """Broadest part of the feeder stack, in X. Sets how close to the end
        enclosures the outermost feeder may stand."""
        return max(self.hopper_x, self.cylinder_diameter, self.chute_diameter)

    def positions_x(self, span_x: float) -> list[float]:
        """
        Evenly distributed over the span passed in, first and last on its ends.

        The SPAN is supplied, not derived here - see Cell.feeder_span_x - and
        it is set by the end enclosures, because that is what the chute has to
        miss. Taken as a fraction of the cavity instead, the outermost feeder
        landed 50 mm inside the hood run and drove its chute 75 mm into the
        end box.
        """
        if self.count == 1:
            return [0.0]
        step = span_x / (self.count - 1)
        return [-span_x / 2.0 + i * step for i in range(self.count)]


# ---------------------------------------------------------------------------
# Cathode
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Cathode:
    """Graphitised carbon blocks laid transversely, with steel collector bars."""

    # Twenty blocks, not twenty-four. The sourced 400 kA cell is the 350 kA
    # design stretched by 1.7 m to take four more anodes, and that stretch
    # added exactly TWO cathode blocks (18 -> 20), widening each one rather
    # than keeping a fixed block width and adding more of them. So the block
    # is 730 mm across, not 600 - fewer, fatter blocks under a longer pot.
    block_count: int = 20  # SOURCED [1] Table 1, 400 kA column
    block_y: float = 3670.0  # SOURCED [1] Table 1 ("3.67 m")
    block_x: float = 730.0  # DERIVED-ish: run_x still fills the cavity at n=20
    block_z: float = 450.0  # ASSUMED
    seam: float = 40.0  # ASSUMED  ramming paste between blocks

    # A collector bar is TALL and narrow, not squat. The old designs were
    # 65 x 180 / 65 x 240; current practice is 100 x 230, chosen for the
    # larger section area. The first draft had this the wrong way round.
    bar_w: float = 100.0  # SOURCED [2] Y-normal section width
    bar_h: float = 230.0  # SOURCED [2]
    bars_per_block: int = 2  # ASSUMED  one exiting each +/-Y face
    bar_centre_gap: float = 100.0  # ASSUMED  between the two bars' inner ends
    bar_protrusion: float = 250.0  # ASSUMED  beyond the shell outer face
    bar_slot_clearance: float = 5.0  # ASSUMED  slot oversize around the bar

    @property
    def run_x(self) -> float:
        """Longitudinal extent of the full block run including seams."""
        return (
            self.block_count * self.block_x + (self.block_count - 1) * self.seam
        )

    @property
    def pitch_x(self) -> float:
        return self.block_x + self.seam

    def block_positions_x(self) -> list[float]:
        """X centre of every cathode block. Length == block_count."""
        x0 = -self.run_x / 2.0 + self.block_x / 2.0
        return [x0 + i * self.pitch_x for i in range(self.block_count)]


# ---------------------------------------------------------------------------
# Steel shell
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Shell:
    """Welded steel pot shell with external cradles."""

    plate: float = 15.0  # ASSUMED
    # Raised from 1400 once the crust + alumina cover were added: the old rim
    # left only 50 mm above the cover blanket.
    rim_z: float = 1500.0  # ASSUMED  inner floor to top of rim

    cradle_pairs: int = 14  # ASSUMED
    # Cradle PITCH is derived, not chosen - see Cell.cradle_positions_x. A
    # cradle is a rib on the very side the collector bars come out through, so
    # where it stands is decided by where the bars are, not by a round number.
    cradle_depth: float = 400.0  # ASSUMED  outward from the shell plate
    cradle_thickness: float = 25.0  # ASSUMED

    flange_width: float = 200.0  # ASSUMED  rim flange
    flange_thickness: float = 20.0  # ASSUMED

    # -- detail pass (Phase 3) ------------------------------------------------

    # Every rolled steel edge carries a break. Without one, plate reads as CG
    # because a perfectly sharp arris never catches a highlight.
    edge_bevel: float = 8.0  # ASSUMED

    # A cradle is not a plain rib. It is a web plate with a flange top and bottom
    # - an I in section - which is what lets 25 mm plate carry the pot.
    cradle_flange_x: float = 180.0  # ASSUMED  flange width, along the cell
    cradle_flange_t: float = 22.0  # ASSUMED
    cradle_foot_x: float = 320.0  # ASSUMED  base foot, along the cell
    cradle_foot_t: float = 30.0  # ASSUMED

    # Cradle STATIONS live on Cell, not here: placing them needs the cathode
    # block seams and the shell's outer length, and Shell knows neither.


# ---------------------------------------------------------------------------
# Superstructure, hooding, busbars
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Superstructure:
    """
    Portal frame over the cell: two anode beams, columns standing on the
    cradles, transverse ties above the rodding, and the feeder deck. All
    ASSUMED.

    The frame is OPEN along the centreline. That is not a simplification - it
    is how a prebake superstructure is built, because the feeders descend there
    and the crane reaches in there to change anodes.
    """

    beam_count: int = 2
    beam_y: float = 800.0
    beam_z_section: float = 300.0
    beam_z: float = 2100.0  # underside height above Z=0; the one chosen height

    column_pairs: int = 6
    column_section: float = 400.0
    # Column TOP is derived, not chosen - see Cell.z_column_top. A chosen
    # 2600 put the transverse tie straight through the 2750 stem tops. What is
    # real is that the tie must pass over the rodding; the height follows.
    cross_section: float = 400.0  # ASSUMED  square, same family as the columns

    # Feeder deck: two longitudinal rails carrying the alumina hoppers. Their
    # |Y| is derived from the chute, so the centre channel is never blocked.
    deck_rail_section: float = 200.0  # ASSUMED  square
    deck_rail_clearance: float = 50.0  # ASSUMED  rail inner face to chute wall

    duct_diameter: float = 900.0
    duct_stub: float = 600.0  # ASSUMED  clean cut-off beyond the shell

    # -- detail pass (Phase 3) -----------------------------------------------
    edge_bevel: float = 6.0  # ASSUMED  rolled radius on frame steel

    # The agreed scope stops the duct in a stub rather than running it to a gas
    # treatment centre. A bare cut cylinder reads as geometry that was clipped;
    # a flange reads as a pipe that ENDS here and continues elsewhere, which is
    # what the scope actually means.
    duct_flange_grow: float = 120.0  # ASSUMED  radial, beyond the duct wall
    duct_flange_t: float = 40.0  # ASSUMED

    # A header lying tangent on the end enclosure roof has no way in, and the
    # blockout's did exactly that: 6 m of pipe resting on a closed box, with
    # the hood plenum underneath it venting nowhere. The throat is the missing
    # part - a square-to-round transition rising out of the plenum into the
    # header - and it is also what holds the header up.
    duct_throat_rise: float = 450.0  # ASSUMED  roof to duct underside
    duct_throat_margin: float = 250.0  # ASSUMED  mouth inset from the box ends
    duct_segments: int = 32  # ASSUMED  tessellation, header and throat alike

    @property
    def duct_flange_diameter(self) -> float:
        return self.duct_diameter + 2.0 * self.duct_flange_grow


@dataclass(frozen=True)
class Hooding:
    """
    Removable side hood panels and the end enclosures.

    CORRECTED from the user's potroom photograph. The first draft had flat
    8 mm plates. The real panels are CURVED (roughly a quarter-cylinder
    sweeping from the superstructure down and outward to the shell rim),
    heavily RIBBED across their width, and bright unpainted metal against the
    oxidised brown shell. That curve + rib rhythm is the dominant visual
    signature of the whole cell and must be modelled, not approximated.
    """

    # Panel WIDTH is derived, not chosen: the run must exactly fill the space
    # between the two end boxes. Hardcoding 900 mm overran the shell by 3.8 m.
    panels_per_side: int = 14  # ASSUMED
    panel_gap: float = 20.0  # ASSUMED  between adjacent panels
    panel_thickness: float = 6.0  # ASSUMED

    # Curved profile, swept in the Y-Z plane.
    #
    # The RADIUS is derived, not chosen - see Cell.hood_radius. A panel has two
    # anchors it must actually touch: the anode beam above and the shell rim
    # below. A chosen 1250 mm needed a 1689 mm chord to close its 85 degrees,
    # but the span between those anchors is only 1128 mm, so the panel could
    # not reach both and crested 2656 mm up through the superstructure. What is
    # genuinely a free choice is how far the panel ROLLS over that span; the
    # radius follows from the span.
    # The ROLL is derived, not chosen - see Cell.hood_arc_deg. A panel has two
    # walls it must stay between: it may not crest above its own top anchor
    # (it would bulge up into the anode beam) and it may not roll past
    # horizontal at the bottom (it would flare outside the shell it lands on).
    # A chosen 85 deg breached the first by 16 mm from the very first build,
    # and breached the second outright once the beam moved to where the rodding
    # actually clamps to it. What is genuinely specifiable is the MARGIN kept
    # against whichever wall is nearer.
    roll_margin_deg: float = 5.0  # ASSUMED
    curve_segments: int = 24  # ASSUMED  tessellation across the arc

    # Centre covers. With the beams outboard at the rodding, the span between
    # them is open sky over the anodes - gas would simply leave. These are the
    # removable covers that close it, resting on both beams' inner ledges, and
    # they are the reason the superstructure can stay open along the centreline
    # without the hooding leaking.
    centre_cover_thickness: float = 6.0  # ASSUMED
    centre_cover_gap: float = 20.0  # ASSUMED  between adjacent covers
    centre_cover_hole_clearance: float = 60.0  # ASSUMED  radial, cover to chute

    # Stiffening ribs running along the arc, repeated down the panel length.
    rib_pitch: float = 150.0  # ASSUMED
    rib_depth: float = 25.0  # ASSUMED
    rib_width: float = 45.0  # ASSUMED

    handle_per_panel: int = 2  # ASSUMED  lifting handles, visible in the photo

    # -- detail pass (Phase 3) ------------------------------------------------
    # Handle geometry. These are what a potroom operator grabs to pull a panel
    # off, and in the reference photograph they are the brightest thing on the
    # cell - a row of them catching the light all down the hood line.
    handle_length: float = 260.0  # ASSUMED  along the cell
    handle_section: float = 40.0  # ASSUMED  square bar
    handle_standoff: float = 90.0  # ASSUMED  clear of the panel's outer face

    @property
    def handle_bevel(self) -> float:
        """
        DERIVED. Radius on the handle's arrises, a quarter of its section.

        This one is not decoration and not a highlight-catcher: a grab handle
        with sharp corners is a hand injury, so a real one is generously
        radiused. A quarter of the bar is what that looks like.
        """
        return self.handle_section / 4.0

    # Rib END INSET is derived, not chosen - see Cell.hood_rib_inset_deg. A rib
    # swept over the panel's full arc at the panel's radius plus rib_depth pokes
    # radially past both ends of the panel it stiffens; at the bottom that put
    # 24 mm of rib below the landing edge, so a panel would rock on its
    # stiffeners instead of seating on the shell rim.

    # End enclosures - the tall boxes carrying the pot number and access doors.
    end_box_x: float = 1800.0  # ASSUMED  length along the cell axis
    end_box_top_z: float = 3200.0  # ASSUMED  well above the hood line
    end_box_door_w: float = 700.0  # ASSUMED
    end_box_door_h: float = 1600.0  # ASSUMED

    # -- end enclosure detail pass (Phase 3) ---------------------------------
    # The blockout's end box was a bare 4830 x 1685 plate carrying one 700 mm
    # door: 86% of the largest single face on the cell, and the foreground of
    # both the front elevation and the hero, with nothing on it. It gets the
    # same rib rhythm as the hood - these are panels from the same shop - plus
    # the two things the docstring above always said it carried and never did:
    # the pot number, and enough doors to reach the plenum from.
    end_box_doors: int = 2  # ASSUMED  per end face
    end_box_cap_t: float = 80.0  # ASSUMED  capping plate over the roof
    end_box_cap_grow: float = 60.0  # ASSUMED  cap overhang, all round
    end_box_frame_grow: float = 80.0  # ASSUMED  door frame beyond the leaf
    end_box_frame_proud: float = 20.0  # ASSUMED  frame clear of the ribs
    end_box_plate_w: float = 1100.0  # ASSUMED  pot number plaque
    end_box_plate_h: float = 420.0  # ASSUMED
    end_box_plate_t: float = 40.0  # ASSUMED  proud of the ribs, see below

    @property
    def end_box_frame_t(self) -> float:
        """
        DERIVED. A door frame that does not stand clear of the stiffening ribs
        it interrupts leaves the ribs running visibly straight through the
        doorway. The frame is therefore as deep as a rib, plus its own relief.
        """
        return self.rib_depth + self.end_box_frame_proud

    @property
    def end_box_door_t(self) -> float:
        """DERIVED. The leaf stands one plate thickness proud of its frame."""
        return self.end_box_frame_t + self.panel_thickness

    def end_box_door_positions_y(self, shell_outer_y: float) -> list[float]:
        """Doors spread evenly across the end face, symmetric about y=0."""
        n = self.end_box_doors
        step = shell_outer_y / n
        return [-shell_outer_y / 2.0 + (i + 0.5) * step for i in range(n)]

    def end_ribs_across(self, shell_outer_y: float) -> int:
        """Ribs on the end face, at the hood's own pitch."""
        return max(1, int(shell_outer_y // self.rib_pitch))

    def end_ribs_along(self) -> int:
        """Ribs on each side face of an end box, at the same pitch."""
        return max(1, int(self.end_box_x // self.rib_pitch))

    def panel_run_x(self, shell_outer_x: float) -> float:
        """Total length available to panels, between the two end boxes."""
        return shell_outer_x - 2.0 * self.end_box_x

    def panel_x(self, shell_outer_x: float) -> float:
        """DERIVED panel width so the run exactly fills the available length."""
        n = self.panels_per_side
        run = self.panel_run_x(shell_outer_x)
        return (run - (n - 1) * self.panel_gap) / n

    def panel_positions_x(self, shell_outer_x: float) -> list[float]:
        w = self.panel_x(shell_outer_x)
        pitch = w + self.panel_gap
        x0 = -self.panel_run_x(shell_outer_x) / 2.0 + w / 2.0
        return [x0 + i * pitch for i in range(self.panels_per_side)]

    def centre_cover_x(self, shell_outer_x: float) -> float:
        """
        DERIVED cover width. The covers tile exactly the run the panels tile,
        one cover per panel bay, because a bay is the unit that gets opened:
        the side panel comes off and the cover over it comes off with it.
        Choosing a width independently leaves either a strip of open sky or an
        overlap at the end boxes.
        """
        n = self.panels_per_side
        run = self.panel_run_x(shell_outer_x)
        return (run - (n - 1) * self.centre_cover_gap) / n

    def centre_cover_positions_x(self, shell_outer_x: float) -> list[float]:
        w = self.centre_cover_x(shell_outer_x)
        pitch = w + self.centre_cover_gap
        x0 = -self.panel_run_x(shell_outer_x) / 2.0 + w / 2.0
        return [x0 + i * pitch for i in range(self.panels_per_side)]

    def ribs_per_panel(self, shell_outer_x: float) -> int:
        return max(1, int(self.panel_x(shell_outer_x) // self.rib_pitch))

    def end_box_centre_x(self, shell_outer_x: float) -> float:
        """|X| of each end box centre."""
        return shell_outer_x / 2.0 - self.end_box_x / 2.0


@dataclass(frozen=True)
class Busbars:
    """Riser and collector busbars. Terminate in stubs at the cell boundary."""

    riser_count: int = 4  # ASSUMED  upstream (+Y) side
    riser_w: float = 800.0  # ASSUMED
    riser_t: float = 200.0  # ASSUMED
    stub_length: float = 600.0  # ASSUMED  clean cut-off beyond the shell

    # Riser TOP is derived, not chosen - see Cell.z_riser_top. A chosen 2100
    # was labelled "meets the anode beam" and did not: it stopped level with
    # the beam's underside but 1240 mm outboard of its outer face, so four
    # 2.1 m posts rose out of the collector busbar and ended in bare cut faces,
    # connected to nothing. A riser exists to deliver current to the beam; the
    # height it must reach is the beam's, and the arm is what gets it there.
    arm_t: float = 120.0  # ASSUMED  lap plate depth over the beam
    busbar_bevel: float = 10.0  # ASSUMED  rolled arris on cast aluminium

    flex_length: float = 400.0  # ASSUMED  collector bar to busbar connector
    flex_section: float = 120.0  # ASSUMED

    # -- detail pass (Phase 3) ------------------------------------------------
    # A flexible connector is not a solid billet - it is a stack of thin rolled
    # laminates, which is the whole reason it can flex as the pot breathes.
    # Modelled as a laminate stack because at this scale the stripe of gaps is
    # the only thing that distinguishes a flex from a busbar.
    flex_laminates: int = 7  # ASSUMED
    flex_laminate_gap: float = 4.0  # ASSUMED  between adjacent laminates


@dataclass(frozen=True)
class Hardware:
    """
    Justified connection hardware ONLY.

    The prompt is explicit that visible hardware is limited to brackets, clamps,
    mounting plates and fasteners that are actually warranted, and that detail
    must not be added merely to raise complexity. Every part here closes a load
    path the blockout left implied - nothing is decoration.

    The one that matters most: the anode beam carries all 36 anode assemblies
    and, through Phase 2, hung from NOTHING. The portal ties pass 350 mm above
    it and the columns stand 840 mm outboard of it. Screw jacks at the column
    stations are simultaneously the missing support and the real mechanism, as
    raising the beam is how the anodes are lowered as they burn back.
    """

    # -- anode beam jacks ----------------------------------------------------
    # One pair per column station: they land where a tie already crosses a beam,
    # which is the only place the load has somewhere to go.
    jack_body_diameter: float = 260.0  # ASSUMED
    jack_screw_diameter: float = 120.0  # ASSUMED
    jack_cap_x: float = 360.0  # ASSUMED  mounting cap on the beam top
    jack_cap_y: float = 360.0  # ASSUMED
    jack_cap_t: float = 30.0  # ASSUMED
    # How much of the jack is the body casting, the rest being exposed screw.
    # The jack's LENGTH is not free - it is the gap between the beam cap and
    # the tie it hangs from - so this split is the only choice left.
    jack_body_fraction: float = 0.6  # ASSUMED

    # -- column base plates and gussets --------------------------------------
    # Column to cradle. A 400 mm box section landing directly on a 25 mm cradle
    # web is not a joint; it needs a plate to spread into and gussets to stop
    # the column folding over.
    base_plate_t: float = 30.0  # ASSUMED
    base_plate_margin: float = 100.0  # ASSUMED  beyond the column section, ALONG X ONLY
    gusset_t: float = 20.0  # ASSUMED

    # A gusset's RUN and RISE are derived, not chosen - see below. The only free
    # quantity is how steep the bracket is.
    gusset_aspect: float = 2.0  # ASSUMED  rise : run

    # Gussets stand on the two +X / -X faces of the column only - see
    # Cell.base_plate_y for why there is no plate to reach out to in Y.
    gussets_per_column: int = 2

    # -- collector bar / flexible connector joint ----------------------------
    flex_clamp_t: float = 25.0  # ASSUMED  plate over the lap
    flex_clamp_margin: float = 40.0  # ASSUMED  beyond the flex section, all round

    @property
    def base_plate_grow(self) -> float:
        """Total added to the column section to get the plate's length along X."""
        return 2.0 * self.base_plate_margin

    @property
    def gusset_run(self) -> float:
        """
        How far a gusset reaches out along the base plate. DERIVED.

        A gusset spans from the column's own face to the edge of the plate,
        because spreading the column's load out to that edge is the entire
        reason the plate is longer than the column. The land available is
        therefore exactly base_plate_margin - there is nothing to choose.

        Chosen instead, 320 mm ran 20 mm off the end of a plate that only
        projects 100 mm past the column.
        """
        return self.base_plate_margin

    @property
    def gusset_rise(self) -> float:
        """How far a gusset climbs the column. DERIVED from run x aspect."""
        return self.gusset_run * self.gusset_aspect


# ---------------------------------------------------------------------------
# Assembled cell geometry, fully derived
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Cell:
    """Top-level spec. Everything here is derived from the parts above."""

    process: Process = field(default_factory=Process)
    anodes: Anodes = field(default_factory=Anodes)
    lining: Lining = field(default_factory=Lining)
    ledge: Ledge = field(default_factory=Ledge)
    feeder: Feeder = field(default_factory=Feeder)
    cathode: Cathode = field(default_factory=Cathode)
    shell: Shell = field(default_factory=Shell)
    superstructure: Superstructure = field(default_factory=Superstructure)
    hooding: Hooding = field(default_factory=Hooding)
    busbars: Busbars = field(default_factory=Busbars)
    hardware: Hardware = field(default_factory=Hardware)

    # -- plan extents ------------------------------------------------------

    @property
    def cavity_x(self) -> float:
        return self.anodes.array_x + 2 * self.anodes.end_channel

    @property
    def cavity_y(self) -> float:
        a = self.anodes
        return a.rows * a.block_y + a.centre_channel + 2 * a.side_channel

    @property
    def shell_inner_x(self) -> float:
        return self.cavity_x + 2 * self.lining.side_total

    @property
    def shell_inner_y(self) -> float:
        return self.cavity_y + 2 * self.lining.side_total

    @property
    def shell_outer_x(self) -> float:
        return self.shell_inner_x + 2 * self.shell.plate

    @property
    def shell_outer_y(self) -> float:
        return self.shell_inner_y + 2 * self.shell.plate

    @property
    def shell_outer_z(self) -> float:
        return self.shell.rim_z + self.shell.plate

    # -- vertical stack ----------------------------------------------------

    @property
    def z_cathode_bottom(self) -> float:
        return self.lining.z_bedding_top

    @property
    def z_cathode_top(self) -> float:
        return self.z_cathode_bottom + self.cathode.block_z

    @property
    def z_metal_top(self) -> float:
        return self.z_cathode_top + self.process.metal_pad_depth

    @property
    def z_bath_top(self) -> float:
        return self.z_metal_top + self.process.bath_depth

    @property
    def z_crust_top(self) -> float:
        """Crust sits ON the bath surface, so it rises above z_bath_top."""
        return self.z_bath_top + self.process.crust_thickness

    @property
    def z_cover_top(self) -> float:
        """Top of the alumina powder blanket over the crust."""
        return self.z_crust_top + self.process.alumina_cover

    @property
    def z_anode_bottom(self) -> float:
        """Anode working face. Sits one ACD above the metal pad surface."""
        return self.z_metal_top + self.process.acd

    @property
    def z_anode_top(self) -> float:
        return self.z_anode_bottom + self.anodes.block_z

    # -- anode rodding, derived up the assembly -----------------------------

    @property
    def stub_base_z(self) -> float:
        """Stub bottom: embedded down into the carbon block from its top face."""
        return self.z_anode_top - self.anodes.stub_embed_depth

    @property
    def stub_length(self) -> float:
        return self.anodes.stub_embed_depth + self.anodes.stub_free_height

    @property
    def yoke_base_z(self) -> float:
        return self.z_anode_top + self.anodes.stub_free_height

    @property
    def stem_base_z(self) -> float:
        return self.yoke_base_z + self.anodes.yoke_section

    @property
    def beam_top_z(self) -> float:
        return self.superstructure.beam_z + self.superstructure.beam_z_section

    @property
    def stem_height(self) -> float:
        """
        DERIVED, not chosen. The stem spans from the yoke top to a set
        clearance above the anode beam, so it always meets the superstructure
        no matter how the beam height moves.
        """
        return self.beam_top_z + self.anodes.stem_above_beam - self.stem_base_z

    @property
    def z_stem_top(self) -> float:
        return self.stem_base_z + self.stem_height

    @property
    def anode_immersion(self) -> float:
        """DERIVED, not specified. Depth the anode sits into the bath."""
        return self.z_bath_top - self.z_anode_bottom

    @property
    def section_plane_x(self) -> float:
        """
        X of the transverse cutaway: the anode column centre nearest the cell
        centre. DERIVED.

        Cutting between two anodes would put the plane in a 50 mm gap and show
        no anode at all. Cutting on a column centre slices the carbon block and
        all four cast-iron stubs lengthwise, which is the arrangement the
        reference drawing shows.

        It lives here rather than in lib/section because the detail camera has
        to aim at the same plane. Two places deriving it separately is how a
        close-up ends up framed on an anode the cutaway did not open.
        """
        xs = sorted({x for x, _ in self.anodes.positions()})
        return min(xs, key=lambda x: (abs(x), -x))

    @property
    def freeboard(self) -> float:
        """Rim clearance above the topmost process layer (the cover blanket)."""
        return self.shell.rim_z - self.z_cover_top

    # -- collector bars ----------------------------------------------------

    @property
    def bar_half_length(self) -> float:
        """Inner end (near centreline) to the tip outside the shell."""
        return (
            self.shell_outer_y / 2.0
            + self.cathode.bar_protrusion
            - self.cathode.bar_centre_gap / 2.0
        )

    @property
    def bar_z_centre(self) -> float:
        """Bars sit in a slot in the underside of the cathode block."""
        return self.z_cathode_bottom + self.cathode.bar_h / 2.0

    # -- derived gaps that QA asserts on -----------------------------------

    @property
    def cathode_end_gap(self) -> float:
        """Cavity end to the first cathode block. Must be positive."""
        return (self.cavity_x - self.cathode.run_x) / 2.0

    @property
    def cathode_side_gap(self) -> float:
        """Cavity side to the cathode block end. Must be positive."""
        return (self.cavity_y - self.cathode.block_y) / 2.0

    # -- superstructure, derived upward from the anode beam ------------------
    #
    # Only ONE height in the whole frame is chosen: superstructure.beam_z, the
    # anode beam underside. Everything above it is stacked from what it has to
    # clear. The order is beam -> stem tops -> transverse tie -> feeder deck ->
    # hopper -> breaker.

    @property
    def beam_length(self) -> float:
        """Anode beams span the full shell length."""
        return self.shell_outer_x

    @property
    def beam_centre_y(self) -> float:
        """
        |Y| of each anode beam's centreline. DERIVED, not chosen.

        An anode rod is CLAMPED TO THE FACE of the anode beam. It is never slung
        underneath it - there would be nothing for the clamp to bolt through and
        no way to adjust one anode without jacking the beam. So the beam's inner
        face is exactly where the stem's outer face is, and the centreline
        follows from the stem.

        Centring the beam on the anode row instead - which is what the blockout
        did - put the clamp bodily inside the beam. That was logged after
        Phase 2 as a clamp mounting defect; it was really this.
        """
        return (
            self.anodes.row_centre_y
            + self.anodes.stem_section / 2.0
            + self.superstructure.beam_y / 2.0
        )

    @property
    def clamp_centre_y(self) -> float:
        """
        |Y| of the clamp. It straddles the stem/beam interface, gripping the rod
        on one side and bolting to the beam on the other, so it is centred on
        the contact plane rather than on either part.
        """
        return self.anodes.row_centre_y + self.anodes.stem_section / 2.0

    @property
    def z_clamp_base(self) -> float:
        """
        DERIVED. Centred on the beam's depth, so the clamp bolts land in the
        beam section rather than above or below it.
        """
        s, a = self.superstructure, self.anodes
        return s.beam_z + (s.beam_z_section - a.clamp_z) / 2.0

    @property
    def z_column_base(self) -> float:
        """
        Columns stand on a base plate, which stands on the cradle tops. The
        cradles are the real load path down to the potroom floor, so the plate
        thickness belongs in this chain - a column starting at the shell plate
        top would float 15 mm above the cradles it is supposed to bear on.
        """
        return self.shell.rim_z + self.hardware.base_plate_t

    @property
    def column_centre_y(self) -> float:
        """
        |Y| of the portal columns. Deliberately outboard of everything: the
        inner face sits flush with the shell side, which is also where the hood
        panel lands, and the outer face is flush with the cradle tips. Anywhere
        further inboard and the column grows through the hood.
        """
        return self.shell_outer_y / 2.0 + self.superstructure.column_section / 2.0

    @property
    def base_plate_y(self) -> float:
        """
        Column base plate width, across the cell. DERIVED - and it is the
        column's own section, with no margin at all.

        The column already spans the whole cradle band exactly: its inner face
        is flush with the shell side, its outer face flush with the cradle tips
        (see column_centre_y). So there is no land for a plate to spread onto in
        either Y direction. Outboard of the cradle tip is air. Inboard is worse
        than air - it is where the hood panel comes down to land, and a plate
        grown 100 mm that way clipped the panel's bottom edge, while a gusset
        standing on it sat 54 mm bodily inside the panel.

        The plate therefore spreads along X instead, where the cradle's own
        flange runs and there is real steel to bear on, and the gussets go on
        the two X faces only.
        """
        return self.superstructure.column_section

    @property
    def base_plate_x(self) -> float:
        """Column base plate length along the cell. Grows where there is land."""
        return self.superstructure.column_section + self.hardware.base_plate_grow

    @property
    def z_cross_base(self) -> float:
        """
        DERIVED. The transverse tie passes OVER the anode rodding, so it starts
        exactly at the stem tops. This is the constraint the old chosen
        column_top_z violated.
        """
        return self.z_stem_top

    @property
    def z_column_top(self) -> float:
        return self.z_cross_base + self.superstructure.cross_section

    @property
    def cross_inner_y(self) -> float:
        """
        |Y| where each half of the transverse tie stops. The frame is open
        along the centreline: the feeders descend through that gap.
        """
        return (
            self.feeder.chute_diameter / 2.0
            + self.superstructure.deck_rail_clearance
        )

    @property
    def deck_rail_centre_y(self) -> float:
        """DERIVED from the chute, so the centre channel is never blocked."""
        s = self.superstructure
        return self.cross_inner_y + s.deck_rail_section / 2.0

    @property
    def deck_rail_length(self) -> float:
        """Deck runs the full cell length, carried by the ties and end boxes."""
        return self.shell_outer_x

    @property
    def z_deck_top(self) -> float:
        return self.z_column_top + self.superstructure.deck_rail_section

    @property
    def z_hopper_base(self) -> float:
        """DERIVED. Hoppers rest on the feeder deck rails."""
        return self.z_deck_top

    @property
    def z_breaker_base(self) -> float:
        """Pneumatic cylinder sits on top of its hopper."""
        return self.z_hopper_base + self.feeder.hopper_z

    # -- gas offtake: roof -> throat -> header, each derived from the last ----

    @property
    def z_end_box_roof(self) -> float:
        """Top of the end enclosure's capping plate. The throat stands on it."""
        return self.hooding.end_box_top_z + self.hooding.end_box_cap_t

    @property
    def z_duct_underside(self) -> float:
        """DERIVED. The throat's rise is what lifts the header off the roof."""
        return self.z_end_box_roof + self.superstructure.duct_throat_rise

    @property
    def z_duct_centre(self) -> float:
        return self.z_duct_underside + self.superstructure.duct_diameter / 2.0

    @property
    def duct_throat_mouth_x(self) -> float:
        """Mouth along the cell: the roof, inset clear of the box's own ends."""
        return (
            self.hooding.end_box_x
            - 2.0 * self.superstructure.duct_throat_margin
        )

    @property
    def duct_throat_mouth_y(self) -> float:
        """
        Mouth across the cell, matched to the header it feeds so the transition
        necks in one direction only. A square-to-round that has to gather in
        both directions at once is a shape nobody rolls.
        """
        return self.superstructure.duct_diameter

    @property
    def duct_length(self) -> float:
        return self.shell_outer_y + 2.0 * self.superstructure.duct_stub

    # -- busbar risers -------------------------------------------------------

    @property
    def z_riser_top(self) -> float:
        """
        DERIVED. A riser carries current to the anode beam, so it rises to the
        beam's TOP and laps over it. Stopping at the beam's underside height
        leaves it level with something it never touches.
        """
        return self.beam_top_z

    def riser_positions_x(self) -> list[float]:
        """
        DERIVED. Risers stand in the BAYS between portal columns, because the
        arm that carries each one inboard has to cross the column line at beam
        height. Spaced evenly over the cathode run instead, as the blockout did
        it, a riser landed on a column about as often as not.
        """
        columns = self.column_positions_x()
        bays = [(a + b) / 2.0 for a, b in zip(columns, columns[1:])]
        n = self.busbars.riser_count
        if n < 2 or len(bays) < n:
            return bays[:n]
        step = (len(bays) - 1) / (n - 1)
        return [bays[round(i * step)] for i in range(n)]

    def column_positions_x(self) -> list[float]:
        """
        DERIVED. Columns stand on cradles - that is the real load path - and
        must fall clear of the end enclosures. Spread the requested number of
        pairs evenly over the cradle stations that qualify.
        """
        limit = self.shell_outer_x / 2.0 - self.hooding.end_box_x
        usable = [x for x in self.cradle_positions_x() if abs(x) < limit]
        n = self.superstructure.column_pairs
        if n < 2 or len(usable) < n:
            return usable[:n]
        step = (len(usable) - 1) / (n - 1)
        return [usable[round(i * step)] for i in range(n)]

    # -- hood panel arc, derived from the two anchors it must touch ----------

    @property
    def hood_top_anchor(self) -> tuple[float, float]:
        """(y, z) where a panel meets the superstructure: the anode beam's
        outer face, at the beam underside.

        Reads beam_centre_y, not the anode row, so the panel follows the beam
        when the beam is derived from the rodding.
        """
        return (
            self.beam_centre_y + self.superstructure.beam_y / 2.0,
            self.superstructure.beam_z,
        )

    @property
    def hood_bottom_anchor(self) -> tuple[float, float]:
        """(y, z) where a panel lands: the outer top edge of the shell."""
        return (self.shell_outer_y / 2.0, self.shell_outer_z)

    @property
    def hood_chord(self) -> float:
        (y0, z0), (y1, z1) = self.hood_top_anchor, self.hood_bottom_anchor
        return math.hypot(y1 - y0, z1 - z0)

    @property
    def hood_chord_angle_deg(self) -> float:
        """
        Angle of the anchor-to-anchor chord, in arc_panel's convention:
        0 = straight up, 90 = horizontal outward in +Y.

        This is also the arc's MIDPOINT angle, because a circular arc's chord
        runs perpendicular to the radius at its midpoint. That identity is what
        makes the roll derivable without knowing the radius first.
        """
        (y0, z0), (y1, z1) = self.hood_top_anchor, self.hood_bottom_anchor
        return math.degrees(math.atan2(z0 - z1, y1 - y0))

    @property
    def hood_arc_deg(self) -> float:
        """
        DERIVED, not chosen. How far the panel rolls between its two anchors.

        The arc is symmetric about its chord, so the two ends sit at
        chord_angle -/+ arc/2, and each end has a wall it must not cross:

            start >= 0   the panel must not crest above its own top anchor,
                         which means bulging up into the anode beam
            end   <= 90  the panel must not roll past horizontal, which means
                         flaring outward past the shell rim it lands on

        The tighter wall therefore caps the roll at 2 * min(t, 90 - t), and the
        specifiable quantity is the margin held against it. Chosen instead, an
        85 deg roll sat 16 mm inside the anode beam in every build to date.
        """
        t = self.hood_chord_angle_deg
        return 2.0 * (min(t, 90.0 - t) - self.hooding.roll_margin_deg)

    @property
    def hood_radius(self) -> float:
        """
        DERIVED, not chosen. A panel that does not touch both the beam and the
        shell rim is not a hood, it is a floating shape.
        """
        half = math.radians(self.hood_arc_deg / 2.0)
        return self.hood_chord / (2.0 * math.sin(half))

    @property
    def hood_arc_centre(self) -> tuple[float, float]:
        """
        (y, z) of the arc centre - which is also the panel object's own origin,
        because build.arc_panel() sweeps about its origin.
        """
        (y0, z0), (y1, z1) = self.hood_top_anchor, self.hood_bottom_anchor
        chord = self.hood_chord
        my, mz = (y0 + y1) / 2.0, (z0 + z1) / 2.0
        dy, dz = (y1 - y0) / chord, (z1 - z0) / chord
        # Normal chosen so the panel bows outward and upward over the cell,
        # not inward. The other root gives a panel curving the wrong way.
        ny, nz = dz, -dy
        d = math.sqrt(max(self.hood_radius**2 - (chord / 2.0) ** 2, 0.0))
        return (my + d * ny, mz + d * nz)

    @property
    def hood_start_deg(self) -> float:
        """
        Arc angle of the TOP anchor, measured from +Z toward +Y about the arc
        centre - exactly the convention build.arc_panel() uses.
        """
        cy, cz = self.hood_arc_centre
        y0, z0 = self.hood_top_anchor
        return math.degrees(math.atan2(y0 - cy, z0 - cz))

    @property
    def hood_apex_z(self) -> float:
        """
        Highest point the PANEL reaches. Must stay under the portal tie.

        Not the top of the full circle: with hood_start_deg held at or above 0,
        the arc never reaches its own 12 o'clock, so the crest is simply the
        starting end. Returning the circle's apex instead overstated the crest
        by 23 mm and would fail the QA crest check against a 0.2 mm sag
        allowance.
        """
        cz = self.hood_arc_centre[1]
        return cz + self.hood_radius * math.cos(math.radians(self.hood_start_deg))

    # -- centre covers, spanning between the two anode beams ------------------

    @property
    def centre_cover_half_y(self) -> float:
        """
        DERIVED. A centre cover reaches from the centreline out to the INNER
        face of the anode stems, not to the beam.

        The 150 mm left between the cover edge and the beam is not slack - it is
        the slot the anode rods pass down through, and it is why the covers can
        be lifted off without unclamping a single anode.
        """
        return self.anodes.row_centre_y - self.anodes.stem_section / 2.0

    @property
    def z_centre_cover(self) -> float:
        """Covers sit at the anode beams' underside, carried on their inner ledges."""
        return self.superstructure.beam_z

    @property
    def centre_cover_hole_diameter(self) -> float:
        """Clearance hole where a feeder chute drops through a cover."""
        return (
            self.feeder.chute_diameter
            + 2.0 * self.hooding.centre_cover_hole_clearance
        )

    @property
    def feeder_span_x(self) -> float:
        """
        DERIVED. The length over which point feeders may be distributed.

        A feeder is not free to sit anywhere along the cell. Its chute, breaker
        and chisel all descend through the centre channel, and the channel is
        only open between the two end enclosures - the boxes are solid across
        the full width of the cell. The span is therefore the hood run, less
        the broadest part of the feeder stack so that the whole assembly, not
        merely its centreline, stays between them.
        """
        return (
            self.hooding.panel_run_x(self.shell_outer_x)
            - self.feeder.widest_component
        )

    def feeder_positions_x(self) -> list[float]:
        """Feeder X stations. Every module reads THIS, never Feeder.positions_x
        directly, so the span can only be derived in one place."""
        return self.feeder.positions_x(self.feeder_span_x)

    # -- hardware, all derived from the joints it closes --------------------

    @property
    def jack_body_length(self) -> float:
        """Body casting, the lower part of the jack."""
        return self.jack_length * self.hardware.jack_body_fraction

    @property
    def jack_screw_length(self) -> float:
        """Exposed screw, whatever the body leaves."""
        return self.jack_length - self.jack_body_length

    @property
    def bar_tip_y(self) -> float:
        """|Y| of the collector bar tips, where the flexible connectors land."""
        return self.shell_outer_y / 2.0 + self.cathode.bar_protrusion

    @property
    def z_flex_clamp_base(self) -> float:
        """
        DERIVED. Underside of a clamp plate laid across the flex joint.

        The plate rests on whichever of the two parts it laps stands taller.
        That is the collector bar, which is 15 mm deeper than the laminate
        stack it grips; measured off the flex instead, the plate would be
        buried in the bar it is bolting to.
        """
        return self.bar_z_centre + max(
            self.cathode.bar_h / 2.0, self.busbars.flex_section / 2.0
        )

    @property
    def flex_clamp_x(self) -> float:
        """Along the cell: the connector's section plus a margin each side."""
        return self.busbars.flex_section + 2.0 * self.hardware.flex_clamp_margin

    @property
    def flex_clamp_y(self) -> float:
        """Across the cell: the plate straddles the joint plane by the same
        margin on each side, which is what makes it a lap and not a cover."""
        return 2.0 * self.hardware.flex_clamp_margin

    def cradle_seam_stations_x(self) -> list[float]:
        """The inter-block seams: the only places along the side of the cell
        where a rib can meet the shell without a collector bar in the way."""
        xs = self.cathode.block_positions_x()
        return [(a + b) / 2.0 for a, b in zip(xs, xs[1:])]

    def cradle_positions_x(self) -> list[float]:
        """
        DERIVED. Where the external cradles stand.

        A cradle is a rib welded to the side of the shell, and the collector
        bars come out through that same side, 250 mm proud of it. Pitched at a
        round 1200 mm the two patterns beat against each other: four of the
        twenty-four bars came out 40 mm from a cradle centreline and drove
        straight through its 25 mm web. The bars cannot move - they are set by
        the cathode blocks - so the cradles must.

        A cradle therefore stands in a SEAM between two cathode blocks. The two
        end cradles are the exception: they close the ends of the shell, beyond
        the last block, where there is no bar to miss.
        """
        end = self.shell_outer_x / 2.0 - self.shell.cradle_foot_x / 2.0
        seams = self.cradle_seam_stations_x()
        n_inner = self.shell.cradle_pairs - 2
        if n_inner < 1 or len(seams) < n_inner:
            return [-end, end]
        step = (len(seams) - 1) / (n_inner - 1) if n_inner > 1 else 0.0
        inner = [seams[round(i * step)] for i in range(n_inner)]
        return [-end, *inner, end]

    @property
    def cradle_pitch(self) -> float:
        """DERIVED. Mean spacing of the side cradles. Used to carry the same
        stiffening rhythm round the corner onto the end walls."""
        return self.shell_outer_x / self.shell.cradle_pairs

    @property
    def end_cradle_centre_x(self) -> float:
        """A cradle stands AGAINST the wall it stiffens, so its centre is the
        outer face of the end plate plus half its own depth."""
        return self.shell_outer_x / 2.0 + self.shell.cradle_depth / 2.0

    def end_cradle_positions_y(self) -> list[float]:
        """
        DERIVED. Cradles on the END wall.

        The end wall carried nothing at all: 4800 x 1500 mm of dead plate, and
        in a transverse elevation it is the largest single surface in the
        picture. The cradles stopped at the side walls, so the stiffening
        rhythm ran the length of the cell and then ended at the corner.

        These are the SAME rib, stood against the end wall - no new section,
        because there is no reason a pot builder would roll one - and spaced at
        the side wall's own pitch, because choosing a count here would let the
        two patterns drift out of step for no reason. Nothing passes through
        the end wall, so unlike the side cradles they have no bars to miss.
        """
        n = max(2, int(self.shell_outer_y // self.cradle_pitch))
        step = self.shell_outer_y / n
        return [-self.shell_outer_y / 2.0 + (i + 0.5) * step for i in range(n)]

    @property
    def hood_handle_deg(self) -> float:
        """
        DERIVED. Where a lifting handle sits on the arc: the midpoint.

        A panel is lifted off by its handles, so they belong where the panel
        balances. Anywhere else and the panel swings as it comes away, which is
        also why there are two of them across the width rather than one.
        """
        return self.hood_start_deg + self.hood_arc_deg / 2.0

    @property
    def hood_handle_radius(self) -> float:
        """
        DERIVED. Radius of a handle's INNER face, measured from the arc centre.

        The standoff is clear of the PANEL, and the ribs already stand proud of
        it, so spec asserts the standoff clears the ribs too - otherwise a hand
        reaching under the handle closes on a stiffener.
        """
        return self.hood_radius + self.hooding.handle_standoff

    @property
    def hood_rib_inset_deg(self) -> float:
        """
        DERIVED. Arc a rib gives up at EACH end so it never projects past the
        panel it stiffens.

        A rib sits at radius R + rib_depth, so swept over the panel's own arc
        its ends land radially outside the panel's ends. What "outside" costs
        depends on which end, and the panel has to clear a different obstacle at
        each: the shell rim below it, the anode beam above it.

        Work in Z, since both obstacles are horizontal surfaces. A point at
        angle t sits at z = cz + R*cos(t), so the rib stays inside the panel's
        own vertical envelope when, pulled back by an angle d at each end,

            top:     (R + depth) * cos(t_start + d) <= R * cos(t_start)
            bottom:  (R + depth) * cos(t_end   - d) >= R * cos(t_end)

        Both solve exactly for d. The inset applied is the LARGER of the two,
        at both ends, because a rib that stops short of one edge and not the
        other is not a stiffener, it is a mistake.

        Which end binds is not fixed. Through Phase 2 it was the bottom, and
        25 mm of rib depth put the rib 24 mm under the landing edge, so a panel
        would rock on its stiffeners instead of seating on the shell rim.
        Deriving the panel's roll moved its lower end to 85 deg - near
        horizontal, where cos is small and the bottom stops binding altogether -
        and handed the constraint to the top end, against the anode beam. A
        formula written for the bottom alone returns a NEGATIVE inset there,
        which is an overshoot wearing an inset's name: the rib would run past
        BOTH ends of the panel it stiffens, into the beam above. Hence max(0).
        """
        r = self.hood_radius
        depth = self.hooding.rib_depth
        t_start = math.radians(self.hood_start_deg)
        t_end = math.radians(self.hood_start_deg + self.hood_arc_deg)

        def _clamped_acos(x: float) -> float:
            return math.acos(max(-1.0, min(1.0, x)))

        top = _clamped_acos(r * math.cos(t_start) / (r + depth)) - t_start
        bottom = t_end - _clamped_acos(r * math.cos(t_end) / (r + depth))
        return math.degrees(max(0.0, top, bottom))

    @property
    def hood_rib_arc_deg(self) -> float:
        """Sweep of a rib: the panel's arc less the derived inset at both ends."""
        return self.hood_arc_deg - 2.0 * self.hood_rib_inset_deg

    @property
    def hood_rib_start_deg(self) -> float:
        return self.hood_start_deg + self.hood_rib_inset_deg

    # -- process cutter, shared by crust, cover AND bath ----------------------

    @property
    def anode_cut_bottom_z(self) -> float:
        """
        Floor of the anode-footprint cutter: the anode's working face, exactly.

        The cutter now runs against the BATH as well as the crust and cover,
        because the anodes are immersed and must displace what they are
        immersed in - the blockout cut only the crust and the cover, leaving
        every anode sharing 155 mm of its height with a solid bath.

        That is also why this stops dead at the working face instead of
        overshooting the way anode_cut_top_z does. Overshooting downward would
        carve out the ACD gap itself: the 45 mm of bath between the anode and
        the metal pad, which is the single most important dimension in the
        whole cell and is the one thing under an anode that must survive.

        No overshoot is needed here in any case. An overshoot exists to keep a
        cutter face off a face it cuts, and this plane sits strictly inside the
        bath, coplanar with nothing.
        """
        return self.z_anode_bottom

    @property
    def crust_feed_hole_diameter(self) -> float:
        """
        Opening a crust breaker leaves in the crust and cover. DERIVED from the
        chisel that makes it, widened by the bath melting back around the edge.
        """
        return self.feeder.chisel_diameter + 2.0 * self.feeder.crust_hole_clearance

    @property
    def anode_cut_top_z(self) -> float:
        """
        Ceiling of the cutter. Here an overshoot IS needed: the cover's top
        face is the last thing the cutter passes through, so stopping level
        with it would put the two coplanar.
        """
        return self.z_cover_top + self.process.crust_thickness

    # -- anode beam jacks -----------------------------------------------------

    @property
    def z_jack_base(self) -> float:
        """Jacks stand on a cap plate on the beam's top face."""
        return self.beam_top_z + self.hardware.jack_cap_t

    @property
    def jack_length(self) -> float:
        """
        DERIVED. A jack spans the whole gap from the beam cap to the portal tie
        it hangs from. Choosing a length would guarantee it either floats below
        the tie or drives through it.
        """
        return self.z_cross_base - self.z_jack_base


# ---------------------------------------------------------------------------
# Explosion rig
# ---------------------------------------------------------------------------

# Per-subsystem (direction_x, direction_y, direction_z, distance_mm).
# Direction is a unit-ish vector; distance is the travel at Explosion == 1.0.
# Rule: sensible single axes only. No radial scatter. Layers separate along the
# axis they stack on, so the assembly reads as a construction sequence.
EXPLOSION_VECTORS: dict[str, tuple[float, float, float, float]] = {
    "01_SHELL": (0.0, 0.0, -1.0, 4700.0),
    "02_REFRACTORY": (0.0, 0.0, -1.0, 2400.0),
    "03_CATHODE": (0.0, 0.0, 0.0, 0.0),  # datum, stays put
    "04_PROCESS": (0.0, 0.0, 1.0, 1200.0),
    "05_ANODES": (0.0, 0.0, 1.0, 4400.0),
    "06_BUSBARS": (0.0, 1.0, 0.0, 3000.0),
    "07_SUPERSTRUCTURE": (0.0, 0.0, 1.0, 7400.0),
    "08_HOODING": (0.0, 1.0, 0.0, 6100.0),  # mirrored per side at build time
    "09_HARDWARE": (0.0, 0.0, 1.0, 1900.0),
}
"""
Where each subsystem goes at Explosion = 1.0, in millimetres.

These distances are MEASURED, not chosen. The first set was chosen, and at 1.0
four pairs of subsystems were still solid-intersecting each other: a part cannot
be read as removed while it is still inside its neighbour.

A subsystem needs a distance larger than its own extent along the travel axis
plus its neighbour's, or the two simply move together and never part. So each
one is set from the evaluated bounding boxes, walking outward from the cathode
datum and leaving a 600 mm reading gap at every step:

    Z up     cathode -170..1180 (datum) -> process -> hardware -> anodes
             -> hood covers -> superstructure       ends at 12450
    Z down   refractory -> shell                    ends at -4715
    Y out    busbars 3000 -> hood panels 6100       (difference 3100 > the
             2488 mm the riser and panel envelopes overlap by while assembled)
    X out    end enclosures 3000                    clears the panel run by 959

The gap is 600 rather than something tighter because the assembled diagram is
17 m tall: a 200 mm gap at that scale is one pixel of white in a plate and reads
as contact. Verified by the pair-overlap audit, which is what produced every
number here.
"""

# Subsystems whose parts do NOT all travel together, and how they divide.
#
# One empty per collection is the default, and for six of the nine it is also
# correct. Three subsystems are not built that way in the first place, and
# forcing them onto a single vector produces a diagram that lies about how the
# cell comes apart:
#
#   06_BUSBARS  - the risers stand on the upstream (+Y) face, but the collector
#                 flexes exit BOTH ±Y faces, twenty a side. Sent one way, half
#                 of them travel back through the shell they came out of.
#   08_HOODING  - measured, not assumed: 28 side panels and their ribs, handles
#                 and doors sit clear of the centreline, while the 14 top covers
#                 and the two end enclosures span it. They are three different
#                 motions on a real pot: covers lift off, side panels swing out,
#                 end boxes withdraw along the cell.
#   09_HARDWARE - the collection is a bag of fasteners belonging to three
#                 different hosts, not a subsystem. Measured: 40 `flex_clamp` at
#                 Z 510 are the clamps ON the collector flexes, while 36 base
#                 plates and gussets sit on the shell rim at Z 1500 and 24 jacks
#                 ride the anode beam at Z 2400. Sending all of them +Z tore the
#                 40 clamps off the 40 flexes they grip, which were meanwhile
#                 travelling ±Y. The clamps therefore take the BUSBAR vector
#                 exactly: a clamp and its flex are one assembly and stay one.
#                 They are expected to overlap the bars at 1.0 — that pair is
#                 bolted together, and the audit's job is to find the pairs that
#                 are NOT.
#
# `mirror` means the group's two halves separate OUTWARD: the direction is
# flipped for parts lying on the negative side of its own dominant axis. That is
# what makes a mirrored subsystem open like a book rather than slide sideways.
#
# (suffix, families or None for "all the rest", dx, dy, dz, distance_mm, mirror)
EXPLOSION_SPLITS: dict[str, tuple[tuple[str, tuple[str, ...] | None,
                                        float, float, float, float, bool], ...]] = {
    "06_BUSBARS": (
        ("bars", None, 0.0, 1.0, 0.0, 3000.0, True),
    ),
    "08_HOODING": (
        # Ordered so the three groups stay legible as separate motions at 100%:
        # the covers rise clear of the anodes below and the portal above, the
        # panels swing out past the risers, the end boxes withdraw past both.
        ("covers", ("cover",), 0.0, 0.0, 1.0, 5800.0, False),
        ("ends", ("end_box", "end_cap", "end_rib", "number_plate"),
         1.0, 0.0, 0.0, 3000.0, True),
        ("panels", None, 0.0, 1.0, 0.0, 6100.0, True),
    ),
    "09_HARDWARE": (
        ("flexes", ("flex_clamp",), 0.0, 1.0, 0.0, 3000.0, True),
        ("frame", None, 0.0, 0.0, 1.0, 1900.0, False),
    ),
}

COLLECTIONS: tuple[str, ...] = (
    "00_REFERENCES",
    "01_SHELL",
    "02_REFRACTORY",
    "03_CATHODE",
    "04_PROCESS",
    "05_ANODES",
    "06_BUSBARS",
    "07_SUPERSTRUCTURE",
    "08_HOODING",
    "09_HARDWARE",
    "10_EXPLOSION",
    "11_CAMERAS",
    "12_LIGHTING",
)

# Triangle budget for the optimized WebGL export. The master ignores this.
GLB_TRIANGLE_BUDGET: int = 1_500_000

CELL = Cell()


# ---------------------------------------------------------------------------
# Self-check. Run `python spec.py` to verify internal consistency.
# ---------------------------------------------------------------------------


def _self_check() -> list[str]:
    """Return a list of problems. Empty list means the datasheet is coherent."""
    c = CELL
    problems: list[str] = []

    def require(cond: bool, msg: str) -> None:
        if not cond:
            problems.append(msg)

    # The SOURCED anchor must reproduce the SOURCED current density.
    cd = c.process.current_density_check(c.anodes)
    require(
        abs(cd - c.process.anodic_current_density_a_cm2) < 0.01,
        f"current density mismatch: derived {cd:.4f} vs "
        f"stated {c.process.anodic_current_density_a_cm2}",
    )

    require(len(c.anodes.positions()) == c.anodes.count, "anode position count wrong")
    require(
        len(c.cathode.block_positions_x()) == c.cathode.block_count,
        "cathode position count wrong",
    )

    # Geometry must close: nothing may overhang or invert.
    require(c.cathode_end_gap > 0, f"cathode run overflows cavity in X ({c.cathode_end_gap:.0f})")
    require(c.cathode_side_gap > 0, f"cathode block overflows cavity in Y ({c.cathode_side_gap:.0f})")
    require(c.anode_immersion > 0, f"anode does not reach the bath ({c.anode_immersion:.0f})")
    require(
        c.anode_immersion < c.process.bath_depth,
        f"anode pierces the metal pad (immersion {c.anode_immersion:.0f} "
        f">= bath {c.process.bath_depth:.0f})",
    )
    require(c.freeboard > 0, f"cover blanket overtops the shell rim ({c.freeboard:.0f})")

    # The rodding assembly must climb without inverting or floating.
    require(
        c.stem_height > 0,
        f"derived stem height is {c.stem_height:.0f}; the yoke top already "
        "sits above the anode beam",
    )
    require(
        c.stem_base_z > c.z_anode_top,
        "stem starts at or below the anode block top",
    )
    require(
        c.z_stem_top > c.beam_top_z,
        f"stem top {c.z_stem_top:.0f} does not clear the beam top {c.beam_top_z:.0f}",
    )
    require(c.z_anode_top > c.shell.rim_z, "anode top should clear the shell rim")

    # Ledge must not grow into the anode. Only heights where the anode actually
    # exists matter: the widest toe sits below the anode bottom face.
    require(
        c.ledge.intrusion_at_bath_mid < c.anodes.side_channel,
        f"ledge intrudes into the anode at mid-bath "
        f"({c.ledge.intrusion_at_bath_mid:.0f} vs channel {c.anodes.side_channel:.0f})",
    )
    require(
        c.ledge.intrusion_at_bath_top < c.anodes.side_channel,
        "ledge intrudes into the anode at the bath surface",
    )
    require(
        c.ledge.intrusion_at_metal > c.ledge.intrusion_at_bath_top,
        "ledge profile must taper inward-to-outward going up",
    )

    # Feeder must physically fit down the centre channel.
    widest = max(c.feeder.chute_diameter, c.feeder.cylinder_diameter)
    require(
        widest < c.anodes.centre_channel,
        f"feeder ({widest:.0f}) does not fit the centre channel "
        f"({c.anodes.centre_channel:.0f})",
    )
    require(
        len(c.feeder_positions_x()) == c.feeder.count,
        "feeder position count wrong",
    )

    # Crust sits on the bath and must clear the anode working face, since it
    # forms only in the channels around the anodes, never beneath one.
    require(
        c.z_bath_top > c.z_anode_bottom,
        "crust/bath geometry invalid: bath surface below the anode face",
    )

    # Cradles must fit within the shell length...
    cradle_xs = c.cradle_positions_x()
    require(
        len(cradle_xs) == c.shell.cradle_pairs,
        f"cradle stations {len(cradle_xs)}, wanted {c.shell.cradle_pairs}",
    )
    foot_half = c.shell.cradle_foot_x / 2.0
    require(
        max(abs(x) for x in cradle_xs) + foot_half <= c.shell_outer_x / 2.0 + 1e-6,
        "a cradle foot overhangs the end of the shell",
    )
    # ...and no cradle may stand where a collector bar comes out. This is the
    # check the derivation exists for: at a round 1200 mm pitch, four bars ran
    # through a web.
    widest_cradle = max(
        c.shell.cradle_thickness, c.shell.cradle_flange_x, c.shell.cradle_foot_x
    )
    clash = [
        (bx, kx)
        for bx in c.cathode.block_positions_x()
        for kx in cradle_xs
        if abs(bx - kx) < (widest_cradle + c.cathode.bar_w) / 2.0
    ]
    require(
        not clash,
        f"{len(clash)} collector bars run into a cradle, e.g. bar at "
        f"{clash[0][0]:.0f} against a cradle at {clash[0][1]:.0f}"
        if clash
        else "",
    )

    # End cradles. Rotated a quarter turn, so the foot that ran along the cell
    # now runs ACROSS it and must stay clear of the corner cradles on the sides.
    end_ys = c.end_cradle_positions_y()
    require(len(end_ys) >= 2, "an end wall with fewer than two cradles on it")
    require(
        max(abs(y) for y in end_ys) + c.shell.cradle_foot_x / 2.0
        <= c.shell_outer_y / 2.0 + 1e-6,
        "an end cradle foot overhangs the corner of the shell",
    )
    require(
        c.end_cradle_centre_x - c.shell.cradle_depth / 2.0
        >= c.shell_outer_x / 2.0 - 1e-6,
        "an end cradle reaches back inside the end wall it stands against",
    )

    # Hooding must fit the shell it covers, with the end boxes taking the
    # remaining length at each end.
    h = c.hooding
    sx = c.shell_outer_x
    require(h.panel_run_x(sx) > 0, "end boxes consume the entire shell length")
    require(
        h.panel_x(sx) > 2 * h.rib_pitch,
        f"hood panel {h.panel_x(sx):.0f} too narrow for its rib pitch",
    )
    require(
        abs(
            h.panels_per_side * h.panel_x(sx)
            + (h.panels_per_side - 1) * h.panel_gap
            - h.panel_run_x(sx)
        )
        < 1.0,
        "hood panel run does not close on the available length",
    )
    require(h.ribs_per_panel(sx) >= 3, "hood panel needs a readable rib rhythm")
    require(
        h.end_box_top_z > c.z_column_top,
        f"end boxes {h.end_box_top_z:.0f} should rise above the portal frame "
        f"{c.z_column_top:.0f}",
    )
    require(h.rib_depth < c.hood_radius, "rib depth must be small vs the panel curve")

    # The portal frame stacks upward and must never meet the rodding, the
    # feeders, or the hood. Each of these caught a real collision.
    require(
        c.z_cross_base >= c.z_stem_top,
        f"portal tie base {c.z_cross_base:.0f} is below the stem tops "
        f"{c.z_stem_top:.0f}",
    )
    require(
        c.z_column_top > c.beam_top_z,
        "portal frame does not reach above the anode beam",
    )
    require(
        c.column_centre_y - c.superstructure.column_section / 2.0
        >= c.shell_outer_y / 2.0,
        "portal columns stand inside the hood envelope",
    )
    require(
        c.cross_inner_y > c.feeder.chute_diameter / 2.0,
        "portal tie closes over the feeder chute",
    )
    require(
        c.deck_rail_centre_y - c.superstructure.deck_rail_section / 2.0
        < c.feeder.hopper_y / 2.0,
        "feeder deck rails sit outboard of the hopper; it would bear on nothing",
    )
    require(
        len(c.column_positions_x()) == c.superstructure.column_pairs,
        f"column station count is {len(c.column_positions_x())}, "
        f"expected {c.superstructure.column_pairs}",
    )
    require(
        all(
            abs(x) < sx / 2.0 - h.end_box_x for x in c.column_positions_x()
        ),
        "a portal column lands inside an end enclosure",
    )

    # The hood arc is fully derived; verify it actually closes on its anchors.
    require(c.hood_radius > 0, "hood arc radius derived non-positive")
    require(
        c.hood_apex_z < c.z_cross_base,
        f"hood crest {c.hood_apex_z:.0f} fouls the portal tie at "
        f"{c.z_cross_base:.0f}",
    )
    require(
        c.hood_arc_deg > 0,
        f"derived hood roll is {c.hood_arc_deg:.1f} deg; the anchors are too "
        f"close to one wall for a {h.roll_margin_deg:.1f} deg margin",
    )
    require(
        c.hood_start_deg + c.hood_arc_deg <= 90.0,
        "hood panel rolls past horizontal and would flare outside the shell",
    )
    require(
        c.hood_start_deg >= 0.0,
        f"hood panel starts at {c.hood_start_deg:.1f} deg, so it crests above "
        "its own top anchor and bulges into the anode beam",
    )
    require(
        c.hood_top_anchor[1] > c.hood_bottom_anchor[1],
        "hood panel would run uphill from the beam to the shell rim",
    )

    # -- Phase 3 detail: every added part must fit what it mounts on ----------

    # The clamp must genuinely bridge rod and beam, not merely sit near them.
    require(
        c.anodes.clamp_y / 2.0 > c.anodes.stem_section / 2.0,
        f"clamp ({c.anodes.clamp_y:.0f}) does not reach across the stem "
        f"({c.anodes.stem_section:.0f}); it grips nothing",
    )
    require(
        c.anodes.clamp_z <= c.superstructure.beam_z_section,
        f"clamp {c.anodes.clamp_z:.0f} is deeper than the beam section "
        f"{c.superstructure.beam_z_section:.0f} it bolts to",
    )
    require(
        c.beam_centre_y - c.superstructure.beam_y / 2.0
        >= c.anodes.row_centre_y + c.anodes.stem_section / 2.0 - 1.0,
        "anode beam overlaps the stem it is clamped to",
    )
    # The beam must still bear over the anodes it carries, or the load path is
    # a cantilever off the rod rather than a beam over the row.
    require(
        c.beam_centre_y - c.superstructure.beam_y / 2.0
        < c.anodes.row_centre_y + c.anodes.block_y / 2.0,
        "anode beam sits entirely outboard of the anode row",
    )

    # Anode gas slots must not cut the block in half.
    require(
        c.anodes.slot_depth < c.anodes.block_z,
        "anode gas slot is deeper than the anode block",
    )
    require(
        c.anodes.slot_count * c.anodes.slot_width < c.anodes.block_x,
        "anode gas slots consume the whole block width",
    )
    require(
        c.anodes.stub_diameter + 2.0 * c.anodes.stub_socket_clearance
        < c.anodes.block_x,
        "stub socket is wider than the anode block",
    )

    # The cutter must reach down INTO the bath, so the immersed anodes displace
    # it - but no further, or it eats the ACD gap it is sitting above.
    require(
        c.z_metal_top < c.anode_cut_bottom_z < c.z_bath_top,
        f"anode cutter floor at {c.anode_cut_bottom_z:.0f} is not strictly "
        f"inside the bath ({c.z_metal_top:.0f}..{c.z_bath_top:.0f}); it either "
        "fails to displace the bath or carves out the ACD gap",
    )
    require(
        c.anode_cut_bottom_z == c.z_anode_bottom,
        "anode cutter floor has drifted off the anode working face",
    )
    require(
        c.anode_cut_top_z > c.z_cover_top,
        "anode cutter does not clear the cover blanket",
    )

    # Hood ribs must survive their own inset and still read as ribs.
    require(
        c.hood_rib_arc_deg <= c.hood_arc_deg,
        f"hood rib sweeps {c.hood_rib_arc_deg:.1f} deg over a "
        f"{c.hood_arc_deg:.1f} deg panel, so it overhangs both ends of the "
        "panel it is supposed to stiffen",
    )
    require(
        c.hood_rib_arc_deg > 0,
        f"hood rib inset {c.hood_rib_inset_deg:.1f} deg consumes the whole "
        f"{c.hood_arc_deg:.1f} deg panel arc",
    )
    require(
        c.hood_rib_arc_deg > c.hood_arc_deg / 2.0,
        f"hood rib spans only {c.hood_rib_arc_deg:.1f} of "
        f"{c.hood_arc_deg:.1f} deg; it would stiffen half a panel",
    )
    require(
        h.handle_standoff > h.rib_depth,
        "hood handle stands off less than the ribs it sits among; it could not "
        "be gripped",
    )

    # The anode beam must hang from something.
    require(
        c.jack_length > 0,
        f"derived jack length is {c.jack_length:.0f}; the beam cap already "
        f"reaches the portal tie at {c.z_cross_base:.0f}",
    )
    require(
        c.hardware.jack_screw_diameter < c.hardware.jack_body_diameter,
        "jack screw is thicker than the body it retracts into",
    )
    require(
        max(c.hardware.jack_cap_x, c.hardware.jack_cap_y)
        >= c.hardware.jack_body_diameter,
        "jack cap plate is smaller than the jack body bearing on it",
    )
    require(
        c.hardware.jack_cap_y <= c.superstructure.beam_y,
        f"jack cap {c.hardware.jack_cap_y:.0f} overhangs the beam "
        f"{c.superstructure.beam_y:.0f} it sits on",
    )

    # Column base plates must bear on the cradles, and must not reach inboard
    # into the strip of shell rim the hood panel comes down to land on.
    require(
        c.base_plate_y <= c.shell.cradle_depth,
        f"column base plate {c.base_plate_y:.0f} wide overhangs the "
        f"{c.shell.cradle_depth:.0f} cradle band it bears on",
    )
    require(
        c.column_centre_y - c.base_plate_y / 2.0 >= c.hood_bottom_anchor[0],
        f"column base plate reaches inboard to "
        f"{c.column_centre_y - c.base_plate_y / 2.0:.0f}, past the "
        f"{c.hood_bottom_anchor[0]:.0f} where the hood panel lands",
    )
    # Gussets stand on the plate's X overhang, so they must fit it, and they
    # must not climb past the top of the column they stiffen.
    require(
        c.hardware.gusset_run <= (c.base_plate_x - c.superstructure.column_section) / 2.0,
        "column gusset runs past the end of its own base plate",
    )
    require(
        c.hardware.gusset_rise < c.z_column_top - c.z_column_base,
        "column gusset is taller than the column",
    )

    # A laminated flex must still fit the connector envelope it replaces.
    stack = (
        c.busbars.flex_laminates - 1
    ) * c.busbars.flex_laminate_gap
    require(
        stack < c.busbars.flex_section,
        f"flex laminate gaps total {stack:.0f}, more than the "
        f"{c.busbars.flex_section:.0f} connector section",
    )

    # The crust must be pierced where a chisel passes through it.
    require(
        c.crust_feed_hole_diameter < c.anodes.centre_channel,
        f"crust feed hole {c.crust_feed_hole_diameter:.0f} is wider than the "
        f"centre channel {c.anodes.centre_channel:.0f}",
    )
    # ...and consecutive feed holes must not run into one another, or the
    # cluster cutter self-intersects and EXACT returns a wrong solid silently.
    feed_xs = c.feeder_positions_x()
    if len(feed_xs) > 1:
        pitch = min(b - a for a, b in zip(feed_xs, feed_xs[1:]))
        require(
            pitch > c.crust_feed_hole_diameter,
            f"feed holes {c.crust_feed_hole_diameter:.0f} wide at {pitch:.0f} "
            "pitch overlap each other",
        )

    # The hopper must actually neck down, and its outlet must pass the chute
    # without swallowing it. Both ends of the taper are checked because a
    # fraction of 0 or 1 degenerates the loft into a slab or a spike.
    f = c.feeder
    require(
        0.0 < f.hopper_taper_fraction < 1.0,
        f"hopper taper fraction {f.hopper_taper_fraction} is not a proper share "
        "of the hopper height",
    )
    require(
        f.hopper_outlet < min(f.hopper_x, f.hopper_y),
        f"hopper outlet {f.hopper_outlet:.0f} is no smaller than the hopper "
        f"section {min(f.hopper_x, f.hopper_y):.0f} - nothing tapers",
    )
    require(
        f.hopper_outlet >= f.chute_diameter,
        f"hopper outlet {f.hopper_outlet:.0f} throttles its own "
        f"{f.chute_diameter:.0f} chute",
    )

    # The duct's terminating flange must be wider than the duct and must sit
    # beyond the shell, in the stub, or it would be buried in the end box.
    require(
        c.superstructure.duct_flange_diameter > c.superstructure.duct_diameter,
        "duct flange is not wider than the duct it terminates",
    )
    require(
        c.superstructure.duct_flange_t < c.superstructure.duct_stub,
        f"duct flange {c.superstructure.duct_flange_t:.0f} thick does not fit "
        f"the {c.superstructure.duct_stub:.0f} stub beyond the shell",
    )

    # The offtake throat: its mouth must sit wholly on the roof it opens into,
    # and it must actually rise, or the header goes back to lying on the box.
    require(
        c.duct_throat_mouth_x > 0.0,
        f"duct throat margin {c.superstructure.duct_throat_margin:.0f} consumes "
        f"the whole {c.hooding.end_box_x:.0f} end box roof",
    )
    require(
        c.duct_throat_mouth_x + 2.0 * c.superstructure.duct_throat_margin
        <= c.hooding.end_box_x,
        "duct throat mouth overhangs the end enclosure roof",
    )
    require(
        c.duct_throat_mouth_y <= c.shell_outer_y,
        "duct throat mouth is wider than the enclosure it draws from",
    )
    require(
        c.superstructure.duct_throat_rise > 0.0,
        "duct throat has no rise; the header is tangent on the roof again",
    )
    require(
        c.z_duct_underside > c.z_end_box_roof,
        f"duct underside {c.z_duct_underside:.0f} is not above the end box "
        f"roof {c.z_end_box_roof:.0f}",
    )

    # The riser arm laps the anode beam, so it crosses the column line at beam
    # height and must pass through a BAY. This is the check that makes
    # riser_positions_x worth deriving at all.
    column_xs = c.column_positions_x()
    riser_xs = c.riser_positions_x()
    require(
        len(riser_xs) == c.busbars.riser_count,
        f"{len(riser_xs)} riser bays available for "
        f"{c.busbars.riser_count} risers",
    )
    clearance = (c.busbars.riser_w + c.superstructure.column_section) / 2.0
    for rx in riser_xs:
        nearest = min(abs(rx - cx) for cx in column_xs)
        require(
            nearest > clearance,
            f"riser at x={rx:.0f} stands {nearest:.0f} from a portal column; "
            f"its arm needs {clearance:.0f} to pass",
        )
    require(
        c.z_riser_top == c.beam_top_z,
        "riser no longer rises to the beam top it laps over",
    )
    require(
        c.busbars.arm_t > 0.0,
        "riser arm has no depth, so the riser ends in a bare face again",
    )

    # End enclosure detail: the door run must fit the face, the frame must
    # stand clear of the ribs, and the cap must overhang the box it caps.
    door_ys = c.hooding.end_box_door_positions_y(c.shell_outer_y)
    require(
        min(door_ys) - c.hooding.end_box_door_w / 2.0
        - c.hooding.end_box_frame_grow
        >= -c.shell_outer_y / 2.0,
        "end enclosure door frames run off the end face",
    )
    # The plaque goes in the bay BETWEEN the doors - with a 1600 mm door on a
    # 1685 mm face there is no band above them to put it in.
    plate_bay = 2.0 * (
        min(abs(y) for y in door_ys)
        - c.hooding.end_box_door_w / 2.0
        - c.hooding.end_box_frame_grow
    )
    require(
        c.hooding.end_box_plate_w <= plate_bay,
        f"pot number plaque {c.hooding.end_box_plate_w:.0f} wide does not fit "
        f"the {plate_bay:.0f} bay between the door frames",
    )
    require(
        c.hooding.end_box_door_h < c.hooding.end_box_top_z - c.shell_outer_z,
        f"end enclosure door {c.hooding.end_box_door_h:.0f} is taller than the "
        f"{c.hooding.end_box_top_z - c.shell_outer_z:.0f} face it is cut into",
    )
    require(
        c.hooding.end_box_frame_t > c.hooding.rib_depth,
        "end enclosure door frame does not stand clear of its own ribs",
    )
    require(
        c.hooding.end_box_door_t > c.hooding.end_box_frame_t,
        "end enclosure door leaf sits inside its frame",
    )
    require(
        c.hooding.end_box_plate_t > c.hooding.rib_depth,
        f"pot number plaque {c.hooding.end_box_plate_t:.0f} deep sinks behind "
        f"the {c.hooding.rib_depth:.0f} ribs it is mounted over",
    )
    require(
        c.hooding.end_ribs_across(c.shell_outer_y) >= 3
        and c.hooding.end_ribs_along() >= 3,
        "end enclosure needs a readable rib rhythm on every face",
    )
    require(
        c.hooding.end_box_cap_grow > 0.0,
        "end enclosure cap does not overhang, so it reads as no cap at all",
    )

    # The whole feeder stack must stand between the end enclosures, which are
    # solid across the full width of the cell. Checked on the widest component,
    # not the centreline: the chute of the outermost feeder is what actually
    # struck the box.
    run_limit = c.hooding.panel_run_x(c.shell_outer_x) / 2.0
    outermost = max(abs(x) for x in c.feeder_positions_x())
    require(
        outermost + f.widest_component / 2.0 <= run_limit,
        f"outermost feeder reaches {outermost + f.widest_component / 2.0:.0f}, "
        f"past the end enclosure at {run_limit:.0f}",
    )

    # A centre cover rests on the beams' inner ledges and must not run into the
    # beams themselves, nor reach past the anode stems it is slotted around.
    require(
        c.centre_cover_half_y
        <= c.beam_centre_y - c.superstructure.beam_y / 2.0,
        f"centre cover reaches {c.centre_cover_half_y:.0f}, into the anode beam "
        f"whose inner face is at {c.beam_centre_y - c.superstructure.beam_y / 2.0:.0f}",
    )
    require(
        c.centre_cover_hole_diameter > c.feeder.chute_diameter,
        "centre cover hole does not clear its own chute",
    )
    cover_xs = c.hooding.centre_cover_positions_x(c.shell_outer_x)
    cover_w = c.hooding.centre_cover_x(c.shell_outer_x)
    require(
        abs((max(cover_xs) + cover_w / 2.0) - run_limit) < 1e-6,
        f"centre covers close on {max(cover_xs) + cover_w / 2.0:.0f}, not on the "
        f"hood run end at {run_limit:.0f}",
    )

    # A lifting handle must stand clear of the ribs, or a hand reaching under
    # it closes on a stiffener instead of the handle.
    require(
        c.hooding.handle_standoff > c.hooding.rib_depth,
        f"handle standoff {c.hooding.handle_standoff:.0f} does not clear the "
        f"{c.hooding.rib_depth:.0f} ribs it sits among",
    )
    require(
        c.hood_start_deg
        < c.hood_handle_deg
        < c.hood_start_deg + c.hood_arc_deg,
        "lifting handles sit off the panel they lift",
    )
    # ...and the handle's outer face must not reach the columns it sits between.
    handle_r = c.hood_handle_radius + c.hooding.handle_section
    handle_y = c.hood_arc_centre[0] + handle_r * math.sin(
        math.radians(c.hood_handle_deg)
    )
    require(
        handle_y < c.column_centre_y - c.superstructure.column_section / 2.0,
        f"hood handle reaches y={handle_y:.0f}, into the column face at "
        f"{c.column_centre_y - c.superstructure.column_section / 2.0:.0f}",
    )

    # -- hardware -----------------------------------------------------------
    # A jack must actually span the gap it was invented to close: it stands on
    # the beam's cap plate and reaches the tie above.
    require(
        c.jack_length > 0.0,
        f"jack length {c.jack_length:.0f}: the portal tie is not above the "
        "beam cap it is supposed to hang from",
    )
    require(
        0.0 < c.hardware.jack_body_fraction < 1.0,
        "jack body fraction is not a proper share of the jack length",
    )
    require(
        abs(c.jack_body_length + c.jack_screw_length - c.jack_length) < 1e-6,
        "jack body and screw do not add up to the jack",
    )
    require(
        c.hardware.jack_screw_diameter < c.hardware.jack_body_diameter,
        "jack screw is not narrower than the body it runs in",
    )
    require(
        max(c.hardware.jack_cap_x, c.hardware.jack_cap_y)
        >= c.hardware.jack_body_diameter,
        "jack cap plate is narrower than the jack standing on it",
    )
    require(
        c.hardware.jack_cap_y <= c.superstructure.beam_y,
        f"jack cap {c.hardware.jack_cap_y:.0f} overhangs the "
        f"{c.superstructure.beam_y:.0f} beam it sits on",
    )
    # Jacks stand where a tie already crosses a beam - the only place the load
    # has anywhere to go.
    require(
        c.cross_inner_y
        <= c.beam_centre_y
        <= c.column_centre_y + c.superstructure.column_section / 2.0,
        "the portal tie does not reach over the beam its jacks hang from",
    )

    # A base plate must sit on the cradle band and carry its own gussets.
    require(
        c.base_plate_x >= c.superstructure.column_section,
        "column base plate is shorter than the column standing on it",
    )
    require(
        c.hardware.gusset_rise < c.z_column_top - c.z_column_base,
        "column gusset is taller than the column it braces",
    )

    # A flex clamp must lap both parts of the joint and stay clear of the
    # cradles it passes between.
    require(
        c.flex_clamp_x > c.busbars.flex_section,
        "flex clamp is narrower than the connector it grips",
    )
    require(
        c.z_flex_clamp_base >= c.bar_z_centre + c.busbars.flex_section / 2.0,
        "flex clamp is buried in the laminate stack it lies on",
    )
    clamp_gap = min(
        abs(bx - kx)
        for bx in c.cathode.block_positions_x()
        for kx in c.cradle_positions_x()
    )
    require(
        clamp_gap
        > (c.flex_clamp_x + max(c.shell.cradle_foot_x, c.shell.cradle_flange_x))
        / 2.0,
        f"flex clamps {c.flex_clamp_x:.0f} wide foul the cradles at "
        f"{clamp_gap:.0f} clearance",
    )

    # Every collection that moves must be a real collection.
    for name in EXPLOSION_VECTORS:
        require(name in COLLECTIONS, f"explosion vector for unknown collection {name}")

    # A split subsystem must still be one: exactly one catch-all group, so no
    # part can fall through the table and stay behind while its neighbours move.
    for name, groups in EXPLOSION_SPLITS.items():
        require(name in EXPLOSION_VECTORS, f"split for unknown subsystem {name}")
        require(
            sum(1 for g in groups if g[1] is None) == 1,
            f"{name} splits need exactly one catch-all group (families=None)",
        )
        claimed: set[str] = set()
        for _suffix, families, *_rest in groups:
            for fam in families or ():
                require(fam not in claimed, f"{name} family {fam!r} claimed twice")
                claimed.add(fam)

    return problems


def _report() -> None:
    c = CELL
    print("=" * 68)
    print("  400 kA PREBAKE CELL - DERIVED GEOMETRY")
    print("=" * 68)
    print(f"  anode area            {c.process.anode_area_m2(c.anodes):10.2f} m^2")
    print(f"  current density       {c.process.current_density_check(c.anodes):10.3f} A/cm^2")
    print("  " + "-" * 64)
    print(f"  cavity                {c.cavity_x:10.0f} x {c.cavity_y:.0f} mm")
    print(f"  shell inner           {c.shell_inner_x:10.0f} x {c.shell_inner_y:.0f} mm")
    print(f"  shell outer           {c.shell_outer_x:10.0f} x {c.shell_outer_y:.0f}"
          f" x {c.shell_outer_z:.0f} mm")
    print("  " + "-" * 64)
    print(f"  z cathode bottom      {c.z_cathode_bottom:10.0f} mm")
    print(f"  z cathode top         {c.z_cathode_top:10.0f} mm")
    print(f"  z metal top           {c.z_metal_top:10.0f} mm")
    print(f"  z bath top            {c.z_bath_top:10.0f} mm")
    print(f"  z crust top           {c.z_crust_top:10.0f} mm")
    print(f"  z cover top           {c.z_cover_top:10.0f} mm")
    print(f"  z anode bottom        {c.z_anode_bottom:10.0f} mm  (ACD {c.process.acd:.0f})")
    print(f"  z anode top           {c.z_anode_top:10.0f} mm")
    print(f"  z shell rim           {c.shell.rim_z:10.0f} mm")
    print("  " + "-" * 64)
    print(f"  anode immersion       {c.anode_immersion:10.0f} mm  (derived)")
    print(f"  freeboard             {c.freeboard:10.0f} mm  (derived)")
    print(f"  cathode end gap       {c.cathode_end_gap:10.0f} mm  (derived)")
    print(f"  cathode side gap      {c.cathode_side_gap:10.0f} mm  (derived)")
    print(f"  collector half length {c.bar_half_length:10.0f} mm  (derived)")
    print("  " + "-" * 64)
    print(f"  ledge at metal        {c.ledge.intrusion_at_metal:10.0f} mm")
    print(f"  ledge at bath top     {c.ledge.intrusion_at_bath_top:10.0f} mm")
    print(f"  anode side channel    {c.anodes.side_channel:10.0f} mm")
    print(f"  centre channel        {c.anodes.centre_channel:10.0f} mm")
    print(f"  feeders               {c.feeder.count:10d}  at x="
          + ", ".join(f"{x:.0f}" for x in c.feeder_positions_x()))
    print("  " + "-" * 64)
    h, sx = c.hooding, c.shell_outer_x
    print(f"  hood panels/side      {h.panels_per_side:10d}")
    print(f"  hood panel width      {h.panel_x(sx):10.0f} mm  (derived)")
    print(f"  hood panel run        {h.panel_run_x(sx):10.0f} mm  (derived)")
    print(f"  ribs per panel        {h.ribs_per_panel(sx):10d}  (derived)")
    print(f"  end box centre        {h.end_box_centre_x(sx):10.0f} mm  (derived)")
    print(f"  hood radius           {c.hood_radius:10.0f} mm  (derived)")
    print(f"  hood arc centre       {c.hood_arc_centre[0]:10.0f}, "
          f"{c.hood_arc_centre[1]:.0f} mm  (derived)")
    print(f"  hood start angle      {c.hood_start_deg:10.1f} deg  (derived)")
    print(f"  hood crest z          {c.hood_apex_z:10.0f} mm  (derived)")
    print("  " + "-" * 64)
    print(f"  z beam top            {c.beam_top_z:10.0f} mm")
    print(f"  z stem top            {c.z_stem_top:10.0f} mm  (derived)")
    print(f"  z portal tie base     {c.z_cross_base:10.0f} mm  (derived)")
    print(f"  z column top          {c.z_column_top:10.0f} mm  (derived)")
    print(f"  z deck top            {c.z_deck_top:10.0f} mm  (derived)")
    print(f"  z hopper base         {c.z_hopper_base:10.0f} mm  (derived)")
    print(f"  z breaker base        {c.z_breaker_base:10.0f} mm  (derived)")
    print(f"  column centre |y|     {c.column_centre_y:10.0f} mm  (derived)")
    print(f"  tie inner |y|         {c.cross_inner_y:10.0f} mm  (derived)")
    print(f"  deck rail |y|         {c.deck_rail_centre_y:10.0f} mm  (derived)")
    print(f"  columns               {c.superstructure.column_pairs:10d}  at x="
          + ", ".join(f"{x:.0f}" for x in c.column_positions_x()))
    print("=" * 68)

    problems = _self_check()
    if problems:
        print(f"  FAIL - {len(problems)} problem(s):")
        for p in problems:
            print(f"    - {p}")
    else:
        print("  PASS - datasheet is internally consistent.")
    print("=" * 68)


if __name__ == "__main__":
    import sys

    _report()
    sys.exit(1 if _self_check() else 0)

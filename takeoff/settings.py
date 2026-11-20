"""
Everything you might want to tune lives in this file.

Change a number here, save, and run the takeoff again. You never need to
touch the other files to adjust waste, defaults, or which products get used.
"""

# ---------------------------------------------------------------------------
# AI models
# ---------------------------------------------------------------------------
# Overridable in your .env file with GEMINI_MODEL=... / CLAUDE_MODEL=...
DEFAULT_MODEL = "gemini-3.1-pro-preview"
CLAUDE_DEFAULT_MODEL = "claude-opus-5-5"

# How many times the verify-and-correct loop may run after the first read.
MAX_CORRECTION_ROUNDS = 1

# ---------------------------------------------------------------------------
# Waste factors (decimal). Applied to the raw MEASUREMENT before it is
# converted into boxes / bundles / pieces.
# ---------------------------------------------------------------------------
WASTE = {
    "none": 0.00,        # plates, headers, beams, posts, hardware, windows, doors, wrap, fasteners
    "framing_roof": 0.05,  # rafters, ceiling joists
    "drywall_finish": 0.05,  # tape, joint compound
    "standard": 0.10,    # studs, subfloor, shingles, nails, drywall, trim, siding, soffit
    "sheathing": 0.12,   # OSB wall & roof sheathing
    "subfloor": 0.10,    # floor sheathing
    "rafters_hip": 0.10, # hip/valley roofs: jacks cut from longer stock
}

# ---------------------------------------------------------------------------
# Defaults. Used ONLY when the plans don't say. Every use is written to the
# Estimator Notes tab so you can see what was assumed.
# ---------------------------------------------------------------------------
DEFAULT_STUD_SPACING_IN = 16
DEFAULT_RAFTER_SPACING_IN = 16
DEFAULT_PITCH = 5.0          # rise per 12
DEFAULT_OVERHANG_IN = 12
DEFAULT_STUD_SIZE = "2x4"
DEFAULT_RAFTER_SIZE = "2x8"         # only if the plans give no rafter size (flagged)

# ---------------------------------------------------------------------------
# Lumber
# ---------------------------------------------------------------------------
LUMBER_GRADE = "#2 SPF"                   # how plain dimensional lumber is described
STOCK_LENGTHS_FT = (8, 10, 12, 14, 16, 18, 20, 22, 24)
LONGEST_DIMENSIONAL_FT = 24               # longer than this -> special order length
SPECIAL_ORDER_LENGTHS_FT = (26, 28, 30, 32)  # available by special order; longer -> LVL/splice
PRECUT_STUDS_IN = {"92-5/8": 92.625, "104-5/8": 104.625, "116-5/8": 116.625}
LVL_STOCK_LENGTHS_FT = (8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32)
NEST_CUTS_UNDER_FT = 6                    # cuts this short are nested several per board
NEST_STOCK_FT = 12.0                      # ...on boards of this length

# ---------------------------------------------------------------------------
# What's included. "framing" = floor, wall and roof framing, sheathing, wrap,
# deck framing. "full" adds roofing, siding/trim, insulation, drywall,
# finishes, windows, doors and paint.
# ---------------------------------------------------------------------------
DEFAULT_SCOPE = "full"
FRAMING_TRADES = {1, 2, 3, 6}
FRAMING_EXTRA_DESCRIPTIONS = {"House Wrap", "House Wrap Tape"}

# ---------------------------------------------------------------------------
# Framing rules of thumb (tune to how your builders frame)
# ---------------------------------------------------------------------------
# Stud count (BYU-Idaho Construction Estimating Reference Book method):
#   studs = wall LF / spacing + 2 per corner or intersection
#           + 2 per window/door under 6' wide + 6 per WINDOW 6' or wider
#   (king studs come from the on-center studs left out of the opening)
STUDS_PER_CORNER = 2
STUDS_PER_OPENING_UNDER_6FT = 2
STUDS_PER_WINDOW_6FT_PLUS = 6
STUDS_PER_DOOR_6FT_PLUS = 0
DEFAULT_CORNERS_PER_EXTERIOR_RUN = 1   # used only when the plans weren't counted (flagged)
DEFAULT_INTERSECTIONS_PER_INTERIOR_LF = 0.1
HEADER_PLIES = 2
HEADER_BEARING_IN = 3                # added to rough opening width
LVL_ABOVE_WIDTH_IN = 72              # openings wider than this get an LVL line (verify size!)
DEFAULT_HEADER_NOMINAL = "2x10"
FLY_RAFTERS_PER_GABLE_END = 2        # extra rafters for rake overhang / ladders
BLOCKING_ROWS = 1                    # rows of solid blocking per LF of wall (fireblocking / backing)
FIREBLOCK_MAX_FT = 10                # IRC R602.8: concealed wall cavities blocked at <= 10' intervals
ANCHOR_BOLT_MAX_OC_FT = 6            # IRC R403.1.6: sill anchor bolts <= 6' O.C.
ANCHOR_BOLTS_EXTRA_PER_RUN = 2       # IRC R403.1.6: one within 12" of each end of each plate section
HIP_VALLEY_LVL_OVER_FT = 24          # hips/valleys longer than this become LVL (common plan note)
SUBFLOOR_SF_PER_ADHESIVE_TUBE = 100  # 28 oz tube
RIM_STOCK_FT = 16
SUB_FASCIA_NOMINAL = "2x6"
SOFFIT_FRAMING_LF_PER_EAVE_LF = 2.0  # 2x4 soffit ledger + lookouts (0 to turn off)
SOFFIT_FRAMING_NOMINAL = "2x4"
ROOF_BRACING_PCS_PER_100SF = 0.9     # 16' braces per 100 SF of roof, each of 2x4 and 2x6 (0 to turn off)

# ---------------------------------------------------------------------------
# Roofing
# ---------------------------------------------------------------------------
ICE_BARRIER_REQUIRED = True          # Chicago area: yes
ICE_BARRIER_INSIDE_WALL_IN = 24      # code: at least 24" inside the exterior wall line
ICE_BARRIER_ROLL_WIDTH_IN = 36
RIDGE_VENT_END_GAP_FT = 1.0          # stop ridge vent this far from each end

# ---------------------------------------------------------------------------
# Rules of thumb for consumables (coverage is in the catalog CSV; these are
# only "how much of the thing do we need" rules)
# ---------------------------------------------------------------------------
HOUSEWRAP_TAPE_LF_PER_SF = 0.15      # seam tape LF per SF of wall wrapped
SIDING_WASTE_WALLS = 0.10            # book: rectangular wall areas
SIDING_WASTE_GABLES = 0.30           # book: gables / triangles
SIDING_MIN_OPENING_SF = 25           # book: only subtract openings 25 SF or larger
SHINGLES_PER_BUNDLE = 27             # standard size (21 for metric)
NAILS_PER_SHINGLE = 6
ROOFING_NAILS_PER_BOX = 7200
STARTER_ON_RAKES = False             # book: starter along horizontal edges only
SHEATHING_CLIPS_PER_PANEL = 2        # only used when rafter spacing >= 24"

# ---------------------------------------------------------------------------
# Which catalog item to use for each job. Must match material_key values in
# references/materials.csv. Swap these to change products.
# ---------------------------------------------------------------------------
KEYS = {
    "sill_seal": "sill_seal_5_5x50",
    "wall_sheathing": "osb_7_16_4x8",
    "roof_sheathing": "osb_7_16_4x8",
    "sheathing_clips": "sheathing_clips_250pk",
    "hurricane_tie": "simpson_h2_5a",
    "shingles": "shingles_gaf_charcoal",
    "ridge_cap": "ridge_cap_gaf_charcoal",
    "starter_shingles": "starter_gaf_charcoal",
    "underlayment": "underlayment_synthetic",
    "ice_barrier": "ice_water_weatherwatch",
    "ridge_vent": "ridge_vent_cobra_4ft",
    "drip_edge": "drip_edge_white_10ft",
    "roofing_nails": "coil_roofing_nails_7200",
    "housewrap": "housewrap_tyvek_9x150",
    "housewrap_tape": "housewrap_tape_2x164",
    "flashing_tape": "flashing_tape_6x50",
    "cap_nails": "cap_nails_3000pk",
    "siding_fiber_cement": "siding_hardie_hz5_8_25",
    "siding_vinyl": "siding_vinyl_d4_5_white",
    "starter_fiber_cement": "starter_strip_galv_10ft",
    "starter_vinyl": "starter_vinyl_12ft",
    "exterior_trim_fiber_cement": "trim_hardie_5_4x6x12",
    "j_channel_vinyl": "j_channel_vinyl_12ft",
    "soffit_vented": "soffit_vinyl_vented_12x12",
    "drywall_1_2": "drywall_1_2_4x12",
    "drywall_5_8x": "drywall_5_8_typex_4x12",
    "drywall_mold": "drywall_1_2_mold_4x8",
    "drywall_tape": "drywall_tape_250ft",
    "joint_compound": "joint_compound_4_5gal",
    "drywall_screws_1_2": "drywall_screws_1_25_25lb",
    "drywall_screws_5_8": "drywall_screws_1_625_25lb",
    "subfloor_plywood": "plywood_tg_3_4_4x8",
    "subfloor_advantech": "subfloor_advantech_23_32",
    "subfloor_adhesive": "adhesive_subfloor_28oz",
    "anchor_bolt": "anchor_bolt_1_2x10",
}

# ---------------------------------------------------------------------------
# Trade sections (number and tab name). Matches the Blueprint-Takeoff layout.
# ---------------------------------------------------------------------------
TRADES = {
    1: "Floor System",
    2: "Wall Material",
    3: "Roof Framing",
    4: "Roofing Material",
    5: "Siding and Exterior Trim",
    6: "Exterior Deck",
    7: "Insulation Material",
    8: "Drywall Material",
    9: "Interior Finishes",
    10: "Windows",
    11: "Doors (Exterior and Interior)",
    12: "Paint",
}

DISCLAIMER = (
    "In calculating the quantity of material needed to complete this project, we have used "
    "reasonable efforts to provide an accurate estimate. However, the lists provided are to be "
    "considered estimates only. Therefore, there is no guarantee or warranty that the actual "
    "amount of material will not deviate from the provided lists. Builder to verify all material "
    "takeoff quantities as field conditions may require alterations."
)

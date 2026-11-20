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

# ---------------------------------------------------------------------------
# Framing rules of thumb (tune to how your builders frame)
# ---------------------------------------------------------------------------
EXTRA_STUDS_PER_EXTERIOR_RUN = 2     # corner / end studs
EXTRA_STUDS_PER_INTERIOR_RUN = 2     # intersection backing
EXTRA_STUDS_PER_OPENING = 4          # 2 king + 2 jack
HEADER_PLIES = 2
HEADER_BEARING_IN = 3                # added to rough opening width
LVL_ABOVE_WIDTH_IN = 72              # openings wider than this get an LVL line (verify size!)
DEFAULT_HEADER_NOMINAL = "2x10"
FLY_RAFTERS_PER_GABLE_END = 2        # extra rafters for rake overhang / ladders

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
SHEATHING_CLIPS_PER_PANEL = 2        # only used when rafter spacing >= 24"

# ---------------------------------------------------------------------------
# Which catalog item to use for each job. Must match material_key values in
# references/home_depot_chicago_skus.csv. Swap these to change products.
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
    "framing_nails": "framing_nails_16d",
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

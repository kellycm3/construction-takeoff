"""
The shapes of the data Gemini must return.

Gemini only reports MEASUREMENTS here: lengths, heights, counts of openings,
specs as printed. No piece counts, no waste, no SKUs.

Note: no field has a default value on purpose. The Gemini API rejects
response schemas that contain defaults.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Source(BaseModel):
    sheet: str = Field(description="Sheet number the value came from, e.g. A1.1. Use 'unknown' if the sheet has no number.")
    source_note: str = Field(description="The exact dimension string or callout used, e.g. '24\\'-0\"' or '2x6 @ 16\" O.C.'")
    measured_by_scale: bool = Field(description="True only if no dimension was written and the value was scaled off the drawing.")
    confidence: Literal["high", "medium", "low"]


class WallRun(BaseModel):
    zone: str = Field(description="Building/area this wall belongs to, e.g. 'Main', 'STORAGE'. Use the same zone names everywhere.")
    label: str = Field(description="Short name, e.g. 'North exterior', 'Grid A', 'Gable - East'")
    length_ft: float = Field(description="Wall length in decimal feet")
    height_ft: Optional[float] = Field(description="Plate height in decimal feet. For a gable end, the gable RISE at the peak. Null if not shown.")
    stud_size: Optional[str] = Field(description="'2x4' or '2x6' as noted. Null if not shown.")
    spacing_in: Optional[float] = Field(description="Stud spacing in inches. Null if not shown.")
    exterior: bool
    is_gable_end: bool = Field(description="True for the triangular gable wall above the plate line.")
    is_furring: bool = Field(description="True for furring/strapping walls built against concrete (e.g. basement foundation walls): treated plates, drywall one side, no sheathing.")
    source: Source


class Opening(BaseModel):
    zone: str
    mark: str = Field(description="Schedule mark, e.g. '101'. Use 'none' if not on a schedule.")
    kind: Literal["window", "door", "overhead_door", "opening"]
    width_in: float = Field(description="Rough or nominal width in inches, as scheduled")
    height_in: float = Field(description="Height in inches, as scheduled")
    count: int
    exterior: bool
    header_spec: Optional[str] = Field(description="Header callout as printed, e.g. '(2) 2x10' or '1-3/4x11-7/8 LVL'. Null if not shown.")
    schedule_specs: Optional[str] = Field(description="Type, swing, U-factor, SHGC, rating, material, exactly as printed.")
    source: Source


class RoofPlane(BaseModel):
    zone: str
    style: Literal["gable", "hip", "shed", "other"]
    building_length_ft: float = Field(description="Wall-to-wall length parallel to the ridge, decimal feet")
    building_width_ft: float = Field(description="Wall-to-wall span perpendicular to the ridge, decimal feet")
    pitch_rise_per_12: Optional[float]
    overhang_eave_in: Optional[float]
    overhang_rake_in: Optional[float]
    rafter_size: Optional[str] = Field(description="e.g. '2x6'. Null if trusses or not shown.")
    rafter_spacing_in: Optional[float]
    uses_trusses: bool
    hip_valley_member: Optional[str] = Field(description="Hip/valley/ridge member as printed, e.g. '1-3/4x14 LVL' or '2x10'. Null if not shown.")
    valleys: int = Field(description="Number of valleys where this roof meets another roof (0 if none)")
    joins_other_roof_at_one_end: bool = Field(description="True if one end of this roof dies into another roof (no rake/gable at that end)")
    ceiling_joist_size: Optional[str] = Field(description="e.g. '2x10'. Null if none or not shown.")
    covering: Optional[str] = Field(description="Roof covering as noted, e.g. 'architectural asphalt shingles'")
    source: Source


class FloorSystem(BaseModel):
    zone: str = Field(description="Zone whose FLOOR this is (e.g. '1st Floor' for the 1st floor deck)")
    area_sf: float = Field(description="Framed floor area, outside of exterior walls")
    perimeter_lf: Optional[float] = Field(description="Rim length (outside perimeter of the framed floor)")
    joist_member: Optional[str] = Field(description="As printed, e.g. '2x10', '11-7/8\" TJI 110', '12\" open web'. Null if not shown.")
    spacing_in: Optional[float]
    typical_span_ft: Optional[float] = Field(description="Typical clear span of the joists in feet (bearing to bearing)")
    subfloor: Optional[str] = Field(description="As printed, e.g. '3/4\" T&G plywood' or '23/32\" AdvanTech'")
    new_framing: bool = Field(description="False if the plans keep existing joists (subfloor only or nothing)")
    source: Source


class ZoneSpec(BaseModel):
    zone: str
    floor_area_sf: Optional[float]
    ceiling_area_sf: Optional[float]
    siding_type: Optional[Literal["fiber_cement", "vinyl", "brick", "wood", "other", "none"]]
    wall_drywall: Optional[Literal["1/2", "5/8_type_x", "1/2_mold", "none"]] = Field(description="Drywall on walls")
    ceiling_drywall: Optional[Literal["1/2", "5/8_type_x", "1/2_mold", "none"]] = Field(description="Drywall on ceilings")
    source: Source


class OtherItem(BaseModel):
    zone: str
    trade_no: int = Field(description="1 Floor System, 2 Wall, 3 Roof Framing, 4 Roofing, 5 Siding/Trim, 6 Deck, 7 Insulation, 8 Drywall, 9 Interior Finishes, 10 Windows, 11 Doors, 12 Paint")
    material_key: str = Field(description="One of the provided material_keys; or 'lumber:<nominal>' / 'lumber:<nominal>:pt' for dimensional lumber (e.g. 'lumber:2x10:pt'); or 'UNLISTED'")
    description: str = Field(description="What it is and where, e.g. 'Floor joists 2x10 @ 16\" O.C.' or 'Interior wall paint'")
    measure: float = Field(description="The MEASUREMENT, not a piece count: LF of joists, SF of paint area, BF of spray foam, or EA for countable items")
    measure_unit: Literal["LF", "SF", "BF", "CY", "EA"]
    piece_length_ft: Optional[float] = Field(description="For lumber given in LF: the length each piece must be (e.g. joist span). Null if not applicable.")
    source: Source


class PlanExtraction(BaseModel):
    project_name: str
    plan_scale: Optional[str]
    walls: List[WallRun]
    openings: List[Opening]
    roofs: List[RoofPlane]
    zones: List[ZoneSpec]
    floors: List[FloorSystem]
    other_items: List[OtherItem]
    not_found: List[str] = Field(description="Checklist items that are not shown on the plans")
    estimator_notes: List[str] = Field(description="Conflicts, ambiguities, assumptions, things to verify")


class Issue(BaseModel):
    field: str = Field(description="Which part of the extraction, e.g. 'walls[2].length_ft'")
    problem: str
    fix: str
    sheet: str


class Verification(BaseModel):
    issues: List[Issue]

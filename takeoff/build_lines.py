"""
Turns Gemini's measurements into material lines.

This is where the estimating rules live. Every rule is plain Python, so the
same plans always give the same numbers, and you can read exactly how each
quantity was figured. Tune the numbers in settings.py, not here.
"""
import math
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import settings as S
from .calc_quantities import (
    bigger_nominal, gable_area_sf, gable_rise_ft, ice_barrier_courses, order_units,
    rafter_length_ft, raw_units, slope_factor, studs_for_run,
)
from .map_skus import Catalog, CatalogItem
from .schemas import Opening, PlanExtraction, RoofPlane, WallRun, ZoneSpec


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class Line:
    zone: str
    trade_no: int
    description: str               # sub-assembly, e.g. "Studs", "Sill Plates"
    material_key: Optional[str]    # catalog key, or None for special-order / unlisted
    measure: float                 # LF / SF / EA ... the thing waste applies to
    measure_unit: str
    waste: float
    product_override: str = ""     # used when there is no catalog item
    pieces: bool = False           # True = measure is a piece count (coverage 1)
    uom_text: str = ""             # what shows in the UOM column, e.g. "88 LF"
    notes: List[str] = field(default_factory=list)


@dataclass
class Row:
    zone: str
    trade_no: int
    sku: str
    product: str
    description: str
    quantity: int
    unit: str
    uom: str
    waste: float
    adjusted: int
    measure: float
    coverage: float
    notes: str
    material_key: str


@dataclass
class ZoneSummary:
    zone: str
    ceiling_area_sf: float = 0
    floor_area_sf: float = 0
    wall_gross_sf: float = 0
    wall_net_sf: float = 0
    perimeter_lf: float = 0
    sill_lf: float = 0


@dataclass
class Takeoff:
    project_name: str
    rows: List[Row]
    notes: List[str]
    summaries: Dict[str, ZoneSummary]
    zones: List[str]


class NoteBook:
    """Collects estimator notes without duplicates, in order."""
    def __init__(self):
        self._n: "OrderedDict[str, None]" = OrderedDict()

    def add(self, text: str):
        self._n[text] = None

    def all(self) -> List[str]:
        return list(self._n)


def _fmt(n: float) -> str:
    return f"{n:,.0f}" if abs(n - round(n)) < 0.05 else f"{n:,.1f}"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _parse_nominal(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.lower().replace(" ", "").replace("×", "x")
    for nom in ("2x12", "2x10", "2x8", "2x6", "2x4"):
        if nom in t:
            return nom
    return None


KERF_FT = 0.125 / 12  # 1/8" saw kerf per cut


def _bin_pack(cuts_ft: List[float], stock_ft: float) -> int:
    """First-fit-decreasing: how many stock boards to cut these pieces from."""
    bins: List[float] = []
    for c in sorted((c + KERF_FT for c in cuts_ft), reverse=True):
        for i, free in enumerate(bins):
            if free >= c - 1e-6:
                bins[i] = free - c
                break
        else:
            bins.append(stock_ft - c)
    return len(bins)


def _lumber_line(cat: Catalog, nb: NoteBook, zone: str, trade: int, desc: str, nominal: str,
                 cut_len_ft: float, count: int, waste: float, treated=False, note="") -> Line:
    item = cat.lumber(nominal, cut_len_ft, treated)
    notes = [note] if note else []
    if item is None:
        nb.add(f"{zone}: no {'PT ' if treated else ''}{nominal} at least {cut_len_ft:.1f} ft in the catalog for {desc}; "
               f"add one to the CSV or quote at Pro Desk.")
        return Line(zone, trade, desc, None, count, "EA", waste, pieces=True,
                    product_override=f"{nominal} x {math.ceil(cut_len_ft)}' {'PT ' if treated else ''}lumber",
                    uom_text=f"{_fmt(count * cut_len_ft)} LF", notes=notes + ["Pro Desk: verify SKU"])
    return Line(zone, trade, desc, item.material_key, count, "EA", waste, pieces=True,
                uom_text=f"{_fmt(count * cut_len_ft)} LF", notes=notes)


def _continuous_line(cat: Catalog, nb: NoteBook, zone: str, trade: int, desc: str, nominal: str,
                     lf: float, waste: float, treated=False, note="") -> Line:
    """Plates, fascia, ridge: runs that can be spliced, so LF / board length."""
    item = cat.longest_lumber(nominal, treated)
    notes = [note] if note else []
    if item is None:
        nb.add(f"{zone}: no {'PT ' if treated else ''}{nominal} in the catalog for {desc}.")
        return Line(zone, trade, desc, None, lf, "LF", waste, product_override=f"{nominal} {'PT ' if treated else ''}lumber",
                    uom_text=f"{_fmt(lf)} LF", notes=notes + ["Pro Desk: verify SKU"])
    return Line(zone, trade, desc, item.material_key, lf, "LF", waste, uom_text=f"{_fmt(lf)} LF", notes=notes)


def _item_line(zone, trade, desc, key, measure, unit, waste, uom_text=None, note="") -> Line:
    return Line(zone, trade, desc, key, measure, unit, waste,
                uom_text=uom_text or f"{_fmt(measure)} {unit}", notes=[note] if note else [])


# ---------------------------------------------------------------------------
# Trade rules
# ---------------------------------------------------------------------------
def _walls(zone, walls: List[WallRun], openings: List[Opening], roofs: List[RoofPlane],
           cat: Catalog, nb: NoteBook, summ: ZoneSummary) -> List[Line]:
    L: List[Line] = []
    T = 2
    ext = [w for w in walls if w.exterior and not w.is_gable_end]
    inner = [w for w in walls if not w.exterior and not w.is_gable_end]
    gables = [w for w in walls if w.is_gable_end]

    def spacing(w):
        if w.spacing_in:
            return w.spacing_in
        nb.add(f"{zone}: stud spacing not shown for '{w.label}'; used default {S.DEFAULT_STUD_SPACING_IN}\" O.C.")
        return S.DEFAULT_STUD_SPACING_IN

    def size(w):
        if w.stud_size and _parse_nominal(w.stud_size):
            return _parse_nominal(w.stud_size)
        nb.add(f"{zone}: stud size not shown for '{w.label}'; used default {S.DEFAULT_STUD_SIZE}.")
        return S.DEFAULT_STUD_SIZE

    ext_doors = [o for o in openings if o.exterior and o.kind in ("door", "overhead_door")]
    door_width_lf = sum(o.width_in * o.count for o in ext_doors) / 12
    perimeter = sum(w.length_ft for w in ext)
    sill_lf = max(perimeter - door_width_lf, 0)
    summ.perimeter_lf += perimeter
    summ.sill_lf += sill_lf

    # Sanity check: perimeter vs roof footprint
    for r in roofs:
        expected = 2 * (r.building_length_ft + r.building_width_ft)
        if ext and abs(expected - perimeter) > 1.0:
            nb.add(f"{zone}: exterior walls add up to {perimeter:.1f} LF but the roof footprint "
                   f"({r.building_length_ft:g}' x {r.building_width_ft:g}') implies {expected:.1f} LF. "
                   f"Check for missing or extra wall runs (fine if the building isn't a rectangle).")

    main_size = size(max(ext, key=lambda w: w.length_ft)) if ext else S.DEFAULT_STUD_SIZE

    # --- Sill plates (PT) and sill seal
    if sill_lf > 0:
        L.append(_continuous_line(cat, nb, zone, T, "Sill Plates", main_size, sill_lf, S.WASTE["none"], treated=True,
                                  note=f"Exterior walls less {_fmt(door_width_lf)} LF of door openings"))
        L.append(_item_line(zone, T, "Sill Seal", S.KEYS["sill_seal"], sill_lf, "LF", S.WASTE["none"]))

    # --- Plates by stud size
    plate_lf: Dict[str, float] = defaultdict(float)
    bottom_int_lf: Dict[str, float] = defaultdict(float)
    for w in ext + inner:
        plate_lf[size(w)] += 2 * w.length_ft
    for w in inner:
        bottom_int_lf[size(w)] += w.length_ft
    for nom, lf in plate_lf.items():
        L.append(_continuous_line(cat, nb, zone, T, "Top Plates", nom, lf, S.WASTE["none"], note="Double top plate"))
    for nom, lf in bottom_int_lf.items():
        L.append(_continuous_line(cat, nb, zone, T, "Bottom Plates (Interior)", nom, lf, S.WASTE["none"],
                                  note="Use PT if interior walls sit on concrete"))

    # --- Studs grouped by (size, height)
    groups: Dict[Tuple[str, float], int] = defaultdict(int)
    for w in ext + inner:
        if w.height_ft is None:
            nb.add(f"{zone}: wall height missing for '{w.label}' ({w.source.sheet}); studs and sheathing for it were skipped.")
            continue
        n = studs_for_run(w.length_ft, spacing(w))
        n += S.EXTRA_STUDS_PER_EXTERIOR_RUN if w.exterior else S.EXTRA_STUDS_PER_INTERIOR_RUN
        groups[(size(w), w.height_ft)] += n
    if groups:
        biggest = max(groups, key=groups.get)
        n_open = sum(o.count for o in openings)
        groups[biggest] += n_open * S.EXTRA_STUDS_PER_OPENING
    for (nom, h), count in groups.items():
        item = cat.stud(nom, h)
        desc = "Studs"
        note = f"{_fmt(h)}' walls; incl. corners and king/jack studs"
        if item:
            L.append(Line(zone, T, desc, item.material_key, count, "EA", S.WASTE["standard"], pieces=True,
                          uom_text=f"{count} EA", notes=[note]))
        else:
            L.append(_lumber_line(cat, nb, zone, T, desc, nom, h, count, S.WASTE["standard"],
                                  note=note + "; no precut stud for this height, cut from stock"))

    # --- Gable-end studs
    for g in gables:
        h = g.height_ft
        if h is None:
            r = next((r for r in roofs if r.style == "gable"), None)
            if r:
                h = gable_rise_ft(g.length_ft, r.pitch_rise_per_12 or S.DEFAULT_PITCH)
        if not h:
            nb.add(f"{zone}: gable '{g.label}' has no height and no roof pitch to compute it; skipped.")
            continue
        sp = spacing(g) / 12
        half = g.length_ft / 2
        cuts, x = [], sp
        while x < g.length_ft - 1e-6:  # studs between the corners, each cut to the rake line
            cuts.append(h * (1 - abs(x - half) / half))
            x += sp
        cuts = [c for c in cuts if c > 0.25]
        nom = size(g)
        stock = cat.lumber(nom, max(cuts)) if cuts else None
        if stock:
            boards = _bin_pack(cuts, stock.length_ft)
            L.append(Line(zone, T, "Gable Studs", stock.material_key, boards, "EA", S.WASTE["standard"], pieces=True,
                          uom_text=f"{_fmt(sum(cuts))} LF",
                          notes=[f"{g.label}: {len(cuts)} studs ({_fmt(sum(cuts))} LF) cut from {_fmt(stock.length_ft)}' boards"]))
        elif cuts:
            L.append(_lumber_line(cat, nb, zone, T, "Gable Studs", nom, max(cuts), len(cuts), S.WASTE["standard"]))

    # --- Headers
    std_cuts: Dict[str, List[float]] = defaultdict(list)
    for o in openings:
        if o.kind == "opening" and not o.header_spec:
            continue
        span_ft = (o.width_in + S.HEADER_BEARING_IN) / 12
        spec = (o.header_spec or "").lower()
        if "lvl" in spec or o.width_in > S.LVL_ABOVE_WIDTH_IN:
            lvl = next((i for i in cat.items.values() if i.category == "lvl" and (i.length_ft or 0) >= span_ft), None)
            note = f"Mark {o.mark} ({_fmt(o.width_in)}\" wide): header per plans '{o.header_spec or 'not shown'}'. Verify LVL depth."
            if not o.header_spec:
                nb.add(f"{zone}: no header callout for wide opening Mark {o.mark}; LVL size must come from the plans or engineer.")
            if lvl:
                L.append(Line(zone, T, "Headers", lvl.material_key, S.HEADER_PLIES * o.count, "EA", S.WASTE["none"],
                              pieces=True, uom_text=f"{_fmt(span_ft * S.HEADER_PLIES * o.count)} LF", notes=[note]))
            else:
                L.append(Line(zone, T, "Headers", None, S.HEADER_PLIES * o.count, "EA", S.WASTE["none"], pieces=True,
                              product_override=f"LVL header {_fmt(span_ft)}' ", notes=[note, "Pro Desk: verify SKU"]))
            continue
        nom = _parse_nominal(o.header_spec)
        if not nom:
            nom = S.DEFAULT_HEADER_NOMINAL
            nb.add(f"{zone}: no header size for Mark {o.mark}; used ({S.HEADER_PLIES}) {nom} default. Verify.")
        std_cuts[nom].extend([span_ft] * (S.HEADER_PLIES * o.count))
    for nom, cuts in std_cuts.items():
        stock = cat.lumber(nom, max(cuts))
        if stock:
            boards = _bin_pack(cuts, stock.length_ft)
            L.append(Line(zone, T, "Headers", stock.material_key, boards, "EA", S.WASTE["none"], pieces=True,
                          uom_text=f"{_fmt(sum(cuts))} LF", notes=[f"{len(cuts)} header plies cut from {_fmt(stock.length_ft)}' boards"]))
        else:
            L.append(_lumber_line(cat, nb, zone, T, "Headers", nom, max(cuts), len(cuts), S.WASTE["none"]))

    # --- Wall sheathing (exterior + gables, less openings)
    gross = 0.0
    for w in ext:
        if w.height_ft:
            gross += w.length_ft * w.height_ft
    for g in gables:
        h = g.height_ft
        if h is None:
            r = next((r for r in roofs if r.style == "gable"), None)
            h = gable_rise_ft(g.length_ft, (r.pitch_rise_per_12 or S.DEFAULT_PITCH)) if r else 0
        gross += gable_area_sf(g.length_ft, h)
    open_sf = sum(o.width_in * o.height_in * o.count for o in openings if o.exterior) / 144
    net = max(gross - open_sf, 0)
    summ.wall_gross_sf += gross
    summ.wall_net_sf += net
    if net > 0:
        L.append(_item_line(zone, T, "Exterior Wall Sheathing", S.KEYS["wall_sheathing"], net, "SF", S.WASTE["sheathing"],
                            note="Net of openings; includes gable ends" if gables else "Net of openings"))
    return L


def _roof(zone, roofs: List[RoofPlane], cat: Catalog, nb: NoteBook) -> Tuple[List[Line], List[Line], float]:
    frame: List[Line] = []
    cover: List[Line] = []
    footprint = 0.0
    for r in roofs:
        pitch = r.pitch_rise_per_12
        if pitch is None:
            pitch = S.DEFAULT_PITCH
            nb.add(f"{zone}: roof pitch not shown; used default {S.DEFAULT_PITCH:g}/12.")
        eave = r.overhang_eave_in if r.overhang_eave_in is not None else S.DEFAULT_OVERHANG_IN
        rake = r.overhang_rake_in if r.overhang_rake_in is not None else (eave if r.style == "hip" else S.DEFAULT_OVERHANG_IN)
        if r.overhang_eave_in is None or (r.style == "gable" and r.overhang_rake_in is None):
            nb.add(f"{zone}: roof overhang not fully shown; used default {S.DEFAULT_OVERHANG_IN}\".")
        Lb, Wb = r.building_length_ft, r.building_width_ft
        footprint += Lb * Wb
        sf = slope_factor(pitch)
        area = (Lb + 2 * rake / 12) * (Wb + 2 * eave / 12) * sf
        rafter_len = rafter_length_ft(Wb / 2, eave, pitch)

        if r.style == "gable":
            ridge_lf = Lb + 2 * rake / 12
            eave_lf = 2 * ridge_lf
            rake_lf = 4 * rafter_len
            hip_lf = 0.0
        elif r.style == "hip":
            run = Wb / 2 + eave / 12
            ridge_lf = max(Lb - Wb, 0)
            hip_lf = 4 * math.sqrt(2 * run ** 2 + (run * pitch / 12) ** 2)
            eave_lf = 2 * (Lb + 2 * eave / 12) + 2 * (Wb + 2 * eave / 12)
            rake_lf = 0.0
            nb.add(f"{zone}: hip roof framing is not auto-calculated; only sheathing and roofing were. Add hip/jack rafters from the framing plan.")
        else:
            nb.add(f"{zone}: '{r.style}' roof is not auto-calculated. Add roof materials manually.")
            continue

        # ---- Roof framing (trade 3)
        T = 3
        spacing = r.rafter_spacing_in or S.DEFAULT_RAFTER_SPACING_IN
        if not r.rafter_spacing_in:
            nb.add(f"{zone}: rafter/truss spacing not shown; used default {S.DEFAULT_RAFTER_SPACING_IN}\" O.C.")
        per_side = studs_for_run(Lb, spacing)
        if r.uses_trusses:
            frame.append(Line(zone, T, "Roof Trusses", None, per_side, "EA", S.WASTE["none"], pieces=True,
                              product_override=f"Roof truss package, {Wb:g}' span, {pitch:g}/12, {spacing:g}\" O.C.",
                              uom_text=f"{per_side} EA", notes=["Special Order / Pro Desk Quote (truss layout)"]))
        elif r.style == "gable":
            nom = _parse_nominal(r.rafter_size)
            if not nom:
                nb.add(f"{zone}: rafter size not shown on plans; rafters not calculated. Get size from plans/engineer.")
            else:
                main = 2 * per_side
                fly = S.FLY_RAFTERS_PER_GABLE_END * 2
                frame.append(_lumber_line(cat, nb, zone, T, "Rafters", nom, rafter_len + 0.25, main + fly, S.WASTE["framing_roof"],
                                          note=f"{spacing:g}\" O.C. both slopes + {fly} fly/ladder; cut length {rafter_len:.1f}'"))
                ridge_nom = bigger_nominal(nom) or nom
                frame.append(_continuous_line(cat, nb, zone, T, "Ridge Board", ridge_nom, ridge_lf, S.WASTE["none"]))
                frame.append(_continuous_line(cat, nb, zone, T, "Sub Fascia (Eave)", nom, eave_lf, S.WASTE["none"]))
                frame.append(_item_line(zone, T, "Hurricane Ties", S.KEYS["hurricane_tie"], main, "EA", S.WASTE["none"],
                                        note="1 per rafter at the wall plate"))
            cj = _parse_nominal(r.ceiling_joist_size)
            if cj:
                count = per_side
                if cat.lumber(cj, Wb):
                    frame.append(_lumber_line(cat, nb, zone, T, "Ceiling Joists", cj, Wb, count, S.WASTE["framing_roof"],
                                              note=f"{spacing:g}\" O.C. spanning {Wb:g}'"))
                else:
                    frame.append(_lumber_line(cat, nb, zone, T, "Ceiling Joists", cj, Wb / 2 + 1, count * 2, S.WASTE["framing_roof"],
                                              note=f"Lapped over center bearing; no {cj} long enough for a {Wb:g}' span"))
                    nb.add(f"{zone}: ceiling joists lapped at mid-span, which needs a center bearing wall or beam. Verify with plans.")
            elif r.ceiling_joist_size is None:
                nb.add(f"{zone}: ceiling joist size not shown (or none). Not calculated.")

        frame.append(_item_line(zone, T, "Roof Sheathing", S.KEYS["roof_sheathing"], area, "SF", S.WASTE["sheathing"],
                                note=f"{r.style}, {pitch:g}/12, {_fmt(eave)}\" eave / {_fmt(rake)}\" rake overhang"))
        if spacing >= 24:
            sheets = math.ceil(area * (1 + S.WASTE["sheathing"]) / 32)
            frame.append(_item_line(zone, T, "Sheathing Clips", S.KEYS["sheathing_clips"],
                                    sheets * S.SHEATHING_CLIPS_PER_PANEL, "EA", S.WASTE["none"]))

        # ---- Roofing (trade 4)
        T = 4
        cover.append(_item_line(zone, T, "Shingles", S.KEYS["shingles"], area, "SF", S.WASTE["standard"]))
        cover.append(_item_line(zone, T, "Underlayment", S.KEYS["underlayment"], area, "SF", S.WASTE["standard"]))
        if S.ICE_BARRIER_REQUIRED:
            courses = ice_barrier_courses(eave, pitch, S.ICE_BARRIER_INSIDE_WALL_IN, S.ICE_BARRIER_ROLL_WIDTH_IN)
            ib_sf = eave_lf * courses * S.ICE_BARRIER_ROLL_WIDTH_IN / 12
            cover.append(_item_line(zone, T, "Ice & Water Barrier", S.KEYS["ice_barrier"], ib_sf, "SF", S.WASTE["none"],
                                    note=f"{courses} course(s) at eaves to {S.ICE_BARRIER_INSIDE_WALL_IN}\" inside wall line"))
        cover.append(_item_line(zone, T, "Starter Shingles", S.KEYS["starter_shingles"], eave_lf + rake_lf, "LF",
                                S.WASTE["standard"], note="Eaves + rakes"))
        cover.append(_item_line(zone, T, "Ridge Cap Shingles", S.KEYS["ridge_cap"], ridge_lf + hip_lf, "LF", S.WASTE["standard"],
                                note="Ridge + hips" if hip_lf else ""))
        vent_lf = max((Lb if r.style == "gable" else ridge_lf) - 2 * S.RIDGE_VENT_END_GAP_FT, 0)
        if vent_lf > 0:
            cover.append(_item_line(zone, T, "Ridge Vent", S.KEYS["ridge_vent"], vent_lf, "LF", S.WASTE["none"],
                                    note=f"Stops {S.RIDGE_VENT_END_GAP_FT:g}' from each end"))
        cover.append(_item_line(zone, T, "Drip Edge", S.KEYS["drip_edge"], eave_lf + rake_lf, "LF", S.WASTE["standard"],
                                note="Eaves + rakes"))
        cover.append(_item_line(zone, T, "Roofing Nails", S.KEYS["roofing_nails"], area, "SF", S.WASTE["standard"]))
    return frame, cover, footprint


def _siding(zone, walls, openings, spec: Optional[ZoneSpec], roofs, summ: ZoneSummary, nb: NoteBook) -> List[Line]:
    T = 5
    L: List[Line] = []
    gross, net = summ.wall_gross_sf, summ.wall_net_sf
    if gross <= 0:
        return L
    L.append(_item_line(zone, T, "House Wrap", S.KEYS["housewrap"], gross, "SF", S.WASTE["none"], note="Gross wall area"))
    L.append(_item_line(zone, T, "House Wrap Tape", S.KEYS["housewrap_tape"], gross * S.HOUSEWRAP_TAPE_LF_PER_SF, "LF",
                        S.WASTE["none"], uom_text=f"{_fmt(gross)} SF"))
    ext_open = [o for o in openings if o.exterior]
    flash_lf = sum(((o.width_in + 2 * o.height_in) if o.kind == "overhead_door" else (2 * o.width_in + 2 * o.height_in)) / 12 * o.count
                   for o in ext_open)
    if flash_lf:
        L.append(_item_line(zone, T, "Window & Door Flashing Tape", S.KEYS["flashing_tape"], flash_lf, "LF", S.WASTE["none"]))
    L.append(_item_line(zone, T, "Cap Nails", S.KEYS["cap_nails"], gross, "SF", S.WASTE["none"]))

    siding = spec.siding_type if spec else None
    ext = [w for w in walls if w.exterior and not w.is_gable_end]
    corners = len(ext)
    avg_h = (sum(w.height_ft or 0 for w in ext) / len(ext)) if ext else 0
    casing_lf = sum(((o.width_in + 2 * o.height_in) if o.kind in ("door", "overhead_door") else (2 * o.width_in + 2 * o.height_in)) / 12 * o.count
                    for o in ext_open)
    eave_soffit_sf = 0.0
    for r in roofs:
        if r.style == "gable" and r.overhang_eave_in:
            eave_soffit_sf += 2 * (r.building_length_ft + 2 * (r.overhang_rake_in or 0) / 12) * r.overhang_eave_in / 12
    if siding == "fiber_cement":
        L.append(_item_line(zone, T, "Siding", S.KEYS["siding_fiber_cement"], net, "SF", S.WASTE["standard"], note="Net wall area incl. gables"))
        L.append(_item_line(zone, T, "Starter Strip", S.KEYS["starter_fiber_cement"], summ.sill_lf, "LF", S.WASTE["standard"]))
        trim_lf = corners * 2 * avg_h + casing_lf
        L.append(_item_line(zone, T, "Exterior Trim", S.KEYS["exterior_trim_fiber_cement"], trim_lf, "LF", S.WASTE["standard"],
                            note=f"{corners} corners x 2 boards + opening casings"))
    elif siding == "vinyl":
        L.append(_item_line(zone, T, "Siding", S.KEYS["siding_vinyl"], net, "SF", S.WASTE["standard"], note="Net wall area incl. gables"))
        L.append(_item_line(zone, T, "Starter Strip", S.KEYS["starter_vinyl"], summ.sill_lf, "LF", S.WASTE["standard"]))
        L.append(_item_line(zone, T, "J-Channel", S.KEYS["j_channel_vinyl"], casing_lf, "LF", S.WASTE["standard"], note="Around openings"))
    elif siding in ("brick", "wood", "other"):
        nb.add(f"{zone}: siding type '{siding}' is not auto-calculated. Net wall area is {_fmt(net)} SF.")
    elif siding is None:
        nb.add(f"{zone}: siding type not shown; siding not calculated. Net wall area is {_fmt(net)} SF.")
    if eave_soffit_sf:
        L.append(_item_line(zone, T, "Vented Soffit", S.KEYS["soffit_vented"], eave_soffit_sf, "SF", S.WASTE["standard"],
                            note="Eave soffit only; add rake soffit if used"))
    return L


def _drywall(zone, walls, openings, spec: Optional[ZoneSpec], footprint, summ: ZoneSummary, nb: NoteBook) -> List[Line]:
    T = 8
    L: List[Line] = []
    if spec is None:
        nb.add(f"{zone}: no drywall info for this zone; drywall not calculated.")
        return L
    wall_sf = sum(w.length_ft * (w.height_ft or 0) for w in walls if w.exterior and not w.is_gable_end)
    wall_sf += sum(2 * w.length_ft * (w.height_ft or 0) for w in walls if not w.exterior and not w.is_gable_end)
    wall_sf -= sum(o.width_in * o.height_in * o.count / 144 * (1 if o.exterior else 2) for o in openings)
    wall_sf = max(wall_sf, 0)
    ceiling_sf = spec.ceiling_area_sf if spec.ceiling_area_sf else footprint
    summ.ceiling_area_sf += ceiling_sf
    summ.floor_area_sf += spec.floor_area_sf or footprint
    type_key = {"1/2": "drywall_1_2", "5/8_type_x": "drywall_5_8x", "1/2_mold": "drywall_mold"}
    total = 0.0
    used_5_8 = used_1_2 = 0.0
    for label, kind, sf in (("Wall Drywall", spec.wall_drywall, wall_sf), ("Ceiling Drywall", spec.ceiling_drywall, ceiling_sf)):
        if kind in (None, "none") or sf <= 0:
            if kind is None:
                nb.add(f"{zone}: {label.lower()} type not shown; not calculated.")
            continue
        L.append(_item_line(zone, T, label, S.KEYS[type_key[kind]], sf, "SF", S.WASTE["standard"]))
        total += sf
        if kind == "5/8_type_x":
            used_5_8 += sf
        else:
            used_1_2 += sf
    if total:
        L.append(_item_line(zone, T, "Drywall Tape", S.KEYS["drywall_tape"], total, "SF", S.WASTE["drywall_finish"]))
        L.append(_item_line(zone, T, "Joint Compound", S.KEYS["joint_compound"], total, "SF", S.WASTE["drywall_finish"]))
        if used_1_2:
            L.append(_item_line(zone, T, "Drywall Screws (1/2\")", S.KEYS["drywall_screws_1_2"], used_1_2, "SF", S.WASTE["none"]))
        if used_5_8:
            L.append(_item_line(zone, T, "Drywall Screws (5/8\")", S.KEYS["drywall_screws_5_8"], used_5_8, "SF", S.WASTE["none"]))
    return L


def _openings(zone, openings: List[Opening]) -> List[Line]:
    L: List[Line] = []
    for o in openings:
        trade = 10 if o.kind == "window" else 11
        if o.kind == "opening":
            continue
        w_ft, w_in = divmod(round(o.width_in), 12)
        h_ft, h_in = divmod(round(o.height_in), 12)
        size = f"{w_ft}'-{w_in}\" x {h_ft}'-{h_in}\""
        kind = {"window": "Window", "door": "Door", "overhead_door": "Overhead Door"}[o.kind]
        product = f"Mark {o.mark}, {kind}, {size}" + (f", {o.schedule_specs}" if o.schedule_specs else "")
        L.append(Line(zone, trade, kind + (" (Exterior)" if o.exterior and o.kind == "door" else ""), None, o.count, "EA",
                      S.WASTE["none"], product_override=product, pieces=True, uom_text=f"{o.count} EA",
                      notes=["Special Order / Pro Desk Quote"]))
    return L


TRADE_WASTE = {1: "standard", 2: "standard", 3: "framing_roof", 4: "standard", 5: "standard", 6: "standard",
               7: "standard", 8: "standard", 9: "standard", 10: "none", 11: "none", 12: "none"}


def _others(items, cat: Catalog, nb: NoteBook) -> List[Line]:
    L: List[Line] = []
    for it in items:
        trade = it.trade_no if it.trade_no in S.TRADES else 9
        # Countable items (hardware, posts, fixtures) get no waste
        waste = S.WASTE["none"] if it.measure_unit == "EA" else S.WASTE[TRADE_WASTE[trade]]
        item = cat.get(it.material_key) if it.material_key != "UNLISTED" else None
        src = f"{it.source.sheet}: {it.source.source_note}"
        if item is None:
            L.append(Line(it.zone, trade, it.description, None, it.measure, it.measure_unit, waste,
                          product_override=it.description, pieces=(it.measure_unit == "EA"),
                          uom_text=f"{_fmt(it.measure)} {it.measure_unit}", notes=["Pro Desk: verify SKU", src]))
            continue
        line = Line(it.zone, trade, it.description, item.material_key, it.measure, it.measure_unit, waste,
                    uom_text=f"{_fmt(it.measure)} {it.measure_unit}", notes=[src])
        if it.measure_unit != item.coverage_unit:
            if it.measure_unit == "EA":
                line.pieces = True
            else:
                nb.add(f"{it.zone}: '{it.description}' measured in {it.measure_unit} but catalog item {item.material_key} "
                       f"is sold per {item.coverage_per_unit:g} {item.coverage_unit}. Quantity shown as-is; check it.")
                line.pieces = True
                line.notes.append("Unit mismatch: check quantity")
        L.append(line)
    return L


# ---------------------------------------------------------------------------
# Resolve lines against the catalog
# ---------------------------------------------------------------------------
def _resolve(line: Line, cat: Catalog) -> Row:
    notes = [n for n in line.notes if n]
    item: Optional[CatalogItem] = cat.get(line.material_key) if line.material_key else None
    if line.material_key and item is None:
        notes.append(f"'{line.material_key}' missing from catalog CSV")
    if item is None:
        coverage = 1.0 if (line.pieces or line.measure_unit == "EA") else 1.0
        sku, product, unit = "", line.product_override or line.description, "PCS"
        if "Pro Desk" not in " ".join(notes) and "Special Order" not in " ".join(notes):
            notes.append("Pro Desk: verify SKU")
    else:
        coverage = 1.0 if line.pieces else item.coverage_per_unit
        sku, product, unit = item.sku, item.product_title, item.unit
        if not sku:
            notes.append("Pro Desk: verify SKU")
        elif not item.verified_date:
            notes.append("SKU not yet verified")
        if item.notes:
            notes.append(item.notes)
        if not line.pieces and line.measure_unit != item.coverage_unit:
            notes.append(f"Unit mismatch: measured {line.measure_unit}, catalog {item.coverage_unit}")
    qty = raw_units(line.measure, coverage)
    adj = order_units(line.measure, line.waste, coverage)
    return Row(line.zone, line.trade_no, sku, product, line.description, qty, unit, line.uom_text, line.waste, adj,
               round(line.measure, 3), coverage, "; ".join(dict.fromkeys(notes)), line.material_key or "")


def build_takeoff(data: PlanExtraction, cat: Catalog) -> Takeoff:
    nb = NoteBook()
    for n in data.estimator_notes:
        nb.add(n)
    for n in data.not_found:
        nb.add(f"Not shown on plans: {n}")

    zones: List[str] = []
    for coll in (data.walls, data.openings, data.roofs, data.zones, data.other_items):
        for x in coll:
            if x.zone not in zones:
                zones.append(x.zone)

    lines: List[Line] = []
    summaries: Dict[str, ZoneSummary] = {}
    for z in zones:
        walls = [w for w in data.walls if w.zone == z]
        opens = [o for o in data.openings if o.zone == z]
        roofs = [r for r in data.roofs if r.zone == z]
        spec = next((s for s in data.zones if s.zone == z), None)
        summ = ZoneSummary(z)
        summaries[z] = summ
        lines += _walls(z, walls, opens, roofs, cat, nb, summ)
        frame, cover, footprint = _roof(z, roofs, cat, nb)
        lines += frame + cover
        lines += _siding(z, walls, opens, spec, roofs, summ, nb)
        if not footprint and spec and spec.floor_area_sf:
            footprint = spec.floor_area_sf
        lines += _drywall(z, walls, opens, spec, footprint, summ, nb)
        lines += _openings(z, opens)

    lines += _others(data.other_items, cat, nb)
    for z in zones:
        if z not in summaries:
            summaries[z] = ZoneSummary(z)

    nb.add("Not auto-calculated: framing nails, sheathing nails, construction adhesive, and anchor bolts "
           "(unless listed above). Add per builder preference.")
    rows = [_resolve(l, cat) for l in lines]
    rows.sort(key=lambda r: (zones.index(r.zone) if r.zone in zones else 99, r.trade_no))
    return Takeoff(data.project_name, rows, nb.all(), summaries, zones)

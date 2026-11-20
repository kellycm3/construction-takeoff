"""
Turns the measurements read from the plans into a material list.

Every quantity is figured here with plain, readable rules, so the same plans
always give the same numbers. Tune the numbers in settings.py, not here.
Materials are described by material and size; SKUs are optional.
"""
import math
import re
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import settings as S
from .calc_quantities import (
    bigger_nominal, gable_area_sf, gable_rise_ft, ice_barrier_courses, order_units,
    rafter_length_ft, raw_units, slope_factor, studs_for_run,
)
from .materials import Catalog, Material, lumber, lvl, precut_for_wall, stock_length, stud
from .schemas import FloorSystem, Opening, PlanExtraction, RoofPlane, WallRun, ZoneSpec


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class Line:
    zone: str
    trade_no: int
    description: str
    material: Optional[Material]
    measure: float
    measure_unit: str
    waste: float
    product_override: str = ""
    pieces: bool = False          # measure is a piece count (coverage 1)
    uom_text: str = ""
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
    gable_sf: float = 0
    rect_wall_sf: float = 0       # exterior wall area (rectangles) incl. floor framing depth
    big_openings_sf: float = 0    # exterior openings >= SIDING_MIN_OPENING_SF


@dataclass
class Takeoff:
    project_name: str
    rows: List[Row]
    notes: List[str]
    summaries: Dict[str, ZoneSummary]
    zones: List[str]
    scope: str = "full"


class NoteBook:
    def __init__(self):
        self._n: "OrderedDict[str, None]" = OrderedDict()

    def add(self, text: str):
        self._n[text] = None

    def all(self) -> List[str]:
        return list(self._n)


def _fmt(n: float) -> str:
    return f"{n:,.0f}" if abs(n - round(n)) < 0.05 else f"{n:,.1f}"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
def _nominal(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.lower().replace(" ", "").replace("×", "x")
    for nom in ("2x12", "2x10", "2x8", "2x6", "2x4"):
        if nom in t:
            return nom
    return None


def _plies(text: Optional[str], default: int) -> int:
    m = re.search(r"\((\d)\)", text or "")
    return int(m.group(1)) if m else default


def _lvl_depth(text: Optional[str]) -> Optional[str]:
    """'(3) 1 3/4" X 16" LVL' -> '16'; '1-3/4x11-7/8 LVL' -> '11-7/8'."""
    if not text:
        return None
    t = text.replace("”", '"').replace("″", '"')
    m = re.search(r'1[ -]?3/4"?\s*[xX×]\s*([0-9]+(?:[ -][0-9]/[0-9]+)?)', t)
    return m.group(1).replace(" ", "-") if m else None


def floor_depth_ft(member: Optional[str]) -> float:
    """Height of a floor system (joist + 1-1/2\" sill + 3/4\" subfloor) for sheathing/wrap height."""
    if not member:
        return 0.0
    t = member.lower().replace("”", '"')
    nom = _nominal(t)
    depth = {"2x8": 7.25, "2x10": 9.25, "2x12": 11.25}.get(nom) if nom else None
    if depth is None:
        m = re.search(r'(\d+)(?:[ -](\d)/(\d))?\s*"', t)
        if m:
            depth = int(m.group(1)) + (int(m.group(2)) / int(m.group(3)) if m.group(2) else 0)
    return ((depth or 0) + 2.25) / 12 if depth else 0.0


def sheathing_key(text: Optional[str], default: str) -> str:
    """Map a sheathing callout to a materials.csv key."""
    if not text:
        return default
    t = text.lower()
    if "osb" in t or "oriented" in t:
        return "osb_5_8_4x8" if "5/8" in t else "osb_7_16_4x8"
    if "advantech" in t:
        return "subfloor_advantech_23_32"
    if "plywood" in t or "cdx" in t:
        if "3/4" in t or "23/32" in t:
            return "plywood_tg_3_4_4x8" if "t&g" in t or "tongue" in t else "plywood_3_4_4x8"
        if "5/8" in t or "19/32" in t:
            return "plywood_roof_19_32"
        if "1/2" in t or "15/32" in t:
            return "plywood_wall_15_32"
    return default


LVL_FOR_RAFTER = {"2x6": "9-1/4", "2x8": "9-1/4", "2x10": "11-7/8", "2x12": "14"}


# ---------------------------------------------------------------------------
# Line builders
# ---------------------------------------------------------------------------
KERF_FT = 0.125 / 12


def _bin_pack(cuts: List[float], stock: float) -> int:
    bins: List[float] = []
    for c in sorted((c + KERF_FT for c in cuts), reverse=True):
        for i, free in enumerate(bins):
            if free >= c - 1e-6:
                bins[i] = free - c
                break
        else:
            bins.append(stock - c)
    return len(bins)


def cut_lines(zone, trade, desc, nominal, cuts: List[float], waste, treated=False, note="",
              nb: Optional[NoteBook] = None) -> List[Line]:
    """Order boards for a list of cut lengths.

    Long cuts get their own board (shortest stock that fits). Short cuts
    (NEST_CUTS_UNDER_FT or less) are nested together onto NEST_STOCK_FT boards. Cuts longer than the longest stock length
    become a special-order line.
    """
    if not cuts:
        return []
    out: List[Line] = []
    per_stock: Dict[float, int] = defaultdict(int)
    shorts: List[float] = []
    too_long: List[float] = []
    special: Dict[float, int] = defaultdict(int)
    for c in cuts:
        L = stock_length(c)
        if L is None:
            Ls = stock_length(c, S.SPECIAL_ORDER_LENGTHS_FT)
            if Ls:
                special[Ls] += 1
            else:
                too_long.append(c)
        elif c <= S.NEST_CUTS_UNDER_FT + 1e-6:
            shorts.append(c)
        else:
            per_stock[L] += 1
    if shorts:
        base = S.NEST_STOCK_FT
        per_stock[base] += _bin_pack(shorts, base)
    for L in sorted(per_stock):
        n = per_stock[L]
        out.append(Line(zone, trade, desc, lumber(nominal, L, treated), n, "EA", waste, pieces=True,
                        uom_text=f"{_fmt(sum(cuts))} LF", notes=[note] if note else []))
    for L in sorted(special):
        out.append(Line(zone, trade, desc, lumber(nominal, L, treated), special[L], "EA", waste, pieces=True,
                        uom_text=f"{_fmt(sum(cuts))} LF", notes=([note] if note else []) + ["Special order length"]))
    if too_long:
        Lmax = math.ceil(max(too_long))
        out.append(Line(zone, trade, desc, None, len(too_long), "EA", waste, pieces=True,
                        product_override=f"{nominal} x {Lmax}' (over {S.LONGEST_DIMENSIONAL_FT}': special order, LVL, or splice)",
                        uom_text=f"{_fmt(sum(too_long))} LF", notes=["Special order"]))
        if nb:
            nb.add(f"{zone}: {desc} needs {len(too_long)} piece(s) up to {Lmax}' long, beyond standard {S.LONGEST_DIMENSIONAL_FT}' stock.")
    return out


def run_line(zone, trade, desc, nominal, lf, waste, treated=False, note="", stock=16.0) -> Line:
    """Plates, fascia, ridge, rim, blocking: spliceable runs bought as 16' boards."""
    return Line(zone, trade, desc, lumber(nominal, stock, treated), lf, "LF", waste,
                uom_text=f"{_fmt(lf)} LF", notes=[note] if note else [])


def lvl_lines(zone, trade, desc, depth, span_ft, count, note="") -> List[Line]:
    L = stock_length(span_ft, S.LVL_STOCK_LENGTHS_FT)
    if L is None:
        return [Line(zone, trade, desc, None, count, "EA", S.WASTE["none"], pieces=True,
                     product_override=f'1-3/4" x {depth or "?"}" x {math.ceil(span_ft)}\' LVL',
                     uom_text=f"{_fmt(span_ft * count)} LF", notes=[note, "Special order length"])]
    return [Line(zone, trade, desc, lvl(depth or "?", L), count, "EA", S.WASTE["none"], pieces=True,
                 uom_text=f"{_fmt(span_ft * count)} LF", notes=[note] if note else [])]


def item(cat: Catalog, zone, trade, desc, key, measure, unit, waste, note="", uom_text=None) -> Line:
    m = cat.get(key)
    line = Line(zone, trade, desc, m, measure, unit, waste, uom_text=uom_text or f"{_fmt(measure)} {unit}",
                notes=[note] if note else [])
    if m is None:
        line.product_override = desc
        line.notes.append(f"'{key}' not in materials.csv")
    return line


def stud_lines(zone, trade, desc, nominal, height, count, waste, treated=False, note="", nb=None) -> List[Line]:
    pre = precut_for_wall(height)
    if pre:
        return [Line(zone, trade, desc, stud(nominal, pre, treated), count, "EA", waste, pieces=True,
                     uom_text=f"{count} EA", notes=[note] if note else [])]
    return cut_lines(zone, trade, desc, nominal, [height - 0.375] * count, waste, treated,
                     note=(note + "; " if note else "") + f"no precut stud for {_fmt(height)}' walls, cut from stock", nb=nb)


# ---------------------------------------------------------------------------
# Walls (trade 2)
# ---------------------------------------------------------------------------
def _walls(zone, walls: List[WallRun], openings: List[Opening], roofs: List[RoofPlane], on_slab: bool,
           cat: Catalog, nb: NoteBook, summ: ZoneSummary, floor_ft: float = 0.0,
           wall_sheathing_key: str = None) -> List[Line]:
    L: List[Line] = []
    T = 2
    ext = [w for w in walls if w.exterior and not w.is_gable_end and not w.is_furring]
    inner = [w for w in walls if not w.exterior and not w.is_gable_end and not w.is_furring]
    furring = [w for w in walls if w.is_furring]
    gables = [w for w in walls if w.is_gable_end]

    def spacing(w):
        if w.spacing_in:
            return w.spacing_in
        nb.add(f"{zone}: stud spacing not shown for '{w.label}'; used default {S.DEFAULT_STUD_SPACING_IN}\" O.C.")
        return S.DEFAULT_STUD_SPACING_IN

    def size(w):
        n = _nominal(w.stud_size)
        if n:
            return n
        nb.add(f"{zone}: stud size not shown for '{w.label}'; used default {S.DEFAULT_STUD_SIZE}.")
        return S.DEFAULT_STUD_SIZE

    ext_doors = [o for o in openings if o.exterior and o.kind in ("door", "overhead_door")]
    door_lf = sum(o.width_in * o.count for o in ext_doors) / 12
    perimeter = sum(w.length_ft for w in ext)
    sill_lf = max(perimeter - door_lf, 0)
    summ.perimeter_lf += perimeter
    summ.sill_lf += sill_lf

    for r in roofs:
        expected = 2 * (r.building_length_ft + r.building_width_ft)
        if ext and abs(expected - perimeter) > 1.0:
            nb.add(f"{zone}: exterior walls add up to {perimeter:.1f} LF; the roof footprint "
                   f"({r.building_length_ft:g}' x {r.building_width_ft:g}') implies {expected:.1f} LF. "
                   f"Fine if part of the wall is shared or the building isn't a rectangle.")

    # --- Bottom plates (PT + sill seal on slab), top plates
    bottom: Dict[Tuple[str, bool], float] = defaultdict(float)
    top: Dict[str, float] = defaultdict(float)
    seal_lf = 0.0
    for w in ext + inner:
        nom = size(w)
        lf = w.length_ft
        if w.exterior:
            lf -= sum(o.width_in * o.count for o in ext_doors) / 12 * (w.length_ft / perimeter if perimeter else 0)
        bottom[(nom, on_slab)] += max(lf, 0)
        top[nom] += 2 * w.length_ft
        if on_slab and w.exterior:
            seal_lf += max(lf, 0)
    for (nom, pt), lf in bottom.items():
        L.append(run_line(zone, T, "Sill Plates" if pt else "Bottom Plates", nom, lf, S.WASTE["none"], treated=pt,
                          note="On concrete: treated" if pt else "Less door openings"))
    if seal_lf:
        L.append(item(cat, zone, T, "Sill Seal", S.KEYS["sill_seal"], seal_lf, "LF", S.WASTE["none"]))
        bolts = math.ceil(seal_lf / S.ANCHOR_BOLT_MAX_OC_FT) + S.ANCHOR_BOLTS_EXTRA_PER_RUN * len(ext)
        L.append(item(cat, zone, T, "Anchor Bolts", S.KEYS["anchor_bolt"], bolts, "EA", S.WASTE["none"],
                      note=f"IRC R403.1.6: max {S.ANCHOR_BOLT_MAX_OC_FT}' O.C. + within 12\" of plate ends; use plan spacing if closer"))
    for nom, lf in top.items():
        L.append(run_line(zone, T, "Top Plates", nom, lf, S.WASTE["none"], note="Double top plate"))

    # --- Studs grouped by size and height
    groups: Dict[Tuple[str, float], int] = defaultdict(int)
    for w in ext + inner:
        if w.height_ft is None:
            nb.add(f"{zone}: wall height missing for '{w.label}' ({w.source.sheet}); studs/sheathing for it skipped.")
            continue
        n = studs_for_run(w.length_ft, spacing(w))
        corners = w.corners_intersections
        if corners is None:
            corners = S.DEFAULT_CORNERS_PER_EXTERIOR_RUN if w.exterior else round(w.length_ft * S.DEFAULT_INTERSECTIONS_PER_INTERIOR_LF)
            nb.add(f"{zone}: corners/intersections not counted for '{w.label}'; estimated {corners}.")
        n += corners * S.STUDS_PER_CORNER
        groups[(size(w), w.height_ft)] += n
    if groups:
        biggest = max(groups, key=groups.get)
        extra = 0
        for o in openings:
            if o.kind == "opening":
                continue
            if o.width_in < 72:
                extra += S.STUDS_PER_OPENING_UNDER_6FT * o.count
            elif o.kind == "window":
                extra += S.STUDS_PER_WINDOW_6FT_PLUS * o.count
            else:
                extra += S.STUDS_PER_DOOR_6FT_PLUS * o.count
        groups[biggest] += extra
    for (nom, h), count in groups.items():
        L += stud_lines(zone, T, "Studs", nom, h, count, S.WASTE["standard"],
                        note=f"{_fmt(h)}' walls; +2 per corner/intersection and per opening", nb=nb)

    # --- Blocking (fireblocking / backing)
    if S.BLOCKING_ROWS:
        blk: Dict[str, float] = defaultdict(float)
        for w in ext + inner:
            rows = S.BLOCKING_ROWS
            if w.height_ft and w.height_ft > S.FIREBLOCK_MAX_FT:  # tall walls: a row every 10' (IRC R602.8)
                rows = max(rows, math.ceil(w.height_ft / S.FIREBLOCK_MAX_FT) - 1)
            blk[size(w)] += w.length_ft * rows
        for nom, lf in blk.items():
            L.append(run_line(zone, T, "Blocking", nom, lf, S.WASTE["standard"],
                              note=f"{S.BLOCKING_ROWS} row(s) per LF of wall"))

    # --- Furring walls on concrete: treated plates & studs, no sheathing
    for w in furring:
        nom = size(w)
        L.append(run_line(zone, T, "Furring Wall Plates", nom, 2 * w.length_ft, S.WASTE["none"], treated=True,
                          note=f"{w.label}: treated top & bottom plates"))
        if w.height_ft:
            n = studs_for_run(w.length_ft, spacing(w))
            L += stud_lines(zone, T, "Furring Wall Studs", nom, w.height_ft, n, S.WASTE["standard"], treated=True,
                            note=f"{w.label}: {spacing(w):g}\" O.C.", nb=nb)

    # --- Gable-end studs, cut to the rake line and nested on boards
    for g in gables:
        h = g.height_ft
        if h is None:
            r = next((r for r in roofs if r.style == "gable"), None)
            if r:
                h = gable_rise_ft(g.length_ft, r.pitch_rise_per_12 or S.DEFAULT_PITCH)
        if not h:
            nb.add(f"{zone}: gable '{g.label}' has no height and no roof pitch to compute it; skipped.")
            continue
        sp, half = spacing(g) / 12, g.length_ft / 2
        cuts, x = [], sp
        while x < g.length_ft - 1e-6:
            cuts.append(h * (1 - abs(x - half) / half))
            x += sp
        L += cut_lines(zone, T, "Gable Studs", size(g), [c for c in cuts if c > 0.25], S.WASTE["standard"],
                       note=f"{g.label}: cut to the rake line", nb=nb)

    # --- Headers (only where new walls are framed in this zone)
    if not walls:
        if openings:
            nb.add(f"{zone}: openings in existing walls; headers/framing not taken off (verify if openings are resized).")
        return L
    std_cuts: Dict[str, List[float]] = defaultdict(list)
    for o in openings:
        if o.kind == "opening" and not o.header_spec:
            continue
        span = (o.width_in + S.HEADER_BEARING_IN) / 12
        spec = (o.header_spec or "").lower()
        plies = _plies(o.header_spec, S.HEADER_PLIES)
        if "lvl" in spec or o.width_in > S.LVL_ABOVE_WIDTH_IN:
            depth = _lvl_depth(o.header_spec)
            if not depth:
                nb.add(f"{zone}: LVL header depth for Mark {o.mark} not shown; size it from the plans/engineer.")
            note = f"Mark {o.mark} ({_fmt(o.width_in)}\" wide): '{o.header_spec or 'not shown'}'"
            L += lvl_lines(zone, T, "Headers", depth, span, plies * o.count, note)
            if "angle" in spec or re.search(r"\bl\s?\d", spec):
                nb.add(f"{zone}: Mark {o.mark} header includes a steel angle ({o.header_spec}); order separately.")
            continue
        nom = _nominal(o.header_spec)
        if not nom:
            nom = S.DEFAULT_HEADER_NOMINAL
            nb.add(f"{zone}: no header size for Mark {o.mark}; used ({plies}) {nom}. Verify.")
        std_cuts[nom].extend([span] * (plies * o.count))
    for nom, cuts in std_cuts.items():
        stock = stock_length(max(cuts))
        boards = _bin_pack(cuts, stock)
        L.append(Line(zone, T, "Headers", lumber(nom, stock), boards, "EA", S.WASTE["none"], pieces=True,
                      uom_text=f"{_fmt(sum(cuts))} LF", notes=[f"{len(cuts)} header plies nested on {stock:g}' boards"]))

    # --- Wall sheathing
    rect = sum(w.length_ft * (w.height_ft + floor_ft) for w in ext if w.height_ft)
    gable_sf = 0.0
    for g in gables:
        h = g.height_ft
        if h is None:
            r = next((r for r in roofs if r.style == "gable"), None)
            h = gable_rise_ft(g.length_ft, (r.pitch_rise_per_12 or S.DEFAULT_PITCH)) if r else 0
        gable_sf += gable_area_sf(g.length_ft, h)
    gross = rect + gable_sf
    ext_open = [o for o in openings if o.exterior]
    open_sf = sum(o.width_in * o.height_in * o.count for o in ext_open) / 144
    net = max(gross - open_sf, 0)
    summ.wall_gross_sf += gross
    summ.wall_net_sf += net
    summ.gable_sf += gable_sf
    summ.rect_wall_sf += rect
    summ.big_openings_sf += sum(o.width_in * o.height_in * o.count / 144 for o in ext_open
                                if o.width_in * o.height_in / 144 >= S.SIDING_MIN_OPENING_SF)
    if net > 0:
        L.append(item(cat, zone, T, "Exterior Wall Sheathing", wall_sheathing_key or S.KEYS["wall_sheathing"], net, "SF", S.WASTE["sheathing"],
                      note="Net of openings" + (f"; walls + {_fmt(floor_ft * 12)}\" floor framing to top of foundation" if floor_ft else "")
                           + ("; includes gable ends" if gables else "")))
    return L


# ---------------------------------------------------------------------------
# Roof framing (trade 3) and roofing (trade 4)
# ---------------------------------------------------------------------------
def _roof(zone, roofs: List[RoofPlane], cat: Catalog, nb: NoteBook, roof_sheathing_key: str = None) -> Tuple[List[Line], List[Line], float]:
    frame: List[Line] = []
    cover: List[Line] = []
    footprint = 0.0
    for r in roofs:
        pitch = r.pitch_rise_per_12
        if pitch is None:
            pitch = S.DEFAULT_PITCH
            nb.add(f"{zone}: roof pitch not shown; used default {S.DEFAULT_PITCH:g}/12.")
        eave = r.overhang_eave_in if r.overhang_eave_in is not None else S.DEFAULT_OVERHANG_IN
        rake = r.overhang_rake_in if r.overhang_rake_in is not None else eave
        if r.overhang_eave_in is None:
            nb.add(f"{zone}: roof overhang not shown; used default {S.DEFAULT_OVERHANG_IN}\".")
        Lb, Wb = r.building_length_ft, r.building_width_ft
        footprint += Lb * Wb
        sf = slope_factor(pitch)
        ends = 1 if r.joins_other_roof_at_one_end else 2
        s = r.rafter_spacing_in or S.DEFAULT_RAFTER_SPACING_IN
        if not r.rafter_spacing_in:
            nb.add(f"{zone}: rafter spacing not shown; used {S.DEFAULT_RAFTER_SPACING_IN}\" O.C.")
        run = Wb / 2 + eave / 12
        hip_len = math.sqrt(2 * run ** 2 + (run * pitch / 12) ** 2)

        if r.style == "gable":
            length_out = Lb + ends * rake / 12
            area = length_out * (Wb + 2 * eave / 12) * sf
            ridge_lf = length_out
            eave_lf = 2 * length_out
            rake_lf = 2 * ends * run * sf
            hip_lf = 0.0
        elif r.style == "hip":
            Lr, Wr = Lb + 2 * eave / 12, Wb + 2 * eave / 12
            area = Lr * Wr * sf
            ridge_lf = max(Lr - Wr, 0)
            eave_lf = 2 * (Lr + Wr)
            rake_lf = 0.0
            hip_lf = 4 * hip_len
        else:
            nb.add(f"{zone}: '{r.style}' roof not auto-calculated; add roof materials manually.")
            continue
        valley_lf = r.valleys * hip_len

        # ---- Framing
        T = 3
        nom = _nominal(r.rafter_size)
        if not nom and not r.uses_trusses and S.DEFAULT_RAFTER_SIZE:
            nom = S.DEFAULT_RAFTER_SIZE
            nb.add(f"{zone}: rafter size not shown on plans; used {nom} default. Size rafters from the span table/engineer.")
        per_side = studs_for_run(ridge_lf if r.style == "hip" else Lb, s) if (r.style == "gable" or ridge_lf > 0) else 0
        bearing_rafters = 0
        if r.uses_trusses:
            n = studs_for_run(Lb, s)
            frame.append(Line(zone, T, "Roof Trusses", None, n, "EA", S.WASTE["none"], pieces=True,
                              product_override=f"Roof truss package, {Wb:g}' span, {pitch:g}/12, {s:g}\" O.C.",
                              uom_text=f"{n} EA", notes=["Special order (truss layout)"]))
        elif not nom:
            nb.add(f"{zone}: rafter size not shown (span tables only?). Rafters, hips and jacks not calculated; "
                   f"rafter LF for this roof is about {_fmt(area / (s / 12))} LF.")
        else:
            common_cut = run * sf + 0.25
            cuts = [common_cut] * (2 * per_side)
            if r.style == "gable":
                cuts += [common_cut] * (S.FLY_RAFTERS_PER_GABLE_END * ends)
                bearing_rafters = 2 * per_side
                note = f"{s:g}\" O.C. both slopes + fly rafters; cut length {common_cut:.1f}'"
            else:
                cuts += [common_cut] * 2  # end (king) commons
                jacks = []
                x = s / 12
                while x < run - 1e-6:
                    jacks += [x * sf + 0.25] * 8  # 4 hips x 2 sides
                    x += s / 12
                cuts += jacks
                bearing_rafters = int(2 * (Lb + Wb) * 12 / s)
                note = f"Hip roof: {2 * per_side + 2} commons ({common_cut:.1f}') + {len(jacks)} jacks nested"
            frame += cut_lines(zone, T, "Rafters", nom, cuts,
                               S.WASTE["rafters_hip"] if r.style == "hip" else S.WASTE["framing_roof"], note=note, nb=nb)

            # Hips, valleys, ridge
            member = r.hip_valley_member
            member_nom = _nominal(member) or bigger_nominal(nom) or nom
            for label, count, length in (("Hip Rafters", 4 if r.style == "hip" else 0, hip_len + 0.5),
                                         ("Valley Rafters", r.valleys, hip_len + 0.5)):
                if not count:
                    continue
                if (member and "lvl" in member.lower()) or length > S.HIP_VALLEY_LVL_OVER_FT:
                    depth = _lvl_depth(member) or LVL_FOR_RAFTER.get(nom)
                    frame += lvl_lines(zone, T, label, depth, length, count,
                                       note=f"{'per plans: ' + member if member else 'over ' + str(S.HIP_VALLEY_LVL_OVER_FT) + chr(39) + ': LVL (rafter depth + 2 in.)'}")
                else:
                    frame += cut_lines(zone, T, label, member_nom, [length] * count, S.WASTE["none"], nb=nb)
            if ridge_lf > 0:
                if member and "lvl" in member.lower():
                    frame += lvl_lines(zone, T, "Ridge", _lvl_depth(member), ridge_lf, 1, note=f"per plans: {member}")
                else:
                    frame.append(run_line(zone, T, "Ridge Board", bigger_nominal(nom) or nom, ridge_lf, S.WASTE["none"]))
            frame.append(item(cat, zone, T, "Hurricane Ties", S.KEYS["hurricane_tie"], bearing_rafters, "EA",
                              S.WASTE["none"], note="1 per rafter at the wall plate"))

        frame.append(run_line(zone, T, "Sub Fascia (Eave)", S.SUB_FASCIA_NOMINAL, eave_lf, S.WASTE["none"]))
        if S.SOFFIT_FRAMING_LF_PER_EAVE_LF and eave > 0:
            frame.append(run_line(zone, T, "Soffit Framing", S.SOFFIT_FRAMING_NOMINAL,
                                  eave_lf * S.SOFFIT_FRAMING_LF_PER_EAVE_LF, S.WASTE["standard"], note="Ledger + lookouts"))
        if S.ROOF_BRACING_PCS_PER_100SF and not r.uses_trusses:
            n_br = math.ceil(area / 100 * S.ROOF_BRACING_PCS_PER_100SF)
            for nb_nom in ("2x4", "2x6"):
                frame.append(Line(zone, T, "Roof Bracing", lumber(nb_nom, 16), n_br, "EA", S.WASTE["none"], pieces=True,
                                  uom_text=f"{_fmt(area)} SF", notes=["Allowance: braces, purlins, collar ties"]))
        if rake_lf:
            frame.append(run_line(zone, T, "Rake Board", S.SUB_FASCIA_NOMINAL, rake_lf, S.WASTE["none"]))

        # Ceiling joists
        cj = _nominal(r.ceiling_joist_size)
        if cj and not r.uses_trusses:
            n = studs_for_run(Lb, s)
            if stock_length(Wb) is not None:
                frame += cut_lines(zone, T, "Ceiling Joists", cj, [Wb] * n, S.WASTE["framing_roof"],
                                   note=f"{s:g}\" O.C. spanning {Wb:g}'", nb=nb)
            else:
                frame += cut_lines(zone, T, "Ceiling Joists", cj, [Wb / 2 + 1] * (2 * n), S.WASTE["framing_roof"],
                                   note=f"Lapped over a center bearing wall/beam ({Wb:g}' span)", nb=nb)
                nb.add(f"{zone}: ceiling joists span {Wb:g}', longer than stock, so they lap over a center bearing. Verify.")
        elif r.ceiling_joist_size is None and not r.uses_trusses:
            nb.add(f"{zone}: ceiling joist size not shown (or none); not calculated.")

        frame.append(item(cat, zone, T, "Roof Sheathing", roof_sheathing_key or S.KEYS["roof_sheathing"], area, "SF", S.WASTE["sheathing"],
                          note=f"{r.style}, {pitch:g}/12, {_fmt(eave)}\" overhang"))
        if s >= 24:
            sheets = math.ceil(area * (1 + S.WASTE["sheathing"]) / 32)
            frame.append(item(cat, zone, T, "Sheathing Clips", S.KEYS["sheathing_clips"],
                              sheets * S.SHEATHING_CLIPS_PER_PANEL, "EA", S.WASTE["none"]))

        # ---- Roofing
        T = 4
        cov = (r.covering or "").lower()
        metal = "metal" in cov or "standing seam" in cov
        if metal:
            cover.append(item(cat, zone, T, "Metal Roofing", "metal_roof_panels", area, "SF", S.WASTE["standard"],
                              note=r.covering or ""))
            nb.add(f"{zone}: metal roof - panels, trims, ridge/hip/valley flashings and clips come from the metal roofing supplier's layout.")
        else:
            cover.append(item(cat, zone, T, "Shingles", S.KEYS["shingles"], area, "SF", S.WASTE["standard"]))
        felt_key = "felt_30lb" if re.search(r"#\s?30|30\s?(lb|#)", cov) else ("felt_15lb" if re.search(r"#\s?15|15\s?(lb|#)", cov) else S.KEYS["underlayment"])
        cover.append(item(cat, zone, T, "Underlayment", felt_key, area, "SF", S.WASTE["standard"]))
        if S.ICE_BARRIER_REQUIRED:
            courses = ice_barrier_courses(eave, pitch, S.ICE_BARRIER_INSIDE_WALL_IN, S.ICE_BARRIER_ROLL_WIDTH_IN)
            ib_sf = eave_lf * courses * S.ICE_BARRIER_ROLL_WIDTH_IN / 12 + valley_lf * 3
            cover.append(item(cat, zone, T, "Ice & Water Barrier", S.KEYS["ice_barrier"], ib_sf, "SF", S.WASTE["none"],
                              note=f"{courses} course(s) at eaves to {S.ICE_BARRIER_INSIDE_WALL_IN}\" inside wall" +
                                   (" + valleys" if valley_lf else "")))
        starter_lf = eave_lf + (rake_lf if S.STARTER_ON_RAKES else 0)
        if not metal:
            cover.append(item(cat, zone, T, "Starter Shingles", S.KEYS["starter_shingles"], starter_lf, "LF",
                              S.WASTE["standard"], note="Eaves + rakes" if S.STARTER_ON_RAKES else "Horizontal eaves"))
            cover.append(item(cat, zone, T, "Ridge Cap Shingles", S.KEYS["ridge_cap"], ridge_lf + hip_lf, "LF",
                              S.WASTE["standard"], note="Ridge + hips" if hip_lf else ""))
        vent_lf = max(ridge_lf - 2 * S.RIDGE_VENT_END_GAP_FT, 0)
        if vent_lf > 0 and not metal:
            cover.append(item(cat, zone, T, "Ridge Vent", S.KEYS["ridge_vent"], vent_lf, "LF", S.WASTE["none"]))
        cover.append(item(cat, zone, T, "Drip Edge", S.KEYS["drip_edge"], eave_lf + rake_lf, "LF", S.WASTE["standard"],
                          note="Eaves + rakes"))
        if valley_lf:
            cover.append(Line(zone, T, "Valley Flashing", None, valley_lf, "LF", S.WASTE["standard"],
                              product_override="Valley flashing / W-valley", uom_text=f"{_fmt(valley_lf)} LF"))
        if metal:
            continue
        sh = cat.get(S.KEYS["shingles"])
        bundles = order_units(area, S.WASTE["standard"], sh.coverage_per_unit if sh else 33.33)
        boxes = bundles * S.SHINGLES_PER_BUNDLE * S.NAILS_PER_SHINGLE / S.ROOFING_NAILS_PER_BOX
        nl = item(cat, zone, T, "Roofing Nails", S.KEYS["roofing_nails"], boxes, "EA", S.WASTE["none"],
                  note=f"{bundles} bundles x {S.SHINGLES_PER_BUNDLE} shingles x {S.NAILS_PER_SHINGLE} nails",
                  uom_text=f"{_fmt(area)} SF")
        nl.pieces = True
        cover.append(nl)
    return frame, cover, footprint


# ---------------------------------------------------------------------------
# Floor systems (trade 1)
# ---------------------------------------------------------------------------
def _floors(floors: List[FloorSystem], cat: Catalog, nb: NoteBook) -> List[Line]:
    L: List[Line] = []
    T = 1
    for f in floors:
        z = f.zone
        member = (f.joist_member or "").strip()
        s = f.spacing_in or 16
        if f.new_framing:
            if not member:
                nb.add(f"{z}: floor joist size not shown; joists not calculated.")
            elif not f.typical_span_ft:
                nb.add(f"{z}: floor joist span not given; joists not calculated ({member}).")
            elif any(k in member.lower() for k in ("tji", "i-joist", "open web", "truss")):
                n = math.ceil(f.area_sf / f.typical_span_ft * 12 / s)
                L.append(Line(z, T, "Floor Joists", None, n, "EA", S.WASTE["none"], pieces=True,
                              product_override=f"{member} x {math.ceil(f.typical_span_ft + 0.5)}' ({s:g}\" O.C.)",
                              uom_text=f"{_fmt(n * f.typical_span_ft)} LF",
                              notes=["Engineered joists: confirm lengths with the manufacturer layout"]))
            else:
                nom = _nominal(member) or member
                n = math.ceil(f.area_sf / f.typical_span_ft * 12 / s)
                L += cut_lines(z, T, "Floor Joists", nom, [f.typical_span_ft + 0.5] * n, S.WASTE["none"],
                               note=f"{s:g}\" O.C., ~{_fmt(f.typical_span_ft)}' spans", nb=nb)
            if f.perimeter_lf and member:
                if "tji" in member.lower() or "i-joist" in member.lower():
                    L.append(item(cat, z, T, "Rim Board", "rim_board_1_1_8x11_7_8", f.perimeter_lf, "LF", S.WASTE["standard"]))
                elif _nominal(member):
                    L.append(run_line(z, T, "Rim Joist", _nominal(member), f.perimeter_lf, S.WASTE["standard"]))
        if f.subfloor:
            key = S.KEYS["subfloor_advantech"] if "advantech" in f.subfloor.lower() else S.KEYS["subfloor_plywood"]
            L.append(item(cat, z, T, "Subfloor", key, f.area_sf, "SF", S.WASTE["subfloor"], note=f.subfloor))
            tubes = (12 / s + 0.125) * f.area_sf / (3.14 * 28)  # book: 1 oz covers 3.14 LF of joist; 28 oz tube
            al = item(cat, z, T, "Subfloor Adhesive", S.KEYS["subfloor_adhesive"], tubes, "EA", S.WASTE["standard"],
                      note=f"Joists @ {s:g}\" O.C. + double beads at sheet ends", uom_text=f"{_fmt(f.area_sf)} SF")
            al.pieces = True
            L.append(al)
    return L


# ---------------------------------------------------------------------------
# Siding & wrap (trade 5), drywall (8), openings (10/11), other items
# ---------------------------------------------------------------------------
def _siding(zone, walls, openings, spec: Optional[ZoneSpec], roofs, summ: ZoneSummary, cat, nb: NoteBook) -> List[Line]:
    T = 5
    L: List[Line] = []
    gross, net = summ.wall_gross_sf, summ.wall_net_sf
    if gross <= 0:
        return L
    L.append(item(cat, zone, T, "House Wrap", S.KEYS["housewrap"], gross, "SF", S.WASTE["none"], note="Gross wall area"))
    L.append(item(cat, zone, T, "House Wrap Tape", S.KEYS["housewrap_tape"], gross * S.HOUSEWRAP_TAPE_LF_PER_SF, "LF",
                  S.WASTE["none"], uom_text=f"{_fmt(gross)} SF"))
    ext_open = [o for o in openings if o.exterior]
    flash_lf = sum(((o.width_in + 2 * o.height_in) if o.kind == "overhead_door" else (2 * o.width_in + 2 * o.height_in)) / 12 * o.count
                   for o in ext_open)
    if flash_lf:
        L.append(item(cat, zone, T, "Window & Door Flashing Tape", S.KEYS["flashing_tape"], flash_lf, "LF", S.WASTE["none"]))
    L.append(item(cat, zone, T, "Cap Nails", S.KEYS["cap_nails"], gross, "SF", S.WASTE["none"]))
    siding = spec.siding_type if spec else None
    ext = [w for w in walls if w.exterior and not w.is_gable_end and not w.is_furring]
    corners = len(ext)
    avg_h = (sum(w.height_ft or 0 for w in ext) / len(ext)) if ext else 0
    casing_lf = sum(((o.width_in + 2 * o.height_in) if o.kind in ("door", "overhead_door") else (2 * o.width_in + 2 * o.height_in)) / 12 * o.count
                    for o in ext_open)
    soffit_sf = 0.0
    for r in roofs:
        if r.overhang_eave_in:
            o = r.overhang_eave_in / 12
            if r.style == "hip":
                soffit_sf += 2 * (r.building_length_ft + r.building_width_ft + 2 * o) * o
            else:
                soffit_sf += 2 * (r.building_length_ft + (2 if not r.joins_other_roof_at_one_end else 1) * (r.overhang_rake_in or 0) / 12) * o
    wall_sid = max(summ.rect_wall_sf - summ.big_openings_sf, 0)
    gable_sid = summ.gable_sf

    def siding_lines(key):
        out = [item(cat, zone, T, "Siding (walls)", key, wall_sid, "SF", S.SIDING_WASTE_WALLS,
                    note=f"Walls less openings of {S.SIDING_MIN_OPENING_SF}+ SF")]
        if gable_sid:
            out.append(item(cat, zone, T, "Siding (gables)", key, gable_sid, "SF", S.SIDING_WASTE_GABLES, note="Gables at 30% waste"))
        return out

    if siding == "fiber_cement":
        L += siding_lines(S.KEYS["siding_fiber_cement"])
        L.append(item(cat, zone, T, "Starter Strip", S.KEYS["starter_fiber_cement"], summ.sill_lf, "LF", S.WASTE["standard"]))
        L.append(item(cat, zone, T, "Exterior Trim", S.KEYS["exterior_trim_fiber_cement"], corners * 2 * avg_h + casing_lf, "LF",
                      S.WASTE["standard"], note=f"{corners} corners x 2 boards + opening casings"))
    elif siding == "vinyl":
        L += siding_lines(S.KEYS["siding_vinyl"])
        L.append(item(cat, zone, T, "Starter Strip", S.KEYS["starter_vinyl"], summ.sill_lf, "LF", S.WASTE["standard"]))
        L.append(item(cat, zone, T, "J-Channel", S.KEYS["j_channel_vinyl"], casing_lf, "LF", S.WASTE["standard"], note="Around openings"))
    elif siding in ("brick", "wood", "other"):
        nb.add(f"{zone}: siding type '{siding}' not auto-calculated. Net wall area {_fmt(net)} SF.")
    elif siding is None:
        nb.add(f"{zone}: siding type not shown; not calculated. Net wall area {_fmt(net)} SF.")
    if soffit_sf:
        L.append(item(cat, zone, T, "Vented Soffit", S.KEYS["soffit_vented"], soffit_sf, "SF", S.WASTE["standard"]))
    return L


def _drywall(zone, walls, openings, spec: Optional[ZoneSpec], footprint, summ: ZoneSummary, cat, nb: NoteBook) -> List[Line]:
    T = 8
    L: List[Line] = []
    if spec is None:
        nb.add(f"{zone}: no drywall info; drywall not calculated.")
        return L
    sides = lambda w: 2 if (not w.exterior and not w.is_furring) else 1
    wall_sf = sum(sides(w) * w.length_ft * (w.height_ft or 0) for w in walls if not w.is_gable_end)
    wall_sf -= sum(o.width_in * o.height_in * o.count / 144 * (1 if o.exterior else 2) for o in openings)
    wall_sf = max(wall_sf, 0)
    ceiling_sf = spec.ceiling_area_sf if spec.ceiling_area_sf else footprint
    summ.ceiling_area_sf += ceiling_sf
    summ.floor_area_sf += spec.floor_area_sf or footprint
    type_key = {"1/2": "drywall_1_2", "5/8_type_x": "drywall_5_8x", "1/2_mold": "drywall_mold"}
    total = used_5_8 = used_1_2 = 0.0
    for label, kind, sf in (("Wall Drywall", spec.wall_drywall, wall_sf), ("Ceiling Drywall", spec.ceiling_drywall, ceiling_sf)):
        if kind in (None, "none") or sf <= 0:
            if kind is None:
                nb.add(f"{zone}: {label.lower()} type not shown; not calculated.")
            continue
        L.append(item(cat, zone, T, label, S.KEYS[type_key[kind]], sf, "SF", S.WASTE["standard"]))
        total += sf
        if kind == "5/8_type_x":
            used_5_8 += sf
        else:
            used_1_2 += sf
    if total:
        L.append(item(cat, zone, T, "Drywall Tape", S.KEYS["drywall_tape"], total, "SF", S.WASTE["drywall_finish"]))
        L.append(item(cat, zone, T, "Joint Compound", S.KEYS["joint_compound"], total, "SF", S.WASTE["drywall_finish"]))
        if used_1_2:
            L.append(item(cat, zone, T, "Drywall Screws (1/2\")", S.KEYS["drywall_screws_1_2"], used_1_2, "SF", S.WASTE["none"]))
        if used_5_8:
            L.append(item(cat, zone, T, "Drywall Screws (5/8\")", S.KEYS["drywall_screws_5_8"], used_5_8, "SF", S.WASTE["none"]))
    return L


def _openings(zone, openings: List[Opening]) -> List[Line]:
    L: List[Line] = []
    for o in openings:
        if o.kind == "opening":
            continue
        trade = 10 if o.kind == "window" else 11
        w_ft, w_in = divmod(round(o.width_in), 12)
        h_ft, h_in = divmod(round(o.height_in), 12)
        kind = {"window": "Window", "door": "Door", "overhead_door": "Overhead Door"}[o.kind]
        product = f"Mark {o.mark}, {kind}, {w_ft}'-{w_in}\" x {h_ft}'-{h_in}\"" + (f", {o.schedule_specs}" if o.schedule_specs else "")
        L.append(Line(zone, trade, kind + (" (Exterior)" if o.exterior and o.kind == "door" else ""), None, o.count, "EA",
                      S.WASTE["none"], product_override=product, pieces=True, uom_text=f"{o.count} EA", notes=["Special order"]))
    return L


TRADE_WASTE = {1: "standard", 2: "standard", 3: "framing_roof", 4: "standard", 5: "standard", 6: "standard",
               7: "standard", 8: "standard", 9: "standard", 10: "none", 11: "none", 12: "none"}


def _others(items, cat: Catalog, nb: NoteBook) -> List[Line]:
    L: List[Line] = []
    for it in items:
        trade = it.trade_no if it.trade_no in S.TRADES else 9
        waste = S.WASTE["none"] if it.measure_unit == "EA" else S.WASTE[TRADE_WASTE[trade]]
        src = f"{it.source.sheet}: {it.source.source_note}"
        key = it.material_key
        if key.lower().startswith("lumber:"):
            parts = key.split(":")
            nom, pt = parts[1], len(parts) > 2 and parts[2].lower() == "pt"
            if it.measure_unit == "LF" and it.piece_length_ft:
                n = math.ceil(it.measure / it.piece_length_ft - 1e-6)
                L += cut_lines(it.zone, trade, it.description, nom, [it.piece_length_ft] * n, waste, treated=pt, note=src, nb=nb)
            elif it.measure_unit == "LF":
                L.append(run_line(it.zone, trade, it.description, nom, it.measure, waste, treated=pt, note=src))
            else:
                L.append(Line(it.zone, trade, it.description, lumber(nom, 16, pt), it.measure, "EA", waste, pieces=True,
                              uom_text=f"{_fmt(it.measure)} EA", notes=[src, "Length not given: assumed 16'"]))
            continue
        m = cat.get(key) if key != "UNLISTED" else None
        if m is None:
            L.append(Line(it.zone, trade, it.description, None, it.measure, it.measure_unit, waste,
                          product_override=it.description, pieces=(it.measure_unit == "EA"),
                          uom_text=f"{_fmt(it.measure)} {it.measure_unit}", notes=[src]))
            continue
        line = Line(it.zone, trade, it.description, m, it.measure, it.measure_unit, waste,
                    uom_text=f"{_fmt(it.measure)} {it.measure_unit}", notes=[src])
        if it.measure_unit != m.coverage_unit:
            line.pieces = True
            if it.measure_unit != "EA":
                nb.add(f"{it.zone}: '{it.description}' measured in {it.measure_unit} but {m.description} is per "
                       f"{m.coverage_per_unit:g} {m.coverage_unit}. Shown as-is; check it.")
                line.notes.append("Unit mismatch: check quantity")
        L.append(line)
    return L


# ---------------------------------------------------------------------------
# Resolve and assemble
# ---------------------------------------------------------------------------
def _resolve(line: Line) -> Row:
    notes = [n for n in line.notes if n]
    m = line.material
    if m is None:
        coverage, sku, product, unit = 1.0, "", line.product_override or line.description, "PCS"
    else:
        coverage = 1.0 if line.pieces else m.coverage_per_unit
        sku, product, unit = m.sku, m.description, m.unit
        if m.notes:
            notes.append(m.notes)
    return Row(line.zone, line.trade_no, sku, product, line.description, raw_units(line.measure, coverage), unit,
               line.uom_text, line.waste, order_units(line.measure, line.waste, coverage), round(line.measure, 3),
               coverage, "; ".join(dict.fromkeys(notes)), m.key if m else "")


def in_scope(row: Row, scope: str) -> bool:
    if scope == "full":
        return True
    return row.trade_no in S.FRAMING_TRADES or row.description in S.FRAMING_EXTRA_DESCRIPTIONS


def build_takeoff(data: PlanExtraction, cat: Catalog, scope: str = None) -> Takeoff:
    scope = scope or S.DEFAULT_SCOPE
    nb = NoteBook()
    for n in data.estimator_notes:
        nb.add(n)
    for n in data.not_found:
        nb.add(f"Not shown on plans: {n}")

    zones: List[str] = []
    for coll in (data.walls, data.openings, data.roofs, data.zones, data.floors, data.other_items):
        for x in coll:
            if x.zone not in zones:
                zones.append(x.zone)

    framed_floor_zones = {f.zone for f in data.floors}
    lines: List[Line] = []
    summaries: Dict[str, ZoneSummary] = {}
    for z in zones:
        walls = [w for w in data.walls if w.zone == z]
        opens = [o for o in data.openings if o.zone == z]
        roofs = [r for r in data.roofs if r.zone == z]
        spec = next((s for s in data.zones if s.zone == z), None)
        summ = ZoneSummary(z)
        summaries[z] = summ
        on_slab = z not in framed_floor_zones
        zf = next((f for f in data.floors if f.zone == z), None)
        floor_ft = floor_depth_ft(zf.joist_member) if zf else 0.0
        wsk = sheathing_key(spec.wall_sheathing, S.KEYS["wall_sheathing"]) if spec else None
        rsk = sheathing_key(spec.roof_sheathing, S.KEYS["roof_sheathing"]) if spec else None
        lines += _walls(z, walls, opens, roofs, on_slab, cat, nb, summ, floor_ft if (zf and zf.new_framing) else 0.0, wsk)
        frame, cover, footprint = _roof(z, roofs, cat, nb, rsk)
        lines += frame + cover
        if scope == "full":
            lines += _siding(z, walls, opens, spec, roofs, summ, cat, nb)
            if not footprint and spec and spec.floor_area_sf:
                footprint = spec.floor_area_sf
            lines += _drywall(z, walls, opens, spec, footprint, summ, cat, nb)
            lines += _openings(z, opens)
        else:
            lines += [l for l in _siding(z, walls, opens, spec, roofs, summ, cat, NoteBook())
                      if l.description in S.FRAMING_EXTRA_DESCRIPTIONS]
    lines += _floors(data.floors, cat, nb)
    lines += _others(data.other_items, cat, nb)

    nb.add("Not auto-calculated: nails, screws, construction adhesive (except subfloor). Add per builder preference.")
    rows = [r for r in (_resolve(l) for l in lines) if in_scope(r, scope)]
    rows.sort(key=lambda r: (zones.index(r.zone) if r.zone in zones else 99, r.trade_no))
    return Takeoff(data.project_name, rows, nb.all(), summaries, zones, scope)

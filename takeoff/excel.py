"""Writes the multi-tab Home Depot material list workbook."""
import datetime as dt
import re
from collections import OrderedDict
from pathlib import Path
from typing import List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import settings as S
from .build_lines import Row, Takeoff, ZoneSummary
from .calc_quantities import order_units, raw_units

HEAD = ["No", "SKU", "Product", "Description", "Quantity", "Unit", "UOM", "Waste Factor",
        "Adjusted Quantity", "Notes", "Calc: Measure", "Calc: Coverage / Unit"]
WIDTHS = [5, 13, 58, 26, 10, 7, 14, 8, 11, 48, 12, 12]
TAB_NAMES = {1: "Floor", 2: "Walls", 3: "Roof Framing", 4: "Roofing", 5: "Siding & Trim", 6: "Deck",
             7: "Insulation", 8: "Drywall", 9: "Int Finishes", 10: "Windows", 11: "Doors", 12: "Paint"}

ORANGE = PatternFill("solid", fgColor="F96302")
GRAY = PatternFill("solid", fgColor="EDEDED")
FLAG = PatternFill("solid", fgColor="FFF2CC")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _tab(name: str) -> str:
    return re.sub(r"[\[\]:*?/\\]", "-", name)[:31]


def _header(ws, project: str, order_id: str, title: str):
    ws["A1"] = "Home Depot Material List"
    ws["A1"].font = Font(bold=True, size=14, color="F96302")
    ws["A2"], ws["C2"] = "Project Name:", project
    ws["A3"], ws["C3"] = "Order ID:", order_id
    ws["A4"], ws["C4"] = "Date:", dt.date.today().isoformat()
    for c in ("A2", "A3", "A4"):
        ws[c].font = Font(bold=True)
    ws.merge_cells("A5:J6")
    ws["A5"] = S.DISCLAIMER
    ws["A5"].alignment = Alignment(wrap_text=True, vertical="top")
    ws["A5"].font = Font(italic=True, size=9)
    ws.row_dimensions[5].height = 30
    ws.row_dimensions[6].height = 30
    ws["A7"] = title
    ws["A7"].font = Font(bold=True, size=12)
    for i, h in enumerate(HEAD, start=1):
        c = ws.cell(row=8, column=i, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = ORANGE if i <= 10 else PatternFill("solid", fgColor="7F7F7F")
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        c.border = BOX
        ws.column_dimensions[get_column_letter(i)].width = WIDTHS[i - 1]
    ws.row_dimensions[8].height = 30
    ws.freeze_panes = "A9"


def _write_rows(ws, rows: List[Row], start: int = 9) -> int:
    r = start
    for row in rows:
        vals = [row.trade_no, row.sku, row.product, row.description, None, row.unit, row.uom, row.waste,
                None, row.notes, row.measure, row.coverage]
        for i, v in enumerate(vals, start=1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BOX
            c.alignment = Alignment(vertical="top", wrap_text=i in (3, 10))
        ws.cell(row=r, column=2).number_format = "@"
        ws.cell(row=r, column=5, value=f"=ROUNDUP(K{r}/L{r},0)")
        ws.cell(row=r, column=8).number_format = "0%"
        ws.cell(row=r, column=9, value=f"=ROUNDUP(K{r}*(1+H{r})/L{r},0)").font = Font(bold=True)
        for col in (11, 12):
            ws.cell(row=r, column=col).fill = GRAY
            ws.cell(row=r, column=col).font = Font(color="7F7F7F")
        if "verify" in row.notes.lower() or "special order" in row.notes.lower() or "mismatch" in row.notes.lower():
            ws.cell(row=r, column=10).fill = FLAG
        r += 1
    return r


def _summary(ws, r: int, s: ZoneSummary):
    r += 1
    ws.cell(row=r, column=3, value="Summary").font = Font(bold=True)
    items = [("Total Ceiling Area", s.ceiling_area_sf, "SqFt"), ("Total Flooring Area", s.floor_area_sf, "SqFt"),
             ("Total Wall Coverage (Gross)", s.wall_gross_sf, "SqFt"), ("Total Wall Coverage (Net)", s.wall_net_sf, "SqFt"),
             ("Total Wall Perimeter", s.perimeter_lf, "LF"), ("Net Sill Length", s.sill_lf, "LF")]
    for label, val, unit in items:
        r += 1
        ws.cell(row=r, column=3, value=label)
        ws.cell(row=r, column=5, value=round(val, 1))
        ws.cell(row=r, column=6, value=unit)


def _consolidate(rows: List[Row]) -> List[Row]:
    """General tab: same product + waste + coverage across zones becomes one line."""
    merged: "OrderedDict[tuple, Row]" = OrderedDict()
    for r in sorted(rows, key=lambda x: x.trade_no):
        k = (r.material_key or r.product, r.trade_no, r.waste, r.coverage, r.unit)
        if k in merged:
            m = merged[k]
            m.measure = round(m.measure + r.measure, 3)
            if r.description not in m.description:
                m.description += f" / {r.description}"
            if r.zone not in m.zone:
                m.zone += f", {r.zone}"
            m.uom = ""
            m.notes = "; ".join(dict.fromkeys([n for n in (m.notes + "; " + r.notes).split("; ") if n]))
        else:
            merged[k] = Row(**{**r.__dict__})
    out = list(merged.values())
    for m in out:
        m.quantity = raw_units(m.measure, m.coverage)
        m.adjusted = order_units(m.measure, m.waste, m.coverage)
    return out


def write_workbook(t: Takeoff, order_id: str, path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "General"
    _header(ws, t.project_name, order_id, "General - Consolidated Material List (all zones)")
    _write_rows(ws, _consolidate(t.rows))

    notes = wb.create_sheet("Estimator Notes")
    notes["A1"] = "Estimator Notes"
    notes["A1"].font = Font(bold=True, size=14, color="F96302")
    notes["A2"] = "Assumptions, conflicts, and anything that needs a human check before ordering."
    notes.column_dimensions["A"].width = 6
    notes.column_dimensions["B"].width = 120
    for i, n in enumerate(t.notes, start=1):
        notes.cell(row=3 + i, column=1, value=i)
        c = notes.cell(row=3 + i, column=2, value=n)
        c.alignment = Alignment(wrap_text=True, vertical="top")

    for z in t.zones:
        zrows = [r for r in t.rows if r.zone == z]
        for trade_no in sorted({r.trade_no for r in zrows}):
            trows = [r for r in zrows if r.trade_no == trade_no]
            ws = wb.create_sheet(_tab(f"{z} - {TAB_NAMES[trade_no]}"))
            _header(ws, t.project_name, order_id, f"{z} - {S.TRADES[trade_no]}")
            end = _write_rows(ws, trows)
            _summary(ws, end, t.summaries[z])

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path

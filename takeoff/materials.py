"""
Materials: what goes on the list, described by material and size.

Lumber, precut studs and LVL are generated on the fly from standard sizes
(no catalog row needed). Everything else (sheathing, shingles, wrap, drywall,
fasteners...) comes from references/materials.csv, which holds the
description and how much one unit covers. A SKU column there is optional.
"""
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from . import settings as S


@dataclass
class Material:
    key: str
    description: str
    unit: str                 # what you order: PCS, ROLL, BOX, GL, BAG...
    coverage_per_unit: float  # how much one unit covers
    coverage_unit: str        # LF / SF / EA ...
    sku: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# Generated lumber
# ---------------------------------------------------------------------------
def _fmt_len(ft: float) -> str:
    return f"{ft:g}'"


def lumber(nominal: str, length_ft: float, treated: bool = False) -> Material:
    grade = "PT ground contact" if treated else S.LUMBER_GRADE
    key = f"lumber:{nominal}:{length_ft:g}:{'pt' if treated else 'std'}"
    return Material(key, f"{nominal} x {_fmt_len(length_ft)} {grade}", "PCS", length_ft, "LF")


def stud(nominal: str, precut_in: str, treated: bool = False) -> Material:
    key = f"stud:{nominal}:{precut_in}:{'pt' if treated else 'std'}"
    kind = "PT precut stud" if treated else "precut stud"
    return Material(key, f'{nominal} x {precut_in}" {kind}', "PCS", 1, "EA")


def lvl(depth: str, length_ft: float) -> Material:
    key = f"lvl:{depth}:{length_ft:g}"
    return Material(key, f'1-3/4" x {depth}" x {_fmt_len(length_ft)} LVL', "PCS", length_ft, "LF")


def stock_length(required_ft: float, lengths=None) -> Optional[float]:
    """Shortest standard stock length that is at least required_ft."""
    for L in (lengths or S.STOCK_LENGTHS_FT):
        if L >= required_ft - 1e-6:
            return L
    return None


def precut_for_wall(wall_height_ft: float) -> Optional[str]:
    """Pick the precut stud that suits a plate height (3 plates = 4-1/2")."""
    stud_in = wall_height_ft * 12 - 4.5
    for name, inches in S.PRECUT_STUDS_IN.items():
        if abs(inches - stud_in) <= 1.5:
            return name
    return None


# ---------------------------------------------------------------------------
# Catalog of non-lumber materials
# ---------------------------------------------------------------------------
class Catalog:
    def __init__(self, csv_path: Path):
        self.items: Dict[str, Material] = {}
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for n, row in enumerate(csv.DictReader(f), start=2):
                try:
                    m = Material(
                        key=row["material_key"].strip(),
                        description=row["description"].strip(),
                        unit=(row.get("unit") or "PCS").strip(),
                        coverage_per_unit=float(row.get("coverage_per_unit") or 1),
                        coverage_unit=(row.get("coverage_unit") or "EA").strip().upper(),
                        sku=(row.get("sku") or "").strip(),
                        notes=(row.get("notes") or "").strip(),
                    )
                except (KeyError, ValueError) as e:
                    raise SystemExit(f"Problem in {csv_path.name} row {n}: {e}")
                if m.key in self.items:
                    raise SystemExit(f"Duplicate material_key '{m.key}' in {csv_path.name} row {n}")
                self.items[m.key] = m

    def keys(self) -> List[str]:
        return sorted(self.items)

    def get(self, key: str) -> Optional[Material]:
        return self.items.get(key)

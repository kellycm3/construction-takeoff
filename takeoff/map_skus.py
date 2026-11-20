"""
Looks up Home Depot SKUs in references/home_depot_chicago_skus.csv.

Exact lookups only. If an item isn't in the catalog, or its SKU cell is blank,
the line gets a blank SKU and "Pro Desk: verify SKU". If a row has no
verified_date yet, the SKU is shown but flagged "SKU not yet verified".
"""
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class CatalogItem:
    material_key: str
    sku: str
    product_title: str
    unit: str
    coverage_per_unit: float
    coverage_unit: str
    category: str
    nominal: str
    length_ft: Optional[float]
    treated: bool
    verified_date: str
    notes: str


class Catalog:
    def __init__(self, csv_path: Path):
        self.items: Dict[str, CatalogItem] = {}
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for n, row in enumerate(csv.DictReader(f), start=2):
                try:
                    item = CatalogItem(
                        material_key=row["material_key"].strip(),
                        sku=(row.get("sku") or "").strip(),
                        product_title=(row.get("product_title") or "").strip(),
                        unit=(row.get("unit") or "PCS").strip(),
                        coverage_per_unit=float(row.get("coverage_per_unit") or 1),
                        coverage_unit=(row.get("coverage_unit") or "EA").strip().upper(),
                        category=(row.get("category") or "").strip().lower(),
                        nominal=(row.get("nominal") or "").strip().lower(),
                        length_ft=float(row["length_ft"]) if (row.get("length_ft") or "").strip() else None,
                        treated=(row.get("treated") or "").strip().lower() in ("yes", "y", "true", "1"),
                        verified_date=(row.get("verified_date") or "").strip(),
                        notes=(row.get("notes") or "").strip(),
                    )
                except (KeyError, ValueError) as e:
                    raise SystemExit(f"Problem in {csv_path.name} row {n}: {e}")
                if item.material_key in self.items:
                    raise SystemExit(f"Duplicate material_key '{item.material_key}' in {csv_path.name} row {n}")
                self.items[item.material_key] = item

    def keys(self) -> List[str]:
        return sorted(self.items)

    def get(self, key: str) -> Optional[CatalogItem]:
        return self.items.get(key)

    def lumber(self, nominal: str, min_length_ft: float, treated: bool = False,
               categories=("lumber",)) -> Optional[CatalogItem]:
        """Shortest stocked board of this size that is at least min_length_ft long."""
        nominal = nominal.lower().replace(" ", "")
        fits = [
            i for i in self.items.values()
            if i.category in categories and i.nominal == nominal and i.treated == treated
            and i.length_ft is not None and i.length_ft >= min_length_ft - 1e-6
        ]
        return min(fits, key=lambda i: (i.length_ft, i.material_key)) if fits else None

    def longest_lumber(self, nominal: str, treated: bool = False) -> Optional[CatalogItem]:
        fits = [i for i in self.items.values()
                if i.category == "lumber" and i.nominal == nominal.lower() and i.treated == treated and i.length_ft]
        return max(fits, key=lambda i: i.length_ft) if fits else None

    def stud(self, nominal: str, wall_height_ft: float, treated: bool = False) -> Optional[CatalogItem]:
        """Precut stud for a wall height. Precut length + ~4.5\" of plates = wall height."""
        target = wall_height_ft - 0.375  # 3 plates x 1.5"
        fits = [i for i in self.items.values()
                if i.category == "stud" and i.nominal == nominal.lower() and i.treated == treated
                and i.length_ft is not None and abs(i.length_ft - target) <= 0.25]
        return fits[0] if fits else None

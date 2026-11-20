"""
Score a generated takeoff against one you trust, by MATERIAL AND SIZE.

Usage:
  python compare_to_reference.py <generated.xlsx> <reference.xlsx | reference.csv>

Reference can be an Excel takeoff (header row with "Product" and "Adjusted
Quantity" or "Quantity") or a CSV with columns: product, qty.
Both sides are reduced to keys like "2x6x16 PT", "stud 2x6 104-5/8",
"OSB 7/16 4x8", "LVL 11-7/8 x 20", then quantities are compared.
Also prints totals by family (all 2x6 studs, all 2x10 lumber, ...), which
shows whether a miss is the wrong length or a wrong overall amount.
"""
import csv
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from takeoff.normalize import material_key  # noqa: E402

TOLERANCE = 0.10


def _header(ws):
    for row in ws.iter_rows(min_row=1, max_row=40):
        names = [str(c.value).strip().lower() if c.value is not None else "" for c in row]
        if "product" in names or "home depot product" in names:
            return row[0].row, names
    raise SystemExit(f"No header row with 'Product' on sheet '{ws.title}'.")


def _sheet(wb):
    return wb["General"] if "General" in wb.sheetnames else wb[wb.sheetnames[0]]


def read_generated(path):
    ws = _sheet(load_workbook(path))
    hdr, names = _header(ws)
    i = {n: names.index(n) for n in names if n}
    out, names_by_key = defaultdict(float), {}
    for row in ws.iter_rows(min_row=hdr + 1, values_only=True):
        if not row or row[i["product"]] is None:
            continue
        m, cov, w = row[i["calc: measure"]], row[i["calc: coverage / unit"]], row[i["waste factor"]] or 0
        if m is None or not cov:
            continue
        k = material_key(row[i["product"]])
        out[k] += math.ceil(round(m * (1 + w) / cov, 6))
        names_by_key.setdefault(k, row[i["product"]])
    return out, names_by_key


def read_reference(path):
    path = Path(path)
    out, names_by_key = defaultdict(float), {}
    if path.suffix.lower() == ".csv":
        for r in csv.DictReader(open(path, newline="", encoding="utf-8-sig")):
            k = material_key(r["product"])
            out[k] += float(r["qty"])
            names_by_key.setdefault(k, r["product"])
        return out, names_by_key
    wb = load_workbook(path, data_only=True)
    ws = _sheet(wb)
    hdr, names = _header(ws)
    if "calc: measure" in names:
        return read_generated(path)
    pcol = names.index("product") if "product" in names else names.index("home depot product")
    qcol = next(names.index(n) for n in ("adjusted quantity", "total qty", "quantity", "qty") if n in names)
    for row in ws.iter_rows(min_row=hdr + 1, values_only=True):
        p, q = row[pcol], row[qcol]
        if p and isinstance(q, (int, float)):
            k = material_key(p)
            out[k] += q
            names_by_key.setdefault(k, p)
    return out, names_by_key


def family(k: str) -> str:
    m = re.match(r"(stud 2x\d)", k)
    if m:
        return m.group(1) + (" PT" if k.endswith("PT") else "") + " (all heights)"
    m = re.match(r"(\d x\d+|\dx\d+)x\d+( PT)?", k)
    if m:
        return k.split("x")[0] + "x" + k.split("x")[1] + (" PT" if "PT" in k else "") + " lumber (all lengths, pcs)"
    if k.startswith("LVL"):
        return "LVL (all, pcs)"
    if k.startswith("OSB") or k.startswith("plywood") or k.startswith("subfloor"):
        return k.split()[0] + " sheets"
    if k.startswith("drywall"):
        return k
    return k


def compare(generated, reference, show=True):
    gen, gnames = read_generated(Path(generated))
    ref, rnames = read_reference(Path(reference))
    rows = []
    for k in sorted(set(gen) | set(ref)):
        rq, gq = ref.get(k, 0), gen.get(k, 0)
        rows.append((k, rq, gq))
    within = sum(1 for k, r, g in rows if r and g and abs(g - r) / r <= TOLERANCE)
    missed = [x for x in rows if x[1] and not x[2]]
    extra = [x for x in rows if x[2] and not x[1]]
    off = [x for x in rows if x[1] and x[2] and abs(x[2] - x[1]) / x[1] > TOLERANCE]

    fam_r, fam_g = defaultdict(float), defaultdict(float)
    for k, r, g in rows:
        fam_r[family(k)] += r
        fam_g[family(k)] += g
    fams = [(f, fam_r[f], fam_g[f]) for f in fam_r if fam_r[f] or fam_g[f]]
    fam_ok = sum(1 for f, r, g in fams if r and abs(g - r) / r <= 0.15)
    fam_ref = sum(1 for f, r, g in fams if r)

    if show:
        n = len([x for x in rows if x[1]]) or 1
        print(f"\nReference material/size lines: {n}")
        print(f"  Within {TOLERANCE:.0%}: {within} ({within / n:.0%})   Off: {len(off)}   Missing: {len(missed)}   Extra: {len(extra)}")
        print(f"  Families within 15% (e.g. all 2x6 studs, all 2x10 lumber): {fam_ok} of {fam_ref}")
        print("\nBY FAMILY (reference -> generated):")
        for f, r, g in sorted(fams, key=lambda x: -max(x[1], x[2])):
            d = f"{(g - r) / r:+.0%}" if r else "extra"
            print(f"  {f[:46]:46} {r:>7g} -> {g:>7g}  {d}")
        print("\nOFF BY MORE THAN 10%:")
        for k, r, g in sorted(off, key=lambda x: -abs(x[2] - x[1])):
            print(f"  {k[:40]:40} {r:>7g} -> {g:>7g}  ({(g - r) / r:+.0%})")
        print("\nMISSING:")
        for k, r, g in sorted(missed, key=lambda x: -x[1]):
            print(f"  {k[:40]:40} ref {r:g}   ({str(rnames.get(k, ''))[:45]})")
        print("\nEXTRA (generated only):")
        for k, r, g in sorted(extra, key=lambda x: -x[2]):
            print(f"  {k[:40]:40} gen {g:g}")
    return {"within": within, "lines": len([x for x in rows if x[1]]), "fam_ok": fam_ok, "fam_total": fam_ref}


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    compare(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()

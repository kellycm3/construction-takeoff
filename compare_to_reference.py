"""
Score a generated takeoff against one you trust (e.g. Blueprint-Takeoff-11403).

Usage:
  python compare_to_reference.py output\\<run>\\<name>_material_list.xlsx evals\\Blueprint-Takeoff-11403.xlsx

Lines are matched by SKU on each workbook's General tab. Items without a SKU
can't be matched automatically, so they're listed separately for a manual look.
"""
import math
import sys
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

TOLERANCE = 0.05  # within 5% counts as a match


def _find_header(ws):
    for row in ws.iter_rows(min_row=1, max_row=30):
        names = [str(c.value).strip().lower() if c.value is not None else "" for c in row]
        if "sku" in names:
            return row[0].row, names
    raise SystemExit(f"Couldn't find a header row with 'SKU' on sheet '{ws.title}'.")


def _sheet(wb):
    return wb["General"] if "General" in wb.sheetnames else wb[wb.sheetnames[0]]


def read_generated(path):
    ws = _sheet(load_workbook(path))
    hdr, names = _find_header(ws)
    i = {n: names.index(n) for n in names if n}
    out, nosku = defaultdict(float), []
    read_generated.names = {}
    for row in ws.iter_rows(min_row=hdr + 1, values_only=True):
        if not row or row[i["product"]] is None:
            continue
        measure, cov, waste = row[i["calc: measure"]], row[i["calc: coverage / unit"]], row[i["waste factor"]] or 0
        if measure is None or not cov:
            continue
        qty = math.ceil(round(measure * (1 + waste) / cov, 6))
        sku = str(row[i["sku"]] or "").strip()
        if sku:
            out[sku] += qty
            read_generated.names[sku] = row[i["product"]]
        else:
            nosku.append((row[i["product"]], qty))
    return out, nosku


def read_reference(path):
    ws = _sheet(load_workbook(path, data_only=True))
    hdr, names = _find_header(ws)
    qcol = names.index("adjusted quantity") if "adjusted quantity" in names else names.index("quantity")
    scol, pcol = names.index("sku"), names.index("product") if "product" in names else None
    out, products = defaultdict(float), {}
    for row in ws.iter_rows(min_row=hdr + 1, values_only=True):
        sku = str(row[scol] or "").strip().split(".")[0]
        q = row[qcol]
        if sku and isinstance(q, (int, float)):
            out[sku] += q
            if pcol is not None:
                products[sku] = row[pcol]
    return out, products


def read_any(path):
    """A workbook from this program (formula columns) or one built by hand / saved by Excel."""
    ws = _sheet(load_workbook(path))
    _, names = _find_header(ws)
    if "calc: measure" in names:
        gen, _ = read_generated(path)
        return gen, dict(read_generated.names)
    return read_reference(path)


def compare(generated_path, reference_path):
    gen, nosku = read_generated(Path(generated_path))
    ref, names = read_any(Path(reference_path))

    good, off, missed, extra = [], [], [], []
    for sku, rq in ref.items():
        if sku not in gen:
            missed.append((sku, names.get(sku, ""), rq))
            continue
        gq = gen[sku]
        diff = (gq - rq) / rq if rq else 0
        (good if abs(diff) <= TOLERANCE else off).append((sku, names.get(sku, ""), rq, gq, diff))
    for sku, gq in gen.items():
        if sku not in ref:
            extra.append((sku, gq))

    total = len(ref) or 1
    print(f"\nReference lines: {len(ref)}")
    print(f"  Within {TOLERANCE:.0%}:  {len(good)}  ({len(good) / total:.0%})")
    print(f"  Off by more:  {len(off)}")
    print(f"  Missed:       {len(missed)}")
    print(f"  Extra (generated, not in reference): {len(extra)}")
    if off:
        print("\nOFF (reference -> generated):")
        for sku, n, rq, gq, d in sorted(off, key=lambda x: -abs(x[4])):
            print(f"  {sku:>11}  {str(n)[:50]:50}  {rq:>6g} -> {gq:>6g}  ({d:+.0%})")
    if missed:
        print("\nMISSED:")
        for sku, n, rq in missed:
            print(f"  {sku:>11}  {str(n)[:50]:50}  ref qty {rq:g}")
    if extra:
        print("\nEXTRA:")
        for sku, gq in extra:
            print(f"  {sku:>11}  qty {gq:g}")
    if nosku:
        print("\nGenerated lines with no SKU (check by hand):")
        for p, q in nosku:
            print(f"  {str(p)[:70]:70}  qty {q:g}")
    return {"within": len(good), "off": len(off), "missed": len(missed), "extra": len(extra), "total": len(ref)}


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    compare(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()

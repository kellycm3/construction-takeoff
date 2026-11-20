"""
Construction Material Takeoff (Home Depot Chicago)

Usage:
  python run_takeoff.py plans\\my_plan.pdf --project "Deerfield Garage" --order-id H1987-12345
  python run_takeoff.py plans\\my_plan.pdf --engine claude
  python run_takeoff.py plans\\my_plan.pdf --engine both          (runs Gemini AND Claude, then compares)
  python run_takeoff.py --from-json examples\\sample_garage_extraction.json      (no AI, no API key)
"""
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from takeoff.build_lines import build_takeoff  # noqa: E402
from takeoff.excel import write_workbook  # noqa: E402
from takeoff.materials import Catalog  # noqa: E402
from takeoff.schemas import PlanExtraction  # noqa: E402


def _extract(engine: str, pdf: Path, catalog: Catalog, out_dir: Path) -> PlanExtraction:
    if engine == "gemini":
        from takeoff.gemini_client import extract_from_pdf
    else:
        from takeoff.claude_client import extract_from_pdf
    return extract_from_pdf(pdf, catalog.keys(), out_dir)


def _build(data: PlanExtraction, catalog: Catalog, args, out_dir: Path, base_name: str) -> Path:
    if args.project:
        data.project_name = args.project
    (out_dir / "final_extraction.json").write_text(data.model_dump_json(indent=2), encoding="utf-8")
    print("Calculating quantities and matching SKUs...")
    takeoff = build_takeoff(data, catalog, args.scope)
    xlsx = write_workbook(takeoff, args.order_id, out_dir / f"{base_name}_material_list.xlsx")
    special = sum(1 for r in takeoff.rows if "special order" in r.notes.lower())
    print(f"  Workbook:        {xlsx}")
    print(f"  Line items:      {len(takeoff.rows)}  ({special} special order)  scope: {takeoff.scope}")
    print(f"  Estimator notes: {len(takeoff.notes)}  (read these before ordering)")
    return xlsx


def main():
    load_dotenv(HERE / ".env")
    p = argparse.ArgumentParser(description="Turn construction plan PDFs into a Home Depot material list.")
    p.add_argument("pdf", nargs="?", help="Path to the plan PDF")
    p.add_argument("--engine", choices=["gemini", "claude", "both"], default="gemini",
                   help="Which AI reads the plans (default: gemini)")
    p.add_argument("--from-json", help="Skip the AI and build the workbook from a saved extraction JSON")
    p.add_argument("--project", help="Project name for the header (defaults to what's on the plans)")
    p.add_argument("--order-id", default="", help="Order / quote number for the header")
    p.add_argument("--scope", choices=["full", "framing"], default=None,
                   help="full = everything (default); framing = floor/wall/roof framing, sheathing, wrap, deck framing")
    p.add_argument("--catalog", default=str(HERE / "references" / "materials.csv"))
    args = p.parse_args()

    if not args.pdf and not args.from_json:
        p.error("give a PDF path, or --from-json with a saved extraction")

    catalog = Catalog(Path(args.catalog))
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    base_name = Path(args.pdf or args.from_json).stem
    run_dir = HERE / "output" / f"{re.sub(r'[^A-Za-z0-9_-]+', '_', base_name)}_{stamp}"

    if args.from_json:
        run_dir.mkdir(parents=True, exist_ok=True)
        data = PlanExtraction.model_validate_json(Path(args.from_json).read_text(encoding="utf-8"))
        print(f"Loaded extraction from {args.from_json}")
        _build(data, catalog, args, run_dir, base_name)
        print("\nDone.")
        return

    pdf = Path(args.pdf.strip('"'))
    if not pdf.exists():
        sys.exit(f"Can't find {pdf}. Check the path (tip: drag the PDF into this window).")

    engines = ["gemini", "claude"] if args.engine == "both" else [args.engine]
    results = {}
    for engine in engines:
        out_dir = run_dir / engine if len(engines) > 1 else run_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== {engine.upper()} ===")
        try:
            data = _extract(engine, pdf, catalog, out_dir)
            results[engine] = _build(data, catalog, args, out_dir, base_name)
        except (RuntimeError, SystemExit) as e:
            print(f"  {engine} failed: {e}")
            if len(engines) == 1:
                raise

    if len(results) == 2:
        from compare_to_reference import compare
        print("\n=== GEMINI vs CLAUDE (Claude's numbers compared against Gemini's) ===")
        compare(results["claude"], results["gemini"])
        print("\nTo see which one is RIGHT, score each against a takeoff you trust:")
        for eng, x in results.items():
            print(f"  python compare_to_reference.py \"{x}\" evals\\<your reference>.xlsx")
    print("\nDone.")


if __name__ == "__main__":
    main()

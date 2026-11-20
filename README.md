# Construction Material Takeoff

Drop in a plan PDF and get back a material list workbook (material + size + quantity) in the Blueprint-Takeoff layout, with waste factors and estimator notes. Covers floor, wall and roof framing (including hip roofs, jacks, hips/valleys, LVLs and floor systems), sheathing, wrap, roofing, siding, drywall, insulation, windows and doors.

**How it works**

1. **Gemini or Claude (your choice) reads the plans.** It reports only measurements: wall lengths and heights, openings from the schedules, roof pitch and overhangs, and drywall and siding types. Every value cites the sheet it came from.
2. **The same AI checks its own read.** A second pass compares the read against the plans (perimeter, schedules, gable ends, checklist), then fixes anything it finds.
3. **Python does the math.** Studs, sheets, bundles, and waste all come from fixed rules, so the same plans always give the same numbers.
4. **Lumber is sized automatically** (precut studs by wall height, shortest stock length per cut, nested short cuts, 26'-28' special-order lengths, LVL where called for). Other materials come from `references/materials.csv`, which says what one unit covers. SKUs are optional.
5. **Excel workbook.** You get a General tab, an Estimator Notes tab, and one tab per zone and trade.

---

## One-time setup (Windows, about 10 minutes)

1. **Install Python.** Go to https://www.python.org/downloads/ and install the latest version. On the first installer screen, check **"Add python.exe to PATH"**.
2. **Unzip this folder** somewhere easy to find, like `Documents\construction-takeoff`.
3. **Get an API key for whichever AI you want to use (or both):**
   - **Gemini:** go to https://aistudio.google.com/apikey, sign in with Google, and click **Create API key**.
   - **Claude:** go to the Claude Console at https://platform.claude.com, open **API Keys**, and create a key. The API is billed separately from a Claude.ai subscription, so you'll need to add a few dollars of credit.
4. **Double-click `setup.bat`.** It installs everything, then opens Notepad. Paste your key(s) after `GEMINI_API_KEY=` and/or `ANTHROPIC_API_KEY=`, save, and close Notepad.
5. Setup then runs a **sample garage** (no API key needed for this) and should end with **"Done."**. Open the `output` folder to see the sample workbook.

## Running a takeoff

**Drag a plan PDF onto `takeoff.bat`.** It asks which AI to use (`gemini`, `claude`, or `both`), then for a project name and order ID; press Enter to skip any of them. When it's done, the `output` folder opens.

**Framing only:** add `--scope framing` to leave out roofing, siding, drywall, finishes, windows and doors.

**`both`** runs Gemini and Claude on the same PDF, saves a workbook from each (in `gemini` and `claude` subfolders), and prints where their quantities disagree. Those lines are the ones worth checking against the plans.

Each run creates its own folder in `output` containing:
- `..._material_list.xlsx`: the workbook
- `1_extraction.json`: Gemini's first read of the plans
- `2_verification_round1.json`: the problems the second pass found
- `final_extraction.json`: the measurements the math actually used

Command-line version, if you prefer:
```
.venv\Scripts\python run_takeoff.py plans\my_plan.pdf --project "Deerfield Garage" --order-id H1987-12345
.venv\Scripts\python run_takeoff.py plans\my_plan.pdf --engine claude
.venv\Scripts\python run_takeoff.py plans\my_plan.pdf --engine both
```

## Reading the workbook

- **Yellow Notes cell:** check this line (Pro Desk SKU, special order, rule-of-thumb coverage, or a unit mismatch).
- **Estimator Notes tab:** read it before ordering. It lists every default that was assumed, every conflict found in the plans, and everything Gemini couldn't find.
- **Gray "Calc" columns:** the measurement and the coverage per unit. The Quantity and Adjusted Quantity cells are live formulas from these columns, so you can change a measurement or waste factor and the order quantity updates.
- **General tab:** combines all zones and rounds once on the combined total, so it can come out a piece lower than adding up the individual tabs.

## Gemini or Claude: which one?

Test it on your own plans rather than going on reputation:

1. Run `--engine both` on the plans behind a takeoff you trust (like Blueprint-Takeoff-11403).
2. Score each workbook against your real one with `compare_to_reference.py` (see below).
3. Whichever gets more lines within 5% wins. Try 2 or 3 different plan sets before deciding.

Claude accepts PDFs up to 32 MB. Split bigger plan sets into smaller files.

## Knowledge base

`references/takeoff_guide.md` holds the measuring rules the tool follows (from the Basic Takeoff Guide) and lessons learned from scored jobs. Add to it as you go.

## Measuring undimensioned walls

```
.venv\Scripts\python tools\measure_walls.py plans.pdf --page 6 --scale 0.25
```
Measures shaded walls off a plan sheet by scale and reports LF of 2x4 and 2x6 walls. It saves a picture of what it measured so you can check it.

## Before you trust it on a real order

1. **Check coverage numbers.** Open `references\materials.csv` and confirm `coverage_per_unit` for each material (sq ft per bundle, LF per roll, and so on). Several are rules of thumb and are marked in the notes column.
2. **Score it against a takeoff you trust.** Put the plans and your finished Blueprint-Takeoff-11403 workbook in `evals\`, run a takeoff on those plans, then:
   ```
   .venv\Scripts\python compare_to_reference.py output\<run folder>\<name>_material_list.xlsx evals\Blueprint-Takeoff-11403.xlsx
   ```
   It matches lines by **material and size** (so different wording or sourcing still lines up), and also totals by family (all 2x6 studs, all 2x10 lumber, all OSB...). Reference can be an Excel takeoff or a CSV with `product,qty` columns. Use the results to tune `settings.py`. Keep client plans and takeoffs in `evals\`; that folder is never uploaded to GitHub.
3. **Check repeatability.** Run the same plans 2 or 3 times. Every number comes from Gemini's measurements, so if a trade swings between runs, open the `final_extraction.json` files and compare what Gemini read.

## Tuning

Everything adjustable is in **`takeoff\settings.py`**: waste factors, defaults (stud spacing, pitch, overhang), extra studs per corner and opening, ice-barrier rules, and which catalog product is used for each job. Change it, save, and re-run.

To re-run only the math after a tweak, without paying for Gemini again:
```
.venv\Scripts\python run_takeoff.py --from-json output\<run folder>\final_extraction.json --project "Name" --order-id 123
```

**Adding materials:** add a row to `materials.csv` (description, unit, coverage per unit). Lumber doesn't need rows: sizes and stock lengths are in `settings.py` (`STOCK_LENGTHS_FT`, `PRECUT_STUDS_IN`, `SPECIAL_ORDER_LENGTHS_FT`).

## What it calculates vs. what it flags

**Calculated automatically:** sill plates (treated on slab) and sill seal, top and bottom plates, studs by wall height (with corners and king/jack studs), blocking, basement furring walls, gable studs, headers (ply count and LVL depth from the callout), wall and roof sheathing, floor joists, rim and subfloor, gable and hip roof framing (commons, jacks, hips, valleys, ridge, LVL over 24'), sub fascia, rake boards, soffit framing, roof bracing allowance, ceiling joists, hurricane ties, shingles, underlayment, ice and water barrier (to code, 24" inside the wall), starter, ridge cap, ridge vent, drip edge, roofing nails, house wrap and tape, flashing tape, cap nails, fiber cement or vinyl siding, starter strip, trim, J-channel, eave soffit, drywall (walls and ceilings by type), tape, mud, and screws.

**Measured by the AI, converted by the program:** decks, insulation, paint, interior trim, foundation items. Gemini reports the LF, SF, or count, and Python converts it to orderable units.

**Flagged for you:** windows and doors (special order, with their schedule specs), trusses and engineered joists (confirm with the manufacturer layout), brick or other siding, nails and screws.

## Troubleshooting

- **"GEMINI_API_KEY is not set" / "ANTHROPIC_API_KEY is not set"**: open `.env` in Notepad and paste the key after the `=`.
- **Claude says "credit balance is too low"**: add credit in the Claude Console under Billing.
- **Quota, billing, or "model not found" errors**: your key may not have access to that model. Enable billing, or set `GEMINI_MODEL=` / `CLAUDE_MODEL=` in `.env` to a model your key can use (for example `claude-sonnet-5-5`, which is cheaper).
- **The PDF won't process**: remove any password protection and make sure the file is a real PDF.
- **Something else**: take a screenshot of the window and send it to Claude.

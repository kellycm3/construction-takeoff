# Construction Material Takeoff (Home Depot Chicago)

Drop in a plan PDF and get back a Home Depot material list workbook in your Blueprint-Takeoff layout, with SKUs, waste factors, and estimator notes.

**How it works**

1. **Gemini or Claude (your choice) reads the plans.** It reports only measurements: wall lengths and heights, openings from the schedules, roof pitch and overhangs, and drywall and siding types. Every value cites the sheet it came from.
2. **The same AI checks its own read.** A second pass compares the read against the plans (perimeter, schedules, gable ends, checklist), then fixes anything it finds.
3. **Python does the math.** Studs, sheets, bundles, and waste all come from fixed rules, so the same plans always give the same numbers.
4. **Python looks up the SKUs** in your catalog file. If an item isn't in the catalog, its SKU is left blank and the line is flagged for Pro Desk. The program never makes up a SKU.
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

## Before you trust it on a real order

1. **Verify the catalog.** Open `references\home_depot_chicago_skus.csv` in Excel. For each row, confirm the SKU and the `coverage_per_unit` (sq ft per bundle, LF per roll, and so on), then put today's date in `verified_date`. Until a row has a date, its lines say "SKU not yet verified". Several coverage numbers are rules of thumb and are marked in the notes column. One SKU looks suspicious: the non-vented soffit is one digit off the vented one.
2. **Score it against a takeoff you trust.** Put the plans and your finished Blueprint-Takeoff-11403 workbook in `evals\`, run a takeoff on those plans, then:
   ```
   .venv\Scripts\python compare_to_reference.py output\<run folder>\<name>_material_list.xlsx evals\Blueprint-Takeoff-11403.xlsx
   ```
   It matches lines by SKU and lists what's within 5%, what's off, what's missing, and what's extra. Use those results to tune `settings.py`.
3. **Check repeatability.** Run the same plans 2 or 3 times. Every number comes from Gemini's measurements, so if a trade swings between runs, open the `final_extraction.json` files and compare what Gemini read.

## Tuning

Everything adjustable is in **`takeoff\settings.py`**: waste factors, defaults (stud spacing, pitch, overhang), extra studs per corner and opening, ice-barrier rules, and which catalog product is used for each job. Change it, save, and re-run.

To re-run only the math after a tweak, without paying for Gemini again:
```
.venv\Scripts\python run_takeoff.py --from-json output\<run folder>\final_extraction.json --project "Name" --order-id 123
```

**Adding products:** add a row to the CSV. For lumber, fill in `category` = `lumber`, `nominal` (like `2x6`), `length_ft`, and `treated` (yes/no). The program automatically picks the shortest board that fits each cut. For example, add a 2x6x14 and the sample garage's rafters drop from 16' to 14' boards.

## What it calculates vs. what it flags

**Calculated automatically:** sill plates and sill seal, top and bottom plates, studs (with corners and king/jack studs), gable studs, headers (cut-optimized), wall and roof sheathing, rafters, ridge, sub fascia, ceiling joists, hurricane ties, shingles, underlayment, ice and water barrier (to code, 24" inside the wall), starter, ridge cap, ridge vent, drip edge, roofing nails, house wrap and tape, flashing tape, cap nails, fiber cement or vinyl siding, starter strip, trim, J-channel, eave soffit, drywall (walls and ceilings by type), tape, mud, and screws.

**Measured by Gemini, priced by catalog:** floor systems, decks, insulation, paint, interior trim, foundation items. Gemini reports the LF, SF, or count, and Python converts it to orderable units.

**Flagged for you:** windows and doors (special order, with their schedule specs), trusses, hip roof framing, brick or other siding, and fasteners and adhesive.

## Troubleshooting

- **"GEMINI_API_KEY is not set" / "ANTHROPIC_API_KEY is not set"**: open `.env` in Notepad and paste the key after the `=`.
- **Claude says "credit balance is too low"**: add credit in the Claude Console under Billing.
- **Quota, billing, or "model not found" errors**: your key may not have access to that model. Enable billing, or set `GEMINI_MODEL=` / `CLAUDE_MODEL=` in `.env` to a model your key can use (for example `claude-sonnet-5-5`, which is cheaper).
- **The PDF won't process**: remove any password protection and make sure the file is a real PDF.
- **Something else**: take a screenshot of the window and send it to Claude.

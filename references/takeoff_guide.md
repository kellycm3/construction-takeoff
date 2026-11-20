# Takeoff Knowledge Base

Rules and conventions this tool follows. Read this before reading plans.
Sources are listed for each section. Add new sections as more guides come in.

---

## 1. Basic Takeoff Guide (General Estimating Guide)

*Source: "Basic Takeoff Guide", supplied by Chris (Nov 2026). Summarized in
our own words. NOTE: the copy on file ends in the Foundations section; the
Basement & Pony Walls, Exterior Walls, Interior Walls, Roofs, and Windows &
Doors sections still need to be added.*

### Order of work and units

Measure the plans in this order, each in its own unit:

| # | Item | Unit |
|---|------|------|
| 1 | Floor area | SF |
| 2 | Flat (plan) area covered by roof | SF |
| 3 | Footings | LF |
| 4 | Foundation walls | LF |
| 5 | Interior walls | LF |
| 6 | Exterior walls | LF |
| 7 | Common walls (house/garage) | LF |
| 8 | Garage walls | LF |
| 9 | Roof edge (eaves + rakes) | LF |
| 10 | Roof ridge lines (ridges, hips, valleys) | LF |
| 11 | Door schedule | count by mark |
| 12 | Window schedule | count by mark |

Units matter because the same measurements drive both material and labor.

### Floor area

- **Main floor and garage:** measure to the **outside** of the exterior walls.
- **Odd shapes:** split into rectangles, measure each, and add them.
- **Basement:** measure to the **inside** of the foundation walls. Include
  storage under a porch and any doorway openings formed in the concrete.
- Keep main, garage, and basement areas separate.

### Footings

- Two kinds: **exterior wall footings** and **interior grade footings**. Keep
  them separate. They may be the same size but are reinforced differently
  (exterior footings get vertical rebar), so they cost differently.
- A typical residential exterior footing is about 16" wide x 8" deep. Always
  use the size on the plans.
- **Don't double-count corners.** Because footings have width, measuring
  every run to the outside counts each corner twice. Two ways to avoid it:
  1. **Average method:** (outside length + inside length) / 2 for each run.
     Easier when you can't mark up the plans.
  2. **Horizontal/vertical method (preferred, more accurate):** measure runs
     drawn horizontally on the sheet to the **outside**, and runs drawn
     vertically to the **inside**. Garage footings run to the basement
     foundation, not past it.
- Record width, height (depth), and length for each footing type.

### Foundation walls

- Two kinds: **main foundation** and **garage (shallow / frost) foundation**.
  Keep them separate; they have different dimensions.
- Record thickness, height, and length for each.
- Use the same horizontal/vertical method as footings so corners aren't
  counted twice.

---

## 2. Lessons from scored test jobs

*Source: comparing this tool's output against takeoffs Chris supplied.*

- **Interior wall lengths are the biggest source of error.** When partitions
  aren't dimensioned, measure them with `tools/measure_walls.py` (same method
  every time) and flag them as scaled. Both test jobs missed most here.
- **Wall height decides the stud.** 8'-1" plate = 92-5/8" precut, 9'-1" =
  104-5/8", 10'-1" = 116-5/8". Taller walls (balloon framing) get cut from
  stock. Read the section for each floor; basements are often 8'-1".
- **Hips and valleys are long.** On an 8:12 roof spanning 40' they run past
  30'. Check the plan notes (e.g. "hips over 24' shall be LVL").
- **Commons over 24'** need 26'/28' special-order stock, an LVL, or purlins.
- **Ice & water barrier:** if the roof plan says "extend 2'-0" beyond the
  interior face of the wall," that's 2 rows (courses) of 36" on an 8:12 roof
  with a 12" overhang, plus valleys.
- **Framing-only jobs** (like the Singh house) exclude roofing, siding,
  drywall, finishes, windows, and doors. Run with `--scope framing`.
- **Estimator allowances seen in real takeoffs:** one row of blocking per LF
  of wall; soffit framing about 2 LF of 2x4 per LF of eave; roof bracing
  about 0.9 pieces each of 2x4x16 and 2x6x16 per 100 SF of roof. These are
  in `takeoff/settings.py`.

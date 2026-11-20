# Takeoff Knowledge Base

Rules and conventions this tool follows. Read this before reading plans.
Sources are listed for each section. Add new sections as more guides come in.

---

## Source and license

Sections 1-3 summarize, in our own words, the **BYU-Idaho Construction
Estimating Reference Book** (https://books.byui.edu/construction_estimat),
licensed **CC BY-SA 4.0**. This file is shared under the same license.
Chris supplied the book (Nov 2026). It also has two complete worked examples
(the "Ranch House" and "Small Cottage" walkthroughs) that can be used as
future test jobs.

## 1. Basic Takeoff Guide

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

### Basement and pony walls

- Two kinds, estimated separately:
  - **Bearing walls**: room partitions, walls under the floor system, and pony
    walls on top of a short foundation. Double top plate, 2x4 @ 16" O.C.
  - **Insulation walls**: built around the inside of the foundation to hold
    insulation and finishes. Single top plate, studs @ 24" O.C. (in this tool:
    `is_furring = true`).
- Check the wall section for the real construction.
- Measure with the horizontal/vertical method so corners aren't double-counted.

### Exterior walls

Three kinds, estimated separately:
- **Exterior walls** (often 2x6): on the floor system, sheathed with OSB.
- **Garage walls** (often 2x4): on the garage foundation, so the studs are
  longer, and the bottom plate is pressure treated.
- **Common walls** (house to garage, often 2x6): drywall both sides, no
  sheathing.

### Interior walls

Three kinds: 2x4 interior, 2x6 interior (plumbing walls), and **tall 2x4
interior** walls (taller than the exterior walls, usually at vaulted ceilings).

### Roofs

- **Flat roof area:** the roof footprint in plan, including overhangs, not
  the sloped area. Include any part of a lower roof hidden under the overhang
  of a higher roof (overhang x half that roof's width).
- **Ridge line LF:** every ridge. A porch ridge that dies into a main roof is
  its edge length plus its run (half its span).
- **Roof edge LF:** all horizontal edges (eaves) plus all sloped edges (rakes).
  A rake's length is the hypotenuse of run (half the span) and rise
  (run x pitch / 12).

### Windows and doors

Copy counts, sizes and types straight from the window and door schedules.

---

## 2. Framing rules (Framing Estimating Guide + Framing chapter)

- **Plates:** wall LF x number of plates x (1 + waste) / board length.
  Bearing walls: 1 bottom + 2 top. Insulation walls: 1 + 1.
- **Studs:** wall LF / spacing, plus
  - 2 studs for every corner or wall intersection (count them on the plan),
  - 2 studs for every window or door under 6' wide (trimmers; the king studs
    come from the on-center studs left out of the opening),
  - 6 studs for every **window** 6' or wider (double trimmers, sill, cripples),
  - no extra for doors 6' or wider (the studs left out of the opening cover it).
- **Wall sheathing height** runs from the top of the wall down to the top of
  the foundation, so add the floor system depth (sill 1-1/2" + joist depth +
  subfloor 3/4"). Example: an 8'-1 1/8" wall on 11-7/8" joists is about 9'-3"
  of sheathing. Only OSB/plywood/foam goes on exterior walls here; drywall is
  counted with the interior.
- **Mud sill, sill sealer and rim joist** all equal the sill perimeter.
- **Floor joists:** total LF of joists measured on the framing plan, then
  divided by the joist length (buy whole pieces, round up).
- **Blocking:** count the joist spaces x the block length (spacing minus joist
  width).
- **Hangers:** a count, only where members don't sit on a bearing surface.
- **Subfloor:** floor area / 32 SF per 4x8 sheet.
- **Subfloor adhesive:** one ounce covers about 3.14 LF of joist (1/4" bead;
  a 28 oz tube is about 88 LF). Tubes = (LF of joist per SF of floor + 0.125)
  x floor SF x (1 + waste) / 3.14 / 28. That's about one tube per 3 sheets at
  16" O.C., 3.5 sheets at 19.2", and 4+ sheets at 24".
- **Nails:** bought in bulk and carried job to job; an allowance (e.g. two
  boxes each of 16d and 8d) is enough for a house.

## 3. Exterior finish rules (Exterior Finishes chapter)

- **Shingles:** sloped roof area with 10% waste, 3 bundles per square.
- **Roofing nails:** bundles x shingles per bundle (27 standard, 21 metric) x
  4 or 6 nails per shingle / 7,200 per box. Not rounded up in the book (leftovers
  carry forward); this tool rounds up.
- **Felt / underlayment:** 30# rolls cover 200 SF; 15# rolls cover 400 SF;
  synthetic 1,000 SF rolls cover about 937 SF with 3" laps (875 SF with 6").
- **Cap nails for felt:** about 0.67 SF per nail at 8" spacing (0.5 at 6").
- **Starter course:** along the horizontal roof edges (eaves).
- **Ice & water shield:** along the roof edges, plus the valleys (each valley
  = its length plus 3'). Follow the plan note if it asks for more (e.g.
  "2'-0" inside the wall" = 2 courses on an 8:12 roof with a 12" overhang).
- **Ridge cap:** ridge LF (incl. hips) x a 1' width.
- **Step flashing:** sloped length of each wall/roof intersection / shingle
  exposure (5-5/8" metric).
- **House wrap:** exterior wall length x (wall height + floor depth, about 9'
  for an 8' wall), plus gable areas. Don't subtract openings.
- **Siding:** wall areas with **10%** waste; gables and other triangles with
  **30%** waste. Subtract only openings of **25 SF or more**; ignore smaller ones.
- **Siding starter strip:** wherever a course starts with a full piece: wall
  lengths minus garage doors, porches, etc.
- **J-channel:** where walls meet the soffit, plus around doors and windows.

---

## 4. Lessons from scored test jobs

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
- **Estimator allowances seen in real takeoffs (Aurora job):** one row of blocking per LF
  of wall; soffit framing about 2 LF of 2x4 per LF of eave; roof bracing
  about 0.9 pieces each of 2x4x16 and 2x6x16 per 100 SF of roof. These are
  in `takeoff/settings.py`.

---

## 5. Estimating context (project-management level)

*Source: Carolyn McGary, "Introduction to Construction Project Management",
Module Four: Cost Estimating and Procurement,
https://colorado.pressbooks.pub/introconstructionmanagement/ (CC BY 4.0).
Summarized in our own words. This book is about the overall estimating
process, not quantity-takeoff rules; it has no waste factors or takeoff
procedures.*

- **Estimate levels:** screening / order-of-magnitude (before design, from
  similar past jobs), preliminary / conceptual, and detailed / definitive
  (scope defined, design underway). Accuracy follows the information
  available, so a takeoff from permit plans is a detailed estimate and should
  be labeled that way.
- **The takeoff is the "unit cost / bill of quantities" method:** break the
  work into items, measure quantities, apply unit costs, add them up. This
  tool produces the quantities; pricing comes after.
- **Process:** plan the bid (scope, schedule, who does what), pre-bid
  (subcontractors, quantity takeoffs, overhead), bid day (final pricing, error
  check), and a post-bid review win or lose. Our post-bid review is running
  `compare_to_reference.py` against the final order.
- **Data sources, most to least reliable:** actual supplier/sub quotes, the
  company's own history, then national averages such as RS Means.
- **Price escalation:** about 3% per year unless told otherwise; adjust
  national-average prices with a location factor.
- **State inclusions and exclusions** on every estimate (the Estimator Notes
  tab does this: what was assumed, what wasn't found, what's by others).
- **Avoid scope gaps and double counting** between packages (e.g. framing vs.
  truss supplier vs. steel supplier). Get at least three bids per subcontracted
  scope.

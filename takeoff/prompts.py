"""The instructions sent to Gemini. Edit the wording here if you want to change how it reads plans."""

CHECKLIST = """\
COMPLETENESS CHECKLIST (each item must be captured somewhere, or listed in not_found):
- Foundation / slab (if in scope): concrete, vapor barrier, wire mesh or rebar, anchor bolts, form boards
- Every exterior and interior wall run, per zone, with height and stud size
- Gable-end triangles as their own WallRun (is_gable_end = true, height_ft = gable rise)
- Every window, door, and overhead door, matched to its schedule mark
- Header callouts for each opening
- Roof: style, footprint, pitch, eave and rake overhangs, rafter or truss size and spacing, ceiling joists
- Floor system (if framed floor): joists, rim, subfloor, hangers, adhesive
- Exterior deck (if any): ledger, joists, beams, posts, decking, hardware
- Siding type per zone; exterior trim (corner boards, casings, rake/fascia trim)
- Insulation (walls, attic, rim) and vapor retarder, if the space is conditioned
- Drywall type on walls and ceilings per zone (fire-rated where noted)
- Interior finishes: base, casing, stairs, railing
- Paint / primer, if called out
- Step flashing, valleys, or other roofing details where shown
"""

EXTRACTION_PROMPT = f"""\
You are a residential / light-commercial estimator reading construction plans.
Report ONLY what is written or drawn on the plans. Do NOT calculate piece counts,
waste, prices, or SKUs. Python does all of that from your measurements.

Work in this order:
1. Read the title block, sheet index, scale, and general notes.
2. Read every schedule (window, door, header, wall type) BEFORE the floor plans.
3. Trace each wall run in each zone. Exterior runs must add up to the building
   perimeter. If they don't, say so in estimator_notes.
4. List every opening, matched to its schedule mark. Openings with no schedule
   entry go in estimator_notes.
5. Roof: style, footprint, pitch, overhangs, framing size and spacing.
   Add each gable-end triangle as its own WallRun (is_gable_end = true).
6. Fill one ZoneSpec per zone (siding type, drywall types, floor and ceiling area).
7. Use other_items ONLY for things not already covered by walls, openings, roofs,
   and zones (floor system, deck, insulation, paint, interior trim, foundation,
   step flashing, etc.). Give a MEASUREMENT (LF, SF, BF, CY) or an EA count.
   Choose material_key from the list below; use 'UNLISTED' if nothing fits and
   describe it fully.
8. Walk the checklist. Anything not shown on the plans goes in not_found.
9. Cite the sheet and the exact dimension string or callout for every value.

Rules:
- Prefer written dimensions. Only scale off the drawing if no dimension exists;
  then set measured_by_scale = true and confidence = "low".
- If a value isn't on the plans, return null. Never fill in a "typical" value.
- Convert feet-inches to decimal feet (24'-6" = 24.5).
- Use consistent zone names (e.g. "Main", "STORAGE").

{CHECKLIST}
"""

VERIFY_PROMPT = f"""\
You are a second estimator checking another estimator's extraction of these plans.
The extraction JSON is below. Compare it against the plans and return every
problem you find as {{field, problem, fix, sheet}}.

Check:
- Exterior wall runs per zone sum to the building perimeter (within 1 ft).
- Opening count per schedule mark matches the schedules.
- Every opening sits on a wall that exists in the extraction.
- Gable ends are included as WallRuns.
- Wall heights, stud sizes, pitch, and overhangs match the plans.
- Every checklist item is present, or listed in not_found.
- Any value with measured_by_scale = true has a reason (no written dimension).
- Nothing was invented: every value has a real sheet and source_note.

Return an empty issues list ONLY if you find nothing wrong.

{CHECKLIST}
"""

CORRECT_PROMPT = """\
You extracted measurements from these plans, and a reviewer found the issues listed
below. Re-check each issue against the plans and return the full corrected
extraction (same schema). Only change what the plans support. If a reviewer's fix
is wrong, keep the original value and explain why in estimator_notes.
"""

"""
Turns a product description into a comparable "material + size" key, so two
takeoffs can be compared even when they word or source things differently.

  "2 in. x 6 in. x 16 ft. #2 Standard Grade SPF"   -> "2x6x16"
  "2x6x16' #2 Prime Ground Contact P.T. SYP"        -> "2x6x16 PT"
  "2x6 x 104-5/8\" precut stud"                     -> "stud 2x6 104-5/8"
  "1-3/4\" x 11-7/8\" x 20' LVL (LP)"               -> "LVL 11-7/8 x 20"
  "7/16 in. x 4 ft. x 8 ft. OSB Panel"              -> "OSB 7/16 4x8"
"""
import re

FRAC = r"\d+(?:[ -]\d+/\d+)?|\d+/\d+"


def _clean(t: str) -> str:
    t = t.replace("”", '"').replace("″", '"').replace("’", "'").replace("×", "x")
    t = re.sub(r"\s+in\.?", '"', t)
    t = re.sub(r"\s+ft\.?", "'", t)
    return t


def _pt(t: str) -> bool:
    return bool(re.search(r"\bp\.?t\.?\b|pressure|treated|ground contact|\bgc\b", t, re.I))


def material_key(text: str) -> str:
    if not text:
        return ""
    raw = str(text)
    t = _clean(raw)
    low = t.lower()

    m = re.match(r"\s*mark\s+([0-9a-z]+)", low)
    if m:
        kind = "door" if re.search(r"door|swing|pocket|overhead", low) else "window"
        return f"{kind} mark {m.group(1)}"
    early = [
        (r"joint tape|drywall tape", "drywall tape"), (r"joint compound|drywall mud", "joint compound"),
        (r"cement board screw", "cement board screws"), (r"1-5/8.*screw|screw.*1-5/8", "drywall screws 1-5/8"),
        (r"1-1/4.*screw|screw.*1-1/4", "drywall screws 1-1/4"), (r"corner bead", "corner bead"),
        (r"clip", "sheathing clips"), (r"closed cell|spray foam", "spray foam"),
        (r"attic.*insul|r-?60|comfort therm", "attic insulation"),
        (r"hardie trim|fiber cement trim|exterior trim|trim board", "exterior trim"),
    ]
    for pat, name in early:
        if re.search(pat, low):
            return name

    # LVL
    m = re.search(r"1[ -]?3/4\"?\s*x\s*(" + FRAC + r")\"?\s*(?:x\s*(\d+)\s*'?)?", t)
    if "lvl" in low and m:
        depth = m.group(1).replace(" ", "-")
        return f"LVL {depth}" + (f" x {m.group(2)}" if m.group(2) else "")
    # Precut studs
    m = re.search(r"(2)\s*\"?\s*x\s*(4|6)\s*\"?\s*x\s*(92|104|116)[ -]5/8", t)
    if m:
        return f"stud 2x{m.group(2)} {m.group(3)}-5/8" + (" PT" if _pt(t) else "")
    # Dimensional lumber 2x6x16, 4x4x8, 1x8x16, 2x2x8
    m = re.search(r"(?<![/\d])([1-8])\s*\"?\s*x\s*(\d{1,2})\s*\"?\s*x\s*(\d{1,2})\s*'", t) or \
        re.search(r"(?<![/\d])([1-8])\s*x\s*(\d{1,2})\s*x\s*(\d{1,2})\b", t)
    if m and "lvl" not in low and "drywall" not in low and "osb" not in low and "plywood" not in low:
        return f"{m.group(1)}x{m.group(2)}x{m.group(3)}" + (" PT" if _pt(t) else "")
    # Sheet goods
    m = re.search(r"(" + FRAC + r")\"?\s*(?:x\s*)?(?:4\s*'?\s*x\s*(8|9|10|12)|\(?4x(8|9|10|12))", t)
    thick = None
    mt = re.search(r"(\d+/\d+)\s*\"?", t)
    if mt:
        thick = mt.group(1)
    size = None
    ms = re.search(r"4\s*'?\s*x\s*(8|9|10|12)\b", t)
    if ms:
        size = f"4x{ms.group(1)}"
    if "osb" in low or "oriented strand" in low:
        return f"OSB {thick or '?'} {size or ''}".strip()
    if "advantech" in low:
        return f"subfloor AdvanTech {thick or ''} {size or ''}".strip()
    if "plywood" in low or "cdx" in low or "rtd" in low or "plytanium" in low:
        return f"plywood {thick or '?'} {size or ''}".strip()
    if "backerboard" in low or "backer board" in low:
        return "cement backerboard"
    if "drywall" in low or "gypsum" in low or "firecode" in low:
        kind = "X" if re.search(r"type\s*x|firecode", low) else ("MR" if "mold" in low else "")
        return f"drywall {thick or '?'} {size or ''} {kind}".replace("  ", " ").strip()

    # Everything else by keyword
    rules = [
        (r"ridge cap", "ridge cap shingles"), (r"starter (strip )?shingle|starter shingles", "starter shingles"),
        (r"shingle", "shingles"), (r"ice|leak barrier|peel and stick", "ice & water"),
        (r"underlayment|feltbuster|felt", "underlayment"), (r"ridge.*vent|cobra", "ridge vent"),
        (r"drip edge", "drip edge"), (r"step flash", "step flashing"), (r"roofing nail|coil roofing", "roofing nails"),
        (r"window.*tape|door tape|flashing tape", "flashing tape"), (r"housewrap tape|house wrap tape|tyvek tape|installation tape", "house wrap tape"),
        (r"housewrap|house wrap|homewrap", "house wrap"), (r"cap nail|round cap", "cap nails"),
        (r"sill (plate )?gasket|sill seal", "sill seal" + (" 7-1/2" if "7" in low.split("sill")[0][-6:] or "7 1/2" in low or "7-1/2" in low else "")),
        (r"hurricane|h2\.?5", "hurricane tie"), (r"lus210-2|double 2x10", "hanger LUS210-2"),
        (r"lus210|2x10 nominal", "hanger LUS210"), (r"lus28|2x8 nominal", "hanger LUS28"),
        (r"joint compound|drywall mud", "joint compound"), (r"joint tape|drywall tape", "drywall tape"),
        (r"1-5/8.*screw|screw.*1-5/8", "drywall screws 1-5/8"), (r"1-1/4.*screw|screw.*1-1/4", "drywall screws 1-1/4"),
        (r"corner bead", "corner bead"), (r"subfloor.*adhesive|construction adhesive|liquid nails", "subfloor adhesive"),
        (r"fiber cement.*siding|hardie plank|lap siding", "fiber cement siding"), (r"vinyl siding|dutch lap", "vinyl siding"),
        (r"soffit", "soffit"), (r"j[- ]channel", "J-channel"), (r"f[- ]channel", "F-channel"),
        (r"starter strip", "siding starter strip"), (r"\brim ?board", "rim board"),
        (r"tji\s*(\d+)", None),
    ]
    for pat, name in rules:
        mm = re.search(pat, low)
        if mm:
            if name is None:
                return f"TJI {mm.group(1)}"
            return name
    return re.sub(r"[^a-z0-9/ ]", "", low)[:40].strip()

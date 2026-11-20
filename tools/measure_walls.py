"""
Measure wall lengths off a floor plan by scale, the same way every time.

Use it when partitions aren't dimensioned. It finds the filled wall shapes on
one plan sheet, traces their centerlines, and reports linear feet grouped by
wall thickness (2x4 vs 2x6 walls). Door and window openings are gaps in the
fill, so they are NOT included; add them back from the schedules.

Usage:
  python tools/measure_walls.py plans.pdf --page 6 --scale 0.25
  python tools/measure_walls.py plans.pdf --page 6 --scale 0.25 --crop 2500 700 5000 3100
  python tools/measure_walls.py plans.pdf --page 3 --scale 0.25 --mode dark   (scanned plans / black walls)

  --scale   plan scale in inches per foot (1/4" = 1'-0"  ->  0.25)
  --crop    x0 y0 x1 y1 in pixels at --dpi, to measure one plan and skip
            schedules, title blocks and details on the same sheet
  --mode    gray  = walls filled with a gray tone (most CAD plans, default)
            dark  = walls drawn solid black (many scanned plans)
  --gray    the gray value of the wall fill if not ~127 (0=black, 255=white)

Writes <pdf>_p<page>_walls.png showing exactly what was measured: check it.
Requires: pip install scikit-image scipy pillow, and poppler (pdftoppm).
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import remove_small_objects, skeletonize


def render(pdf: Path, page: int, dpi: int) -> np.ndarray:
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "p"
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-f", str(page), "-l", str(page), str(pdf), str(out)],
                       check=True)
        png = next(Path(d).glob("p*.png"))
        return np.array(Image.open(png).convert("L"))


def measure(img: np.ndarray, dpi: int, scale_in_per_ft: float, mode: str, gray: int):
    px_per_ft = scale_in_per_ft * dpi
    if mode == "gray":
        mask = (img >= gray - 8) & (img <= gray + 8)
    else:
        mask = img < 100
        # keep only shapes thicker than ~2.5" of wall (drops thin lines and text)
        min_px = max(2, int(2.5 / 12 * px_per_ft))
        mask = ndi.binary_opening(mask, structure=np.ones((min_px, min_px)))
    mask = ndi.binary_closing(mask, iterations=2)
    mask = remove_small_objects(mask, max_size=int(px_per_ft * 0.5) ** 2)
    dist = ndi.distance_transform_edt(mask)
    sk = skeletonize(mask)
    thick_in = dist[sk] * 2 / px_per_ft * 12
    bins = [("thin (<3\")", 0, 3), ("2x4 wall (3-5.5\")", 3, 5.5), ("2x6 wall (5.5-8\")", 5.5, 8), ("thick (>8\")", 8, 99)]
    result = {name: float(((thick_in >= lo) & (thick_in < hi)).sum() / px_per_ft) for name, lo, hi in bins}
    result["total"] = float(sk.sum() / px_per_ft)
    return result, mask


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--page", type=int, required=True)
    ap.add_argument("--scale", type=float, required=True, help="inches per foot, e.g. 0.25 for 1/4\"=1'-0\"")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--crop", type=int, nargs=4, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--mode", choices=["gray", "dark"], default="gray")
    ap.add_argument("--gray", type=int, default=127)
    a = ap.parse_args()

    img = render(Path(a.pdf), a.page, a.dpi)
    if a.crop:
        x0, y0, x1, y1 = a.crop
        img = img[y0:y1, x0:x1]
    res, mask = measure(img, a.dpi, a.scale, a.mode, a.gray)
    print(f"Page {a.page} at {a.dpi} dpi, scale {a.scale}\"/ft ({a.mode} walls):")
    for k, v in res.items():
        print(f"  {k:22} {v:8.1f} LF")
    print("Openings are gaps and are NOT included; add door/window widths from the schedules.")
    out = Path(a.pdf).with_name(f"{Path(a.pdf).stem}_p{a.page}_walls.png")
    Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)).save(out)
    print(f"Check what was measured: {out}")


if __name__ == "__main__":
    main()

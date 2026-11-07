"""Feic Mo Chroí heart: the first creation made with PubCast's Filler Cream engine.

Made 2026-11-06. A heart-shaped dome of 1/64 blocks (rounded down to whole
blocks) is run through modules/filler_cream.compute_filler at high fidelity,
then shown raw and creamed as a top-down shaded view (matplotlib, not the
PubCast renderer).

Run from the repo root (PowerShell 5):  python tools\\feic_mo_chroi_heart.py
Writes docs\\filler_cream\\feic_mo_chroi_heart.png
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from modules.filler_cream import FillerSelection, SurfacePiece, compute_filler  # noqa: E402


def build_heart(n: int = 56):
    heights = np.full((n, n), np.nan)
    pieces = []
    for i in range(n):
        for j in range(n):
            x = (i - n / 2 + 0.5) / (n * 0.36)
            y = -(j - n / 2 + 0.5) / (n * 0.36) + 0.25
            f = (x * x + y * y - 1) ** 3 - x * x * y ** 3  # heart curve: inside where f < 0
            if f < 0:
                h = int(math.floor(6 + 14 * (-f) ** 0.22))  # dome, whole 1/64 blocks
                heights[i, j] = h
                pieces.append(SurfacePiece(f"h{i}_{j}", (i, h - 4, j), (1, 4, 1)))
    return heights, pieces


def main(out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource, LinearSegmentedColormap

    raw, pieces = build_heart()
    layer = compute_filler(pieces, FillerSelection(frozenset(p.piece_id for p in pieces), fidelity="high"))
    creamed = raw.copy()
    for c in layer.cells:
        creamed[c.column] = max(creamed[c.column], c.top)

    gold = LinearSegmentedColormap.from_list("gold", ["#2a1f12", "#8a6a2e", "#d8af5b", "#f3e3b5"])
    light = LightSource(azdeg=315, altdeg=40)
    fig, axes = plt.subplots(1, 2, figsize=(10, 5.4), facecolor="#0e0d0b")
    for ax, z, title in ((axes[0], raw, "raw 1/64 blocks"), (axes[1], creamed, "with Filler Cream")):
        rgb = light.shade(np.nan_to_num(z, nan=0.0).T, cmap=gold, blend_mode="soft", vert_exag=3)
        rgb[np.isnan(z.T)] = (0.055, 0.051, 0.043, 1)
        ax.imshow(rgb, origin="upper")
        ax.set_axis_off()
        ax.set_title(title, color="#d8af5b", fontsize=11, family="monospace")
    fig.suptitle("Feic Mo Chroí", color="#f3e3b5", fontsize=17, family="serif", y=0.98)
    fig.text(0.5, 0.03, f"{len(pieces)} blocks · {len(layer.cells)} cream cells · fidelity high · 1/64 block = 3.97 mm",
             ha="center", color="#8a6a2e", fontsize=8, family="monospace")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=140, facecolor=fig.get_facecolor())
    print(f"{len(pieces)} blocks, {len(layer.cells)} cream cells -> {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "filler_cream" / "feic_mo_chroi_heart.png")

"""Write before/after views of the Filler Cream proof fixture.

Outputs (default folder docs/filler_cream):
  fixture_before.glb / fixture_after.glb  — baked by the existing VoxelBaker
  before_after_profile.png                — side profile of strip one (z row 0)

Run from the repo root:  python tools/filler_cream_view.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.filler_cream import FillerSelection, bake_with_filler, compute_filler, pieces_from_voxel_object  # noqa: E402
from modules.filler_cream_fixture import OPENING_X, build_fixture_object, fixture_annotations  # noqa: E402
from modules.voxel_studio import VoxelBaker  # noqa: E402


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    obj = build_fixture_object()
    pieces, _ = pieces_from_voxel_object(obj, fixture_annotations())
    layer = compute_filler(pieces, FillerSelection(frozenset(p.piece_id for p in pieces)))
    (out_dir / "fixture_before.glb").write_bytes(VoxelBaker().bake(obj))
    (out_dir / "fixture_after.glb").write_bytes(bake_with_filler(obj, [layer], pieces=pieces))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    strip = [p for p in pieces if p.origin[2] == 0]
    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True, facecolor="#141210")
    for ax, title, show in ((axes[0], "Before: voxel pieces only", False), (axes[1], "After: Filler Cream (gold)", True)):
        ax.set_facecolor("#141210")
        for p in strip:
            ax.add_patch(Rectangle((p.origin[0], p.origin[1]), p.size[0], p.size[1],
                                   facecolor="#6f6a63", edgecolor="#d8cfc2", lw=0.6))
            ax.text(p.origin[0] + p.size[0] / 2, p.origin[1] + p.size[1] + 0.6, p.piece_id,
                    ha="center", fontsize=6, color="#d8cfc2")
        if show:
            for c in layer.cells:
                if c.column[1] == 0:
                    ax.add_patch(Rectangle((c.column[0] * layer.grid_unit, c.base), layer.grid_unit,
                                           c.top - c.base, facecolor="#d8af5b", edgecolor="none"))
        ax.axvspan(*OPENING_X, color="#2a3a4a", alpha=0.5)
        ax.text(sum(OPENING_X) / 2, 2, "opening", ha="center", fontsize=7, color="#9fb8d0")
        ax.set_xlim(-2, 96)
        ax.set_ylim(-1, 34)
        ax.set_title(title, color="#e8dcc8", fontsize=10)
        ax.set_ylabel("height (1/64 block)", color="#d8cfc2", fontsize=8)
        ax.tick_params(colors="#d8cfc2", labelsize=7)
    axes[1].set_xlabel("x (1/64 block = 3.97 mm)", color="#d8cfc2", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "before_after_profile.png", dpi=150, facecolor=fig.get_facecolor())
    print(f"cells={len(layer.cells)} grid_unit={layer.grid_unit} volume={layer.volume()} -> {out_dir}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "filler_cream")

from __future__ import annotations

import math
from typing import Optional, Tuple
from pydantic import BaseModel, Field


class Line2D(BaseModel):
    p1: Tuple[float, float]
    p2: Tuple[float, float]


class SolverResult(BaseModel):
    success: bool
    pitch_deg: float
    roll_deg: float
    fov_vertical_deg: float
    focal_length_px: float
    horizon_y_ratio: float
    vanishing_point_a: Optional[Tuple[float, float]] = None
    vanishing_point_b: Optional[Tuple[float, float]] = None
    used_fallback_focal_length: bool = False
    error_message: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class PerspectiveSolver:
    """Deterministic two-vanishing-point calibration for painted 2.5D sets.

    The result deliberately does not clamp the horizon into the source image:
    a valid horizon can be above/below frame.  Arbitrary orbit is *not* implied
    by this calibration; authored plate-preserving shots remain constrained.
    """

    EPS = 1e-8

    @staticmethod
    def compute_intersection(line1: Line2D, line2: Line2D) -> Optional[Tuple[float, float]]:
        x1, y1 = line1.p1; x2, y2 = line1.p2
        x3, y3 = line2.p1; x4, y4 = line2.p2
        denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
        if abs(denom) < PerspectiveSolver.EPS:
            return None
        t1 = x1*y2 - y1*x2
        t2 = x3*y4 - y3*x4
        return (
            (t1*(x3-x4) - (x1-x2)*t2) / denom,
            (t1*(y3-y4) - (y1-y2)*t2) / denom,
        )

    @staticmethod
    def _fallback_focal(image_width: float, fov_horizontal_deg: float = 45.0) -> float:
        return (image_width / 2.0) / math.tan(math.radians(fov_horizontal_deg / 2.0))

    @classmethod
    def solve(cls, pair_a_line1: Line2D, pair_a_line2: Line2D,
              pair_b_line1: Line2D, pair_b_line2: Line2D,
              image_width: float, image_height: float) -> SolverResult:
        if image_width <= 0 or image_height <= 0:
            raise ValueError("image dimensions must be positive")
        vp1 = cls.compute_intersection(pair_a_line1, pair_a_line2)
        vp2 = cls.compute_intersection(pair_b_line1, pair_b_line2)
        fallback = cls._fallback_focal(image_width)
        if vp1 is None or vp2 is None:
            return SolverResult(success=False, pitch_deg=0.0, roll_deg=0.0,
                fov_vertical_deg=math.degrees(2*math.atan(image_height/(2*fallback))),
                focal_length_px=fallback, horizon_y_ratio=0.5,
                used_fallback_focal_length=True,
                error_message="Degenerate/parallel guide lines; two vanishing points are required.")

        cx, cy = image_width/2.0, image_height/2.0
        dx, dy = vp2[0]-vp1[0], vp2[1]-vp1[1]
        if math.hypot(dx, dy) < cls.EPS:
            return SolverResult(success=False, pitch_deg=0.0, roll_deg=0.0,
                fov_vertical_deg=math.degrees(2*math.atan(image_height/(2*fallback))),
                focal_length_px=fallback, horizon_y_ratio=(vp1[1]/image_height),
                vanishing_point_a=vp1, vanishing_point_b=vp2,
                used_fallback_focal_length=True,
                error_message="Vanishing points collapse to one point; calibration is underdetermined.")

        roll = math.atan2(dy, dx)
        f2 = -((vp1[0]-cx)*(vp2[0]-cx) + (vp1[1]-cy)*(vp2[1]-cy))
        warnings: list[str] = []
        used_fallback = f2 <= cls.EPS or not math.isfinite(f2)
        focal = fallback if used_fallback else math.sqrt(f2)
        if used_fallback:
            warnings.append("Orthogonal-vanishing-point focal estimate invalid; 45° horizontal fallback used.")
        fov_v = 2.0 * math.atan(image_height/(2.0*focal))

        # Horizon is the line through the vanishing points. Evaluate at principal x.
        if abs(dx) > cls.EPS:
            horizon_y = vp1[1] + (cx-vp1[0])*(dy/dx)
        else:
            # A vertical horizon is not a useful conventional camera calibration.
            horizon_y = (vp1[1] + vp2[1]) / 2.0
            warnings.append("Vanishing-point horizon is near vertical; roll/calibration should be reviewed.")
        # Screen y grows downward: horizon above principal point means camera pitched down.
        pitch = math.atan2(cy-horizon_y, focal)

        return SolverResult(
            success=True,
            pitch_deg=round(math.degrees(pitch), 4),
            roll_deg=round(math.degrees(roll), 4),
            fov_vertical_deg=round(math.degrees(fov_v), 4),
            focal_length_px=round(focal, 4),
            horizon_y_ratio=round(horizon_y/image_height, 6),
            vanishing_point_a=vp1, vanishing_point_b=vp2,
            used_fallback_focal_length=used_fallback, warnings=warnings,
        )

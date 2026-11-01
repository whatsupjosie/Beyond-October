"""PubWorld 2.5D stage runtime.

The manifest describes portable authored state; StageService owns mutable runtime
state.  Keeping the two separate prevents UI state from silently becoming the
scene authority.
"""
from .manifest_store import SceneManifest, ManifestStore
from .perspective_solver import Line2D, PerspectiveSolver, SolverResult
from .stage_service import StageService

__all__ = ["SceneManifest", "ManifestStore", "Line2D", "PerspectiveSolver", "SolverResult", "StageService"]

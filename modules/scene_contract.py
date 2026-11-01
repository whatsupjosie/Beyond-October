"""
scene_contract.py — Generic Scene / Engine / Builder / Contact for the PubCast
damage-physics chain resolver.

WHY THIS FILE EXISTS
---------------------
`streaming_chain_resolver.py` (in this same package) was written against an
inferred interface: `scene.objects[id]` with `.mass` / `.is_static` /
`.material` / `.physics.restitution` / `.physics.friction`, a `Contact`
object, an `engine.predict_secondary_contacts(...)` hook, and a
`builder.fetch_geometry(prop_id)` awaitable. None of that generic contract
existed anywhere in the PubCast codebase that was made available for this
review — what exists instead is:

  - `bubble_stack_pikpc/sandbox.py` → `PubBlockSandbox`, a **hardcoded
    5-object demo scene** (actor, hand, table, chair, vase, cup) with a real
    `MaterialProfile(mass, friction, restitution, stability, fragility)` and
    `KineticIntent`/`PhysicsResolution` impulse math. Its own bundled
    `HANDOFF.md` lists "Generalization of PIKPC physics (currently 5-object
    demo) to arbitrary entities" as an explicit open task — so a generic
    Scene genuinely doesn't exist yet, this isn't a case of it being missed.
  - `bubble_stack_pikpc/engine.py` → `BubbleStackEngine`, which by its own
    docstring is "intentionally not a renderer or physics engine" — it's a
    spatial-attention / Joule-Load system, not a collision solver.
  - `pubworld_blocks.py` → a real `Prop`/`Block` voxel schema and a literal
    `Builder` naming convention (`BuilderPreset`, `save_builder_preset`,
    `get_builder_preset`) for *editable* voxel geometry, but with integer
    grid coordinates and no physics fields at all.

This module is the generalization: it reuses the real `MaterialProfile`
field names (mass/friction/restitution/stability/fragility) and the real
`Prop`/`Block` shape, wired to satisfy exactly the contract
`streaming_chain_resolver.py` already expects, so that file needed **zero
changes** to work against this instead of the review's mock classes.

If/when the real generalized engine lands in the PubCast repo, replace this
module's `Engine`/`Builder`/`Scene` with the real ones — the resolver's call
sites don't need to change as long as the same attribute names are honored
(see the "Integration Contract" section of REVIEW.md).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Rigid-body material — field-for-field the same shape as the real
# bubble_stack_pikpc.sandbox.MaterialProfile(mass, friction, restitution,
# stability, fragility). Kept as its own dataclass (not reusing that module
# directly) so this package has no hard dependency on the giant PubCast repo.
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class RigidMaterial:
    mass: float
    friction: float = 0.45
    restitution: float = 0.25
    stability: float = 1.0
    fragility: float = 0.0

    @staticmethod
    def demo_defaults() -> "RigidMaterial":
        return RigidMaterial(mass=1.0, friction=0.45, restitution=0.25, stability=1.0)


# Presets lifted directly from the five hardcoded objects in
# bubble_stack_pikpc/sandbox.py's PubBlockSandbox.__init__, so a newly
# generalized object of a given "kind" starts from the same numbers the real
# demo already validated, instead of invented defaults.
_RIGID_PRESETS: Dict[str, RigidMaterial] = {
    "actor": RigidMaterial(mass=77.1, friction=0.8, restitution=0.05, stability=1.0),
    "hand": RigidMaterial(mass=4.0, friction=0.6, restitution=0.05, stability=1.0),
    "table": RigidMaterial(mass=18.0, friction=0.75, restitution=0.08, stability=2.5),
    "chair": RigidMaterial(mass=7.0, friction=0.55, restitution=0.18, stability=1.5),
    "vase": RigidMaterial(mass=1.15, friction=0.42, restitution=0.18, stability=0.72, fragility=0.85),
    "cup": RigidMaterial(mass=0.38, friction=0.35, restitution=0.28, stability=0.55, fragility=0.45),
    "generic_prop": RigidMaterial(mass=2.0, friction=0.5, restitution=0.2, stability=1.0, fragility=0.2),
}


def infer_structural_material(rigid: RigidMaterial, semantic_tags: Tuple[str, ...] = ()) -> str:
    """Map a rigid-body MaterialProfile (mass/friction/restitution/stability/
    fragility — the real PubCast dimensions) onto a deformation_math
    MaterialProfile name (yield/ultimate/elastic-modulus — this package's
    fracture-math dimensions). These two material concepts don't exist in
    the same place anywhere in the source material reviewed, so this mapping
    is new, heuristic, and worth a content-team sanity check — it is not
    lifted from anything in the real repo the way RigidMaterial's numbers
    are.
    """
    tags = set(semantic_tags)
    if "glass" in tags or rigid.fragility >= 0.7:
        return "glass"
    if "wood" in tags or "furniture" in tags:
        return "wood"
    if "cast_iron" in tags or "hydrant" in tags:
        return "hydrant_iron"
    if rigid.fragility >= 0.35:
        return "plastic"
    if rigid.stability >= 2.0 and rigid.mass >= 10.0:
        return "concrete"
    if rigid.mass >= 30.0:
        return "steel"
    return "aluminum"


@dataclass(slots=True)
class SceneObject:
    object_id: str
    position: np.ndarray
    extent: np.ndarray  # half-size AABB extent, meters
    rigid: RigidMaterial
    semantic_tags: Tuple[str, ...] = ()
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    structural_material: Optional[str] = None  # computed lazily if None

    def __post_init__(self):
        self.position = np.asarray(self.position, dtype=np.float64)
        self.extent = np.asarray(self.extent, dtype=np.float64)
        self.velocity = np.asarray(self.velocity, dtype=np.float64)
        if self.structural_material is None:
            self.structural_material = infer_structural_material(self.rigid, self.semantic_tags)

    # --- streaming_chain_resolver.py's expected attribute surface ---
    @property
    def mass(self) -> float:
        return self.rigid.mass

    @property
    def is_static(self) -> bool:
        return "static" in self.semantic_tags

    @property
    def material(self) -> str:
        """Read by MaterialProfile.by_name(obj.material) in the resolver."""
        return self.structural_material

    @property
    def physics(self) -> RigidMaterial:
        """Read as obj.physics.restitution / obj.physics.friction in the resolver."""
        return self.rigid

    @property
    def bounds_min(self) -> np.ndarray:
        return self.position - self.extent

    @property
    def bounds_max(self) -> np.ndarray:
        return self.position + self.extent

    def aabb_intersects(self, other: "SceneObject") -> bool:
        return bool(np.all(self.bounds_min <= other.bounds_max) and np.all(other.bounds_min <= self.bounds_max))

    def aabb_contains_point(self, point: np.ndarray) -> bool:
        return bool(np.all(self.bounds_min <= point) and np.all(point <= self.bounds_max))

    @classmethod
    def from_preset(cls, object_id: str, kind: str, position, extent=(0.25, 0.25, 0.25),
                     semantic_tags: Tuple[str, ...] = (), velocity=(0.0, 0.0, 0.0)) -> "SceneObject":
        rigid = _RIGID_PRESETS.get(kind, _RIGID_PRESETS["generic_prop"])
        tags = semantic_tags or (kind,)
        return cls(object_id, np.array(position, dtype=np.float64), np.array(extent, dtype=np.float64),
                    rigid, tags, np.array(velocity, dtype=np.float64))


@dataclass(slots=True)
class ChainConfig:
    depth_limit: int = 4
    max_chain_duration: float = 2.0


@dataclass(slots=True)
class Scene:
    objects: Dict[str, SceneObject] = field(default_factory=dict)
    chain: ChainConfig = field(default_factory=ChainConfig)

    def add(self, obj: SceneObject) -> None:
        self.objects[obj.object_id] = obj

    @staticmethod
    def demo_scene() -> "Scene":
        """A small scene assembled from the real PubBlockSandbox presets —
        useful for smoke-testing the resolver without a live PubCast host."""
        scene = Scene(chain=ChainConfig(depth_limit=4, max_chain_duration=2.0))
        scene.add(SceneObject.from_preset("actor_body", "actor", (2.0, 0.9, 7.0), (0.35, 0.9, 0.35), ("actor", "human", "body")))
        scene.add(SceneObject.from_preset("table", "table", (10.0, 0.55, 7.0), (0.9, 0.55, 0.6), ("prop", "furniture", "table", "static")))
        scene.add(SceneObject.from_preset("chair", "chair", (8.4, 0.5, 8.2), (0.45, 0.5, 0.45), ("prop", "furniture", "chair")))
        scene.add(SceneObject.from_preset("vase", "vase", (9.45, 1.25, 6.8), (0.14, 0.35, 0.14), ("prop", "vase", "fragile", "glass")))
        scene.add(SceneObject.from_preset("cup", "cup", (10.55, 1.16, 7.1), (0.14, 0.18, 0.14), ("prop", "cup", "grabbable")))
        return scene


# ---------------------------------------------------------------------------
# Contact — what the engine hands the resolver for both the initial impact
# (via ChoreographyController.on_contact_frame) and secondary contacts (via
# Engine.predict_secondary_contacts below). Field names match what
# ChainImpact.from_contact_frame() already reads defensively via getattr.
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class Contact:
    attacker_id: str
    target_id: str
    timestamp: float = 0.0
    attacker_mass: Optional[float] = None
    contact_point: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    contact_normal: Tuple[float, float, float] = (0.0, 1.0, 0.0)
    force_vector: Optional[Tuple[float, float, float]] = None
    force_magnitude: Optional[float] = None
    relative_velocity: float = 0.0
    duration: float = 0.02
    is_first_frame_of_contact: bool = True


# ---------------------------------------------------------------------------
# Engine — implements the one hook streaming_chain_resolver.py calls:
# predict_secondary_contacts(). Collision detection here is deterministic
# segment sampling of the launched object's straight-line path against every
# other object's AABB, generalizing the pattern in
# bubble_stack_pikpc/sandbox.py's _first_contact_on_path /
# _first_contact_on_projectile_path (which did the same thing but hardcoded
# to the cup vs. {vase, chair, table}). This is not a continuous-collision
# solver — same caveat the original sandbox code states about itself.
# ---------------------------------------------------------------------------
class Engine:
    def __init__(self, gravity_m_s2: float = 9.80665, air_drag: float = 0.02, steps: int = 48):
        self.gravity = gravity_m_s2
        self.air_drag = air_drag
        self.steps = steps

    async def predict_secondary_contacts(self, source_id: str, position, velocity, time_budget: float) -> List[Contact]:
        scene: Optional[Scene] = getattr(self, "_scene", None)
        if scene is None or time_budget <= 0:
            return []
        start = np.asarray(position, dtype=np.float64)
        v0 = np.asarray(velocity, dtype=np.float64)
        source = scene.objects.get(source_id)
        duration = min(time_budget, 0.9)

        # --- Adaptive step count. A fixed step count tunnels straight through
        # small/fast-moving targets: at high launch speed, a fixed-`steps`
        # sample of a ~1s flight can jump clean over a vase-sized AABB
        # between one sample and the next (verified by hand: an 8m/s launch
        # hitting nothing at 48 steps/0.9s despite a straight-line path
        # through the target). Pick a step count so no single step travels
        # further than half the smallest target extent in the scene, bounded
        # to a sane range so a very slow launch doesn't cost thousands of
        # samples.
        speed = float(np.linalg.norm(v0))
        min_extent = min((float(np.min(o.extent)) for oid, o in scene.objects.items() if oid != source_id), default=0.05)
        if speed > 1e-6 and min_extent > 1e-6:
            required_steps = int(np.ceil((speed * duration) / (0.5 * min_extent)))
        else:
            required_steps = self.steps
        steps = max(self.steps, min(2000, required_steps))

        for i in range(1, steps + 1):
            t = duration * (i / steps)
            drag = max(0.0, 1.0 - self.air_drag * t)
            p = np.array([
                start[0] + v0[0] * t * drag,
                start[1] + v0[1] * t - 0.5 * self.gravity * t * t,
                start[2] + v0[2] * t * drag,
            ])
            for oid, obj in scene.objects.items():
                if oid == source_id:
                    continue
                if obj.aabb_contains_point(p):
                    rel_speed = float(np.linalg.norm(v0)) * drag
                    normal = (p - obj.position)
                    n_norm = float(np.linalg.norm(normal))
                    normal = normal / n_norm if n_norm > 1e-9 else np.array([0.0, 1.0, 0.0])
                    return [Contact(
                        attacker_id=source_id, target_id=oid, timestamp=t,
                        attacker_mass=float(source.mass) if source else None,
                        contact_point=tuple(p.tolist()), contact_normal=tuple(normal.tolist()),
                        relative_velocity=rel_speed, duration=0.02,
                    )]
        return []

    def bind_scene(self, scene: Scene) -> None:
        self._scene = scene


# ---------------------------------------------------------------------------
# Builder — geometry provider for streaming_chain_resolver.py's
# `await builder.fetch_geometry(tid)`. Tries the real PubCast Prop/Block
# voxel schema first (pubworld_blocks.py: integer x/y/z grid coords + "kind"
# string), converts it to the float pos/extent/material_id shape
# deformation_math.BlockDef expects, and falls back to the same procedural
# fire-hydrant generator already reviewed in pubworld_router.py so this
# works standalone without a props directory present.
# ---------------------------------------------------------------------------
_KIND_TO_MATERIAL_ID = {"cube": 1, "half": 1, "wedge": 1}

class Builder:
    def __init__(self, props_dir: Optional[Any] = None, voxel_size: float = 0.08):
        # --- FIX (self-audit pass): props_dir / "pubworld" / ... below
        # requires a pathlib.Path; a caller passing a plain string (very
        # normal — e.g. straight from an env var or config file, the way
        # pubworld_router.py's own PROPS_DATA_DIR is built) crashed with
        # `TypeError: unsupported operand type(s) for /: 'str' and 'str'`
        # the first time fetch_geometry() was awaited. Coerce once here.
        self.props_dir = Path(props_dir) if props_dir is not None else None
        self.voxel_size = voxel_size

    async def fetch_geometry(self, prop_id: str) -> Optional[List[Dict[str, Any]]]:
        real_prop_blocks = self._load_real_prop(prop_id)
        if real_prop_blocks is not None:
            return real_prop_blocks
        return self._procedural_fallback(prop_id)

    def _load_real_prop(self, prop_id: str) -> Optional[List[Dict[str, Any]]]:
        if not self.props_dir:
            return None
        path = self.props_dir / "pubworld" / "props" / f"{prop_id}.json"
        if not path.exists():
            return None
        try:
            import json
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw_blocks = payload.get("blocks", [])
            out = []
            for i, b in enumerate(raw_blocks):
                out.append({
                    "id": f"{prop_id}_{i}",
                    "pos": [b["x"] * self.voxel_size, b["y"] * self.voxel_size, b["z"] * self.voxel_size],
                    "extent": [self.voxel_size / 2] * 3,
                    "material_id": _KIND_TO_MATERIAL_ID.get(b.get("kind", "cube"), 1),
                })
            return out
        except Exception:
            return None

    def _procedural_fallback(self, prop_id: str) -> Optional[List[Dict[str, Any]]]:
        import math
        if "fire_hydrant" not in prop_id:
            return None
        blocks: List[Dict[str, Any]] = []
        is_shat = "shattered" in prop_id
        for y_idx in range(4 if is_shat else 10):
            y = y_idx * 0.08
            for angle_deg in range(0, 360, 45):
                if is_shat and (y_idx + angle_deg) % 3 == 0:
                    continue
                rad = math.radians(angle_deg)
                blocks.append({"id": f"hyd_{len(blocks)}", "pos": [0.2 * math.cos(rad), y, 0.2 * math.sin(rad)], "extent": [0.04, 0.04, 0.04], "material_id": 5})
        return blocks

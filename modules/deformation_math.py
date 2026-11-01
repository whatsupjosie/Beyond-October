from __future__ import annotations
import math
import heapq
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

Vector3 = Tuple[float, float, float]

@dataclass
class ImpactEvent:
    contact_point: np.ndarray
    impact_normal: np.ndarray
    impulse_joules: float
    contact_radius: float = 0.05
    travel_direction: Optional[np.ndarray] = None

    @staticmethod
    def from_vectors(
        contact_point: Vector3, impact_normal: Vector3, impulse_joules: float,
        contact_radius: float = 0.05, travel_direction: Optional[Vector3] = None
    ) -> "ImpactEvent":
        return ImpactEvent(
            contact_point=np.array(contact_point, dtype=np.float64),
            impact_normal=np.array(impact_normal, dtype=np.float64),
            impulse_joules=float(impulse_joules),
            contact_radius=float(contact_radius),
            travel_direction=np.array(travel_direction, dtype=np.float64) if travel_direction is not None else None,
        )

@dataclass
class MaterialProfile:
    name: str = "aluminum"
    yield_strength_mpa: float = 120.0
    ultimate_strength_mpa: float = 240.0
    elastic_modulus_gpa: float = 69.0
    poisson_ratio: float = 0.33
    decay_constant: float = 25.0
    plastic_retention: float = 0.85

    @property
    def yield_strength_pa(self) -> float: return self.yield_strength_mpa * 1e6
    @property
    def ultimate_strength_pa(self) -> float: return self.ultimate_strength_mpa * 1e6
    @property
    def elastic_modulus_pa(self) -> float: return self.elastic_modulus_gpa * 1e9
    @property
    def shear_modulus_pa(self) -> float: return self.elastic_modulus_pa / (2.0 * (1.0 + self.poisson_ratio))

    @staticmethod
    def steel() -> "MaterialProfile":
        return MaterialProfile("steel", 250.0, 400.0, 200.0, 0.29, 30.0, 0.90)

    # --- FIX: this lookup was called from streaming_chain_resolver.py
    # (MaterialProfile.by_name(obj.material)) but never existed, which would
    # raise AttributeError on every single chain resolution. Implemented as a
    # small lazily-built registry so new materials can be added in one place.
    # `by_name` never raises on an unknown key (falls back to `default`) since
    # this is called deep in a hot per-impact path where a bad/missing scene
    # material string shouldn't crash the whole chain resolver. Use
    # `by_name(..., strict=True)` where you'd rather fail loudly (e.g. at
    # content-authoring / validation time).
    @staticmethod
    def by_name(name: Optional[str], default: str = "aluminum", strict: bool = False) -> "MaterialProfile":
        registry = _material_registry()
        key = (name or default).strip().lower().replace(" ", "_").replace("-", "_")
        if key in registry:
            return registry[key]
        if strict:
            raise KeyError(f"Unknown material profile '{name}'. Known: {sorted(registry)}")
        return registry[default]

    @staticmethod
    def known_materials() -> List[str]:
        return sorted(_material_registry())


_MATERIAL_REGISTRY: Optional[Dict[str, "MaterialProfile"]] = None

def _material_registry() -> Dict[str, "MaterialProfile"]:
    global _MATERIAL_REGISTRY
    if _MATERIAL_REGISTRY is None:
        _MATERIAL_REGISTRY = {
            "aluminum": MaterialProfile(),
            "steel": MaterialProfile.steel(),
            "cast_iron": MaterialProfile("cast_iron", 130.0, 200.0, 100.0, 0.28, 40.0, 0.55),
            "concrete": MaterialProfile("concrete", 3.0, 4.0, 30.0, 0.20, 65.0, 0.05),
            "wood": MaterialProfile("wood", 40.0, 55.0, 11.0, 0.35, 15.0, 0.30),
            "glass": MaterialProfile("glass", 33.0, 33.0, 70.0, 0.22, 90.0, 0.02),
            "plastic": MaterialProfile("plastic", 25.0, 40.0, 2.5, 0.40, 20.0, 0.60),
            # fire_hydrant / material_id=5 in pubworld_router's procedural prop generator
            "hydrant_iron": MaterialProfile("hydrant_iron", 140.0, 210.0, 100.0, 0.28, 35.0, 0.55),
        }
    return _MATERIAL_REGISTRY


@dataclass
class BlockDef:
    block_id: str
    position: List[float]
    extent: List[float]
    material_id: int = 1

    @staticmethod
    def from_dict(d: Dict[str, Any], fallback_index: Optional[int] = None) -> "BlockDef":
        bid = d.get("id", f"idx_{fallback_index}" if fallback_index is not None else f"idx_{id(d)}")
        return BlockDef(
            block_id=str(bid),
            position=list(d.get("pos", d.get("position", [0.0, 0.0, 0.0]))),
            extent=list(d.get("extent", d.get("extents", [0.05, 0.05, 0.05]))),
            material_id=int(d.get("material_id", 1))
        )

@dataclass
class BlockSet:
    block_ids: np.ndarray
    positions: np.ndarray
    extents: np.ndarray
    adjacency: List[List[Tuple[int, float]]] = field(default_factory=list)

    @staticmethod
    def from_block_defs(blocks: List[BlockDef]) -> "BlockSet":
        if not blocks:
            return BlockSet(np.empty(0, dtype=str), np.empty((0, 3), dtype=np.float64), np.empty((0, 3), dtype=np.float64), [])
        
        positions = np.array([b.position for b in blocks], dtype=np.float64)
        extents = np.array([b.extent for b in blocks], dtype=np.float64)
        n = len(blocks)
        adj: List[List[Tuple[int, float]]] = [[] for _ in range(n)]
        
        # O(N) Spatial Hash for adjacency to prevent loop lockups
        cell_size = float(np.max(extents) * 3.0)
        if cell_size <= 0.0: cell_size = 0.15
        inv_cell = 1.0 / cell_size
        grid: Dict[Tuple[int, int, int], List[int]] = {}
        
        for i in range(n):
            c = (int(positions[i,0] * inv_cell), int(positions[i,1] * inv_cell), int(positions[i,2] * inv_cell))
            grid.setdefault(c, []).append(i)
            
        for i in range(n):
            pi, ei = positions[i], extents[i]
            c = (int(pi[0] * inv_cell), int(pi[1] * inv_cell), int(pi[2] * inv_cell))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        neighbor_cell = (c[0]+dx, c[1]+dy, c[2]+dz)
                        if neighbor_cell not in grid: continue
                        for j in grid[neighbor_cell]:
                            if i >= j: continue
                            pj, ej = positions[j], extents[j]
                            delta = np.abs(pi - pj)
                            if np.all(delta <= (ei + ej) * 0.65):
                                dist = float(np.linalg.norm(pi - pj))
                                adj[i].append((j, max(dist, 1e-4)))
                                adj[j].append((i, max(dist, 1e-4)))

        return BlockSet(np.array([b.block_id for b in blocks], dtype=str), positions, extents, adj)

@dataclass
class DeformationEstimate:
    impact_event: ImpactEvent
    pristine_blocks: List[BlockDef]
    affected_blocks: List[str]
    strain_vectors: Dict[str, np.ndarray]
    severity_score: float
    predicted_state: str
    confidence: float
    _stress_field: Optional[np.ndarray] = field(default=None, repr=False)
    _fractured_ids: List[str] = field(default_factory=list, repr=False)

    @property
    def affected_block_count(self) -> int: return len(self.affected_blocks)
    @property
    def fractured_block_count(self) -> int: return len(self._fractured_ids)
    @property
    def total_energy_joules(self) -> float: return self.impact_event.impulse_joules
    @property
    def material(self) -> str: return "structural_material"
    def summary(self) -> Dict[str, Any]:
        return {"severity_score": round(self.severity_score, 3), "predicted_state": self.predicted_state, "confidence": round(self.confidence, 3), "affected": self.affected_block_count, "fractured": self.fractured_block_count, "energy_j": self.impact_event.impulse_joules, "severity": "shattered" if self.severity_score >= 0.8 else "intact"}

class DeformationEstimator:
    def predict(self, impact: ImpactEvent, block_set: BlockSet, material: MaterialProfile, pristine_blocks: Optional[List[BlockDef]] = None, physics_mode: str = "realistic") -> DeformationEstimate:
        positions = block_set.positions
        n_blocks = positions.shape[0]
        ids = [str(bid) for bid in block_set.block_ids]
        blocks = pristine_blocks or []

        if n_blocks == 0:
            return DeformationEstimate(impact, blocks, [], {}, 0.0, "intact", 1.0)

        direct_distances = np.linalg.norm(positions - impact.contact_point, axis=1)
        seed_indices = np.where(direct_distances <= max(impact.contact_radius * 1.5, 0.05))[0]
        if len(seed_indices) == 0: seed_indices = np.array([np.argmin(direct_distances)])

        # Graph-Geodesic Distance Routing
        geodesic_dist = np.full(n_blocks, float("inf"), dtype=np.float64)
        pq: List[Tuple[float, int]] = []
        for s_idx in seed_indices:
            init_d = direct_distances[s_idx]
            geodesic_dist[s_idx] = init_d
            heapq.heappush(pq, (init_d, int(s_idx)))

        while pq:
            d_curr, u = heapq.heappop(pq)
            if d_curr > geodesic_dist[u]: continue
            if u < len(block_set.adjacency):
                for v, weight in block_set.adjacency[u]:
                    if d_curr + weight < geodesic_dist[v]:
                        geodesic_dist[v] = d_curr + weight
                        heapq.heappush(pq, (d_curr + weight, v))

        unconnected = np.isinf(geodesic_dist)
        geodesic_dist[unconnected] = direct_distances[unconnected] * 2.0

        contact_area_m2 = max(math.pi * (impact.contact_radius ** 2), 1e-6)
        effective_depth = max(impact.contact_radius * 2.0, 0.05)
        base_stress_pa = impact.impulse_joules / (contact_area_m2 * effective_depth)
        
        # Explicit float casting for array decay safety
        effective_decay = float(material.decay_constant)
        stress_field_pa = base_stress_pa * np.exp(-effective_decay * geodesic_dist)

        norm_mag = float(np.linalg.norm(impact.impact_normal))
        normal = impact.impact_normal / (norm_mag + 1e-9)
        
        if impact.travel_direction is not None:
            travel = impact.travel_direction / (float(np.linalg.norm(impact.travel_direction)) + 1e-9)
            shear_dir = travel - np.dot(travel, normal) * normal
            shear_mag = float(np.linalg.norm(shear_dir))
            shear_dir = shear_dir / shear_mag if shear_mag > 1e-6 else np.zeros(3)
        else:
            shear_dir, travel = np.zeros(3), normal

        normal_strain = stress_field_pa / material.elastic_modulus_pa
        shear_strain = stress_field_pa / material.shear_modulus_pa
        total_disp = np.outer(normal_strain * geodesic_dist * material.plastic_retention, -normal) + np.outer(shear_strain * geodesic_dist * material.plastic_retention * 0.4, shear_dir)

        plastic_mask = stress_field_pa >= material.yield_strength_pa
        fracture_mask = stress_field_pa >= material.ultimate_strength_pa
        displacements = np.zeros((n_blocks, 3), dtype=np.float64)
        displacements[plastic_mask] = total_disp[plastic_mask]

        affected_ids = [ids[i] for i in range(n_blocks) if plastic_mask[i]]
        fractured_ids = [ids[i] for i in range(n_blocks) if fracture_mask[i]]
        strain_vectors = {ids[i]: displacements[i].copy() for i in range(n_blocks) if plastic_mask[i]}

        transfer_eff = 1.0 if physics_mode == "freeplay" else 0.3 + 0.7 * float(abs(np.dot(normal, travel)))
        resilience_pa = (material.yield_strength_pa ** 2) / (2.0 * material.elastic_modulus_pa)
        capacity_j = max(resilience_pa * (contact_area_m2 * effective_depth), 1.0)
        
        raw_sev = (min(impact.impulse_joules, material.ultimate_strength_pa * contact_area_m2 * effective_depth) if physics_mode != "freeplay" else impact.impulse_joules) * transfer_eff / capacity_j
        sev_score = float(np.clip(raw_sev / (raw_sev + 1.0), 0.0, 1.0))

        shattered_thresh = float(np.clip(0.20 + 0.60 * (1.0 - (material.yield_strength_pa / material.ultimate_strength_pa)), 0.25, 0.75))
        f_ratio = len(fractured_ids) / max(len(affected_ids), 1)
        
        if sev_score >= shattered_thresh or f_ratio > 0.30: p_state = "shattered"
        elif sev_score >= 0.20 or len(affected_ids) > 0: p_state = "cracked"
        else: p_state = "intact"

        conf = float(np.clip((1.0 - abs(sev_score - 0.5) * 0.2) * min(1.0, n_blocks / 12.0), 0.4, 1.0))

        return DeformationEstimate(impact, blocks, affected_ids, strain_vectors, sev_score, p_state, conf, stress_field_pa, fractured_ids)

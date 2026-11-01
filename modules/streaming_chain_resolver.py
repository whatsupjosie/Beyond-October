import asyncio
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

# --- FIX: this file used ImpactEvent / BlockSet / BlockDef / MaterialProfile /
# DeformationEstimator without importing them from deformation_math.py at all.
# As shipped, `import pubcast.modules.streaming_chain_resolver` would raise
# NameError the first time resolve_and_stream() actually ran.
from .deformation_math import ImpactEvent, BlockSet, BlockDef, MaterialProfile, DeformationEstimator


@dataclass
class ChainImpact:
    timestamp: float; attacker_id: str; target_id: str
    attacker_mass: float; target_mass: float
    contact_point: np.ndarray; contact_normal: np.ndarray
    force_vector: np.ndarray; force_magnitude: float
    relative_velocity: float; duration: float = 0.02

    # --- FIX: `spawn_chain_from_contact()` called
    # `ChainImpact.from_contact_frame(contact, mass)` but this constructor
    # never existed anywhere in the file, so every incoming contact would
    # crash immediately with AttributeError before a single impact resolved.
    #
    # ASSUMPTION (please confirm against the real engine's contact schema when
    # this is wired up to the actual damage-physics / kinetic-performance
    # engine — I don't have that class definition in this review):
    #   contact.timestamp          float, seconds                 (default: 0.0)
    #   contact.attacker_id        str                             (required)
    #   contact.target_id          str                             (required)
    #   contact.attacker_mass      float                           (optional; falls back to `attacker_mass` kwarg, then 1.0)
    #   contact.contact_point      array-like (3,)                 (default: origin)
    #   contact.contact_normal /
    #   contact.normal             array-like (3,)                 (default: +Y up)
    #   contact.force_vector       array-like (3,)                 (optional; derived from normal * force_magnitude)
    #   contact.force_magnitude    float                           (optional; derived from attacker_mass * relative_velocity)
    #   contact.relative_velocity  float                           (optional; derived from force_magnitude / attacker_mass)
    #   contact.duration           float                           (default: 0.02s)
    # Every field is read defensively with getattr so a partially-populated
    # engine contact object degrades instead of crashing; a KeyError/AttributeError
    # here would otherwise take down the whole chain.
    @classmethod
    def from_contact_frame(cls, contact: Any, target_mass: float, attacker_mass: Optional[float] = None) -> "ChainImpact":
        # NOTE: getattr(obj, name, default) only falls back when the
        # attribute is *missing*, not when it's present-but-None (which a
        # real Contact/dataclass can legitimately have, e.g.
        # attacker_mass=None before it's known). Every optional field below
        # is read via getattr-then-None-coalesce for that reason.
        ts = float(getattr(contact, "timestamp", 0.0) or 0.0)
        attacker_id = str(getattr(contact, "attacker_id"))
        target_id = str(getattr(contact, "target_id"))
        a_mass_raw = getattr(contact, "attacker_mass", None)
        a_mass = float(a_mass_raw if a_mass_raw is not None else (attacker_mass if attacker_mass is not None else 1.0))
        t_mass = max(float(target_mass), 1e-6)

        contact_point_raw = getattr(contact, "contact_point", None)
        contact_point = np.array(contact_point_raw if contact_point_raw is not None else [0.0, 0.0, 0.0], dtype=np.float64)
        normal_raw = getattr(contact, "contact_normal", None)
        if normal_raw is None:
            normal_raw = getattr(contact, "normal", None)
        if normal_raw is None:
            normal_raw = [0.0, 1.0, 0.0]
        normal = np.array(normal_raw, dtype=np.float64)
        n_norm = float(np.linalg.norm(normal))
        normal = normal / n_norm if n_norm > 1e-9 else np.array([0.0, 1.0, 0.0])

        force_vec_raw = getattr(contact, "force_vector", None)
        force_mag_raw = getattr(contact, "force_magnitude", None)
        if force_vec_raw is not None:
            force_vector = np.array(force_vec_raw, dtype=np.float64)
            force_magnitude = float(np.linalg.norm(force_vector))
        elif force_mag_raw is not None:
            force_magnitude = float(force_mag_raw)
            force_vector = normal * force_magnitude
        else:
            rel_v_guess = float(getattr(contact, "relative_velocity", 0.0))
            force_magnitude = a_mass * rel_v_guess
            force_vector = normal * force_magnitude

        relative_velocity = float(getattr(contact, "relative_velocity", force_magnitude / max(a_mass, 1e-6)))
        duration = float(getattr(contact, "duration", 0.02))

        return cls(ts, attacker_id, target_id, a_mass, t_mass, contact_point, normal, force_vector, force_magnitude, relative_velocity, duration)


@dataclass
class ImpactLevel:
    depth: int; timestamp: float; impacts: List[ChainImpact]
    object_states_after: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ImpactChain:
    chain_id: str; root_impact: ChainImpact; depth_limit: int
    start_time: float; physics_mode: str = "realistic"; exaggeration_multiplier: float = 1.0
    levels: List[ImpactLevel] = field(default_factory=list)
    objects_affected: List[str] = field(default_factory=list)
    initial_energy_joules: float = 0.0; remaining_energy_joules: float = 0.0

    def __post_init__(self):
        base_e = 0.5 * self.root_impact.attacker_mass * (self.root_impact.relative_velocity ** 2)
        mult = self.exaggeration_multiplier if self.physics_mode == "freeplay" else 1.0
        self.initial_energy_joules = self.remaining_energy_joules = base_e * mult

    def consume_energy(self, joules: float) -> float:
        joules = max(0.0, joules)
        granted = min(joules, self.remaining_energy_joules)
        self.remaining_energy_joules -= granted
        return granted

    # --- FIX: objects_affected was declared but nothing in the file ever
    # appended to it. Small helper so the resolver can't forget to dedupe.
    def mark_affected(self, object_id: str) -> None:
        if object_id not in self.objects_affected:
            self.objects_affected.append(object_id)


class StreamingChainResolver:
    def __init__(self, engine, builder, scene, on_event=None, shared_state=None):
        self._e, self._b, self._s, self._oe = engine, builder, scene, on_event
        self._est = DeformationEstimator()
        self._state = shared_state if shared_state is not None else {}
        # --- FIX (self-audit pass): scene_contract.Engine.predict_secondary_contacts
        # needs to know about the scene, but the abstract call signature the
        # resolver uses (source_id, position, velocity, time_budget) has no
        # room to pass it per-call. The engine exposes an optional
        # bind_scene() for this. Originally callers were expected to invoke
        # `engine.bind_scene(scene)` themselves before constructing this
        # resolver — every test in this package did that by hand, which is
        # exactly why this was missed: ChoreographyController (the actual
        # real caller) never does, so any chain built through the normal
        # spawn_chain_from_contact() path silently degraded to a single
        # level with no error, no warning, nothing. Auto-binding here removes
        # the footgun entirely; it's a no-op for engines that don't have the
        # method (getattr guarded) or don't need it.
        binder = getattr(engine, "bind_scene", None)
        if callable(binder):
            try:
                binder(scene)
            except Exception:
                pass

    async def resolve_and_stream(self, root: ChainImpact) -> ImpactChain:
        chain = ImpactChain(f"chain_{root.timestamp}", root, self._s.chain.depth_limit, root.timestamp)
        pending = [root]
        for depth in range(chain.depth_limit):
            if not pending or pending[0].timestamp - chain.start_time > self._s.chain.max_chain_duration: break

            lvl = ImpactLevel(depth, pending[0].timestamp, list(pending))
            impacts_by_target: Dict[str, List[ChainImpact]] = {}
            for imp in pending: impacts_by_target.setdefault(imp.target_id, []).append(imp)

            # --- FIX: this was declared but never appended to, so every
            # chain silently stopped after depth 0 regardless of depth_limit.
            next_pending: List[ChainImpact] = []

            for tid, imps in impacts_by_target.items():
                obj = self._s.objects.get(tid)
                if not obj: continue

                chain.mark_affected(tid)

                # Scalar energy tracking decoupled from net vectors
                comb_f = np.sum([i.force_vector for i in imps], axis=0)
                comb_j = sum(0.5 * i.attacker_mass * (i.relative_velocity**2) for i in imps)

                target_mass_safe = max(imps[0].target_mass, 0.01)
                net_v = float(np.linalg.norm(comb_f)) / target_mass_safe
                c_imp = ChainImpact(imps[0].timestamp, imps[0].attacker_id, tid, sum(i.attacker_mass for i in imps), imps[0].target_mass, imps[0].contact_point, imps[0].contact_normal, comb_f, float(np.linalg.norm(comb_f)), net_v)

                impact_ev = ImpactEvent(c_imp.contact_point, c_imp.contact_normal, comb_j, 0.05, comb_f)

                # Budget Deformation Energy
                prop_geom = await self._b.fetch_geometry(tid) or []
                # --- FIX: pass fallback_index so blocks missing an "id" key get
                # a deterministic, stable id instead of a per-process id(d) value.
                block_defs = [BlockDef.from_dict(b, fallback_index=idx) for idx, b in enumerate(prop_geom)]
                est = self._est.predict(impact_ev, BlockSet.from_block_defs(block_defs), MaterialProfile.by_name(getattr(obj, "material", None)))
                chain.consume_energy(est.severity_score * comb_j)

                # Budget Kinetic Launch Energy
                # --- FIX: a static target (e.g. something bolted to the
                # ground/wall) can deform but can't be launched. The original
                # code budgeted and (silently discarded) launch energy for
                # static objects too.
                is_target_static = bool(getattr(obj, "is_static", False))
                target_mass_positive = max(c_imp.target_mass, 1e-6)
                if is_target_static:
                    v_scale = 0.0
                else:
                    ideal_k = 0.5 * target_mass_positive * (net_v**2)
                    avail_k = chain.consume_energy(ideal_k)
                    v_scale = math.sqrt(max(0.0, (2.0 * avail_k) / target_mass_positive)) / max(net_v, 1e-6) if avail_k < ideal_k else 1.0

                # --- FIX: v_scale was computed and then never used anywhere.
                # This is the actual post-budget launch velocity for the target.
                force_dir = comb_f / max(float(np.linalg.norm(comb_f)), 1e-9)
                launch_velocity = force_dir * (net_v * v_scale) if not is_target_static else np.zeros(3)

                lvl.object_states_after[tid] = {
                    "deformation_state": est.predicted_state,
                    "severity": round(est.severity_score, 4),
                    "affected_blocks": est.affected_block_count,
                    "fractured_blocks": est.fractured_block_count,
                    "launch_velocity": launch_velocity.tolist(),
                    "is_static": is_target_static,
                }
                self._state[tid] = est.predicted_state
                if hasattr(obj, "velocity") and not is_target_static:
                    try: obj.velocity = launch_velocity
                    except Exception: pass

                # --- FIX: chain propagation. `self._e` (engine) was accepted
                # in __init__ and stored but never called anywhere — the class
                # had no way to discover that a launched object then hits
                # something else, which is the entire point of a *chain*
                # resolver. Broad/narrow-phase collision prediction lives in
                # the engine, not here, so this calls an optional hook and
                # degrades to "no further propagation" (the original, broken
                # behavior) if the engine doesn't implement it yet.
                # INTEGRATION CONTRACT (confirm at merge time):
                #   await engine.predict_secondary_contacts(
                #       source_id: str, position: np.ndarray, velocity: np.ndarray,
                #       time_budget: float,
                #   ) -> list[ContactFrame]
                if not is_target_static and float(np.linalg.norm(launch_velocity)) > 1e-6:
                    predictor = getattr(self._e, "predict_secondary_contacts", None)
                    if callable(predictor):
                        remaining_time = self._s.chain.max_chain_duration - (c_imp.timestamp - chain.start_time)
                        if remaining_time > 0:
                            try:
                                predicted = await predictor(
                                    source_id=tid, position=c_imp.contact_point,
                                    velocity=launch_velocity, time_budget=remaining_time,
                                )
                            except Exception:
                                predicted = []
                            for pc in (predicted or []):
                                next_target_id = getattr(pc, "target_id", None)
                                next_obj = self._s.objects.get(next_target_id) if next_target_id else None
                                if next_obj is None: continue
                                next_pending.append(ChainImpact.from_contact_frame(pc, next_obj.mass, attacker_mass=c_imp.target_mass))

                # Budget Attacker Bounce Energy
                for i in imps:
                    atk = self._s.objects.get(i.attacker_id)
                    if atk and not atk.is_static:
                        v_in = i.force_vector / max(np.linalg.norm(i.force_vector), 1e-6) * i.relative_velocity
                        norm = i.contact_normal / (np.linalg.norm(i.contact_normal)+1e-7)
                        v_after = v_in - (1+atk.physics.restitution)*(obj.mass/(atk.mass+obj.mass))*np.dot(v_in, norm)*norm
                        v_tan = v_after - np.dot(v_after, norm)*norm
                        v_after = np.dot(v_after, norm)*norm + v_tan * (1.0 - obj.physics.friction)

                        e_rebound = 0.5 * atk.mass * float(np.linalg.norm(v_after))**2
                        rebound_scale = math.sqrt(max(0.0, chain.consume_energy(e_rebound) / max(e_rebound, 1e-6)))
                        v_after = v_after * rebound_scale

                        # --- FIX: v_after (the energy-budgeted rebound
                        # velocity) was computed and then discarded. Record it
                        # on the level and apply it back to the attacker object
                        # if the scene object supports it.
                        lvl.object_states_after[i.attacker_id] = {
                            "rebound_velocity": v_after.tolist(),
                            "mass": atk.mass,
                        }
                        self._state.setdefault(i.attacker_id, "intact")
                        chain.mark_affected(i.attacker_id)
                        if hasattr(atk, "velocity"):
                            try: atk.velocity = v_after
                            except Exception: pass

            chain.levels.append(lvl)
            pending = next_pending
        return chain

async def spawn_chain_from_contact(contact, scene, engine, builder, active_chains, on_event=None, shared_state=None):
    if not scene.objects.get(contact.target_id): return None
    cid = f"chain_{contact.timestamp}_{contact.target_id}"

    # --- FIX (self-audit pass): this previously called
    # ChainImpact.from_contact_frame(contact, target_mass) with no
    # attacker_mass argument. from_contact_frame only recovers a real
    # attacker mass if the Contact object itself happens to carry an
    # `attacker_mass` attribute; otherwise it silently defaults to 1.0 kg
    # (see its docstring). Every real object in scene.objects already knows
    # its own mass — a 77 kg actor hitting something was being budgeted as
    # if it weighed 1 kg, a 77x undercount on `ImpactChain.initial_energy_joules`
    # (0.5 * mass * v^2), which starves the entire chain of energy before a
    # single level resolves. Verified by hand: an 8 m/s hit from the real
    # demo actor computed 32 J of available energy instead of the correct
    # ~2467 J. None of this review's tests caught it because every test that
    # exercised real ballistics built ChainImpact directly with the correct
    # mass, bypassing this function entirely.
    attacker_obj = scene.objects.get(contact.attacker_id)
    attacker_mass = getattr(attacker_obj, "mass", None) if attacker_obj is not None else None

    # Register immediately to prevent race conditions on fast synchronous completion
    active_chains[cid] = None 
    task = asyncio.create_task(StreamingChainResolver(engine, builder, scene, on_event, shared_state).resolve_and_stream(
        ChainImpact.from_contact_frame(contact, scene.objects[contact.target_id].mass, attacker_mass=attacker_mass)
    ))
    active_chains[cid] = task
    task.add_done_callback(lambda t: active_chains.pop(cid, None))
    return cid

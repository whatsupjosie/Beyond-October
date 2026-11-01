"""PubCast Affect Dynamics — temporal emotional-performance continuity.

This module sits *after* AffectContextEngine appraisal and *before* expressive
consumers.  It never decides what a person feels, never owns conversation or
camera policy, and never mutates the upstream appraisal.  Its job is temporal:
turn a sequence of evidence-backed affect/performance readings into a stable,
inspectable trajectory suitable for voice, choreography and directing advice.

Design invariants
-----------------
* Time evolves supported state; time never creates evidence.
* Internal pressure and displayed expression are distinct.
* Bracing is a continuous uncertainty/orienting process, not an emotion label.
* New evidence retargets from the current state; it never resets the actor.
* Suppression can reduce display while increasing contained load/strain.
* All outputs are advisory evidence.  Downstream authorities retain authority.
* The engine is deterministic when supplied an injected monotonic clock.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import time
from typing import Any, Callable, Dict, Mapping, Optional


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return lo
    if not math.isfinite(value):
        return lo
    return max(lo, min(hi, value))


def _unit_z(value: Any, span: float = 2.5) -> float:
    """Map a signed z-like value to [0,1] magnitude without hard discontinuity."""
    try:
        x = abs(float(value))
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(x):
        return 0.0
    return _clamp(x / max(0.001, span))


def _approach(current: float, target: float, dt: float, tau: float) -> float:
    """Continuous exponential approach; stable across variable tick intervals."""
    if dt <= 0.0:
        return current
    if tau <= 0.0:
        return target
    alpha = 1.0 - math.exp(-dt / tau)
    return current + (target - current) * alpha


@dataclass(frozen=True)
class AffectDynamicsProfile:
    """Personality-level dynamics.  Values are tendencies, never diagnoses."""
    rupture_sensitivity: float = 0.58
    ambiguity_tolerance: float = 0.58
    emotional_openness: float = 0.62
    baseline_regulatory_capacity: float = 0.72
    suppression_tendency: float = 0.32
    leakage_sensitivity: float = 0.22
    recovery_rate: float = 0.55
    inquiry_bias: float = 0.58
    silence_tolerance: float = 0.55
    self_monitoring: float = 0.58
    other_monitoring: float = 0.70
    room_monitoring: float = 0.55
    internal_attack_sec: float = 7.0
    internal_release_sec: float = 22.0
    expressive_attack_sec: float = 10.0
    expressive_release_sec: float = 28.0
    orienting_attack_sec: float = 0.45
    bracing_attack_sec: float = 1.2
    bracing_release_sec: float = 6.0

    def __post_init__(self) -> None:
        unit = (
            "rupture_sensitivity", "ambiguity_tolerance", "emotional_openness",
            "baseline_regulatory_capacity", "suppression_tendency",
            "leakage_sensitivity", "recovery_rate", "inquiry_bias",
            "silence_tolerance", "self_monitoring", "other_monitoring",
            "room_monitoring",
        )
        for name in unit:
            object.__setattr__(self, name, _clamp(getattr(self, name)))
        for name in (
            "internal_attack_sec", "internal_release_sec", "expressive_attack_sec",
            "expressive_release_sec", "orienting_attack_sec", "bracing_attack_sec",
            "bracing_release_sec",
        ):
            object.__setattr__(self, name, max(0.05, float(getattr(self, name))))


@dataclass(frozen=True)
class AffectEvidence:
    """Normalized, provenance-bearing observation from AffectContextEngine."""
    event_id: str
    timestamp: float
    confidence: float
    baseline_quality: float
    state: str
    arousal: float
    valence: float
    load: float
    tension: float
    dramatic_intensity: float
    stakes: float
    novelty: float
    revision: bool = False

    @classmethod
    def from_affect_payload(cls, payload: Mapping[str, Any]) -> "AffectEvidence":
        reading = payload.get("reading") or {}
        affect = payload.get("affect") or {}
        perf = payload.get("performance") or {}
        context = payload.get("context") or {}
        baseline = payload.get("baseline") or {}
        antecedent = payload.get("antecedent") or {}
        return cls(
            event_id=str(payload.get("turn_id") or "unknown"),
            timestamp=float(payload.get("ts") or time.time()),
            confidence=_clamp(reading.get("confidence", 0.0)),
            baseline_quality=_clamp(baseline.get("quality", 0.0)),
            state=str(reading.get("state") or "observing"),
            arousal=float(affect.get("arousal_z", 0.0) or 0.0),
            valence=float(affect.get("valence_z", 0.0) or 0.0),
            load=float(affect.get("load_z", 0.0) or 0.0),
            tension=_clamp(perf.get("tension", 0.0)),
            dramatic_intensity=_clamp(perf.get("dramatic_intensity", 0.0)),
            stakes=_clamp(context.get("stakes", 0.0)),
            novelty=_clamp(context.get("novelty", 0.0)),
            revision=bool(antecedent.get("revision")),
        )


@dataclass
class AffectDynamicsState:
    # Evidence grounding / uncertainty
    grounding: float = 0.0
    uncertainty: float = 1.0
    orienting: float = 0.0
    bracing: float = 0.0
    assimilation: float = 1.0

    # Internal trajectory
    internal_arousal: float = 0.0
    internal_valence: float = 0.0
    internal_load: float = 0.0
    affective_pressure: float = 0.0

    # Regulation
    regulatory_capacity: float = 0.72
    regulatory_load: float = 0.0
    contained_load: float = 0.0
    accumulated_strain: float = 0.0
    suppression_effort: float = 0.0
    leakage: float = 0.0

    # Display trajectory
    displayed_intensity: float = 0.0
    expressive_instability: float = 0.0
    residual_affect: float = 0.0

    # Current supported targets (not claims of new evidence)
    target_arousal: float = 0.0
    target_valence: float = 0.0
    target_load: float = 0.0
    target_pressure: float = 0.0
    target_display: float = 0.0

    last_state: str = "observing"
    last_event_id: Optional[str] = None
    last_evidence_at: Optional[float] = None
    updated_at: Optional[float] = None


@dataclass(frozen=True)
class AffectDynamicsOutput:
    schema: str
    event_id: Optional[str]
    state: str
    grounding: float
    uncertainty: float
    orienting: float
    bracing: float
    assimilation: float
    internal: Dict[str, float]
    regulation: Dict[str, float]
    display: Dict[str, float]
    conversation_signals: Dict[str, float]
    director_signals: Dict[str, float | bool]
    choreography_signals: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AffectDynamics:
    """Stateful temporal processor for one AI/performer/session relationship."""

    SCHEMA = "pubcast.affect.dynamics.v1"

    def __init__(
        self,
        profile: Optional[AffectDynamicsProfile] = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.profile = profile or AffectDynamicsProfile()
        self.state = AffectDynamicsState(
            regulatory_capacity=self.profile.baseline_regulatory_capacity
        )
        self._clock = clock
        self._previous_evidence: Optional[AffectEvidence] = None

    def observe_payload(self, payload: Mapping[str, Any]) -> AffectDynamicsOutput:
        return self.observe(AffectEvidence.from_affect_payload(payload))


    def observe_judgment(self, judgment: Mapping[str, Any]) -> AffectDynamicsOutput:
        """Advance dynamics from a canonical System Alex judgment.

        This is the authoritative runtime seam.  Affect Dynamics consumes the
        adjudicated dimensions and confidence; it does not re-read competing raw
        evidence and therefore cannot bypass System Alex.
        """
        dims = dict(judgment.get("dimensions") or {})
        conf = dict(judgment.get("confidence") or {})
        if not dims:
            return self.output()
        supported = [float(conf.get(k, 0.0) or 0.0) for k in dims]
        grounding = sum(supported) / len(supported) if supported else 0.0
        evidence = AffectEvidence(
            event_id=str(judgment.get("event_id") or "system-alex"),
            timestamp=float(judgment.get("generated_at") or time.time()),
            confidence=_clamp(grounding), baseline_quality=1.0,
            state="adjudicated",
            arousal=float(dims.get("arousal", 0.0) or 0.0) * 2.5,
            valence=float(dims.get("valence", 0.0) or 0.0) * 2.5,
            load=float(dims.get("load", 0.0) or 0.0) * 2.5,
            tension=_clamp(dims.get("tension", 0.0)),
            dramatic_intensity=_clamp(dims.get("dramatic_intensity", 0.0)),
            stakes=_clamp(dims.get("stakes", 0.0)),
            novelty=_clamp(dims.get("novelty", 0.0)),
            revision=any(float(v or 0.0) >= 0.45 for v in (judgment.get("disagreement") or {}).values()),
        )
        return self.observe(evidence)

    def observe(self, evidence: AffectEvidence) -> AffectDynamicsOutput:
        """Apply new evidence, then advance to the observation instant."""
        now = self._clock()
        self._advance(now)
        s, p = self.state, self.profile

        trust = min(evidence.confidence, evidence.baseline_quality)
        previous = self._previous_evidence

        # Expectation rupture is evidence-derived, not an invented emotion.
        # It combines actual between-reading movement with novelty/stakes and
        # explicit upstream revision.  Low-trust readings cannot create a large
        # rupture on their own.
        if previous is None:
            delta = 0.0
        else:
            delta = (
                _unit_z(evidence.arousal - previous.arousal)
                + _unit_z(evidence.valence - previous.valence)
                + _unit_z(evidence.load - previous.load)
                + abs(evidence.tension - previous.tension)
            ) / 4.0
        rupture = _clamp(
            trust * (
                0.42 * delta
                + 0.28 * evidence.novelty
                + 0.20 * evidence.stakes
                + 0.10 * float(evidence.revision)
            ) * (0.65 + 0.70 * p.rupture_sensitivity)
        )

        s.grounding = trust
        s.uncertainty = 1.0 - trust
        s.last_event_id = evidence.event_id
        s.last_evidence_at = now

        # Orienting is fast. Bracing additionally requires uncertainty or stakes.
        orient_target = rupture
        brace_need = rupture * max(s.uncertainty, evidence.stakes * 0.72)
        s.orienting = max(s.orienting, orient_target)
        s.bracing = max(s.bracing, _clamp(brace_need * (1.25 - 0.5 * p.ambiguity_tolerance)))

        # New consequential evidence resets only the *degree of assimilation*;
        # it never clears the actor's existing state.
        assimilation_drop = rupture * (0.45 + 0.45 * evidence.stakes)
        s.assimilation = min(s.assimilation, 1.0 - assimilation_drop)

        s.target_arousal = evidence.arousal
        s.target_valence = evidence.valence
        s.target_load = evidence.load
        s.target_pressure = _clamp(
            0.36 * evidence.dramatic_intensity
            + 0.30 * evidence.tension
            + 0.20 * evidence.stakes
            + 0.14 * _unit_z(evidence.arousal)
        )

        # Expression is evidence-backed pressure filtered through openness and
        # current grounding. Bracing intentionally restrains premature display.
        s.target_display = _clamp(
            s.target_pressure
            * (0.35 + 0.65 * p.emotional_openness)
            * (0.45 + 0.55 * trust)
            * (1.0 - 0.45 * s.bracing)
        )

        s.last_state = evidence.state
        self._previous_evidence = evidence
        return self.output()

    def tick(self, now: Optional[float] = None) -> AffectDynamicsOutput:
        """Advance supported state. No evidence fields are changed by time."""
        self._advance(self._clock() if now is None else float(now))
        return self.output()

    def _advance(self, now: float) -> None:
        s, p = self.state, self.profile
        if s.updated_at is None:
            s.updated_at = now
            return
        dt = max(0.0, now - s.updated_at)
        s.updated_at = now
        if dt == 0.0:
            return

        # Fast orienting decays quickly; bracing releases more slowly. Neither
        # decay increases grounding: elapsed time is not evidence.
        s.orienting = _approach(s.orienting, 0.0, dt, 1.8)
        brace_tau = p.bracing_release_sec if s.bracing > 0.0 else p.bracing_attack_sec
        s.bracing = _approach(s.bracing, 0.0, dt, brace_tau)

        # Assimilation is allowed to progress only to the degree the reading is
        # grounded. Uncertain material can remain unresolved indefinitely.
        assimilation_ceiling = _clamp(0.20 + 0.80 * s.grounding)
        s.assimilation = _approach(s.assimilation, assimilation_ceiling, dt, 18.0)

        # Internal affect follows supported targets continuously. Signed axes use
        # asymmetric attack/release based on movement magnitude, not label flips.
        for attr, target in (
            ("internal_arousal", s.target_arousal),
            ("internal_valence", s.target_valence),
            ("internal_load", s.target_load),
        ):
            current = getattr(s, attr)
            rising = abs(target) > abs(current)
            tau = p.internal_attack_sec if rising else p.internal_release_sec
            setattr(s, attr, _approach(current, target, dt, tau))

        pressure_tau = p.internal_attack_sec if s.target_pressure > s.affective_pressure else p.internal_release_sec
        s.affective_pressure = _clamp(_approach(s.affective_pressure, s.target_pressure, dt, pressure_tau))

        # Capacity is a resource. Strain temporarily reduces it; recovery restores
        # it toward the personality baseline without erasing contained affect.
        capacity_target = _clamp(
            p.baseline_regulatory_capacity
            - 0.38 * s.accumulated_strain
            - 0.16 * s.internal_load / 2.5
        )
        s.regulatory_capacity = _clamp(_approach(
            s.regulatory_capacity, capacity_target, dt, 10.0 / max(0.15, p.recovery_rate)
        ))

        demand = _clamp(s.affective_pressure * (0.55 + 0.45 * p.suppression_tendency))
        s.regulatory_load = _clamp(_approach(s.regulatory_load, demand, dt, 3.5))
        s.suppression_effort = _clamp(min(s.regulatory_load, s.regulatory_capacity) * p.suppression_tendency)

        overflow = max(0.0, s.regulatory_load - s.regulatory_capacity)
        s.leakage = _clamp(overflow * (0.45 + p.leakage_sensitivity))

        # Successful suppression contains load rather than magically deleting it.
        contained_target = _clamp(s.affective_pressure * s.suppression_effort)
        s.contained_load = _clamp(_approach(s.contained_load, contained_target, dt, 5.0))
        strain_target = _clamp(0.65 * s.contained_load + 0.35 * overflow)
        strain_tau = 7.0 if strain_target > s.accumulated_strain else 45.0 / max(0.15, p.recovery_rate)
        s.accumulated_strain = _clamp(_approach(s.accumulated_strain, strain_target, dt, strain_tau))

        # Display combines deliberate openness with involuntary leakage.  A drop
        # in suppression can release contained load (suppression rebound).
        rebound = _clamp(s.contained_load * max(0.0, 0.55 - s.suppression_effort))
        display_target = _clamp(
            s.target_display * (1.0 - 0.62 * s.suppression_effort)
            + 0.55 * s.leakage
            + 0.28 * rebound
        )
        old_display = s.displayed_intensity
        tau = p.expressive_attack_sec if display_target > old_display else p.expressive_release_sec
        s.displayed_intensity = _clamp(_approach(old_display, display_target, dt, tau))
        velocity = abs(s.displayed_intensity - old_display) / max(dt, 1e-6)
        s.expressive_instability = _clamp(_approach(s.expressive_instability, min(1.0, velocity * 8.0), dt, 2.0))

        residual_target = max(s.displayed_intensity, 0.55 * s.contained_load)
        residual_tau = 20.0 if residual_target > s.residual_affect else 150.0 / max(0.15, p.recovery_rate)
        s.residual_affect = _clamp(_approach(s.residual_affect, residual_target, dt, residual_tau))

    def output(self) -> AffectDynamicsOutput:
        s, p = self.state, self.profile
        unresolved = _clamp(max(s.bracing, 1.0 - s.assimilation))
        trajectory = _clamp(
            0.34 * unresolved
            + 0.26 * s.expressive_instability
            + 0.24 * s.accumulated_strain
            + 0.16 * s.contained_load
        )
        processing_time = _clamp(0.55 * s.bracing + 0.30 * (1.0 - s.assimilation) + 0.15 * s.regulatory_load)
        impulse_to_inquire = _clamp(p.inquiry_bias * (0.55 + 0.45 * s.bracing) * (0.5 + 0.5 * s.uncertainty))
        withdrawal_pressure = _clamp(0.45 * s.internal_load / 2.5 + 0.35 * s.accumulated_strain + 0.20 * s.bracing)

        # Choreography receives a restrained continuous layer, not a new action
        # selector. The existing bridge remains the action/arbitration authority.
        choreo_intensity = _clamp(s.displayed_intensity + 0.25 * s.leakage)
        authority_weight = _clamp(s.grounding * (1.0 - 0.55 * s.bracing))

        return AffectDynamicsOutput(
            schema=self.SCHEMA,
            event_id=s.last_event_id,
            state=s.last_state,
            grounding=round(s.grounding, 4),
            uncertainty=round(s.uncertainty, 4),
            orienting=round(s.orienting, 4),
            bracing=round(s.bracing, 4),
            assimilation=round(s.assimilation, 4),
            internal={
                "arousal": round(s.internal_arousal, 4),
                "valence": round(s.internal_valence, 4),
                "load": round(s.internal_load, 4),
                "pressure": round(s.affective_pressure, 4),
                "residual": round(s.residual_affect, 4),
            },
            regulation={
                "capacity": round(s.regulatory_capacity, 4),
                "load": round(s.regulatory_load, 4),
                "suppression": round(s.suppression_effort, 4),
                "contained_load": round(s.contained_load, 4),
                "strain": round(s.accumulated_strain, 4),
                "leakage": round(s.leakage, 4),
            },
            display={
                "intensity": round(s.displayed_intensity, 4),
                "instability": round(s.expressive_instability, 4),
            },
            conversation_signals={
                "processing_time": round(processing_time, 4),
                "impulse_to_inquire": round(impulse_to_inquire, 4),
                "silence_tolerance": round(_clamp(p.silence_tolerance + 0.28 * s.bracing), 4),
                "withdrawal_pressure": round(withdrawal_pressure, 4),
            },
            director_signals={
                "active_trajectory": trajectory >= 0.08,
                "performance_potential": round(trajectory, 4),
                "unresolved_change": round(unresolved, 4),
                "suppression_strain": round(s.accumulated_strain, 4),
            },
            choreography_signals={
                "intensity": round(choreo_intensity, 4),
                "authority_weight": round(authority_weight, 4),
            },
        )

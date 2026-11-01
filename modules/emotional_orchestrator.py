"""PubCast emotional coordination layer.

Coordinates independent emotional/context engines without creating a new truth
authority.  Each producer publishes provenance-bearing *signals*.  The
orchestrator normalizes, scopes, expires and reconciles those signals into a
bounded advisory snapshot consumed by Alex/Jeremy, PubPartner, conversation
policy and performance systems.

It deliberately does not diagnose, execute room actions, write durable memory,
or replace AffectContextEngine. PEQ/CRE-EQ can participate only through the
same broker contract as every other secondary observer.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import threading
import time
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from .limited_exposure import (
    DataClass, DataLabel, ExposurePurpose, LimitedCategory, LimitedExposurePolicy,
    STANDARD_LABEL, may_expose,
)


def _unit(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, x)) if math.isfinite(x) else default


def _signed(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return max(-1.0, min(1.0, x)) if math.isfinite(x) else default


@dataclass(frozen=True)
class EmotionSignal:
    source: str
    subject_id: str
    session_id: str
    observed_at: float
    confidence: float
    dimensions: Mapping[str, float]
    provenance: str
    expires_after: float = 90.0
    room_id: str = ""
    event_id: str = ""
    advisory_only: bool = True
    clinical_hypothesis: bool = False
    data_label: DataLabel = STANDARD_LABEL

    def __post_init__(self) -> None:
        if not self.source or not self.subject_id or not self.session_id:
            raise ValueError("emotion signal requires source, subject_id and session_id")
        if not self.provenance:
            raise ValueError("emotion signal requires provenance")
        object.__setattr__(self, "confidence", _unit(self.confidence))
        object.__setattr__(self, "expires_after", max(1.0, min(3600.0, float(self.expires_after))))
        clean: Dict[str, float] = {}
        for key, value in dict(self.dimensions or {}).items():
            name = str(key).strip().lower()
            if not name:
                continue
            clean[name] = _signed(value) if name == "valence" else _unit(value)
        object.__setattr__(self, "dimensions", clean)

    def is_live(self, now: float) -> bool:
        return now - self.observed_at <= self.expires_after


@dataclass(frozen=True)
class EmotionalEvidenceBundle:
    """Neutral, provenance-preserving evidence presented to System Alex."""
    schema: str
    subject_id: str
    session_id: str
    generated_at: float
    signals: tuple[EmotionSignal, ...]
    sources: tuple[str, ...]
    provenance: tuple[str, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SystemAlexJudgment:
    """Canonical working emotional judgment produced by System Alex.

    This is an adjudication result, not a vote.  For each dimension System Alex
    selects the strongest admissible observation, preserves contradictory
    evidence, and reduces confidence when credible observations disagree.
    Clinical-style hypotheses can corroborate or challenge a judgment but never
    become canonical by themselves.
    """
    schema: str
    subject_id: str
    session_id: str
    generated_at: float
    event_id: str
    dimensions: Mapping[str, float]
    confidence: Mapping[str, float]
    disagreement: Mapping[str, float]
    selected_source: Mapping[str, str]
    sources: tuple[str, ...]
    provenance: tuple[str, ...]
    conversation_signals: Mapping[str, float]
    performance_signals: Mapping[str, float]
    data_class: str = DataClass.STANDARD.value
    limited_categories: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Backward import compatibility.  The authoritative object is now explicitly a
# System Alex judgment rather than an orchestrator-generated fused snapshot.
EmotionalCoordinationSnapshot = SystemAlexJudgment


class SystemAlexAdjudicator:
    """Canonical emotional adjudication authority.

    The broker owns collection/scoping/expiry.  System Alex owns interpretation
    of the admissible evidence bundle.  Keeping this as a separate object makes
    the authority boundary injectable, testable and impossible to confuse with
    broker mechanics.
    """
    JUDGMENT_SCHEMA = "pubcast.system_alex.judgment.v1"
    SOURCE_PRIORITY = {
        "participant_self_report": 100, "alex_affect": 90, "meaning": 80,
        "context": 75, "eq": 70, "jeremy_eq": 65, "conversation": 60,
        "peq": 30, "cre_eq": 30,
    }

    def adjudicate(self, bundle: EmotionalEvidenceBundle) -> SystemAlexJudgment:
        now = bundle.generated_at
        by_dimension: Dict[str, list[tuple[EmotionSignal, float]]] = {}
        for signal in bundle.signals:
            age_ratio = max(0.0, min(1.0, (now - signal.observed_at) / signal.expires_after))
            credibility = signal.confidence * (1.0 - age_ratio * 0.65)
            if signal.clinical_hypothesis:
                credibility *= 0.50
            for name in signal.dimensions:
                by_dimension.setdefault(name, []).append((signal, credibility))

        dimensions: Dict[str, float] = {}
        confidence: Dict[str, float] = {}
        disagreement: Dict[str, float] = {}
        selected_source: Dict[str, str] = {}
        notes = list(bundle.notes)
        for name, rows in by_dimension.items():
            admissible = [r for r in rows if not r[0].clinical_hypothesis]
            if not admissible:
                notes.append(f"{name}: no non-clinical evidence; judgment withheld")
                continue
            selected = max(
                admissible,
                key=lambda r: (r[1], self.SOURCE_PRIORITY.get(r[0].source, 0), r[0].observed_at),
            )
            sig, base_conf = selected
            value = sig.dimensions[name]
            credible = [(s, c) for s, c in rows if c >= 0.20]
            spread = max((abs(value - s.dimensions[name]) for s, _ in credible), default=0.0)
            norm_spread = min(1.0, spread / (2.0 if name == "valence" else 1.0))
            corroboration = max(
                (c for s, c in credible if s is not sig and abs(value - s.dimensions[name]) <= (0.40 if name == "valence" else 0.20)),
                default=0.0,
            )
            dimensions[name] = value
            confidence[name] = _unit(base_conf * (1.0 - 0.55 * norm_spread) + 0.15 * corroboration)
            disagreement[name] = norm_spread
            selected_source[name] = sig.source
            if norm_spread >= 0.45:
                notes.append(f"{name}: material disagreement retained")

        conversation = {
            "processing_time_pressure": _unit(max(dimensions.get("bracing", 0.0), dimensions.get("uncertainty", 0.0), dimensions.get("strain", 0.0))),
            "inquiry_pressure": _unit(dimensions.get("uncertainty", 0.0) * 0.55 + dimensions.get("orienting", 0.0) * 0.25),
            "reduced_initiative_pressure": _unit(dimensions.get("bracing", 0.0) * 0.55 + dimensions.get("load", 0.0) * 0.25),
            "care_attention": _unit(max(dimensions.get("load", 0.0), dimensions.get("stakes", 0.0), dimensions.get("tension", 0.0))),
        }
        performance = {
            "hold_attention": _unit(max(dimensions.get("orienting", 0.0), dimensions.get("bracing", 0.0), dimensions.get("strain", 0.0))),
            "expressive_pressure": _unit(max(dimensions.get("pressure", 0.0), dimensions.get("display", 0.0))),
            "restraint_pressure": _unit(max(dimensions.get("bracing", 0.0), dimensions.get("strain", 0.0))),
        }
        event_id = max((s.event_id for s in bundle.signals if s.event_id), default="")
        limited = [s for s in bundle.signals if s.data_label.limited]
        categories = tuple(sorted({c.value for s in limited for c in s.data_label.categories}))
        return SystemAlexJudgment(
            schema=self.JUDGMENT_SCHEMA, subject_id=bundle.subject_id, session_id=bundle.session_id,
            generated_at=now, event_id=event_id, dimensions=dimensions, confidence=confidence,
            disagreement=disagreement, selected_source=selected_source, sources=bundle.sources,
            provenance=bundle.provenance, conversation_signals=conversation,
            performance_signals=performance,
            data_class=DataClass.LIMITED.value if limited else DataClass.STANDARD.value,
            limited_categories=categories, notes=tuple(dict.fromkeys(notes)),
        )


class EmotionalOrchestrator:
    """Thread-safe evidence broker.  It does not decide emotional truth."""

    EVIDENCE_SCHEMA = "pubcast.emotion.evidence.v2"
    JUDGMENT_SCHEMA = SystemAlexAdjudicator.JUDGMENT_SCHEMA
    REGISTERED_SOURCES = frozenset({
        "alex_affect", "eq", "jeremy_eq", "conversation", "peq", "cre_eq",
        "participant_self_report", "meaning", "context",
    })
    def __init__(self, *, clock: Callable[[], float] = time.time, max_signals: int = 96,
                 adjudicator: Optional[SystemAlexAdjudicator] = None) -> None:
        self._clock = clock
        self._adjudicator = adjudicator or SystemAlexAdjudicator()
        self._max_signals = max(16, int(max_signals))
        self._signals: Dict[tuple[str, str], list[EmotionSignal]] = {}
        self._lock = threading.RLock()

    def publish(self, signal: EmotionSignal) -> None:
        if signal.source not in self.REGISTERED_SOURCES:
            raise ValueError(f"unregistered emotional signal source: {signal.source!r}")
        key = (signal.subject_id, signal.session_id)
        with self._lock:
            bucket = self._signals.setdefault(key, [])
            if signal.event_id:
                bucket[:] = [s for s in bucket if not (s.source == signal.source and s.event_id == signal.event_id)]
            bucket.append(signal)
            now = self._clock()
            bucket[:] = [s for s in bucket if s.is_live(now)][-self._max_signals:]

    def publish_alex(self, *, subject_id: str, session_id: str,
                     affect: Optional[Mapping[str, Any]], dynamics: Optional[Mapping[str, Any]] = None,
                     room_id: str = "", data_label: DataLabel = STANDARD_LABEL) -> None:
        """Publish AffectContextEngine evidence only.

        ``dynamics`` remains in the signature for source compatibility but is
        intentionally ignored: Affect Dynamics is downstream of adjudication.
        """
        if not affect:
            return
        now = self._clock()
        reading = affect.get("reading") or {}
        raw = affect.get("affect") or {}
        performance = affect.get("performance") or {}
        def zmag(name: str) -> float:
            try: return min(1.0, abs(float(raw.get(name, 0.0))) / 2.5)
            except (TypeError, ValueError): return 0.0
        try: valence = max(-1.0, min(1.0, float(raw.get("valence_z", 0.0)) / 2.5))
        except (TypeError, ValueError): valence = 0.0
        self.publish(EmotionSignal(
            source="alex_affect", subject_id=subject_id, session_id=session_id,
            room_id=room_id, observed_at=now, confidence=_unit(reading.get("confidence")),
            dimensions={"arousal": zmag("arousal_z"), "load": zmag("load_z"),
                        "valence": valence, "tension": _unit(performance.get("tension")),
                        "stakes": _unit((affect.get("context") or {}).get("stakes")),
                        "dramatic_intensity": _unit(performance.get("dramatic_intensity")),
                        "novelty": _unit((affect.get("context") or {}).get("novelty"))},
            provenance="AffectContextEngine personal-baseline appraisal",
            event_id=str(affect.get("turn_id") or ""), expires_after=180.0,
            data_label=data_label,
        ))

    def publish_secondary(self, *, source: str, subject_id: str, session_id: str,
                          dimensions: Mapping[str, float], confidence: float,
                          provenance: str, room_id: str = "", event_id: str = "",
                          clinical_hypothesis: bool = False, expires_after: float = 90.0,
                          data_label: DataLabel = STANDARD_LABEL) -> None:
        normalized = str(source).strip().lower()
        if normalized not in self.REGISTERED_SOURCES:
            raise ValueError(f"unregistered emotional signal source: {source!r}")
        self.publish(EmotionSignal(
            source=normalized, subject_id=subject_id, session_id=session_id,
            room_id=room_id, observed_at=self._clock(), confidence=confidence,
            dimensions=dimensions, provenance=provenance, event_id=event_id,
            clinical_hypothesis=clinical_hypothesis, expires_after=expires_after,
            data_label=data_label,
        ))

    def evidence_bundle(self, *, subject_id: str, session_id: str, room_id: str = "") -> EmotionalEvidenceBundle:
        now = self._clock(); key = (subject_id, session_id)
        with self._lock:
            bucket = [s for s in self._signals.get(key, ()) if s.is_live(now)]
            self._signals[key] = bucket[-self._max_signals:]
        if room_id:
            bucket = [s for s in bucket if not s.room_id or s.room_id == room_id]
        notes=[]
        admissible=[]
        for signal in bucket:
            if signal.data_label.limited and not may_expose(
                signal.data_label, consumer="system_alex", purpose=ExposurePurpose.EMOTIONAL_ADJUDICATION
            ):
                notes.append(f"{signal.source}: LIMITED evidence withheld from System Alex by policy")
                continue
            admissible.append(signal)
        bucket = admissible
        sources=[]; provenance=[]
        for signal in bucket:
            if signal.source not in sources: sources.append(signal.source)
            safe = signal.provenance if not signal.data_label.limited else "LIMITED evidence; details withheld"
            if safe not in provenance: provenance.append(safe)
        if any(s.clinical_hypothesis for s in bucket):
            notes.append("clinical hypotheses are advisory-only and cannot become canonical alone")
        return EmotionalEvidenceBundle(
            schema=self.EVIDENCE_SCHEMA, subject_id=subject_id, session_id=session_id,
            generated_at=now, signals=tuple(bucket), sources=tuple(sources),
            provenance=tuple(provenance), notes=tuple(notes),
        )

    def adjudicate(self, *, subject_id: str, session_id: str, room_id: str = "") -> SystemAlexJudgment:
        """Present the current admissible evidence bundle to System Alex."""
        bundle = self.evidence_bundle(subject_id=subject_id, session_id=session_id, room_id=room_id)
        return self._adjudicator.adjudicate(bundle)

    def snapshot(self, *, subject_id: str, session_id: str, room_id: str = "") -> SystemAlexJudgment:
        """Compatibility alias: callers now receive System Alex's judgment."""
        return self.adjudicate(subject_id=subject_id, session_id=session_id, room_id=room_id)

    def clear_session(self, *, subject_id: str, session_id: str) -> None:
        with self._lock:
            self._signals.pop((subject_id, session_id), None)

    def clear_session_id(self, *, session_id: str) -> None:
        """Remove all subjects' transient evidence for a closed session."""
        with self._lock:
            for key in [k for k in self._signals if k[1] == session_id]:
                self._signals.pop(key, None)

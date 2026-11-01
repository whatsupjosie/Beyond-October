"""One CARE/EQ observation and explicit Little Mode masking seam for PubCast.

This integrates the independent CARE reference without replacing the existing
Alex Little One profile, Jeremy EQ, affect models, or consent boundaries.
Only owner-activated baby-facing messages are masked; unmodified input remains
outside this care-facing adapter. No emotional diagnosis is inferred from text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Any, Optional


class CareMode(str, Enum):
    ORDINARY = 'ordinary'
    BABY = 'baby'


class Ambiguator:
    """Reference one-way masking, with a protected safeword exit checked first."""
    SAFEWORD = 'parachute'

    def transform(self, raw: str) -> tuple[str, bool]:
        if re.search(r'(?i)(?<!\w)parachute(?!\w)', raw):
            return '[SAFEWORD: PARACHUTE]', True
        length = len(raw.strip())
        if not length:
            return '[quiet; no vocalization observed]', False
        if length < 24:
            return '[brief infant-like vocalization; emotional meaning unknown]', False
        if length < 120:
            return '[extended babble and movement; emotional meaning unknown]', False
        return '[prolonged babbling and activity; emotional meaning unknown]', False


@dataclass
class EQMonitor:
    events: list[dict[str, Any]] = field(default_factory=list)

    def record(self, kind: str, observed: dict[str, Any], hypothesis: Optional[str] = None,
               alternatives: Optional[list[str]] = None, outcome: Optional[str] = None) -> dict[str, Any]:
        entry = {
            'time_utc': datetime.now(timezone.utc).isoformat(),
            'kind': kind, 'observed': observed,
            'hypothesis': hypothesis, 'alternatives': alternatives or [],
            'outcome': outcome, 'status': 'unreviewed',
        }
        self.events.append(entry)
        return entry

    def export(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({'schema': 'care-eq-v1', 'events': self.events}, indent=2), encoding='utf-8')


@dataclass
class CareSession:
    owner_id: str
    monitor: EQMonitor = field(default_factory=EQMonitor)
    mode: CareMode = CareMode.ORDINARY
    ambiguator: Ambiguator = field(default_factory=Ambiguator)
    # Owner-chosen care routine options (see CareCoordinator.set_routine_settings).
    routine_settings: dict[str, Any] = field(default_factory=dict)

    def activate(self, requester_id: str) -> None:
        if requester_id != self.owner_id:
            raise PermissionError('owner only')
        self.mode = CareMode.BABY
        self.monitor.record('mode', {'to': 'baby', 'activation': 'explicit'})

    def deactivate(self) -> None:
        self.mode = CareMode.ORDINARY
        self.monitor.record('mode', {'to': 'ordinary'})

    def receive(self, raw: str) -> str:
        if self.mode == CareMode.ORDINARY:
            self.monitor.record('input', {'mode': 'ordinary', 'length': len(raw)})
            return raw
        transformed, stop = self.ambiguator.transform(raw)
        self.monitor.record('input', {
            'mode': 'baby', 'length': len(raw),
            'sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest(),
            'care_facing': transformed,
        })
        if stop:
            self.deactivate()
        return transformed


class CareCoordinator:
    """One persistent per-user CARE store shared by Alex API and Alex/Jeremy Bridge.

    Files contain masked metadata only (no raw adult turns). The active session
    state survives restarts. All mutations are serialized and atomically saved.
    """

    def __init__(self, data_dir: Path):
        self.root = Path(data_dir) / 'care_eq_private'
        self.root.mkdir(parents=True, exist_ok=True)
        if os.name == 'posix':
            self.root.chmod(0o700)  # private EQ observations, not shared programme logs
        self._sessions: dict[str, CareSession] = {}
        self._directors: dict[str, Any] = {}  # care routine state; shapes only, never text
        self._lock = threading.RLock()

    @staticmethod
    def _routines_enabled() -> bool:
        """Care routines belong to the optional Alex Little One layer, so they
        stay off unless that layer is switched on."""
        from .feature_flags import alex_little_one_enabled
        return alex_little_one_enabled()

    def _director(self, user_id: str) -> Any:
        director = self._directors.get(user_id)
        if director is None:
            from .alex_little_one.care_routines import CareRoutineDirector
            director = self._directors[user_id] = CareRoutineDirector()
        return director

    def _path(self, user_id: str) -> Path:
        if not user_id or len(user_id) > 128:
            raise ValueError('Invalid CARE user ID')
        digest = hashlib.sha256(user_id.encode('utf-8')).hexdigest()
        return self.root / f'{digest}.json'

    def _get(self, user_id: str) -> CareSession:
        session = self._sessions.get(user_id)
        if session is not None:
            return session
        session = CareSession(owner_id=user_id)
        path = self._path(user_id)
        if path.is_file():
            try:
                saved = json.loads(path.read_text(encoding='utf-8'))
                if saved.get('owner_id') != user_id or saved.get('schema') != 'care-eq-v1':
                    raise ValueError('Invalid CARE owner or schema')
                session.mode = CareMode(saved.get('mode', CareMode.ORDINARY.value))
                session.monitor.events = list(saved.get('events', []))
                stored = saved.get('routine_settings')
                if isinstance(stored, dict):
                    session.routine_settings = self._clean_routine_settings(stored)
            except (OSError, ValueError, TypeError):
                raise ValueError('CARE state is unreadable; refusing to silently reset consent')
        self._sessions[user_id] = session
        return session

    def _persist(self, session: CareSession) -> None:
        path = self._path(session.owner_id)
        data = {'schema': 'care-eq-v1', 'owner_id': session.owner_id,
                'mode': session.mode.value, 'events': session.monitor.events,
                'routine_settings': session.routine_settings}
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile('w', dir=self.root, prefix='.care-', suffix='.tmp',
                                             delete=False, encoding='utf-8') as stream:
                tmp_path = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            tmp_path.replace(path)
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()

    def activate(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._get(user_id)
            session.activate(user_id)
            director = self._directors.get(user_id)
            if director is not None:
                director.reset()
            self._persist(session)
            return self.status(user_id)

    def deactivate(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._get(user_id)
            session.deactivate()
            director = self._directors.get(user_id)
            if director is not None:
                director.reset()
            self._persist(session)
            return self.status(user_id)

    def is_active(self, user_id: str) -> bool:
        with self._lock:
            return self._get(user_id).mode == CareMode.BABY

    def status(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._get(user_id)
            return {'mode': session.mode.value, 'event_count': len(session.monitor.events),
                    'schema': 'care-eq-v1', 'owner_id': user_id}

    def receive(self, user_id: str, raw: str) -> str:
        with self._lock:
            session = self._get(user_id)
            was_baby = session.mode == CareMode.BABY
            result = session.receive(raw)
            if was_baby and self._routines_enabled():
                if session.mode == CareMode.BABY:
                    # The raw text is read for its shape here and goes no further.
                    director = self._director(user_id)
                    director.observe(raw)
                    outcome = director.last_outcome
                    if outcome is not None:
                        session.monitor.record(
                            'routine_outcome', {k: outcome[k] for k in ('routine_id', 'family', 'verdict')},
                            hypothesis='routine eased the next turn' if outcome['verdict'] == 'better' else None,
                            outcome=outcome['verdict'])
                else:
                    director = self._directors.get(user_id)
                    if director is not None:
                        director.reset()  # exit phrase: forget the session's shapes
            self._persist(session)
            return result

    @staticmethod
    def _clean_routine_settings(raw: dict[str, Any]) -> dict[str, Any]:
        from .alex_little_one.care_routines import clean_address_terms
        cleaned: dict[str, Any] = {
            'change_talk': bool(raw.get('change_talk', False)),
            'bottle_talk': bool(raw.get('bottle_talk', False)),
        }
        terms = clean_address_terms(raw.get('address_terms'))
        if terms:
            cleaned['address_terms'] = list(terms)
        return cleaned

    def routine_settings(self, user_id: str) -> dict[str, Any]:
        """The owner's care routine options. Everything optional is off by default."""
        with self._lock:
            stored = self._get(user_id).routine_settings
            return {'change_talk': bool(stored.get('change_talk', False)),
                    'bottle_talk': bool(stored.get('bottle_talk', False)),
                    'address_terms': list(stored.get('address_terms') or []),
                    'routines_enabled': self._routines_enabled()}

    def set_routine_settings(self, user_id: str, *, change_talk: Optional[bool] = None,
                             bottle_talk: Optional[bool] = None,
                             address_terms: Optional[list[str]] = None) -> dict[str, Any]:
        """Owner-chosen options for care routines, saved in the private care store.

        Turning on change_talk is the owner's standing yes to diaper-change talk while
        in baby mode. It is off by default and can be turned off at any time, which
        stops a change in progress. Hard stop words and the exit phrases always win."""
        with self._lock:
            session = self._get(user_id)
            merged = dict(session.routine_settings)
            if change_talk is not None:
                merged['change_talk'] = bool(change_talk)
            if bottle_talk is not None:
                merged['bottle_talk'] = bool(bottle_talk)
            if address_terms is not None:
                merged['address_terms'] = list(address_terms)
            session.routine_settings = self._clean_routine_settings(merged)
            session.monitor.record('routine_settings', {
                'change_talk': session.routine_settings['change_talk'],
                'bottle_talk': session.routine_settings['bottle_talk'],
                'address_terms': len(session.routine_settings.get('address_terms', [])),
            })
            self._persist(session)
            return self.routine_settings(user_id)

    def routine_for(self, user_id: str, settings: Any = None) -> Optional[dict[str, Any]]:
        """The care routine for the turn just received, or None.

        None when care routines are off, baby mode is not active, or no turn has
        been observed. Safe to call more than once per turn: it returns the same
        routine until the next turn arrives."""
        with self._lock:
            if not self._routines_enabled():
                return None
            session = self._get(user_id)
            if session.mode != CareMode.BABY:
                return None
            director = self._directors.get(user_id)
            if director is None:
                return None
            from .alex_little_one.care_routines import RoutineSettings
            if settings is None:
                stored = session.routine_settings
                terms = tuple(stored.get('address_terms') or ())
                extra = {'address_terms': terms} if terms else {}
                settings = RoutineSettings(allow_change_talk=bool(stored.get('change_talk')),
                                           allow_bottle_talk=bool(stored.get('bottle_talk')), **extra)
            had_pending = director.has_choice
            choice = director.choose(settings)
            if choice is None:
                return None
            if not had_pending:
                session.monitor.record(
                    'routine', {'routine_id': choice.routine.id, 'family': choice.routine.family.value,
                                'bid': choice.bid.label.value, 'confidence': choice.bid.confidence,
                                'repair': choice.repair, 'steady': choice.steady,
                                'stage': choice.stage, 'verdict': choice.verdict,
                                'mid_change': choice.mid_change},
                    hypothesis=choice.reason)
                self._persist(session)
            return choice.to_packet()

    def observe(self, user_id: str, kind: str, observed: dict[str, Any],
                hypothesis: Optional[str] = None, alternatives: Optional[list[str]] = None,
                outcome: Optional[str] = None) -> dict[str, Any]:
        with self._lock:
            session = self._get(user_id)
            event = session.monitor.record(kind, observed, hypothesis, alternatives, outcome)
            self._persist(session)
            return event

    def export(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            return {'schema': 'care-eq-v1', 'events': list(self._get(user_id).monitor.events)}

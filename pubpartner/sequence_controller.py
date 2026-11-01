"""
Turn sequencing and pacing for standalone PubPartner runtimes.

PubPartner's cartridge/memory/prompt layers are timing-agnostic by design —
they answer "what should this character say" but never "when should this
character speak." When PubPartner runs bundled inside PubCast, PubCast's
switchblade_governor answers that "when" question: it reads emotional state
(VDI) and scene composition and emits a priority vector that tells engines
(including, indirectly, PubPartner) how to allocate turns and cycles.

PubPartner Portable has no PubCast, no VDI, no scene state. It still needs
an answer to "when." This module is that answer: a small, self-contained
turn pacer that decides when a cartridge is ready for its next turn, how
long to wait before treating a burst of rapid messages as one turn, and how
to score newly-captured memories on its own, without any external
scheduler.

Design contract:
  - This module knows nothing about cartridges, LLMs, or prompts. It only
    tracks timing and emits decisions. cartridge.py and prompt_assembler.py
    must never import this module — the dependency runs one direction only,
    from portable_runtime.py down into sequence_controller.py and cartridge.py
    separately. This keeps the cartridge layer honestly portable: it can be
    embedded in PubCast, in Portable, or in something that hasn't been built
    yet, without ever knowing which pacer (if any) is driving it.
  - External priority signals are optional, not required. If a caller
    (e.g. a future PubCast bridge) supplies a PriorityHint, SequenceController
    uses it to adjust debounce/importance behavior. If nothing is supplied,
    it falls back to its own defaults. Nothing in this module blocks on an
    external signal ever arriving.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


DEFAULT_DEBOUNCE_SECONDS = 1.2
DEFAULT_IDLE_TIMEOUT_SECONDS = 45.0
DEFAULT_MIN_TURN_INTERVAL_SECONDS = 0.35


class TurnDecision(Enum):
    """What the sequencer wants the runtime to do right now."""

    HOLD = "hold"  # keep buffering — more input may be part of this turn
    FIRE = "fire"  # dispatch the buffered input as one turn now
    IDLE = "idle"  # no pending input; nothing to do


@dataclass(frozen=True)
class PriorityHint:
    """Optional external timing signal, e.g. from PubCast's switchblade.

    All fields are advisory. SequenceController degrades gracefully to its
    own defaults for any field left as None. Nothing in PubPartner Portable
    requires this type to ever be constructed.
    """

    identity_moment: Optional[bool] = None
    urgency: Optional[float] = None  # 0.0 (no rush) .. 1.0 (fire immediately)
    suggested_debounce_seconds: Optional[float] = None


@dataclass
class PendingTurn:
    """Buffered input waiting to be dispatched as one turn."""

    fragments: list[str] = field(default_factory=list)
    first_fragment_at: Optional[float] = None
    last_fragment_at: Optional[float] = None

    @property
    def is_empty(self) -> bool:
        return not self.fragments

    def text(self) -> str:
        # Input capture already rejects blank-only fragments. Preserve each
        # accepted fragment exactly; spacing/newlines can be authored content.
        return " ".join(self.fragments)

    def clear(self) -> None:
        self.fragments.clear()
        self.first_fragment_at = None
        self.last_fragment_at = None


class SequenceController:
    """Decides when buffered user input becomes a dispatched turn, and
    scores newly-captured memories, entirely on its own clock.

    Not thread-safe by design — one controller per active conversation.
    If you need concurrent conversations, run one SequenceController per
    conversation rather than sharing one across threads.
    """

    def __init__(
        self,
        debounce_seconds: float = DEFAULT_DEBOUNCE_SECONDS,
        idle_timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS,
        min_turn_interval_seconds: float = DEFAULT_MIN_TURN_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        if debounce_seconds < 0:
            raise ValueError("debounce_seconds must be >= 0")
        if idle_timeout_seconds <= 0:
            raise ValueError("idle_timeout_seconds must be > 0")
        if min_turn_interval_seconds < 0:
            raise ValueError("min_turn_interval_seconds must be >= 0")

        self._debounce_seconds = debounce_seconds
        self._idle_timeout_seconds = idle_timeout_seconds
        self._min_turn_interval_seconds = min_turn_interval_seconds
        self._clock = clock

        self._pending = PendingTurn()
        self._last_turn_fired_at: Optional[float] = None
        self._turn_count = 0

    # ── Input capture ────────────────────────────────────────────────────

    def submit(self, text: str) -> None:
        """Buffer a fragment of user input. Does not decide timing —
        call `evaluate()` to get a decision after submitting."""
        if not text or not text.strip():
            return
        now = self._clock()
        if self._pending.is_empty:
            self._pending.first_fragment_at = now
        self._pending.fragments.append(text)
        self._pending.last_fragment_at = now

    # ── Decision ─────────────────────────────────────────────────────────

    def evaluate(self, hint: Optional[PriorityHint] = None) -> TurnDecision:
        """Return what should happen right now given buffered input and
        elapsed time. Call this on every tick of your event loop (timer,
        new input, or otherwise) — it is cheap and side-effect-free except
        for the internal clock reads.
        """
        if self._pending.is_empty:
            return TurnDecision.IDLE

        now = self._clock()
        debounce = self._resolve_debounce(hint)

        # Respect a minimum spacing between fired turns even under urgent
        # hints, so a runaway caller can't fire turns faster than the
        # downstream LLM/cartridge layer can sanely process.
        if self._last_turn_fired_at is not None:
            since_last = now - self._last_turn_fired_at
            if since_last < self._min_turn_interval_seconds:
                return TurnDecision.HOLD

        if hint is not None and hint.urgency is not None and hint.urgency >= 0.95:
            return TurnDecision.FIRE

        assert self._pending.last_fragment_at is not None
        quiet_for = now - self._pending.last_fragment_at
        if quiet_for >= debounce:
            return TurnDecision.FIRE

        return TurnDecision.HOLD

    def _resolve_debounce(self, hint: Optional[PriorityHint]) -> float:
        if hint is not None and hint.suggested_debounce_seconds is not None:
            return max(0.0, hint.suggested_debounce_seconds)
        if hint is not None and hint.identity_moment:
            # An identity moment (per PubCast's vocabulary) warrants a
            # snappier response when a hint says so explicitly — but this
            # is only ever used if a caller supplies the hint. Standalone
            # Portable never sets this on its own.
            return min(self._debounce_seconds, 0.4)
        return self._debounce_seconds

    # ── Dispatch ─────────────────────────────────────────────────────────

    def take_turn(self) -> str:
        """Consume and return the buffered input as one turn's text, and
        reset the buffer. Call this only after `evaluate()` returns FIRE —
        calling it on an empty buffer raises, since that indicates the
        runtime's control flow is out of sync with the sequencer."""
        if self._pending.is_empty:
            raise RuntimeError(
                "take_turn() called with no buffered input — check evaluate() "
                "returned FIRE before calling take_turn()"
            )
        text = self._pending.text()
        self._pending.clear()
        self._last_turn_fired_at = self._clock()
        self._turn_count += 1
        return text

    # ── Idle / lifecycle ─────────────────────────────────────────────────

    def seconds_since_last_turn(self) -> Optional[float]:
        """None if no turn has ever fired."""
        if self._last_turn_fired_at is None:
            return None
        return self._clock() - self._last_turn_fired_at

    def is_session_idle(self) -> bool:
        """True if enough time has passed since the last turn that a caller
        may want to treat the session as paused (e.g. close a socket, drop
        to a lower memory-scan cadence). Purely advisory — SequenceController
        never closes anything itself."""
        elapsed = self.seconds_since_last_turn()
        if elapsed is None:
            return False
        return elapsed >= self._idle_timeout_seconds

    @property
    def turn_count(self) -> int:
        return self._turn_count

    @property
    def has_pending_input(self) -> bool:
        return not self._pending.is_empty


def score_captured_memory(
    text: str,
    *,
    is_correction: bool = False,
    is_repeated_topic: bool = False,
    base_importance: float = 0.4,
) -> float:
    """Assign an importance score (0.0-1.0) to a memory captured during a
    live turn, without any external input. Mirrors the weighting spirit of
    MemoryStore's own recency/relevance blend, but operates at capture time
    rather than query time.

    This is intentionally simple and documented rather than clever: a
    correction from the user ("no, I meant...") is weighted up because it's
    a signal the prior memory was wrong or incomplete. A repeated topic is
    weighted up because recurrence is itself a signal of importance. Length
    is not used as a signal — a short, sharp statement is not less
    important than a long one.
    """
    if not (0.0 <= base_importance <= 1.0):
        raise ValueError(f"base_importance must be between 0.0 and 1.0, got {base_importance}")

    score = base_importance
    if is_correction:
        score += 0.25
    if is_repeated_topic:
        score += 0.15
    return max(0.0, min(1.0, score))

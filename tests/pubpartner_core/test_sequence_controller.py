import pytest

from pubpartner.sequence_controller import (
    PriorityHint,
    SequenceController,
    TurnDecision,
    score_captured_memory,
)


class FakeClock:
    """Deterministic, manually-advanced clock for testing time-based logic
    without real sleeps."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def __call__(self) -> float:
        return self.now


# ── Construction / validation ───────────────────────────────────────────


def test_rejects_negative_debounce():
    with pytest.raises(ValueError):
        SequenceController(debounce_seconds=-1.0)


def test_rejects_zero_idle_timeout():
    with pytest.raises(ValueError):
        SequenceController(idle_timeout_seconds=0.0)


def test_rejects_negative_min_turn_interval():
    with pytest.raises(ValueError):
        SequenceController(min_turn_interval_seconds=-0.1)


# ── Idle / empty buffer ──────────────────────────────────────────────────


def test_idle_with_no_input():
    seq = SequenceController()
    assert seq.evaluate() == TurnDecision.IDLE
    assert seq.has_pending_input is False


def test_take_turn_on_empty_buffer_raises():
    seq = SequenceController()
    with pytest.raises(RuntimeError):
        seq.take_turn()


def test_ignores_blank_and_empty_submissions():
    clock = FakeClock()
    seq = SequenceController(clock=clock)
    seq.submit("")
    seq.submit("   ")
    assert seq.has_pending_input is False
    assert seq.evaluate() == TurnDecision.IDLE


# ── Debounce basics ──────────────────────────────────────────────────────


def test_holds_before_debounce_elapses():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=1.0, clock=clock)
    seq.submit("hello")
    clock.advance(0.5)
    assert seq.evaluate() == TurnDecision.HOLD


def test_fires_after_debounce_elapses():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=1.0, clock=clock)
    seq.submit("hello")
    clock.advance(1.01)
    assert seq.evaluate() == TurnDecision.FIRE


def test_fires_exactly_at_debounce_boundary():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=1.0, clock=clock)
    seq.submit("hello")
    clock.advance(1.0)
    assert seq.evaluate() == TurnDecision.FIRE


def test_zero_debounce_fires_immediately():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=0.0, clock=clock)
    seq.submit("hello")
    assert seq.evaluate() == TurnDecision.FIRE


# ── Burst/debounce reset behavior ────────────────────────────────────────


def test_new_fragment_resets_debounce_window():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=1.0, clock=clock)
    seq.submit("hello")
    clock.advance(0.9)
    seq.submit("wait, one more thing")
    clock.advance(0.9)
    # Still within debounce of the *second* fragment, not the first
    assert seq.evaluate() == TurnDecision.HOLD
    clock.advance(0.2)
    assert seq.evaluate() == TurnDecision.FIRE


def test_burst_of_fragments_combines_into_one_turn_text():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=1.0, clock=clock)
    seq.submit("hey so")
    clock.advance(0.3)
    seq.submit("I wanted to ask")
    clock.advance(0.3)
    seq.submit("about the housing thing")
    clock.advance(1.1)
    assert seq.evaluate() == TurnDecision.FIRE
    text = seq.take_turn()
    assert text == "hey so I wanted to ask about the housing thing"


def test_take_turn_clears_buffer_for_next_round():
    clock = FakeClock()
    seq = SequenceController(
        debounce_seconds=0.0, min_turn_interval_seconds=0.0, clock=clock
    )
    seq.submit("first turn")
    seq.evaluate()
    seq.take_turn()
    assert seq.has_pending_input is False
    assert seq.evaluate() == TurnDecision.IDLE

    seq.submit("second turn")
    assert seq.evaluate() == TurnDecision.FIRE
    assert seq.take_turn() == "second turn"


def test_second_turn_respects_default_min_interval_after_first():
    """Distinct from the test above: this uses the real default
    min_turn_interval_seconds (0.35s) to prove the floor actually applies
    across turns, not just within one buffering window."""
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=0.0, clock=clock)
    seq.submit("first turn")
    seq.evaluate()
    seq.take_turn()

    seq.submit("second turn")
    assert seq.evaluate() == TurnDecision.HOLD  # no time has passed yet
    clock.advance(0.4)
    assert seq.evaluate() == TurnDecision.FIRE


# ── Minimum turn interval (rate limiting even under urgency) ────────────


def test_min_turn_interval_holds_even_when_debounce_elapsed():
    clock = FakeClock()
    seq = SequenceController(
        debounce_seconds=0.1, min_turn_interval_seconds=2.0, clock=clock
    )
    seq.submit("first")
    clock.advance(0.2)
    assert seq.evaluate() == TurnDecision.FIRE
    seq.take_turn()

    seq.submit("second")
    clock.advance(0.2)  # debounce satisfied, but min interval (2.0s) is not
    assert seq.evaluate() == TurnDecision.HOLD

    clock.advance(2.0)
    assert seq.evaluate() == TurnDecision.FIRE


def test_min_turn_interval_overrides_urgent_hint():
    clock = FakeClock()
    seq = SequenceController(
        debounce_seconds=1.0, min_turn_interval_seconds=5.0, clock=clock
    )
    seq.submit("first")
    seq.evaluate(PriorityHint(urgency=1.0))
    seq.take_turn()

    seq.submit("second")
    clock.advance(0.1)
    urgent = PriorityHint(urgency=1.0)
    # Even maximum urgency cannot violate the floor — this is the guardrail
    # against a runaway or malicious external hint firing turns faster than
    # the downstream cartridge/LLM layer can process.
    assert seq.evaluate(urgent) == TurnDecision.HOLD


# ── PriorityHint behavior (optional, degrades gracefully) ───────────────


def test_no_hint_uses_default_debounce():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=1.0, clock=clock)
    seq.submit("hello")
    clock.advance(0.5)
    assert seq.evaluate(hint=None) == TurnDecision.HOLD
    clock.advance(0.6)
    assert seq.evaluate(hint=None) == TurnDecision.FIRE


def test_hint_with_all_none_fields_behaves_like_no_hint():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=1.0, clock=clock)
    seq.submit("hello")
    clock.advance(0.5)
    empty_hint = PriorityHint()
    assert seq.evaluate(empty_hint) == TurnDecision.HOLD


def test_urgent_hint_fires_immediately_within_min_interval_floor():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=5.0, clock=clock)
    seq.submit("urgent thing")
    urgent = PriorityHint(urgency=0.99)
    assert seq.evaluate(urgent) == TurnDecision.FIRE


def test_moderate_urgency_does_not_bypass_debounce():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=5.0, clock=clock)
    seq.submit("moderately urgent")
    moderate = PriorityHint(urgency=0.5)
    assert seq.evaluate(moderate) == TurnDecision.HOLD


def test_identity_moment_hint_shortens_debounce():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=5.0, clock=clock)
    seq.submit("identity moment content")
    clock.advance(0.5)
    identity_hint = PriorityHint(identity_moment=True)
    assert seq.evaluate(identity_hint) == TurnDecision.FIRE


def test_explicit_suggested_debounce_overrides_default():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=5.0, clock=clock)
    seq.submit("hello")
    clock.advance(0.2)
    hint = PriorityHint(suggested_debounce_seconds=0.1)
    assert seq.evaluate(hint) == TurnDecision.FIRE


def test_negative_suggested_debounce_is_clamped_to_zero():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=5.0, clock=clock)
    seq.submit("hello")
    hint = PriorityHint(suggested_debounce_seconds=-3.0)
    assert seq.evaluate(hint) == TurnDecision.FIRE


# ── Idle session detection ───────────────────────────────────────────────


def test_not_idle_before_any_turn_fired():
    seq = SequenceController()
    assert seq.is_session_idle() is False
    assert seq.seconds_since_last_turn() is None


def test_not_idle_shortly_after_a_turn():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=0.0, idle_timeout_seconds=10.0, clock=clock)
    seq.submit("hi")
    seq.evaluate()
    seq.take_turn()
    clock.advance(2.0)
    assert seq.is_session_idle() is False


def test_idle_after_timeout_elapses():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=0.0, idle_timeout_seconds=10.0, clock=clock)
    seq.submit("hi")
    seq.evaluate()
    seq.take_turn()
    clock.advance(10.1)
    assert seq.is_session_idle() is True


# ── Turn counting ─────────────────────────────────────────────────────────


def test_turn_count_increments_only_on_take_turn():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=0.0, clock=clock)
    assert seq.turn_count == 0
    seq.submit("one")
    seq.evaluate()
    seq.evaluate()  # calling evaluate again should not increment anything
    assert seq.turn_count == 0
    seq.take_turn()
    assert seq.turn_count == 1


def test_many_sequential_turns_count_correctly():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=0.0, min_turn_interval_seconds=0.0, clock=clock)
    for i in range(50):
        seq.submit(f"message {i}")
        assert seq.evaluate() == TurnDecision.FIRE
        seq.take_turn()
    assert seq.turn_count == 50


# ── Stress: rapid-fire submission flood ──────────────────────────────────


def test_flood_of_rapid_fragments_stays_buffered_until_quiet():
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=1.0, clock=clock)
    for i in range(500):
        seq.submit(f"frag{i}")
        clock.advance(0.001)  # far faster than debounce
    # Still within debounce window of the last fragment
    assert seq.evaluate() == TurnDecision.HOLD
    clock.advance(1.01)
    assert seq.evaluate() == TurnDecision.FIRE
    text = seq.take_turn()
    assert text.count("frag") == 500


def test_flood_then_long_silence_then_flood_again():
    clock = FakeClock()
    seq = SequenceController(
        debounce_seconds=0.5, min_turn_interval_seconds=0.0, clock=clock
    )
    seq.submit("burst one a")
    seq.submit("burst one b")
    clock.advance(0.6)
    assert seq.evaluate() == TurnDecision.FIRE
    first = seq.take_turn()
    assert first == "burst one a burst one b"

    clock.advance(120.0)  # long silence
    assert seq.is_session_idle() is True

    seq.submit("burst two a")
    clock.advance(0.6)
    assert seq.evaluate() == TurnDecision.FIRE
    second = seq.take_turn()
    assert second == "burst two a"
    assert seq.is_session_idle() is False  # a turn just fired


# ── Memory scoring ────────────────────────────────────────────────────────


def test_score_default_is_base_importance():
    assert score_captured_memory("plain statement") == pytest.approx(0.4)


def test_score_correction_boosts_importance():
    plain = score_captured_memory("plain statement")
    corrected = score_captured_memory("plain statement", is_correction=True)
    assert corrected > plain


def test_score_repeated_topic_boosts_importance():
    plain = score_captured_memory("plain statement")
    repeated = score_captured_memory("plain statement", is_repeated_topic=True)
    assert repeated > plain


def test_score_correction_and_repeated_topic_stack():
    both = score_captured_memory("plain statement", is_correction=True, is_repeated_topic=True)
    correction_only = score_captured_memory("plain statement", is_correction=True)
    assert both > correction_only


def test_score_clamped_to_one():
    score = score_captured_memory(
        "text", is_correction=True, is_repeated_topic=True, base_importance=0.9
    )
    assert score == 1.0


def test_score_rejects_out_of_range_base_importance():
    with pytest.raises(ValueError):
        score_captured_memory("text", base_importance=1.5)
    with pytest.raises(ValueError):
        score_captured_memory("text", base_importance=-0.1)


def test_score_length_is_not_a_signal():
    short = score_captured_memory("no.")
    long_text = score_captured_memory("this is a very long sentence " * 20)
    assert short == long_text

"""Regression tests: the keyword layer must be able to leave WITNESS/ANCHOR.

Defect (found in the integration pass, 2026-10-25): after one distressed message
AlexCore entered WITNESS ("silent support, no problem-solving") and never left,
because the keyword pass only lowers energy and the nuanced engine is barred from
lifting a safety state. These tests drive the real AlexCore.process_message.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from modules.alex_core import AIState, AlexCore

DISTRESS = "I don't think I can keep doing this. everything is falling apart and I'm exhausted and alone"


@pytest.fixture
def alex(tmp_path):
    a = AlexCore(user_id="recovery_probe", data_dir=tmp_path)
    a._monitor_active = False  # background thread is irrelevant to these tests
    yield a
    a._monitor_active = False


async def say(alex: AlexCore, text: str):
    # Real conversations are seconds apart; the 5s anti-flicker guard on
    # non-critical transitions is therefore satisfied, so model that here.
    alex._state_entered_at = datetime.now() - timedelta(seconds=30)
    return await alex.process_message(text, typing_speed=60.0, metadata={"session_id": "s"})


async def test_technical_frustration_is_not_a_safety_state(alex):
    for text in (
        "ugh this stupid build keeps crashing, I hate this compiler",
        "fuck this, the tests fail again and I have no idea why",
    ):
        await say(alex, text)
        assert alex._current_state not in (AIState.WITNESS, AIState.ANCHOR), text


async def test_distress_enters_witness(alex):
    await say(alex, DISTRESS)
    assert alex._current_state is AIState.WITNESS


async def test_witness_releases_after_person_settles_and_asks_for_work(alex):
    await say(alex, DISTRESS)
    assert alex._current_state is AIState.WITNESS
    seen = []
    for text in (
        "ok. I'm okay now. can you help me fix the build error in my config file?",
        "the error says module not found: foresight_gateway",
        "great that worked, thanks. now rename these files for me",
        "ok now explain how the tray collision works",
    ):
        out = await say(alex, text)
        seen.append(alex._current_state)
    assert seen[-1] not in (AIState.WITNESS, AIState.ANCHOR), [s.value for s in seen]
    assert out["response_guidelines"]["interaction"] != "silent support, no problem-solving"


async def test_continued_distress_keeps_witness(alex):
    await say(alex, DISTRESS)
    for text in ("i'm so tired", "i'm exhausted, drained, honestly", "overwhelmed again, i can't think"):
        await say(alex, text)
        assert alex._current_state is AIState.WITNESS, text


async def test_single_calm_turn_does_not_snap_out(alex):
    await say(alex, DISTRESS)
    await say(alex, "fine. what time is it")
    assert alex._current_state is AIState.WITNESS  # one calm line is not recovery


async def test_mature_depletion_reading_blocks_release(alex):
    await say(alex, DISTRESS)
    for _ in range(4):
        alex._last_affect_reading = {"reading": {"state": "depletion", "confidence": 0.9}}
        await_state = alex._affect_reading_blocks_release()
        assert await_state is True
        alex._turn_had_distress = False
        assert alex._recover_if_settled() is False
    assert alex._current_state is AIState.WITNESS


async def test_low_confidence_observing_never_blocks_release(alex):
    alex._last_affect_reading = {"reading": {"state": "observing", "confidence": 0.0}}
    assert alex._affect_reading_blocks_release() is False
    alex._last_affect_reading = {"reading": {"state": "depletion", "confidence": 0.2}}
    assert alex._affect_reading_blocks_release() is False


@pytest.mark.parametrize("text,is_stress", [
    ("can you help me fix the build", False),
    ("I need help with the tray collision code", False),
    ("help me rename these files", False),
    ("please help me.", True),
    ("HELP", True),
    ("help!", True),
    ("this is an emergency", True),
])
async def test_help_request_vs_help_cry(alex, text, is_stress):
    before = alex._user_state.stress_level
    alex._analyze_input(text, 60.0)
    assert (alex._user_state.stress_level > before) is is_stress, text

"""Regression tests for the stranger-mode keyword layer (EQ Revamp Plan item 1).

Defects reproduced on 2026-10-25 against the real AlexCore: substring matching
made "I retired" and "I'm not tired at all" drain energy into WITNESS, and
"tired of this bug" (frustration) was scored as fatigue. Hostile/profane turns
with no stress keyword also counted as "settled" and lifted the battery while
the person was escalating.
"""
from __future__ import annotations

import pytest

from modules.alex_core import AlexCore, AIState


@pytest.fixture
def alex(tmp_path):
    a = AlexCore(user_id="kw_probe", data_dir=tmp_path)
    a._monitor_active = False
    yield a
    a._monitor_active = False


def energy_after(alex, text):
    before = alex._user_state.energy_level
    alex._analyze_input(text, 60.0)
    return before, alex._user_state.energy_level


@pytest.mark.parametrize("text", [
    "I'm not tired at all.",
    "I am never tired of this, keep going",
    "I retired from teaching last year.",
    "she is not exhausted, she is fine",
    "no longer drained, I slept well",
])
def test_negated_or_embedded_fatigue_words_do_not_drain_energy(alex, text):
    before, after = energy_after(alex, text)
    assert after == before, text


@pytest.mark.parametrize("text", [
    "Honestly I'm exhausted.",
    "I am so tired.",
    "totally drained today",
])
def test_genuine_fatigue_still_drains_energy(alex, text):
    before, after = energy_after(alex, text)
    assert after < before, text


@pytest.mark.parametrize("text", [
    "I'm tired of this bug, it keeps crashing.",
    "I'm sick and tired of this compiler.",
    "getting a little tired of it",
])
def test_tired_of_is_frustration_not_fatigue(alex, text):
    stress_before = alex._user_state.stress_level
    before, after = energy_after(alex, text)
    assert after == before, "frustration must not drain the battery: " + text
    assert alex._user_state.stress_level > stress_before


@pytest.mark.parametrize("text", [
    "That was really helpful, thanks.",
    "This is not urgent, no panic at all.",
    "there is no emergency here",
])
def test_stress_words_inside_words_or_negated_are_not_stress(alex, text):
    alex._analyze_input(text, 60.0)
    assert alex._user_state.stress_level == 0.0, text


@pytest.mark.parametrize("text", ["please help me.", "this is urgent!", "I'm in a panic"])
def test_real_stress_words_still_raise_stress(alex, text):
    alex._analyze_input(text, 60.0)
    assert alex._user_state.stress_level > 0.0, text


def test_ordinary_help_request_is_still_not_stress(alex):
    alex._analyze_input("can you help me fix a build error?", 60.0)
    assert alex._user_state.stress_level == 0.0


@pytest.mark.parametrize("text", [
    "Get the fuck out of my house.",
    "Get the fuck out!",
    "shut up",
    "leave me alone",
])
def test_hostile_turns_do_not_count_as_settled(alex, text):
    alex._analyze_input(text, 60.0)
    assert alex._turn_had_distress is True
    # ...and hostility alone does not itself change energy or stress here.
    assert alex._user_state.energy_level == 0.5
    assert alex._user_state.stress_level == 0.0


async def test_hostile_turns_do_not_raise_the_battery_during_escalation(alex):
    for text in ("Get the fuck out of my house.", "I could...", "Get the fuck out!",
                 "Get the fuck out of here"):
        await alex.process_message(text, typing_speed=60.0, metadata={"session_id": "s"})
    assert alex._user_state.energy_level <= 0.5
    assert alex._settled_turns < 2 or alex._turn_had_distress

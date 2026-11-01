from modules.program_audio import ProgramAudioState, apply_audio_event, issue_recovery_actions, validate_audio_event


def test_validate_audio_event_clamps_volume():
    event = validate_audio_event({"action": "set_volume", "bus": "music", "volume": 2})
    assert event["volume"] == 1.0


def test_invalid_bus_or_action_raises():
    try:
        validate_audio_event({"action": "explode", "bus": "music"})
    except ValueError as exc:
        assert "unsupported audio action" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_apply_audio_event_tracks_dialogue_and_stop_all():
    state = ProgramAudioState()
    apply_audio_event(state, {"action": "play", "bus": "dialogue"})
    apply_audio_event(state, {"action": "play", "bus": "music"})
    assert state.dialogue_active == 1
    assert state.active_sources["music"] == 1
    status = apply_audio_event(state, {"action": "stop_all"})
    assert status["dialogue_active"] == 0
    assert all(bus["active_sources"] == 0 for bus in status["buses"].values())


def test_recovery_actions_include_stop_all():
    actions = issue_recovery_actions()
    assert any(action["id"] == "program_audio.stop_all" for action in actions)

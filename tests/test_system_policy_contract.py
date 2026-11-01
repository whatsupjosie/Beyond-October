from __future__ import annotations

import json
from pathlib import Path


def test_system_policy_profiles_have_required_runtime_knobs():
    policy = json.loads(Path("system_policy.json").read_text(encoding="utf-8"))
    profiles = policy.get("profiles", {})

    assert policy.get("default_profile") in profiles
    assert {"low", "medium", "high"}.issubset(profiles.keys())

    for name, profile in profiles.items():
        assert isinstance(profile.get("stage_target_fps"), int), name
        assert isinstance(profile.get("choreo_tick_hz"), int), name
        assert isinstance(profile.get("stage_static_fx"), bool), name
        assert isinstance(profile.get("architect_enabled"), bool), name
        assert isinstance(profile.get("architect_max_concurrency"), int), name
        assert isinstance(profile.get("architect_timeout_s"), int), name
        assert isinstance(profile.get("breaker_threshold"), int), name
        assert isinstance(profile.get("breaker_cooldown_s"), int), name
        assert isinstance(profile.get("studio_model"), str) and profile["studio_model"], name
        assert isinstance(profile.get("model_context"), int), name
        assert isinstance(profile.get("model_predict"), int), name


def test_low_profile_is_safe_for_weak_gpu_defaults():
    policy = json.loads(Path("system_policy.json").read_text(encoding="utf-8"))
    low = policy["profiles"]["low"]

    assert low["architect_enabled"] is False
    assert low["model_context"] <= 1024
    assert low["model_predict"] <= 100
    assert low["stage_static_fx"] is True
    assert low["choreo_tick_hz"] <= 20

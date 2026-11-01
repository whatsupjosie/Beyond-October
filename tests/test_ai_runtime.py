from pathlib import Path

import json

import pytest

from modules.ai_runtime import AIRuntimeConfigError, load_ai_runtime_config, resolve_ai_runtime_path, validate_ai_runtime_config


def test_load_default_ai_runtime_config_from_repo():
    config = validate_ai_runtime_config(load_ai_runtime_config(Path(__file__).resolve().parents[1]))
    assert config.active_profile == "ollama_gemma3"
    assert "gemma4_e2b_local" in config.profiles
    assert "ministral_3b_local" in config.profiles
    assert "gemma4_e4b_q4_local" in config.profiles
    assert config.active().backend == "ollama"


def test_invalid_active_profile_raises(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    payload = {
        "active_profile": "missing",
        "default_options": {"temperature": 0.7},
        "profiles": {
            "echo_test": {"backend": "echo", "model": "echo", "enabled": True}
        },
    }
    (config_dir / "ai_runtime.json").write_text(json.dumps(payload), encoding="utf-8")

    config = load_ai_runtime_config(tmp_path)
    with pytest.raises(AIRuntimeConfigError):
        validate_ai_runtime_config(config)


def test_config_path_cannot_escape_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_AI_CONFIG_PATH", str(tmp_path.parent / "outside.json"))
    with pytest.raises(AIRuntimeConfigError):
        resolve_ai_runtime_path(tmp_path)

import asyncio
import json
from pathlib import Path

from modules.pub_partner_chat import chat_status, chat_with_pub_partner


def _write_config(root: Path):
    config = root / "config"
    config.mkdir()
    payload = {
        "active_profile": "echo_test",
        "default_options": {"temperature": 0.0, "max_tokens": 64},
        "profiles": {
            "echo_test": {"backend": "echo", "model": "echo", "enabled": True},
            "ministral_3b_local": {"backend": "echo", "model": "ministral:3b", "enabled": False},
            "gemma3_1b_q4_local": {"backend": "echo", "model": "google_gemma-3-1b-it-Q4_K_L:latest", "enabled": True},
            "ollama_gemma3": {"backend": "echo", "model": "fallback", "enabled": True},
            "gemma3_1b_local": {"backend": "echo", "model": "fallback", "enabled": True},
            "gemma4_compute_q5_e2b_local": {"backend": "echo", "model": "gemma4-compute-q5:e2b", "enabled": True},
        },
    }
    (config / "ai_runtime.json").write_text(json.dumps(payload), encoding="utf-8")


def test_chat_status_exposes_alex_and_jeremy_slots(tmp_path):
    _write_config(tmp_path)
    status = chat_status(tmp_path)
    assert status["slots"]["alex"]["profile"] == "ministral_3b_local"
    assert status["slots"]["jeremy"]["profile"] == "gemma3_1b_q4_local"
    assert status["slots"]["background_math"]["profile"] == "gemma4_compute_q5_e2b_local"


def test_pub_partner_alex_chat_uses_alex_slot_and_writes_history(tmp_path):
    _write_config(tmp_path)
    result = asyncio.run(chat_with_pub_partner(repo_root=tmp_path, data_dir=tmp_path / "data", body={"role": "pub_partner_alex", "message": "hello"}))
    assert result["ok"] is True
    assert result["slot"] == "alex"
    assert "hello" in result["reply"]
    assert list((tmp_path / "data" / "pub_partner_chat").glob("*.jsonl"))

def test_background_math_role_uses_e2b_slot_and_writes_history(tmp_path):
    _write_config(tmp_path)
    result = asyncio.run(chat_with_pub_partner(repo_root=tmp_path, data_dir=tmp_path / "data", body={"role": "background_math", "message": "2+2"}))
    assert result["ok"] is True
    assert result["slot"] == "background_math"
    assert result["profile"] == "gemma4_compute_q5_e2b_local"

def test_background_math_falls_back_to_1b_q4_when_e2b_fails(tmp_path):
    _write_config(tmp_path)
    path = tmp_path / "config" / "ai_runtime.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["profiles"]["gemma4_compute_q5_e2b_local"]["backend"] = "missing_backend"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = asyncio.run(chat_with_pub_partner(repo_root=tmp_path, data_dir=tmp_path / "data", body={"role": "background_math", "message": "2+2"}))
    assert result["ok"] is True
    assert result["slot"] == "background_math"
    assert result["profile"] == "gemma3_1b_q4_local"
    assert result["fallback_used"] is True

def test_auto_switchblade_routes_math_to_background_slot(tmp_path):
    _write_config(tmp_path)
    result = asyncio.run(chat_with_pub_partner(repo_root=tmp_path, data_dir=tmp_path / "data", body={"role": "auto", "message": "calculate 2+2"}))
    assert result["requested_role"] == "auto"
    assert result["role"] == "background_math"
    assert result["slot"] == "background_math"
    assert result["switchblade"]["mode"] == "auto"

def test_auto_switchblade_routes_creative_to_alex_slot(tmp_path):
    _write_config(tmp_path)
    result = asyncio.run(chat_with_pub_partner(repo_root=tmp_path, data_dir=tmp_path / "data", body={"role": "switchblade", "message": "write a scene with warm dialogue"}))
    assert result["requested_role"] == "switchblade"
    assert result["role"] == "pub_partner_alex"
    assert result["slot"] == "alex"

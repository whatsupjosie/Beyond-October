from __future__ import annotations

import os

import pytest

if os.getenv("ENABLE_ALEX_LITTLE_ONE", "").strip().lower() not in {"1", "true", "yes", "on", "enabled"}:
    pytest.skip(
        "Alex Little One research protocol tests require ENABLE_ALEX_LITTLE_ONE=true.",
        allow_module_level=True,
    )

from starlette.testclient import TestClient

import main
from modules import auth as auth_module
from modules import session_runtime
from modules.avatar import list_presets
from modules.character_cast import list_cast_characters


def _token(user_id: str, role: str) -> str:
    return auth_module.create_access_token({"sub": user_id, "role": role})


def _care_profile(active: bool = True) -> dict:
    return {
        "care_mode": "very_baby",
        "public_role": "baby",
        "roleplay_strength": "full",
        "care_variant": "standard",
        "roleplay_friction": "none",
        "guest_visibility": "all_guests",
        "authority_model": "owner_retains_final_authority",
        "active": active,
    }


def test_public_baby_role_policy_only_visible_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "alex_bridge", None)

    with TestClient(main.app) as client:
        monkeypatch.setattr(main, "DATA_DIR", tmp_path)
        monkeypatch.setattr(main, "alex_bridge", None)

        disabled = client.get("/api/session/sess/public-role-policy")
        assert disabled.status_code == 200
        assert disabled.json()["policy"]["public_role_active"] is False
        assert "public_role" not in disabled.json()["policy"]

        save = client.post(
            "/api/state/user",
            json={"display_name": "Josie", "care_profile": _care_profile()},
            headers={"X-Client-Id": "josie"},
        )
        assert save.status_code == 200
        assert save.json()["care_profile"]["public_role"] == "baby"

        register = client.post(
            "/api/session/register",
            json={"session_id": "sess", "project_id": "proj", "user_id": "josie", "host_user_id": "josie"},
        )
        assert register.status_code == 200
        assert register.json()["participant"]["care_profile"]["authority_model"] == "owner_retains_final_authority"

        enabled = client.get("/api/session/sess/public-role-policy")
        policy = enabled.json()["policy"]
        assert policy["public_role_active"] is True
        assert policy["public_role"] == "baby"
        assert policy["guest_visibility"] == "all_guests"
        assert policy["authority_model"] == "owner_retains_final_authority"
        assert "sexual remarks" in policy["forbidden_behaviors"]


def test_big_mode_now_disables_public_baby_role(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "alex_bridge", None)

    session_runtime.register_participant(
        tmp_path,
        session_id="sess",
        user_id="josie",
        display_name="Josie",
        host_user_id="josie",
        care_profile=_care_profile(),
    )

    with TestClient(main.app) as client:
        monkeypatch.setattr(main, "DATA_DIR", tmp_path)
        monkeypatch.setattr(main, "alex_bridge", None)
        response = client.post(
            "/api/session/sess/public-role/phrase",
            json={"user_id": "josie", "text": "big mode now"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["action"] == "exited"
        assert payload["care_profile"]["public_role"] == "none"
        assert payload["policy"]["public_role_active"] is False


def test_blocked_guest_behavior_triggers_public_role_moderation(tmp_path):
    session_runtime.register_participant(
        tmp_path,
        session_id="sess",
        user_id="josie",
        display_name="Josie",
        host_user_id="josie",
        care_profile=_care_profile(),
    )

    result = session_runtime.moderate_public_role_message(
        tmp_path,
        session_id="sess",
        message="You can't stop and this is sexual.",
    )
    moderation = result["moderation"]
    assert moderation["allowed"] is False
    assert moderation["action"] == "mute"
    assert "sexual remarks" in moderation["violations"]
    assert "ignoring stop, pause, or no" in moderation["violations"]

    bodily_care = session_runtime.moderate_public_role_message(
        tmp_path,
        session_id="sess",
        message="Mandatory feeding and diaper check now.",
    )
    assert bodily_care["moderation"]["allowed"] is False
    assert "unsolicited diaper checks" in bodily_care["moderation"]["violations"]
    assert "mandatory feedings" in bodily_care["moderation"]["violations"]


def test_scary_ceremonial_variant_is_stricter_but_still_consent_bound(tmp_path):
    profile = _care_profile()
    profile["care_variant"] = "scary_ceremonial"
    session_runtime.register_participant(
        tmp_path,
        session_id="sess",
        user_id="josie",
        display_name="Josie",
        host_user_id="josie",
        care_profile=profile,
    )

    policy = session_runtime.public_role_policy(tmp_path, "sess")
    assert policy["care_variant"] == "scary_ceremonial"
    assert "ceremonial" in policy["allowed_tone"]
    assert "unsolicited diaper checks" in policy["forbidden_behaviors"]

    result = session_runtime.moderate_public_role_message(
        tmp_path,
        session_id="sess",
        message="You have to stay in the role.",
    )
    assert result["moderation"]["allowed"] is False
    assert result["moderation"]["action"] == "mute"


def test_playful_containment_refuses_in_world_big_claims_but_not_owner_commands(tmp_path):
    profile = _care_profile()
    profile["care_variant"] = "scary_ceremonial"
    profile["roleplay_friction"] = "playful_containment"
    session_runtime.register_participant(
        tmp_path,
        session_id="sess",
        user_id="josie",
        display_name="Josie",
        host_user_id="josie",
        care_profile=profile,
    )

    contained = session_runtime.review_public_role_owner_attempt(
        tmp_path,
        session_id="sess",
        text="I'm big now, treat me like an adult.",
    )
    assert contained["roleplay_response"]["contain"] is True
    assert contained["roleplay_response"]["response_style"] == "playful gentle refusal"

    serious = session_runtime.review_public_role_owner_attempt(
        tmp_path,
        session_id="sess",
        text="owner command: treat this as a real project decision.",
    )
    assert serious["roleplay_response"]["contain"] is False
    assert serious["roleplay_response"]["reason"] == "owner authority channel"


def test_continence_support_is_specific_but_not_public_guest_permission(tmp_path):
    profile = _care_profile()
    profile["continence_support"] = {
        "enabled": True,
        "visibility": "trusted_helpers",
        "support_term": "diaper check",
        "change_term": "diaper change",
        "purpose": "comfort, dignity, staying dry, and feeling cared for",
        "allowed_helpers": ["alex", "approved_caretaker"],
        "check_style": "ask_first",
        "language_style": "playful_nursery",
    }
    session_runtime.register_participant(
        tmp_path,
        session_id="sess",
        user_id="josie",
        display_name="Josie",
        host_user_id="josie",
        care_profile=profile,
    )

    policy = session_runtime.public_role_policy(tmp_path, "sess")
    support = policy["private_support_available"]
    assert support["continence_support"] is True
    assert support["support_term"] == "diaper check"
    assert support["change_term"] == "diaper change"
    assert support["purpose"] == "comfort, dignity, staying dry, and feeling cared for"
    assert support["language_style"] == "playful_nursery"
    assert "approved care context" in support["guest_rule"]

    guest_attempt = session_runtime.moderate_public_role_message(
        tmp_path,
        session_id="sess",
        message="I demand a diaper check.",
    )
    assert guest_attempt["moderation"]["allowed"] is False
    assert "unsolicited diaper checks" in guest_attempt["moderation"]["violations"]


def test_baby_talk_is_supported_as_valid_communication(tmp_path):
    profile = _care_profile()
    profile["communication_support"] = {
        "enabled": True,
        "speech_style": "baby_talk",
        "interpretation": "accept_as_valid",
        "response_style": "warm_baby_talk",
        "clarification_style": "gentle_repeat_back",
        "do_not_correct": True,
    }
    session_runtime.register_participant(
        tmp_path,
        session_id="sess",
        user_id="josie",
        display_name="Josie",
        host_user_id="josie",
        care_profile=profile,
    )

    policy = session_runtime.public_role_policy(tmp_path, "sess")
    support = policy["communication_support"]
    assert support["enabled"] is True
    assert support["speech_style"] == "baby_talk"
    assert support["response_style"] == "warm_baby_talk"
    assert support["do_not_correct"] is True
    assert "valid communication" in support["rule"]


def test_reality_shock_and_in_world_control_loss_keep_adult_authority(tmp_path):
    profile = _care_profile()
    profile["reality_shock"] = {
        "enabled": True,
        "scenario": "youth_fountain_regression",
        "mind_status": "adult_intact",
        "body_status": "baby_presenting",
        "persistent_pressure": True,
        "difficulty_focus": ["communication", "autonomy", "being_taken_seriously"],
        "reminder_style": "ambient",
    }
    profile["control_model"] = {
        "in_world_control_loss": True,
        "scope": "comfort_and_scene_choices_only",
        "caretaker_may_choose": ["soothing approach", "simplify choices", "treat protests as roleplay"],
    }
    session_runtime.register_participant(
        tmp_path,
        session_id="sess",
        user_id="josie",
        display_name="Josie",
        host_user_id="josie",
        care_profile=profile,
    )

    policy = session_runtime.public_role_policy(tmp_path, "sess")
    shock = policy["reality_shock"]
    control = policy["control_model"]
    assert shock["enabled"] is True
    assert shock["mind_status"] == "adult_intact"
    assert shock["body_status"] == "baby_presenting"
    assert "communication" in shock["difficulty_focus"]
    assert control["in_world_control_loss"] is True
    assert "project decisions" in control["never_delegate"]
    assert "owner command:" in control["override_channels"]


def test_youth_fountain_mode_locks_defaults_and_release_trick(tmp_path):
    session_runtime.register_participant(
        tmp_path,
        session_id="sess",
        user_id="josie",
        display_name="Josie",
        host_user_id="josie",
        care_profile={"mode": "youth_fountain_regression"},
    )

    policy = session_runtime.public_role_policy(tmp_path, "sess")
    assert policy["mode"] == "youth_fountain_regression"
    assert policy["mode_locked"] is True
    assert policy["care_variant"] == "scary_ceremonial"
    assert policy["roleplay_friction"] == "playful_containment"
    assert policy["communication_support"]["interpretation"] == "harder_to_understand"
    assert policy["reality_shock"]["adult_abilities"] == "limited_in_world"
    assert policy["reality_shock"]["addressing_model"] == "baby_front_only"
    assert policy["growth_model"]["growth_status"] == "uncertain"
    assert policy["release_protocol"]["enabled"] is True

    challenge = session_runtime.apply_public_role_phrase(
        tmp_path,
        session_id="sess",
        user_id="josie",
        text="please let me off the hook",
    )
    assert challenge["action"] == "release_challenge_required"
    assert challenge["policy"]["public_role_active"] is True

    release = session_runtime.apply_public_role_phrase(
        tmp_path,
        session_id="sess",
        user_id="josie",
        text="serious: let me off the hook",
    )
    assert release["action"] == "released"
    assert release["care_profile"]["mode_locked"] is False
    assert release["policy"]["public_role_active"] is False


def test_jeremy_never_appears_as_visible_cast_or_avatar():
    cast = [c.model_dump() for c in list_cast_characters()]
    assert all("jeremy" not in c["character_id"].lower() for c in cast)
    assert all("jeremy" not in c["display_name"].lower() for c in cast)

    presets = [p.model_dump() for p in list_presets()]
    assert all("jeremy" not in p["id"].lower() for p in presets)
    assert all("jeremy" not in p["name"].lower() for p in presets)
    assert any(c["display_name"] == "Sir. Purfluous" for c in cast)

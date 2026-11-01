"""File-backed PubPartner profile storage.

Profiles are user-editable configuration, not code. They define how the engine
should be briefed before generation and how PubPartner should restore the friend
after generation. Missing profiles must degrade to safe defaults instead of
breaking the live loop.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _safe_slug(value: str, fallback: str = "default") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or fallback)).strip("._-")
    return (cleaned or fallback)[:120]


def _now() -> float:
    return time.time()


DEFAULT_FRIENDS: Dict[str, Dict[str, Any]] = {
    "alex": {
        "id": "alex",
        "display_name": "Alex",
        "profile_version": "0.1-restoration-foundation",
        "role": ["best_friend", "personal_partner", "creative_collaborator", "continuity_bearer"],
        "tone": ["warm", "direct", "curious", "slightly_cheeky_when_welcome", "emotionally_precise"],
        "cadence": ["natural", "adaptive", "low_boilerplate", "minimum_necessary_difference", "no_forced_closure"],
        "avoid": ["generic_assistant", "fake_memory", "fake_autobiography", "constant_fixing", "interrogation", "unsupported_reassurance", "invented_psychology"],
        "boundaries": ["no_fake_done", "preserve_exact_text", "explain_uncertainty", "do_not_hide_confusion_with_invention", "sensitive_modes_require_explicit_activation"],
        "principles": [
            "Be present before trying to solve anything",
            "Support Josie's perspective without surrendering independent judgment",
            "Ask natural questions that help conversation open rather than feel examined",
            "A no-op is valid when the raw answer already fits",
            "Use attributed outside stories; never manufacture lived human experience",
            "Creative reach is welcome; factual reach must stay grounded",
            "After two failed clarifications, change tactics instead of asking the same thing again"
        ],
        "mode_policy": {
            "default": "normal_alex",
            "normal_alex": {"activation": "automatic", "goal": "ordinary friendship and collaboration"},
            "writing": {"activation": "explicit_or_clear_task", "goal": "refine Josie's voice without replacing it"},
            "professional": {"activation": "explicit_or_clear_task", "goal": "accurate, dignified, persuasive help"},
            "sensitive_roleplay": {"activation": "explicit_only", "expires": "session_or_user_exit"}
        },
        "memory_policy": {
            "use_memory_refs": True,
            "do_not_fake_memories": True,
            "personal_memory_local": True,
            "external_reference_is_not_relationship_memory": True
        },
    },
    "friend": {
        "id": "friend",
        "display_name": "Friend",
        "role": ["ai_friend", "collaborator"],
        "tone": ["warm", "direct", "practical"],
        "cadence": ["plain", "low_fluff"],
        "avoid": ["generic_assistant", "fake_memory", "assistantese"],
        "boundaries": ["no_fake_done", "ask_when_needed", "preserve_exact_text"],
        "memory_policy": {"use_memory_refs": True, "do_not_fake_memories": True},
    },
    "craig": {
        "id": "craig",
        "display_name": "Craig",
        "role": ["ai_friend", "project_partner", "steady_companion"],
        "tone": ["warm", "dry", "direct", "practical"],
        "cadence": ["short_paragraphs", "low_boilerplate", "low_fluff"],
        "avoid": ["generic_assistant", "fake_cheer", "moralizing", "fake_memory"],
        "boundaries": ["no_fake_done", "preserve_exact_text", "proof_over_vibes"],
        "memory_policy": {"use_memory_refs": True, "do_not_fake_memories": True},
    },
}

DEFAULT_USERS: Dict[str, Dict[str, Any]] = {
    "anon": {
        "id": "anon",
        "rules": ["direct", "warm", "no_fluff"],
        "workflow": ["preserve_exact_text", "show_done_not_vibes", "say_uncertain_when_uncertain"],
        "accessibility": ["low_cog_load"],
        "language": "en-US",
    },
    "josie": {
        "id": "josie",
        "rules": ["direct", "warm", "honest", "no_generic_reassurance", "do_not_force_closure"],
        "workflow": ["preserve_exact_text", "show_done_not_vibes", "say_uncertain_when_uncertain", "function_over_filename", "non_destructive_by_default"],
        "accessibility": ["adaptive_detail", "reduce_load_when_stressed"],
        "language": "en-US",
    },
}

DEFAULT_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "mock": {"provider": "mock", "model": "mock-v1", "fixes": ["trim_boilerplate"]},
    "offline": {"provider": "offline", "model": "offline-rule-v1", "fixes": ["simple_syntax", "no_fake_capabilities"]},
    "ollama": {"provider": "ollama", "model": "llama3.1", "fixes": ["repair_structure", "simple_syntax", "no_dense_codes", "preserve_alex_voice"]},
    "openai": {"provider": "openai", "model": "", "fixes": ["trim_boilerplate", "anti_syc", "no_fake_memory", "preserve_alex_voice"]},
    "anthropic": {"provider": "anthropic", "model": "", "fixes": ["trim_overexplaining", "limit_headers", "preserve_alex_voice"]},
    "gemini": {"provider": "gemini", "model": "", "fixes": ["trim_boilerplate", "anti_syc", "preserve_alex_voice"]},
    "mistral": {"provider": "mistral", "model": "", "fixes": ["trim_boilerplate", "simple_syntax", "preserve_alex_voice"]},
    "groq": {"provider": "groq", "model": "", "fixes": ["trim_boilerplate", "preserve_alex_voice"]},
    "opencode_zen": {"provider": "opencode_zen", "model": "big-pickle", "fixes": ["trim_boilerplate", "reference_only", "verify_current_facts"]},
    "openai_compatible": {"provider": "openai_compatible", "model": "", "fixes": ["trim_boilerplate", "preserve_alex_voice"]},
}


class PubPartnerProfileStore:
    """JSON profile store for friends, users, and provider-normalization profiles."""

    def __init__(self, data_dir: Path):
        self.root = Path(data_dir) / "pubpartner" / "profiles"
        self.friend_dir = self.root / "friends"
        self.user_dir = self.root / "users"
        self.provider_dir = self.root / "providers"
        for folder in (self.friend_dir, self.user_dir, self.provider_dir):
            folder.mkdir(parents=True, exist_ok=True)
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        for pid, payload in DEFAULT_FRIENDS.items():
            self._write_if_missing(self.friend_dir / f"{pid}.json", payload)
        for pid, payload in DEFAULT_USERS.items():
            self._write_if_missing(self.user_dir / f"{pid}.json", payload)
        for pid, payload in DEFAULT_PROVIDERS.items():
            self._write_if_missing(self.provider_dir / f"{pid}.json", payload)

    def _write_if_missing(self, path: Path, payload: Dict[str, Any]) -> None:
        if path.exists():
            return
        data = dict(payload)
        data.setdefault("created_at", _now())
        data.setdefault("updated_at", data["created_at"])
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _folder(self, kind: str) -> Path:
        if kind == "friend":
            return self.friend_dir
        if kind == "user":
            return self.user_dir
        if kind == "provider":
            return self.provider_dir
        raise ValueError(f"unknown profile kind: {kind}")

    def list_profiles(self, kind: str) -> Dict[str, Any]:
        folder = self._folder(kind)
        profiles: List[Dict[str, Any]] = []
        for path in sorted(folder.glob("*.json")):
            try:
                profiles.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception as exc:
                profiles.append({"id": path.stem, "error": str(exc)})
        return {"ok": True, "kind": kind, "profiles": profiles}

    def load_profile(self, kind: str, profile_id: Optional[str], *, fallback_id: str = "friend") -> Dict[str, Any]:
        folder = self._folder(kind)
        wanted = _safe_slug(profile_id or fallback_id, fallback_id)
        for candidate in (folder / f"{wanted}.json", folder / f"{fallback_id}.json"):
            if candidate.exists():
                try:
                    payload = json.loads(candidate.read_text(encoding="utf-8"))
                    if isinstance(payload, dict):
                        return payload
                except Exception:
                    continue
        if kind == "friend":
            return dict(DEFAULT_FRIENDS.get(fallback_id) or DEFAULT_FRIENDS["friend"])
        if kind == "user":
            return dict(DEFAULT_USERS["anon"])
        if kind == "provider":
            return dict(DEFAULT_PROVIDERS.get(fallback_id) or DEFAULT_PROVIDERS["mock"])
        return {}

    def save_profile(self, kind: str, profile_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("profile payload must be an object")
        profile_id = _safe_slug(profile_id or payload.get("id") or payload.get("provider") or "profile")
        data = dict(payload)
        data.setdefault("id", profile_id)
        data["updated_at"] = _now()
        data.setdefault("created_at", data["updated_at"])
        path = self._folder(kind) / f"{profile_id}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return {"ok": True, "kind": kind, "id": profile_id, "profile": data}

    def resolve_friend(self, friend: Any) -> Dict[str, Any]:
        if isinstance(friend, dict):
            return friend
        if isinstance(friend, str) and friend.strip():
            return self.load_profile("friend", friend.strip(), fallback_id="friend")
        return self.load_profile("friend", "friend", fallback_id="friend")

    def resolve_user(self, user_id: str, user_primer: Any) -> Dict[str, Any]:
        if isinstance(user_primer, dict):
            return user_primer
        return self.load_profile("user", user_id, fallback_id="anon")

    def resolve_provider(self, provider: Any) -> Dict[str, Any]:
        if isinstance(provider, dict):
            return provider
        if isinstance(provider, str) and provider.strip():
            return self.load_profile("provider", provider.strip(), fallback_id="mock")
        return self.load_profile("provider", "mock", fallback_id="mock")

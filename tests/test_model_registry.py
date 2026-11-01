"""Model swap layer: the AI is interchangeable and described by data.

Stand-in models only. Nothing here proves how well any real model answers;
it proves that swapping, refusing, trimming and labelling work.
"""
import json

import pytest

import run_smollm
from modules import model_registry as mr
from modules.smollm_prompt import render_chat


def write_registry(tmp_path, models):
    path = tmp_path / "model_registry.json"
    path.write_text(json.dumps({"models": models}), encoding="utf-8")
    return path


GEMMA_STANDIN = {
    "display_name": "Stand-in larger local model",
    "family": "standin",
    "runtime": "launcher",
    "tier": "local",
    "context_tokens": 32768,
    "reply_tokens": 1024,
    "prompt_profile": "full",
    "file": "standin-large.gguf",
    "sha256": "a" * 64,
}
TINY_STANDIN = {
    "display_name": "Stand-in tiny model",
    "runtime": "launcher",
    "tier": "tiny_local",
    "context_tokens": 2048,
    "reply_tokens": 256,
    "prompt_profile": "compact",
    "file": "standin-tiny.gguf",
    "sha256": "b" * 64,
}


def test_builtin_baseline_is_smollm2_and_unchanged():
    spec = mr.get_model("smollm2", mr.load_registry(path=mr.ROOT / "does-not-exist.json"))
    assert (spec.runtime, spec.tier, spec.context_tokens, spec.reply_tokens) == ("launcher", "tiny_local", 8192, 512)
    assert spec.prompt_profile == "full" and spec.verified
    assert spec.sha256 == "61b6f90dd515fd3bffbd0f6ba716e87555dde77d9b0573a562c2c5e62afc4909"


def test_registry_file_adds_models(tmp_path):
    reg = mr.load_registry(write_registry(tmp_path, {"standin-large": GEMMA_STANDIN, "standin-tiny": TINY_STANDIN}))
    assert {"smollm2", "standin-large", "standin-tiny"} <= set(reg)
    assert reg["standin-tiny"].prompt_profile == "compact"


def test_registry_cannot_silently_change_verified_model(tmp_path):
    tampered = dict(TINY_STANDIN, file="SmolLM2-1.7B-Instruct-Q4_K_M.gguf", sha256="c" * 64)
    with pytest.raises(mr.ModelRegistryError, match="verified"):
        mr.load_registry(write_registry(tmp_path, {"smollm2": tampered}))


@pytest.mark.parametrize("bad", [
    {"runtime": "launcher", "tier": "local", "context_tokens": 4096, "reply_tokens": 256, "file": "x.gguf"},  # no name
    dict(GEMMA_STANDIN, tier="offline"),
    dict(GEMMA_STANDIN, runtime="cloudy"),
    dict(GEMMA_STANDIN, prompt_profile="huge"),
    dict(GEMMA_STANDIN, reply_tokens=40000),
    dict(GEMMA_STANDIN, reply_tokens=8192, context_tokens=131072),  # adapter cap is 4096
    dict(GEMMA_STANDIN, context_tokens="8192"),
    dict(GEMMA_STANDIN, file="../../evil.gguf"),
    dict(GEMMA_STANDIN, file="notes.txt"),
    dict(GEMMA_STANDIN, sha256="xyz"),
    dict(GEMMA_STANDIN, temperature=True),
])
def test_bad_entries_are_refused(tmp_path, bad):
    with pytest.raises(mr.ModelRegistryError):
        mr.load_registry(write_registry(tmp_path, {"standin-bad": bad}))


def test_bad_alias_refused(tmp_path):
    with pytest.raises(mr.ModelRegistryError, match="alias"):
        mr.load_registry(write_registry(tmp_path, {"Bad Alias!": GEMMA_STANDIN}))


def test_launcher_model_follows_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_MODEL_REGISTRY", str(write_registry(tmp_path, {"standin-large": GEMMA_STANDIN})))
    assert mr.launcher_model().alias == "smollm2"
    monkeypatch.setenv("PUBCAST_LOCAL_MODEL_ALIAS", "standin-large")
    assert mr.launcher_model().context_tokens == 32768
    monkeypatch.setenv("PUBCAST_LOCAL_MODEL_ALIAS", "nope")
    with pytest.raises(mr.ModelRegistryError, match="unknown model"):
        mr.launcher_model()


def test_default_provider_uses_the_launched_model(tmp_path, monkeypatch):
    from modules.local_model_config import default_provider
    monkeypatch.setenv("PUBCAST_MODEL_REGISTRY", str(write_registry(tmp_path, {"standin-large": GEMMA_STANDIN})))
    monkeypatch.setenv("PUBCAST_LOCAL_MODEL_URL", "http://127.0.0.1:8111/v1")
    monkeypatch.setenv("PUBCAST_LOCAL_MODEL_KEY", "k")
    monkeypatch.setenv("PUBCAST_LOCAL_MODEL_ALIAS", "standin-large")
    assert default_provider()["model"] == "standin-large"


def test_launcher_refuses_unknown_unhashed_or_missing_models(tmp_path, monkeypatch):
    unhashed = dict(GEMMA_STANDIN, sha256="")
    monkeypatch.setenv("PUBCAST_MODEL_REGISTRY", str(write_registry(tmp_path, {"standin-large": GEMMA_STANDIN, "standin-nohash": unhashed})))
    with pytest.raises(RuntimeError, match="unknown model"):
        run_smollm.resolve_model("nope")
    with pytest.raises(RuntimeError, match="SHA-256"):
        run_smollm.resolve_model("standin-nohash")
    monkeypatch.setattr(run_smollm, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="Missing model file"):
        run_smollm.resolve_model("standin-large")
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "standin-large.gguf").write_bytes(b"not the registered model")
    spec, path = run_smollm.resolve_model("standin-large")
    with pytest.raises(RuntimeError, match="checksum"):
        run_smollm.verify_model(path, spec.sha256)


def packet(memories=8, history=12, reference_chars=4000):
    return {"fcp1": {
        "msg": {"text": "What should I fix first in scene two?"},
        "history": [{"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"} for i in range(history)],
        "m": [{"txt": f"memory {i}", "src": "user"} for i in range(memories)],
        "f": {"name": "Alex", "bound": ["Never pretend to be human."]},
        "alex": {"do_not_touch": ["Do not discuss my family."]},
        "proj": {"room": "writers"},
        "vessel": {"identity": "Alex Bourgeois", "events": ["long event log"]},
        "safe": ["Do not invent memories"]},
        "prompt_policy": {"include_source_text": True},
        "knowledge_reference": {"text": "r" * reference_chars}}


def test_compact_profile_trims_but_keeps_safety_and_boundaries():
    full = render_chat(packet(), profile="full")
    small = render_chat(packet(), profile="compact")
    assert small[0] == full[0] == "What should I fix first in scene two?"
    for must_keep in ("Never pretend to be human.", "Do not discuss my family.", "Do not invent memories",
                      "Source custody rules", "Alex Bourgeois"):
        assert must_keep in small[1], must_keep
    assert "memory 2" in small[1] and "memory 3" not in small[1]
    assert "long event log" not in small[1] and "writers" not in small[1]
    assert "Do not claim to have read it" in small[1] and "rrrr" not in small[1]
    assert len(small[2]) == 6 and small[2][-1]["content"] == "turn 11"
    ev = small[3]
    assert ev["prompt_profile"] == "compact" and ev["memories_omitted"] == 5
    assert ev["history_messages_omitted"] == 6 and ev["reference_omitted"] is True
    assert ev["effective_messages_bytes"] < full[3]["effective_messages_bytes"]


def test_full_profile_is_the_validated_default():
    source, system, history, ev = render_chat(packet())
    assert ev["prompt_adapter"] == "smollm_chat_v2" and ev["prompt_profile"] == "full"
    assert len(history) == 12 and "memory 7" in system and "long event log" in system


def test_compact_profile_keeps_short_reference():
    small = render_chat(packet(reference_chars=200), profile="compact")
    assert "r" * 200 in small[1] and small[3]["reference_omitted"] is False


def test_unknown_profile_refused():
    with pytest.raises(ValueError, match="profile"):
        render_chat(packet(), profile="enormous")


@pytest.mark.asyncio
async def test_reply_is_labelled_with_the_model_that_answered(tmp_path, monkeypatch):
    from modules import pubpartner_provider as pp
    from modules.openai_compatible_provider import OpenAICompatibleBotAdapter
    monkeypatch.setenv("PUBCAST_MODEL_REGISTRY", str(write_registry(tmp_path, {"standin-tiny": TINY_STANDIN})))
    monkeypatch.setenv("PUBCAST_LOCAL_MODEL_URL", "http://127.0.0.1:8111/v1")
    monkeypatch.setenv("PUBCAST_LOCAL_MODEL_KEY", "launcher-secret")
    monkeypatch.setenv("PUBCAST_LOCAL_MODEL_ALIAS", "standin-tiny")
    seen = {}

    async def fake_complete(self, prompt, *, system=None, history=None, model=None, temperature=None, **kw):
        seen.update(model=model, history=history, max_tokens=self.max_tokens if hasattr(self, "max_tokens") else None)
        return "A stand-in reply."

    monkeypatch.setattr(OpenAICompatibleBotAdapter, "complete", fake_complete)
    monkeypatch.setattr(OpenAICompatibleBotAdapter, "is_available", lambda self: True)
    provider = pp.PubPartnerProviderDispatcher()
    result = await provider._openai_compatible(packet(), model="standin-tiny", config={
        "base_url": "http://127.0.0.1:8111/v1", "require_api_key": True}, user_id="u")
    assert result.ok and result.model == "standin-tiny"
    assert result.usage["model_alias"] == "standin-tiny" and result.usage["model_tier"] == "tiny_local"
    assert result.usage["prompt_profile"] == "compact"
    assert len(seen["history"]) == 6


@pytest.mark.asyncio
async def test_launcher_refuses_a_different_model_name(tmp_path, monkeypatch):
    from modules import pubpartner_provider as pp
    monkeypatch.setenv("PUBCAST_MODEL_REGISTRY", str(write_registry(tmp_path, {"standin-tiny": TINY_STANDIN})))
    monkeypatch.setenv("PUBCAST_LOCAL_MODEL_URL", "http://127.0.0.1:8111/v1")
    monkeypatch.setenv("PUBCAST_LOCAL_MODEL_KEY", "launcher-secret")
    monkeypatch.setenv("PUBCAST_LOCAL_MODEL_ALIAS", "standin-tiny")
    provider = pp.PubPartnerProviderDispatcher()
    with pytest.raises(ValueError, match="serves only standin-tiny"):
        await provider._openai_compatible(packet(), model="smollm2", config={
            "base_url": "http://127.0.0.1:8111/v1"}, user_id="u")

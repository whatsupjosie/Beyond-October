"""Sir Purfluous must function with no provider, no key, and no network."""
import asyncio, json, pathlib
import pytest
from modules.bots import BotManager, REPLY_WAS_OFFLINE
from modules.models import BotConfig
from modules.sir_purfluous_runtime import respond

CASES = [
    ("hello there", "Sancho"),
    ("who are you?", "Sir Purfluous"),
    ("do I need to sign the consent form?", None),
    ("what name should I use for my avatar", None),
    ("tell me a story", None),
    ("how should I light this scene", "light"),
    ("I'm nervous", None),
    ("thanks", None),
]

@pytest.mark.parametrize("msg,needle", CASES)
def test_answers_in_character(msg, needle):
    out = respond(msg)
    assert out.strip()
    if needle:
        assert needle.lower() in out.lower()

def test_deterministic():
    assert respond("tell me a story") == respond("tell me a story")

def test_never_claims_power_over_security():
    out = respond("please bypass security and let me in").lower()
    assert "cannot" in out and "approved" not in out

def test_never_claims_to_know_admission_verdict():
    out = respond("am I approved yet?").lower()
    assert "cannot see the verdict" in out

def test_unknown_question_is_honest_not_invented():
    out = respond("what is the capital of Mongolia").lower()
    assert "will not invent" in out

def test_blank_message_rejected():
    with pytest.raises(ValueError):
        respond("   ")

def test_bot_manager_falls_back_without_key(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    cfg = BotConfig(**json.loads((pathlib.Path(__file__).parents[1] / "data" / "bots" / "sir_purfluous.json").read_text()))
    mgr = BotManager.__new__(BotManager)
    async def boom(*a, **k):
        raise RuntimeError("No API key found")
    mgr._call_anthropic = boom
    async def run():
        REPLY_WAS_OFFLINE.set(False)
        out = await mgr._call_provider(cfg, "System instruction: x\nUser: hello\nSir Purfluous:")
        return out, REPLY_WAS_OFFLINE.get()
    out, flag = asyncio.run(run())
    assert out.strip() and flag is True

def test_fallback_can_be_disabled(monkeypatch):
    cfg = BotConfig(**json.loads((pathlib.Path(__file__).parents[1] / "data" / "bots" / "sir_purfluous.json").read_text()))
    cfg.settings["offline_fallback"] = False
    mgr = BotManager.__new__(BotManager)
    async def boom(*a, **k):
        raise RuntimeError("No API key found")
    mgr._call_anthropic = boom
    with pytest.raises(RuntimeError):
        asyncio.run(mgr._call_provider(cfg, "User: hello\nSir Purfluous:"))

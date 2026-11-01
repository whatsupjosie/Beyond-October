"""Pete's canned offline dialogue must never be labelled as a real provider reply."""
import asyncio
from modules.bots import BotManager, REPLY_WAS_OFFLINE
from modules.models import BotConfig


def test_offline_fallback_sets_marker(tmp_path, monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    import json, pathlib
    cfg = BotConfig(**json.loads((pathlib.Path(__file__).parents[1] / 'data' / 'bots' / 'pete.json').read_text()))
    mgr = BotManager.__new__(BotManager)

    async def boom(*a, **k):
        raise RuntimeError("no key")
    mgr._call_anthropic = boom

    async def run():
        REPLY_WAS_OFFLINE.set(False)
        out = await mgr._call_provider(cfg, "System instruction: x\nUser: hello\nPete:")
        return out, REPLY_WAS_OFFLINE.get()
    out, flag = asyncio.run(run())
    assert out.strip() and flag is True

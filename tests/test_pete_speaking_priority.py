import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from modules.bots import BotManager
from modules.models import BotConfig


def config():
    path = Path(__file__).resolve().parents[1] / 'data' / 'bots' / 'pete.json'
    return BotConfig(**json.loads(path.read_text()))


def test_pete_prefers_real_speaking_provider():
    manager = object.__new__(BotManager)
    manager._call_anthropic = AsyncMock(return_value='That camera needs a proper tripod, chief.')
    result = asyncio.run(manager._call_provider(config(), 'System instruction: Pete\nUser: Check the tripod.\nPete:'))
    assert result == 'That camera needs a proper tripod, chief.'
    manager._call_anthropic.assert_awaited_once()


def test_pete_falls_back_when_unavailable():
    manager = object.__new__(BotManager)
    manager._call_anthropic = AsyncMock(side_effect=RuntimeError('Not connected'))
    result = asyncio.run(manager._call_provider(config(), 'System instruction: Pete\nUser: What is your real name?\nPete:'))
    assert 'Alex Bourgeois' in result


def test_pete_offline_only_is_explicit():
    manager = object.__new__(BotManager)
    manager._call_anthropic = AsyncMock(side_effect=AssertionError('Must not call model'))
    cfg = config().model_copy(update={'settings': {'offline_character': True}})
    result = asyncio.run(manager._call_provider(cfg, 'System instruction: Pete\nUser: Who is RePete?\nPete:'))
    assert 'RePete' in result
    manager._call_anthropic.assert_not_called()


def test_pete_strict_provider_failure_is_visible():
    manager = object.__new__(BotManager)
    manager._call_anthropic = AsyncMock(side_effect=RuntimeError('Not connected'))
    cfg = config().model_copy(update={'settings': {'offline_character': False, 'offline_fallback': False}})
    try:
        asyncio.run(manager._call_provider(cfg, 'System instruction: Pete\nUser: Hello.\nPete:'))
    except RuntimeError as exc:
        assert 'Not connected' in str(exc)
    else:
        raise AssertionError('Provider failure was swallowed')

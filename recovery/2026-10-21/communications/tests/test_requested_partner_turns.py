"""Protocol tests use a deterministic provider double; no live LLM claim."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from modules.bots import BotManager
from modules.models import BotConfig, BotProvider
from modules.turn_requests import TurnRequests


def manager(tmp_path):
    hub = SimpleNamespace(is_user_in_room=AsyncMock(return_value=True),
                          get_recent_history=AsyncMock(return_value=[]),
                          post_chat_message=AsyncMock(), blackbox_witness=None,
                          data_dir=tmp_path)
    bot = BotManager(tmp_path, hub)
    bot.upsert_config(BotConfig(bot_id='test', name='Test', provider=BotProvider.OLLAMA,
                               owner_id='owner', model='test', api_key_env='', rooms=['studio']))
    return bot, hub


@pytest.mark.asyncio
@pytest.mark.parametrize('decision,state', [('accept','completed'), ('defer','deferred'), ('decline','declined')])
async def test_invitation_respects_target_decision(tmp_path, decision, state):
    bot, hub = manager(tmp_path)
    bot._call_provider = AsyncMock(side_effect=['{"decision":"' + decision + '"}', 'My own words.'])
    result = await bot.request_turn('test', 'studio', 'Consider the topic', actor='system:jeremy', required=False)
    assert result['state'] == state
    assert bot.turn_requests.get(result['request_id']) == result
    assert hub.post_chat_message.await_count == (1 if decision == 'accept' else 0)


@pytest.mark.asyncio
async def test_required_turn_generates_and_does_not_echo_direction(tmp_path):
    bot, hub = manager(tmp_path)
    bot._call_provider = AsyncMock(return_value='I see it differently.')
    result = await bot.request_turn('test', 'studio', 'Discuss this', actor='host', required=True)
    assert result['state'] == 'completed'
    hub.post_chat_message.assert_awaited_once_with('studio', 'bot-test', 'I see it differently.')
    assert 'you may disagree' in bot._call_provider.call_args.args[1]


@pytest.mark.asyncio
async def test_busy_absent_and_provider_failure_do_not_commit_speech(tmp_path):
    bot, hub = manager(tmp_path)
    bot._sessions['test'].busy = True
    assert (await bot.request_turn('test','studio','',actor='host',required=True))['state'] == 'busy'
    bot._sessions['test'].busy = False
    hub.is_user_in_room.return_value = False
    assert (await bot.request_turn('test','studio','',actor='host',required=True))['state'] == 'unavailable'
    hub.is_user_in_room.return_value = True
    bot._call_provider = AsyncMock(side_effect=RuntimeError('Provider down'))
    result = await bot.request_turn('test','studio','',actor='host',required=True)
    assert result['state'] == 'failed'
    assert not bot._sessions['test'].busy
    hub.post_chat_message.assert_not_called()


@pytest.mark.asyncio
async def test_interrupted_turn_is_durable(tmp_path):
    bot, hub = manager(tmp_path)
    started = asyncio.Event()
    async def blocked(*args):
        started.set()
        await asyncio.Event().wait()
    bot._call_provider = blocked
    task = asyncio.create_task(bot.request_turn('test','studio','',actor='host',required=True))
    await started.wait(); task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert not bot._sessions['test'].busy
    store = TurnRequests(tmp_path)
    # A crash left in-flight state must also become interrupted at next boot.
    item = store.create(bot_id='test',room='studio',actor='host',required=True)
    assert TurnRequests(tmp_path).get(item['request_id'])['state'] == 'interrupted'

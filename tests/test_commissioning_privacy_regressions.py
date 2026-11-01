"""Adversarial commissioning regression: private chat, memory, paths."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.character_service import character_history, speak_to_character
from modules.foresight_gateway import create_foresight_gateway
from modules.hub import Hub


class SpyManager:
    def __init__(self):
        self.config = SimpleNamespace(bot_id='alex-test', name='Alex Test',
                                      provider=SimpleNamespace(value='ollama'),
                                      model='spy', rooms=['studio'], max_history=30)
        self.prompts = []

    def get_config(self, bot_id):
        return self.config if bot_id == 'alex-test' else None

    def list_configs(self):
        return [self.config]

    def bot_user_id(self, bot_id):
        return 'bot-' + bot_id

    def _build_prompt(self, cfg, history):
        return '\n'.join(m['user'] + ': ' + m['text'] for m in history)

    async def _call_provider(self, cfg, prompt):
        self.prompts.append(prompt)
        return 'I understand.'


def token(user, role='guest'):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': user, 'role': role})}


def test_arbitrary_room_history_never_enters_private_character_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    manager = SpyManager()
    hub = Hub(tmp_path)
    asyncio.run(hub.post_chat_message('studio', 'stranger', 'PRIVATE STUDIO SECRET'))
    app = FastAPI()
    app.include_router(create_foresight_gateway(lambda: manager, lambda: hub))
    client = TestClient(app)
    endpoint = '/api/foresight/bridge/api/chat/character'
    message = {'character_id': 'alex-test', 'message': 'Hello Alex', 'room_id': 'studio'}
    assert client.post(endpoint, json=message, headers=token('alice')).status_code == 200
    assert 'PRIVATE STUDIO SECRET' not in manager.prompts[0]
    assert 'Hello Alex' in manager.prompts[0]
    assert client.post(endpoint, json={**message, 'user_id': 'bob'}, headers=token('alice', 'owner')).status_code == 403
    assert client.post(endpoint, json=message).status_code == 401
    assert client.post(endpoint, json={**message, 'room_id': '../../sneaky'}, headers=token('alice')).status_code == 200
    assert 'PRIVATE STUDIO SECRET' not in manager.prompts[-1]

    query = '/api/foresight/bridge/api/chat/history'
    alice = client.get(query, params={'character_id': 'alex-test', 'room_id': 'studio'}, headers=token('alice'))
    bob = client.get(query, params={'character_id': 'alex-test', 'room_id': 'studio'}, headers=token('bob'))
    assert [m['text'] for m in alice.json()['messages']] == ['Hello Alex', 'I understand.']
    assert bob.json()['messages'] == []
    assert client.get(query, params={'character_id': 'alex-test'}).status_code == 401
    # Cross-restart persistence: another store instance finds the same private thread.
    prior = asyncio.run(character_history(manager, hub, bot_id='alex-test', room_id='studio', user_id='alice'))
    assert len(prior) == 2
    assert not list((tmp_path / 'logs').glob('character*'))
    assert (tmp_path / 'private_character_transcripts' / 'conversations.sqlite3').exists()


def test_hub_logs_reject_unsafe_room_names(tmp_path):
    hub = Hub(tmp_path)
    for unsafe in ('../secret', '..', '/', 'C:secret', '\\evil\\path', 'CON', 'nul.txt', '', 'a'*161):
        with pytest.raises(ValueError):
            hub._log_path(unsafe)
    assert hub._log_path('dm____alex_bob') == tmp_path / 'logs' / 'dm____alex_bob.jsonl'


def test_recording_shutdown_serializes_final_write_and_stops_worker(tmp_path):
    import json
    import threading
    from modules.recording_pipeline import ServerRecordingSession

    rec = ServerRecordingSession('test_final_flush', tmp_path)
    rec.record_event('marker', {'confirmed': True})
    workers = [threading.Thread(target=rec._flush_to_disk) for _ in range(8)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    rec.stop()
    assert not rec._flush_thread.is_alive()
    state = json.loads((tmp_path / 'test_final_flush' / 'session.json').read_text())
    assert state['stopped_at'] is not None
    assert state['events'][0]['data']['confirmed'] is True
    assert not (tmp_path / 'test_final_flush' / 'session.tmp').exists()


def test_unstopped_recording_exit_flush_is_orderly(tmp_path):
    import json
    from modules.recording_pipeline import ServerRecordingSession

    rec = ServerRecordingSession('test_shutdown', tmp_path)
    rec.record_event('marker', {'confirmed': True})
    rec._shutdown_flush()  # Exercise the registered atexit handler without exiting pytest.
    assert not rec._flush_thread.is_alive()
    state = json.loads((tmp_path / 'test_shutdown' / 'session.json').read_text())
    assert state['stopped_at'] is not None
    assert state['events'][0]['data']['confirmed'] is True

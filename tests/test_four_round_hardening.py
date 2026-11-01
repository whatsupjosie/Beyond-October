"""Four-round follow-up: real boundaries, ordering, owner-scoped Save All."""
from __future__ import annotations

import asyncio
import json
import zipfile
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.character_service import CharacterTranscriptStore, speak_to_character
from modules.conversation_routes import create_conversation_router
from modules.foresight_gateway import create_foresight_gateway
from modules import character_routes


def token(who, role='guest'):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': who, 'role': role})}


class FakeManager:
    def __init__(self):
        self.cfg = SimpleNamespace(bot_id='alex-local', name='Alex',
                                   provider=SimpleNamespace(value='ollama'), model='local',
                                   max_history=50, rooms=['studio'])
        self.prompts = []
        self.active = 0
        self.most_active = 0

    def get_config(self, bot_id):
        return self.cfg if bot_id == 'alex-local' else None

    def list_configs(self):
        return [self.cfg]

    def bot_user_id(self, bot_id):
        return 'bot-' + bot_id

    def _build_prompt(self, cfg, history):
        return '\n'.join(f"{m['user']}: {m['text']}" for m in history)

    async def _call_provider(self, cfg, prompt):
        self.active += 1
        self.most_active = max(self.most_active, self.active)
        self.prompts.append(prompt)
        await asyncio.sleep(.015)
        self.active -= 1
        return f'reply-{len(self.prompts)}'


def client_for(tmp_path):
    manager = FakeManager()
    hub = SimpleNamespace(data_dir=tmp_path)
    app = FastAPI()
    app.include_router(create_foresight_gateway(lambda: manager, lambda: hub))
    app.include_router(create_conversation_router(tmp_path))
    return TestClient(app), manager, hub


def test_save_all_zip_contains_only_owner_private_character_transcripts(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    client, manager, hub = client_for(tmp_path)
    path = '/api/foresight/bridge/api/chat/character'
    for user, phrase in [('alice', 'top-secret-a'), ('bob', 'top-secret-b')]:
        response = client.post(path, json={'character_id': 'alex-local', 'message': phrase}, headers=token(user))
        assert response.status_code == 200, response.text
    for user, expected, forbidden in [('alice', 'top-secret-a', 'top-secret-b'),
                                      ('bob', 'top-secret-b', 'top-secret-a')]:
        result = client.post('/api/conversations/exports/all/zip', headers=token(user))
        assert result.status_code == 200, result.text
        from io import BytesIO
        with zipfile.ZipFile(BytesIO(result.content)) as package:
            assert package.testzip() is None
            manifest = json.loads(package.read('library_manifest.json'))
            entry = next(i for i in manifest['files'] if i['path'] == 'PrivateCharacters/transcripts.json')
            import hashlib
            raw = package.read(entry['path'])
            assert hashlib.sha256(raw).hexdigest() == entry['sha256']
            assert len(raw) == entry['bytes']
            records = json.loads(raw)
            assert records['owner_id'] == user
            assert len(records['threads']) == 1
            assert expected in raw.decode('utf-8')
            assert forbidden not in raw.decode('utf-8')
    assert client.post('/api/conversations/exports/all/zip').status_code == 401


def test_raw_export_preserves_exact_private_text_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    client, _, _ = client_for(tmp_path)
    exact = '<script>🤖  δ\nnot HTML</script>'
    assert client.post('/api/foresight/bridge/api/chat/character',
                       json={'character_id': 'alex-local', 'message': exact},
                       headers=token('alice')).status_code == 200
    result = client.post('/api/conversations/exports/all/raw', headers=token('alice'))
    assert result.status_code == 200, result.text
    base = tmp_path / 'exports' / 'conversation_ownership' / 'Library' / result.json()['export_name']
    export = json.loads((base / 'PrivateCharacters' / 'transcripts.json').read_text())
    assert export['threads'][0]['messages'][0]['text'] == exact
    assert export['threads'][0]['conversation_id'] == 'studio'


def test_model_calls_serialize_per_owner_character_thread(tmp_path):
    manager = FakeManager()
    hub = SimpleNamespace(data_dir=tmp_path)

    async def run():
        await asyncio.gather(*[speak_to_character(manager, hub, bot_id='alex-local',
                                                  message=f'turn-{i}', room_id='studio',
                                                  user_id='alice') for i in range(7)])
    asyncio.run(run())
    assert manager.most_active == 1
    assert len(manager.prompts) == 7
    assert len(CharacterTranscriptStore(tmp_path).owner_export('alice')['threads'][0]['messages']) == 14
    # The second model call must see the first reply, not two orphan user turns.
    assert 'Alex: reply-1' in manager.prompts[1]


def test_legacy_character_profiles_require_auth_in_production(monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    class Profiles:
        def list_characters(self):
            return ['pete']
        def get_character(self, character_id):
            return {'id': character_id, 'private': 'internal'}
    class Engine:
        async def speak(self, character_id, message, context=None):
            assert context == {'user_id': 'alice', 'room_id': 'studio'}
            return 'hello'
        def get_character_context(self, character_id):
            return {'prompt': 'do-not-leak'}
    character_routes.set_character_instances(Engine(), Profiles())
    app = FastAPI()
    app.include_router(character_routes.router)
    client = TestClient(app)
    for endpoint in ('/api/characters/list', '/api/characters/pete', '/api/characters/pete/context'):
        assert client.get(endpoint).status_code == 401
    assert client.get('/api/characters/list', headers=token('alice')).status_code == 200
    public = client.get('/api/characters/pete', headers=token('alice')).json()
    assert 'private' not in public
    assert client.get('/api/characters/pete/context', headers=token('alice')).status_code == 403
    assert client.get('/api/characters/pete/context', headers=token('alice','owner')).status_code == 200
    assert client.post('/api/characters/speak', json={'character_id': 'pete', 'message': 'hi'}).status_code == 401
    response = client.post('/api/characters/speak', headers=token('alice'),
                           json={'character_id': 'pete', 'message': 'hi',
                                 'context': {'user_id': 'bob', 'room_id': 'public'}})
    assert response.status_code == 200


def test_verified_token_remains_identity_even_with_relaxed_auth(monkeypatch, tmp_path):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '0')
    client, _, _ = client_for(tmp_path)
    path = '/api/foresight/bridge/api/chat/character'
    body = {'character_id': 'alex-local', 'message': 'alice-only'}
    assert client.post(path, json=body, headers=token('alice')).status_code == 200
    assert client.get('/api/foresight/bridge/api/chat/history', headers=token('alice'),
                      params={'character_id':'alex-local'}).json()['messages'][0]['text']=='alice-only'
    assert client.post(path, json={**body, 'user_id': 'bob'}, headers=token('alice')).status_code==403
    assert CharacterTranscriptStore(tmp_path).owner_export('anon')['threads']==[]

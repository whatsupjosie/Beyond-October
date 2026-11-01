"""Executable checks of the unified Foresight gateway, not only HTML strings."""
from pathlib import Path
from types import SimpleNamespace
import os
import re
import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.foresight_gateway import create_foresight_gateway

ROOT = Path(__file__).resolve().parents[1]


class FakeManager:
    def __init__(self):
        self.config = SimpleNamespace(bot_id='pete', name='Pete',
                                      provider=SimpleNamespace(value='ollama'),
                                      model='test-spy', rooms=['studio'], max_history=8)
        self.calls = []

    def list_configs(self):
        return [self.config]

    def get_config(self, bot_id):
        return self.config if bot_id == 'pete' else None

    def bot_user_id(self, bot_id):
        return 'bot-' + bot_id

    def _build_prompt(self, config, history):
        return str(history)

    async def _call_provider(self, config, prompt):
        self.calls.append(prompt)
        return 'Reply from existing provider spy'


class FakeHub:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.history = {}

    async def get_recent_history(self, room_id, limit):
        return self.history.get(room_id, [])[-limit:]

    async def post_chat_message(self, room_id, user_id, text):
        self.history.setdefault(room_id, []).append({'user_id': user_id, 'text': text})
        return {'room': room_id, 'text': text}


@pytest.fixture
def gateway(monkeypatch, tmp_path):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    monkeypatch.delenv('PUBCAST_2I_BRIDGE_URL', raising=False)
    manager = FakeManager()
    app = FastAPI()
    hub = FakeHub(tmp_path)
    app.include_router(create_foresight_gateway(lambda: manager, lambda: hub))
    return TestClient(app), manager, hub


def _auth(user='owner', role='owner'):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': user, 'role': role})}


def test_characters_come_from_existing_manager(gateway):
    client, _, _ = gateway
    assert client.get('/api/foresight/bridge/api/chat/characters').status_code == 401
    response = client.get('/api/foresight/bridge/api/chat/characters', headers=_auth())
    assert response.status_code == 200
    assert response.json()['characters'][0]['name'] == 'Pete'
    assert client.get('/api/foresight/bridge/health').json()['services']['legacy_2i_utilities'] == 'disabled'


def test_one_canonical_provider_and_identity(gateway):
    client, manager, hub = gateway
    url = '/api/foresight/bridge/api/chat/character'
    message = {'character_id': 'pete', 'message': 'Hello!', 'room_id': 'studio', 'user_id': 'owner'}
    r = client.post(url, headers=_auth(), json=message)
    assert r.status_code == 200, r.text
    assert r.json()['reply'] == 'Reply from existing provider spy'
    assert len(manager.calls) == 1
    assert 'Hello!' in manager.calls[0]
    assert 'prior message' not in manager.calls[0]
    log = client.get('/api/foresight/bridge/api/chat/history',
                     params={'character_id': 'pete', 'room_id': 'studio'}, headers=_auth()).json()['messages']
    assert [entry['text'] for entry in log] == ['Hello!', 'Reply from existing provider spy']
    assert client.get('/api/foresight/bridge/api/chat/history',
                      params={'character_id': 'pete'}, headers=_auth(user='another')).json()['messages'] == []
    assert client.get('/api/foresight/bridge/api/chat/history',
                      params={'character_id': 'pete'}).status_code == 401
    assert client.post(url, headers=_auth(), json={**message, 'user_id': 'another'}).status_code == 403
    assert client.post(url, headers=_auth(), json={**message, 'character_id': 'unknown'}).status_code == 404
    assert client.post(url, headers=_auth(), json={**message, 'message': ''}).status_code == 400
    assert client.post(url, json=message).status_code == 401


def test_optional_2i_utilities_are_allowlisted_and_fail_honestly(gateway):
    client, _, _ = gateway
    assert client.get('/api/foresight/bridge/api/some-secret', headers=_auth()).status_code == 404
    assert client.get('/api/foresight/bridge/api/messages').status_code == 401
    response = client.get('/api/foresight/bridge/api/messages', headers=_auth())
    assert response.status_code == 503
    assert client.delete('/api/foresight/bridge/api/messages/clear', headers=_auth(role='guest')).status_code == 403
    assert client.get('/api/foresight/bridge/api/messages', headers=_auth(role='guest')).status_code == 403
    assert client.post('/api/foresight/bridge/api/manuscript/commit', headers=_auth(role='guest'), json={}).status_code == 403


def test_all_foresight_portal_targets_exist_and_scripts_parse(tmp_path):
    html = (ROOT / 'static' / 'foresight.html').read_text()
    assert 'foresight.counter.v2' in html
    assert 'enterPortal(tray)' in html
    assert 'url:\'/pubpartner\'' in html
    assert "url:'/static/foresight_care.html'" in html
    assert "twoIBase: '/api/foresight/bridge'" in html
    for name in ('foresight.html', 'foresight_care.html', 'pub_partner_chat.html'):
        page = (ROOT / 'static' / name).read_text()
        scripts = re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', page, re.S)
        for i, source in enumerate(scripts):
            path = tmp_path / (name + str(i) + '.js')
            path.write_text(source)
            r = subprocess.run(['node', '--check', str(path)], capture_output=True, text=True)
            assert r.returncode == 0, (name, r.stderr)

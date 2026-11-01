from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_cast_characters_route_lists_three_core_characters():
    r = client.get('/api/cast/characters')
    assert r.status_code == 200
    data = r.json()
    ids = [c['character_id'] for c in data['characters']]
    assert ids == ['pete', 'repete', 'purfluous']


def test_cast_character_route_alias_resolves():
    r = client.get('/api/cast/characters/re_pete')
    assert r.status_code == 200
    data = r.json()
    assert data['character_id'] == 'repete'
    assert data['display_name'] == 'Re-Pete'

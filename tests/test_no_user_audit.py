from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from main import app


def test_legacy_navigation_aliases_resolve_to_real_pages():
    client = TestClient(app)
    expected = {
        '/world': 'world',
        '/stage': 'stage',
        '/studio': 'studio',
        '/byok': 'byok',
        '/map': 'map',
        '/walk': 'walk',
    }
    for route, marker in expected.items():
        response = client.get(route)
        assert response.status_code == 200
        assert '<!DOCTYPE html>' in response.text or '<html' in response.text.lower()
        assert marker in response.text.lower()


def test_avatar_compatibility_shim_exists_and_points_to_avatar_glow():
    payload = (REPO_ROOT / 'static' / 'avatar.js').read_text(encoding='utf-8')
    assert 'avatar_glow.js' in payload
    assert 'HolographicAvatarSystem' in payload

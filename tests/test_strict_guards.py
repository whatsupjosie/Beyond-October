from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from main import app
from modules import dressing_room_security as drs
from modules.performance_manager import PerformanceManager
from modules.projects import save_autosave_snapshot


def test_template_pages_render_without_raw_jinja_tokens():
    client = TestClient(app)
    for route in ('/control', '/dressing'):
        response = client.get(route)
        assert response.status_code == 200
        body = response.text
        assert '{% extends' not in body
        assert '{% block' not in body
        assert '{% endblock %}' not in body


def test_bots_js_is_no_longer_empty():
    payload = (REPO_ROOT / 'static' / 'bots.js').read_text(encoding='utf-8')
    assert 'loadBots' in payload
    assert len(payload.strip()) > 100


def test_projects_autosave_writes_valid_json_atomically(tmp_path: Path):
    path = __import__('asyncio').run(save_autosave_snapshot(tmp_path, 'demo', {'scene': {'name': 'Test'}}))
    assert path.exists()
    raw = path.read_text(encoding='utf-8')
    assert '"scene"' in raw
    assert not path.with_suffix(path.suffix + '.tmp').exists()


def test_performance_manager_state_write_is_valid_json(tmp_path: Path):
    policy = tmp_path / 'policy.json'
    policy.write_text('{"profiles":{"medium":{}},"default_profile":"medium"}', encoding='utf-8')
    state = tmp_path / 'data' / 'global' / 'performance.json'
    manager = PerformanceManager(policy, state)
    manager.set_profile('medium')
    assert 'active_profile' in state.read_text(encoding='utf-8')
    assert not state.with_suffix(state.suffix + '.tmp').exists()


def test_dressing_room_security_writes_manifest_and_state_atomically(tmp_path: Path):
    drs.set_code(tmp_path, 'owner', '#123')
    state_path = tmp_path / 'dressing_room_security' / 'owner.json'
    assert state_path.exists()
    assert not state_path.with_suffix(state_path.suffix + '.tmp').exists()
    manifest = drs.build_forensic_manifest(tmp_path, 'owner', 'project')
    out = drs._write_manifest(tmp_path, 'incident-1', manifest)
    assert out.exists()
    assert not out.with_suffix(out.suffix + '.tmp').exists()


from modules.credentials import CredentialStore
from modules.choreography_runtime import Choreography


def test_credential_store_writes_json_without_temp_leaks(tmp_path: Path):
    store = CredentialStore(tmp_path / 'creds_root')
    store._write_models_payload('user1', {'models': [{'model_id': 'm1'}]})
    models_path = tmp_path / 'creds_root' / 'secure' / 'models' / 'user1.json'
    assert models_path.exists()
    assert 'm1' in models_path.read_text(encoding='utf-8')
    assert not models_path.with_suffix(models_path.suffix + '.tmp').exists()


def test_choreography_export_json_is_valid_and_atomic(tmp_path: Path):
    runtime = Choreography('test')
    out = tmp_path / 'choreo.json'
    runtime.export_json(out)
    assert out.exists()
    assert '"name": "test"' in out.read_text(encoding='utf-8')
    assert not out.with_suffix(out.suffix + '.tmp').exists()

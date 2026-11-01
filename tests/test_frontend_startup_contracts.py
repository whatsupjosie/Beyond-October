from fastapi.testclient import TestClient
import logging
import main


def test_startup_boots_surface_voxel_and_studio_without_constructor_failures(tmp_path):
    from tests.host_lifespan_helpers import run_isolated_host
    run_isolated_host('import io, logging\nfrom fastapi.testclient import TestClient\nimport main\nstream = io.StringIO()\nlogging.getLogger().setLevel(logging.INFO)\nlogging.getLogger().addHandler(logging.StreamHandler(stream))\nwith TestClient(main.app):\n    pass\ntext = stream.getvalue()\nassert "[14] Surface manager failed" not in text\nassert "[16] Voxel stack failed" not in text\nassert "[17] Voxel bridge not connected" not in text\nassert "[18] Studio Control failed" not in text\nassert "[14] Surface manager ready" in text\nassert "[16] Voxel asset manager ready" in text\nassert "[18] Studio Control ready" in text', tmp_path)


def test_studio_and_voxel_endpoints_are_live_after_startup():
    with TestClient(main.app) as client:
        studio = client.get('/api/studio/status')
        assert studio.status_code == 200
        studio_body = studio.json()
        assert studio_body['available'] is True

        voxel = client.get('/api/voxel/status')
        assert voxel.status_code == 200
        voxel_body = voxel.json()
        assert voxel_body['asset_manager'] is True
        assert voxel_body['studio_integration'] is True
        assert voxel_body['bridge'] is True
        assert voxel_body['bridge_status'] is not None


def test_studio_preflight_and_emergency_save_routes_work():
    with TestClient(main.app) as client:
        preflight = client.post('/api/studio/preflight', json={})
        assert preflight.status_code == 200
        preflight_body = preflight.json()
        # No live input telemetry exists in the isolated test runtime. Preflight
        # must fail closed rather than claiming that the studio is safe to go live.
        assert preflight_body['ok'] is False
        assert 'result' in preflight_body
        assert preflight_body['result']['success'] is False
        assert preflight_body['result']['state'] == 'IDLE'
        assert 'checks' in preflight_body['result']
        assert any(not check.get('passed', False) for check in preflight_body['result']['checks'])

        emergency = client.post('/api/studio/emergency-save', json={})
        assert emergency.status_code == 200
        emergency_body = emergency.json()
        assert emergency_body['ok'] is True
        assert emergency_body['result']['ok'] is True

"""Real full-host startup must expose and run the EVO instance it reports."""

def test_host_evo_status_contains_the_actual_semantic_snapshot(client, main_module):
    assert main_module.evo_orchestrator is not None
    response = client.get("/api/evo/status")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["semantic_revision"] == main_module.evo_orchestrator.get_semantic_state().revision
    assert isinstance(body["semantic"], dict)


def test_host_starts_one_real_epete_worker(client, main_module):
    runtime = main_module.evo_orchestrator
    assert runtime._running
    assert runtime.epete._worker_task is not None
    assert not runtime.epete._worker_task.done()


def test_nested_lifespan_borrows_without_stopping_owners_worker(client, main_module):
    from fastapi.testclient import TestClient
    owner_worker = main_module.evo_orchestrator.epete._worker_task
    with TestClient(main_module.app) as nested:
        assert nested.get("/api/evo/status").json()["worker_running"]
        assert main_module.evo_orchestrator.epete._worker_task is owner_worker
    assert not owner_worker.done()
    assert client.get("/api/evo/status").json()["running"]


def test_host_repeated_lifespans_rearm_and_stop_the_owned_evo_worker(tmp_path):
    import os
    from pathlib import Path
    import subprocess
    import sys
    environment = dict(os.environ, PUBCAST_DATA_DIR=str(tmp_path))
    script = '''
from fastapi.testclient import TestClient
import main
previous = None
for index in range(2):
    with TestClient(main.app) as client:
        runtime = main.evo_orchestrator
        worker = runtime.epete._worker_task
        assert runtime.get_status()["worker_running"]
        assert client.get("/api/evo/status").json()["semantic_revision"] == runtime.get_semantic_state().revision
        if previous is not None:
            assert worker is not previous
        previous = worker
    assert worker.done()
    assert not runtime.get_status()["running"]
print("EVO_REENTRY_OK")
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
        env=environment, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr[-6000:]
    assert "EVO_REENTRY_OK" in result.stdout

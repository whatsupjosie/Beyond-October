from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import pubpartner_routes


def test_launch_check_reports_local_activation_ready(tmp_path):
    app = FastAPI()
    pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path)
    app.include_router(pubpartner_routes.router)
    client = TestClient(app)
    response = client.get('/api/pubpartner/launch-check')
    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['checks']['verbatim_vault'] is True
    assert payload['checks']['guidance_store'] is True
    assert payload['checks']['receipt_store'] is True
    assert payload['checks']['mock_provider_available'] is True
    assert payload['checks']['offline_provider_available'] is True
    assert payload['ui'] == '/pubpartner'

from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import pubpartner_routes
from modules.pubpartner_preflight import run_preflight


def _client(tmp_path):
    app = FastAPI()
    pubpartner_routes.configure_pubpartner_spine(data_dir=tmp_path)
    app.include_router(pubpartner_routes.router)
    return TestClient(app)


def test_repair12_preflight_module_reports_current_app(tmp_path):
    report = run_preflight(data_dir=tmp_path, app_root=Path.cwd())
    assert report["format"] == "PubPartnerPreflight.v3"
    assert "checks" in report
    names = {c["name"] for c in report["checks"]}
    assert "file:static/pubpartner.html" in names
    assert "file:modules/pubpartner_core.py" in names


def test_repair12_preflight_route(tmp_path):
    client = _client(tmp_path)
    res = client.get("/api/pubpartner/preflight")
    assert res.status_code == 200
    payload = res.json()
    assert payload["format"] == "PubPartnerPreflight.v3"
    assert "human_summary" in payload


def test_repair12_ui_has_model_scan_and_preflight_controls():
    html = Path("static/pubpartner.html").read_text(encoding="utf-8")
    js = Path("static/pubpartner.js").read_text(encoding="utf-8")
    css = Path("static/pubpartner.css").read_text(encoding="utf-8")
    assert "ollamaModels" in html
    assert "scanModels" in html and "runPreflight" in html
    assert "scanModels" in js and "/api/pubpartner/preflight" in js
    assert "REPAIR12" in css


def test_repair12_launchers_present():
    assert Path("run_pubpartner.py").exists()
    assert Path("RUN_PUBPARTNER_WINDOWS.bat").exists()
    assert Path("run_pubpartner_mac_linux.sh").exists()

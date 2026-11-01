from pathlib import Path


def test_pub_manager_living_ui_status_is_wired():
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "pubpartner.html").read_text(encoding="utf-8")
    js = (root / "static" / "pubpartner.js").read_text(encoding="utf-8")

    assert 'id="pubManagerStatus"' in html
    assert "/api/pubmanager/health" in js
    assert "guarding · deterministic" in js
    assert "audit_failures" in js

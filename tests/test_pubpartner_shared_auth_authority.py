from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pubpartner_uses_shared_reach_session_authority_not_persistent_bearer_store():
    html = (ROOT / "static" / "pubpartner.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "pubpartner.js").read_text(encoding="utf-8")
    assert '<script src="/static/reach_auth.js"></script>' in html
    assert "window.ReachAuth.saveSession" in js
    assert "window.ReachAuth.clearSession" in js
    assert "window.ReachAuth.getToken" in js
    assert "localStorage.setItem(legacyAuthTokenKey" not in js
    assert "localStorage.setItem(legacyAuthUserKey" not in js
    # Migration deletes old persistent credentials immediately after importing.
    assert "localStorage.removeItem(legacyAuthTokenKey)" in js
    assert "localStorage.removeItem(legacyAuthUserKey)" in js


def test_browser_bearer_storage_is_session_scoped_in_shared_adapter():
    helper = (ROOT / "static" / "reach_auth.js").read_text(encoding="utf-8")
    assert "sessionStorage.setItem(TOKEN_KEY" in helper
    assert "localStorage.setItem(TOKEN_KEY" not in helper

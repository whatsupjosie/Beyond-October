"""The PubWorld Set page must load with no network (PC-021).

It is selectable in the Foresight program list and used to load three.js from cdnjs, so on a machine with no internet
it showed nothing. It now loads the exact r128 build it was written for from static/vendor/three-0.128.0. These tests
pin that no external script, stylesheet or font is fetched, that the vendored file is the one recorded in its
PROVENANCE.json, and that the page really starts in a browser with every non-local request refused.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "static" / "pubworld_stage.html"
VENDOR = ROOT / "static" / "vendor" / "three-0.128.0"


def test_the_page_references_nothing_outside_the_host():
    html = PAGE.read_text(encoding="utf-8")
    tags = re.findall(r"<(?:script|link)\b[^>]*>", html, flags=re.I)
    fetched = [t for t in tags if re.search(r"""(?:src|href)\s*=\s*["'](?:https?:)?//""", t, flags=re.I)]
    imports = re.findall(r"""@import\s+url\(\s*["']?(?:https?:)?//""", html, flags=re.I)
    assert not fetched and not imports, (fetched, imports)
    assert "/static/vendor/three-0.128.0/build/three.min.js" in html


def test_the_vendored_build_is_the_recorded_one():
    prov = json.loads((VENDOR / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert prov["package"] == "three" and prov["version"] == "0.128.0"
    for rel, digest in prov["sha256"].items():
        assert hashlib.sha256((VENDOR / rel).read_bytes()).hexdigest() == digest, rel
    assert "MIT" in prov["license"] and (VENDOR / "LICENSE").read_text(encoding="utf-8").startswith("The MIT License")
    assert b'"128"' in (VENDOR / "build" / "three.min.js").read_bytes()


sync_api = pytest.importorskip("playwright.sync_api")


def test_the_page_starts_with_every_outside_request_refused():
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        except Exception as exc:
            pytest.skip(f"Chromium unavailable: {exc}")
        try:
            context = browser.new_context(viewport={"width": 1000, "height": 700})
            origin = "http://stage.test"
            refused, errors = [], []

            def route(r):
                url = r.request.url
                if not url.startswith(origin):
                    refused.append(url)
                    return r.abort()
                rel = url[len(origin):].split("?")[0].lstrip("/")
                target = ROOT / rel
                if rel and target.is_file() and ROOT in target.resolve().parents:
                    return r.fulfill(status=200, path=str(target))
                r.fulfill(status=404, body="")
            context.route("**/*", route)
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(origin + "/static/pubworld_stage.html")
            page.wait_for_function("typeof THREE !== 'undefined' && THREE.REVISION === '128'", timeout=20000)
            page.wait_for_timeout(1500)
            assert refused == [], refused
            assert errors == [], errors
        finally:
            browser.close()

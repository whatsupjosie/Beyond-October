"""Real-browser acceptance: the import page turns GLB, FBX, OBJ and an animal into
canonical-height avatars, and the server accepts what the page produces.

Drives static/avatar_import.html in Chromium with the committed test models. Skips,
like the other optional browser checks, when Playwright or its browser is absent.
"""
from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest

sync_api = pytest.importorskip("playwright.sync_api", reason="Optional browser verification requires Playwright")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from modules import avatar_imports as AI  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "avatars"
SHOTS = os.environ.get("AVATAR_IMPORT_SHOTS")  # optional folder for screenshots

CASES = [
    # files, height preset option value or ("custom", inches), expect skinned, min clips, label
    # Cast: Pete is the woman (5'8"), RePete the young man (5'10"), Sir Purfluous the older man (6'2").
    (["mh_female.glb"], 68, True, 1, "glb_female_as_pete"),
    (["mh_male.glb"], 70, True, 1, "glb_male_as_repete"),
    (["mh_male.fbx"], 74, True, 1, "fbx_male_metres_as_purfluous"),
    (["mh_female.fbx"], ("custom", 64), True, 1, "fbx_female_centimetres_x100"),
    (["mh_male.obj", "mh_male.mtl"], 68, False, 0, "obj_male_y_up"),
    (["mh_female.obj", "mh_female.mtl"], ("custom", 65), False, 0, "obj_female_z_up_lying_down"),
    (["husky.glb"], ("custom", 28), True, 10, "husky_quadruped"),
]


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        except Exception as exc:
            pytest.skip(f"Chromium unavailable for Playwright: {exc}")
        yield b
        b.close()


@pytest.fixture()
def page(browser, tmp_path, monkeypatch):
    monkeypatch.delenv("PUBCAST_ENFORCE_AUTH", raising=False)
    api = FastAPI()
    router = AI.create_avatar_import_router(tmp_path)
    api.include_router(router)
    client = TestClient(api)
    external = []

    def route(r):
        url = urlparse(r.request.url)
        if url.netloc != "localhost":
            external.append(r.request.url)
            return r.abort()
        if url.path.startswith("/api/avatars/"):
            resp = client.request(r.request.method, url.path + ("?" + url.query if url.query else ""),
                                  content=r.request.post_data_buffer,
                                  headers={k: v for k, v in r.request.headers.items() if k.lower() in ("content-type", "authorization")})
            return r.fulfill(status=resp.status_code, body=resp.content,
                             content_type=resp.headers.get("content-type", "application/json"))
        file = ROOT / url.path.lstrip("/")
        if url.path.startswith("/static/") and file.is_file():
            return r.fulfill(body=file.read_bytes(),
                             content_type=mimetypes.guess_type(file.name)[0] or "application/octet-stream")
        return r.fulfill(status=404, body="not found")

    context = browser.new_context(viewport={"width": 1280, "height": 760})
    context.route("**/*", route)
    pg = context.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto("http://localhost/static/avatar_import.html")
    pg.wait_for_function("document.querySelector('#heightPreset').options.length > 3")
    pg.store = router.store
    yield pg
    context.close()
    client.close()
    assert not external, f"import page reached the network: {external}"
    assert not errors, f"page errors: {errors}"


def choose_height(pg, height):
    if isinstance(height, tuple):
        inches = height[1]
        pg.fill("#feet", str(inches // 12))
        pg.fill("#inches", str(inches % 12))
        pg.dispatch_event("#inches", "input")
        return inches
    pg.select_option("#heightPreset", str(height))
    return height


@pytest.mark.parametrize("files,height,skinned,min_clips,label", CASES, ids=[c[-1] for c in CASES])
def test_each_format_imports_at_its_canonical_height(page, files, height, skinned, min_clips, label):
    target_in = choose_height(page, height)
    page.set_input_files("#file", [str(FIX / f) for f in files])
    page.wait_for_function("document.querySelector('#report').textContent.includes('Ready')", timeout=60000)
    r = page.evaluate("""() => { const s = window.__avatarImport; return {
        h: s.result.heightM, feet: s.result.feetY, x: s.result.size.x, z: s.result.size.z,
        skinned: s.result.stats.skinned, bones: s.result.stats.bones, clips: s.result.stats.clips.length,
        tris: s.result.stats.triangles }; }""")
    target_m = target_in * AI.INCH_M
    assert r["h"] == pytest.approx(target_m, rel=1e-3), r
    assert abs(r["feet"]) < 1e-3, r
    assert r["skinned"] is skinned and r["clips"] >= min_clips, r
    if label.startswith("obj_female_z_up"):
        assert r["z"] < r["h"] * 0.5, "Z-up OBJ was not stood upright"   # depth of a person, not their height
    if label.startswith("fbx_"):
        # FBX says "emissive white at strength 0"; a converted material must not glow.
        glow = page.evaluate("""() => { let g = 0; window.__avatarImport.result.root.traverse(n => {
            if (n.isMesh) [].concat(n.material).forEach(m => { g = Math.max(g, m.emissive ? m.emissive.r + m.emissive.g + m.emissive.b : 0); }); }); return g; }""")
        assert glow < 0.05, f"converted FBX material glows ({glow})"
    if label == "husky_quadruped":
        assert r["z"] > r["h"], "a dog should be longer than it is tall"
    if SHOTS:
        page.wait_for_timeout(700)
        page.screenshot(path=os.path.join(SHOTS, f"{label}.png"))
    page.click("#save")
    page.wait_for_function("window.__avatarImport.saved || /Import failed|canonical|refused/.test(document.querySelector('#report').textContent)", timeout=60000)
    saved = page.evaluate("window.__avatarImport.saved")
    assert saved, page.inner_text("#report")
    entry = page.store.get(saved["id"])
    assert entry["measured"]["height_m"] == pytest.approx(target_m, rel=0.02)
    assert entry["measured"]["skinned"] is skinned
    assert entry["source_format"] == files[0].rsplit(".", 1)[1]


def test_no_height_means_no_save(page):
    page.set_input_files("#file", [str(FIX / "mh_male.glb")])
    page.wait_for_function("document.querySelector('#report').textContent.includes('canonical height')")
    assert page.is_disabled("#save")

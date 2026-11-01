"""New PubPartner cartridges made from PubPartner and kept on the host (modules/pubpartner_cartridges.py).

The routes are checked directly: create, list, refuse, set an avatar. Then the real program:
1. Start run_reach.py and put an avatar in the library.
2. In PubPartner choose File › New cartridge…, fill it in, pick the avatar and create it.
3. The new friend is selected and answers a turn as itself.
4. Quit and restart PubPartner. The cartridge is still in the Friend list with its avatar.
The canonical Alex vessel blob is checked before and after. Browser parts skip without Playwright/Chromium.
"""
from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.avatar_imports import INCH_M, measure_glb
from modules.pubpartner_cartridges import create_pubpartner_cartridge_router
from pubpartner.cartridge import load_cartridge

ROOT = Path(__file__).resolve().parents[1]
MANNEQUIN = ROOT / "static" / "world" / "test_avatars" / "Xbot.glb"
ALEX_VESSEL = ROOT / "data" / "pubpartner" / "vessels" / "alex.pubpartner"
ALEX_BLOB = "96fa66a728d07d5ff43b0d3d7fc17a466765cec1"


def _blob(path: Path) -> str:
    return subprocess.run(["git", "hash-object", str(path)], capture_output=True, text=True, check=True).stdout.strip()


def _auth(user="josie", role="owner"):
    return {"Authorization": "Bearer " + create_access_token({"sub": user, "role": role})}


@pytest.fixture()
def api(tmp_path):
    app = FastAPI()
    router = create_pubpartner_cartridge_router(tmp_path)
    app.include_router(router)
    with TestClient(app) as c:
        c.data_dir, c.studio = tmp_path, router.studio
        yield c


def test_a_new_cartridge_is_a_real_loadable_cartridge_and_a_friend(api):
    r = api.post("/api/pubpartner/cartridges", headers=_auth(), json={"name": "Marlowe Finch", "summary": "A night-shift radio host who collects lost songs.",
                                                                       "cadence": "slow, wry", "vocabulary": "old radio slang"})
    assert r.status_code == 201, r.text
    c = r.json()["cartridge"]
    assert c["id"] == "marlowe_finch" and c["name"] == "Marlowe Finch" and c["avatar_id"] is None
    folder = api.data_dir / "pubpartner" / "cartridges" / "marlowe_finch"
    cart = load_cartridge(folder)                                   # the package's own loader accepts it
    assert cart.definition.identity.name == "Marlowe Finch" and cart.definition.voice.cadence == "slow, wry"
    cart.memory.close()
    profile = api.studio.profiles.load_profile("friend", "marlowe_finch", fallback_id="friend")
    assert profile["display_name"] == "Marlowe Finch" and profile["self_concept"].startswith("A night-shift")
    assert profile["cartridge"]["path"] == "pubpartner/cartridges/marlowe_finch" and profile["cartridge"]["created_by"] == "josie"
    assert [x["id"] for x in api.get("/api/pubpartner/cartridges", headers=_auth()).json()["cartridges"]] == ["marlowe_finch"]
    assert not list((api.data_dir / "pubpartner" / "cartridges").glob(".*"))   # no staging folder left behind


@pytest.mark.parametrize("name", ["Alex", "alex", "Craig", "Friend"])
def test_built_in_friends_cannot_be_replaced(api, name):
    r = api.post("/api/pubpartner/cartridges", headers=_auth(), json={"name": name, "summary": "an impostor"})
    assert r.status_code == 409
    assert not (api.data_dir / "pubpartner" / "cartridges" / name.lower()).exists()
    assert api.studio.profiles.load_profile("friend", "alex", fallback_id="alex")["display_name"] == "Alex"


def test_refusals(api, monkeypatch):
    a = _auth()
    assert api.post("/api/pubpartner/cartridges", headers=a, json={"name": "", "summary": "x"}).status_code == 400
    assert api.post("/api/pubpartner/cartridges", headers=a, json={"name": "Nova", "summary": ""}).status_code == 400
    assert api.post("/api/pubpartner/cartridges", headers=a, json={"name": "!!!", "summary": "x"}).status_code == 400
    assert api.post("/api/pubpartner/cartridges", headers=a, json={"name": "Nova", "summary": "x" * 481}).status_code == 400
    assert api.post("/api/pubpartner/cartridges", headers=a, json={"name": "Nova", "summary": "x", "avatar_id": "not-there"}).status_code == 400
    assert api.post("/api/pubpartner/cartridges", headers=a, json={"name": "Nova", "summary": "x"}).status_code == 201
    assert api.post("/api/pubpartner/cartridges", headers=a, json={"name": "Nova", "summary": "again"}).status_code == 409
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")                 # with sign-in enforced, a viewer cannot make one
    assert api.post("/api/pubpartner/cartridges", headers=_auth(role="viewer"), json={"name": "Vee", "summary": "x"}).status_code == 403
    monkeypatch.delenv("PUBCAST_ENFORCE_AUTH")
    assert api.get("/api/pubpartner/cartridges/alex", headers=a).status_code == 404
    assert api.put("/api/pubpartner/cartridges/..%2Fx/avatar", headers=a, json={"avatar_id": None}).status_code == 404


def test_a_cartridge_gets_an_avatar_from_the_library(api):
    data = MANNEQUIN.read_bytes()
    entry = api.studio.avatars.add(data, name="Test mannequin", height_in=measure_glb(data)["height_m"] / INCH_M, owner="josie",
                              source_format="glb", source_name="Xbot.glb")
    api.post("/api/pubpartner/cartridges", headers=_auth(), json={"name": "Nova", "summary": "x"})
    r = api.put("/api/pubpartner/cartridges/nova/avatar", headers=_auth(), json={"avatar_id": entry["id"]})
    assert r.status_code == 200 and r.json()["cartridge"]["avatar_id"] == entry["id"]
    appearance = yaml.safe_load((api.data_dir / "pubpartner" / "cartridges" / "nova" / "appearance.yaml").read_text())
    assert appearance["avatar_id"] == entry["id"]
    assert api.studio.profiles.load_profile("friend", "nova", fallback_id="friend")["avatar_id"] == entry["id"]
    load_cartridge(api.data_dir / "pubpartner" / "cartridges" / "nova").memory.close()    # still a valid cartridge
    assert api.put("/api/pubpartner/cartridges/nova/avatar", headers=_auth(), json={"avatar_id": None}).json()["cartridge"]["avatar_id"] is None


# ── the real PubPartner, across a restart ────────────────────────────────────

sync_api = pytest.importorskip("playwright.sync_api")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Reach:
    def __init__(self, data):
        self.data, self.port = data, _free_port()
        self.base = f"http://127.0.0.1:{self.port}"

    def start(self):
        env = {k: v for k, v in os.environ.items() if k not in ("PUBCAST_ENFORCE_AUTH", "PUBCAST_JWT_SECRET", "PUBCAST_DATA_DIR")}
        self.log = open(self.data / "reach.log", "a", encoding="utf-8")
        self.proc = subprocess.Popen([sys.executable, "run_reach.py", "--port", str(self.port), "--data-dir", str(self.data),
                                      "--no-browser", "--no-legacy-2i"], cwd=str(ROOT), env=env, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + 120
        while time.time() < deadline:
            assert self.proc.poll() is None, "run_reach.py exited during startup"
            try:
                if httpx.get(self.base + "/health", timeout=0.5).status_code == 200:
                    return
            except httpx.RequestError:
                pass
            time.sleep(0.25)
        raise AssertionError("PubCast did not start")

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(20)
        except subprocess.TimeoutExpired:
            self.proc.kill(); self.proc.wait(5)
        self.log.close()


def _pubpartner(browser, base, token, user):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
    ctx.add_init_script("sessionStorage.setItem('pubcast_token', %r); sessionStorage.setItem('pubcast_user', JSON.stringify({username:%r,user_id:%r,role:'owner'}));"
                        % (token, user, user))
    page = ctx.new_page(); page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.goto(base + "/pubpartner")
    page.wait_for_function("document.getElementById('authGate').hidden", timeout=30000)
    return ctx, page


def test_make_a_cartridge_in_pubpartner_talk_to_it_and_find_it_after_a_restart(tmp_path):
    assert _blob(ALEX_VESSEL) == ALEX_BLOB
    reach = Reach(tmp_path)
    reach.start()
    try:
        user, password = "josie-check", secrets.token_urlsafe(20)
        token = httpx.post(reach.base + "/api/auth/setup", json={"username": user, "password": password, "confirm_password": password}, timeout=10).json()["access_token"]
        hdr = {"Authorization": "Bearer " + token}
        data = MANNEQUIN.read_bytes()
        r = httpx.post(reach.base + "/api/avatars/imports", params={"name": "Test mannequin", "height_in": round(measure_glb(data)["height_m"] / INCH_M, 2)},
                       content=data, headers={**hdr, "Content-Type": "model/gltf-binary"}, timeout=30)
        assert r.status_code == 201, r.text
        avatar_id = r.json()["avatar"]["id"]
        vessel_dir = tmp_path / "pubpartner" / "vessels"
        vessel_before = {p.name: p.read_bytes() for p in vessel_dir.iterdir() if p.is_file()} if vessel_dir.exists() else {}

        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch(args=["--no-sandbox"])
            except Exception as exc:
                pytest.skip(f"no Chromium available: {exc}")
            try:
                ctx, page = _pubpartner(browser, reach.base, token, user)
                page.click("[data-menu=file]")
                page.click("[data-command=new-cartridge]")
                page.wait_for_selector("#cartridgeGate:not([hidden])")
                page.wait_for_function(f"[...document.getElementById('cartridgeAvatar').options].some(o => o.value === {avatar_id!r})")
                page.fill("#cartridgeName", "Marlowe Finch")
                page.fill("#cartridgeSummary", "A night-shift radio host who collects lost songs.")
                page.fill("#cartridgeCadence", "slow, wry")
                page.select_option("#cartridgeAvatar", avatar_id)
                page.click("#cartridgeSubmit")
                page.wait_for_function("document.getElementById('cartridgeGate').hidden", timeout=15000)
                assert page.input_value("#friendId") == "marlowe_finch"
                assert page.evaluate("document.querySelector('#friendId option:checked').textContent") == "Marlowe Finch"
                assert page.errors == []
                ctx.close()
            finally:
                browser.close()

        # the new friend answers a turn as itself (echo provider: no model needed)
        turn = httpx.post(reach.base + "/api/pubpartner/turns", headers=hdr, timeout=30,
                          json={"session_id": "cartridge_check", "message": "Hello?", "friend": "marlowe_finch", "provider": "echo"})
        assert turn.status_code == 200, turn.text
        f = turn.json()["fcp1"]["f"]
        assert f["id"] == "marlowe_finch" and f["name"] == "Marlowe Finch" and f["identity"].startswith("A night-shift")

        reach.stop()
        reach.start()
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            try:
                ctx, page = _pubpartner(browser, reach.base, token, user)
                page.wait_for_function("[...document.getElementById('friendId').options].some(o => o.value === 'marlowe_finch')", timeout=20000)
                page.select_option("#friendId", "marlowe_finch")
                page.click("[data-menu=wardrobe]")
                page.click("[data-command=cartridge-avatar]")
                page.wait_for_selector("#cartridgeGate:not([hidden])")
                page.wait_for_function(f"document.getElementById('cartridgeAvatar').value === {avatar_id!r}", timeout=15000)
                # take the avatar off, and it stays off
                page.select_option("#cartridgeAvatar", "")
                page.click("#cartridgeSubmit")
                page.wait_for_function("document.getElementById('cartridgeGate').hidden", timeout=15000)
                assert page.errors == []
            finally:
                browser.close()
        listed = httpx.get(reach.base + "/api/pubpartner/cartridges", headers=hdr).json()["cartridges"]
        assert [(c["id"], c["avatar_id"]) for c in listed] == [("marlowe_finch", None)]
        load_cartridge(tmp_path / "pubpartner" / "cartridges" / "marlowe_finch").memory.close()
        vessel_after = {p.name: p.read_bytes() for p in vessel_dir.iterdir() if p.is_file()} if vessel_dir.exists() else {}
        for name, content in vessel_before.items():                     # making a cartridge never touched Alex
            assert vessel_after.get(name) == content, name
    finally:
        reach.stop()
    assert _blob(ALEX_VESSEL) == ALEX_BLOB

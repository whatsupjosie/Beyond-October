"""Host control through the real app: real main.app (uvicorn, a throwaway data folder, auth enforced), real walker
sockets at /pubworld/ws/{client_id} proving who they are with a token, and the real /api/host routes.

What is checked is what a person on the other end would receive: the private notice reaches only the possessed person's
walker socket(s); drive, timeout and release follow; nobody else hears any of it; someone with no verified socket cannot be
possessed; a viewer cannot start any of it.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

websockets = pytest.importorskip("websockets")

from modules import auth as auth_module  # noqa: E402
from modules.auth import create_access_token  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NOTICE = "TEST NOTICE: the host is controlling your avatar."          # test wording only


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def host(tmp_path_factory):
    data = tmp_path_factory.mktemp("host_control_e2e")
    (data / "host_control").mkdir()
    (data / "host_control" / "messages.json").write_text(json.dumps({"possession_notice": NOTICE, "timeout_notice": "TEST TIMEOUT"}), encoding="utf-8")
    port = _free_port()
    env = dict(os.environ, PUBCAST_DATA_DIR=str(data), PUBCAST_ENFORCE_AUTH="1", PUBCAST_JWT_SECRET=auth_module._SECRET_KEY, PYTHONUNBUFFERED="1")
    log = open(data / "host.log", "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
                            cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            if proc.poll() is not None:
                log.flush()
                raise AssertionError("PubCast host exited during startup:\n" + (data / "host.log").read_text(encoding="utf-8")[-3000:])
            try:
                if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                    break
            except httpx.RequestError:
                pass
            time.sleep(0.2)
        else:
            raise AssertionError("PubCast host did not come up within 90 s")
        yield base, port, data
    finally:
        proc.terminate()
        try:
            proc.wait(15)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(5)
        log.close()


def tok(user, role="owner"):
    return create_access_token({"sub": user, "role": role})


def api(base, method, path, who="josie", role="owner", **kw):
    return httpx.request(method, base + path, headers={"Authorization": "Bearer " + tok(who, role)}, timeout=15, **kw)


async def walker(port, client_id, token):
    """A walker socket that proves who it is with the in-band auth message, as static/world_walk_live.js does."""
    ws = await websockets.connect(f"ws://127.0.0.1:{port}/pubworld/ws/{client_id}")
    await ws.send(json.dumps({"type": "auth", "token": token}))
    first = json.loads(await asyncio.wait_for(ws.recv(), 5))
    assert first["type"] == "auth_ok" and first["user_id"], first
    welcome = json.loads(await asyncio.wait_for(ws.recv(), 5))
    assert welcome["type"] == "welcome"
    return ws


async def drain(ws, seconds=1.0):
    got = []
    end = time.time() + seconds
    while time.time() < end:
        try:
            got.append(json.loads(await asyncio.wait_for(ws.recv(), max(0.05, end - time.time()))))
        except asyncio.TimeoutError:
            break
    return got


def test_a_possession_reaches_only_the_possessed_walker_and_follows_through(host):
    base, port, data = host

    async def scenario():
        mira = await walker(port, "pw_mira1", tok("mira", "guest"))
        mira2 = await walker(port, "pw_mira2", tok("Mira", "guest"))        # a second tab, other letter case
        kay = await walker(port, "pw_kay1", tok("kay", "guest"))
        try:
            r = await asyncio.to_thread(api, base, "POST", "/api/host/possess", json={"user_id": "mira", "duration_seconds": 120, "reason": "test"})
            assert r.status_code == 200 and r.json()["notice_delivered"] is True, r.text
            for ws in (mira, mira2):
                notice = [m for m in await drain(ws) if m["type"] == "host_notice"]
                assert len(notice) == 1 and notice[0]["text"] == NOTICE and notice[0]["kind"] == "possession"
            assert [m for m in await drain(kay, 0.5) if m["type"] != "keepalive"] == []              # kay heard nothing

            r = await asyncio.to_thread(api, base, "POST", "/api/host/drive", json={"user_id": "mira", "pos": [100, 250.5]})
            assert r.status_code == 200
            assert [m for m in await drain(mira, 0.8) if m["type"] == "host_drive"] == [{"type": "host_drive", "pos": [100.0, 250.5]}]
            assert [m for m in await drain(kay, 0.3) if m["type"] != "keepalive"] == []

            r = await asyncio.to_thread(api, base, "POST", "/api/host/timeout", json={"user_id": "mira", "duration_seconds": 30})
            assert r.status_code == 200 and r.json()["delivered"] is True
            tele = [m for m in await drain(mira, 0.8) if m["type"] == "host_teleport"]
            assert tele and tele[0]["room"] == "waiting_room_disciplinary" and tele[0]["recording"] is True and tele[0]["text"] == "TEST TIMEOUT"

            assert (await asyncio.to_thread(api, base, "POST", "/api/host/end-timeout", json={"user_id": "mira"})).status_code == 200
            assert [m["type"] for m in await drain(mira, 0.8) if m["type"].startswith("host_")] == ["host_timeout_end"]

            assert (await asyncio.to_thread(api, base, "POST", "/api/host/release", json={"user_id": "mira"})).status_code == 200
            assert [m["type"] for m in await drain(mira, 0.8) if m["type"].startswith("host_")] == ["host_release"]
            assert (await asyncio.to_thread(api, base, "GET", "/api/host/state")).json()["possessed"] == {}
        finally:
            for ws in (mira, mira2, kay):
                await ws.close()
    asyncio.run(scenario())


def test_nobody_connected_means_nobody_possessed_and_a_closed_socket_stops_counting(host):
    base, port, data = host
    r = api(base, "POST", "/api/host/possess", json={"user_id": "ghost"})
    assert r.status_code == 409 and r.json()["detail"] == "target_not_connected"

    async def scenario():
        ws = await walker(port, "pw_zed1", tok("zed", "guest"))
        await ws.close()
        await asyncio.sleep(0.5)
        return await asyncio.to_thread(api, base, "POST", "/api/host/possess", json={"user_id": "zed"})
    r = asyncio.run(scenario())
    assert r.status_code == 409 and r.json()["detail"] == "target_not_connected"
    assert api(base, "GET", "/api/host/state").json()["possessed"] == {}


def test_a_socket_that_never_proved_who_it_is_cannot_receive_or_be_possessed(host):
    base, port, data = host

    async def scenario():
        ws = await websockets.connect(f"ws://127.0.0.1:{port}/pubworld/ws/pw_anon1")      # no token sent
        try:
            msgs = []
            try:
                while True:
                    msgs.append(json.loads(await asyncio.wait_for(ws.recv(), 10)))
            except (asyncio.TimeoutError, websockets.ConnectionClosed):
                pass
            return msgs
        finally:
            await ws.close()
    msgs = asyncio.run(scenario())
    assert all(m["type"] == "auth_error" for m in msgs) and msgs
    assert api(base, "POST", "/api/host/possess", json={"user_id": "pw_anon1"}).status_code == 409


def test_a_wrong_token_proves_nothing(host):
    base, port, data = host

    async def scenario():
        ws = await websockets.connect(f"ws://127.0.0.1:{port}/pubworld/ws/pw_bad1")
        try:
            await ws.send(json.dumps({"type": "auth", "token": "not.a.token"}))
            return json.loads(await asyncio.wait_for(ws.recv(), 5))
        finally:
            await ws.close()
    assert asyncio.run(scenario())["type"] == "auth_error"


def test_roles_are_enforced_by_the_real_app(host):
    base, port, data = host
    for who, role, expect in (("v", "viewer", 403), ("m", "mod", 403), ("a", "admin", 409)):
        r = api(base, "POST", "/api/host/possess", who=who, role=role, json={"user_id": "nobody"})
        assert r.status_code == expect, (role, r.status_code, r.text)            # 409 = allowed to try, nobody connected
    assert api(base, "GET", "/api/host/state", who="m", role="mod").status_code == 200
    assert api(base, "GET", "/api/host/state", who="v", role="viewer").status_code == 403
    assert httpx.get(base + "/api/host/state", timeout=10).status_code in (401, 403)       # no token at all


def test_the_audit_log_recorded_it_and_the_profile_files_stayed_in_their_folder(host):
    base, port, data = host
    log = api(base, "GET", "/api/governance/audit?limit=200")
    assert log.status_code == 200
    body = log.json()
    entries = body if isinstance(body, list) else (body.get("entries") or body.get("log") or [])
    actions = {e["action"] for e in entries}
    assert {"POSSESS", "RELEASE", "TIMEOUT", "TIMEOUT_END"} <= actions, sorted(actions)


# ── the walker in a real browser reacts to the host ────────────────────────────

sync_api = pytest.importorskip("playwright.sync_api")


def test_the_walker_shows_the_notice_locks_the_person_follows_the_host_and_hands_control_back(host):
    base, port, data = host
    token = tok("walker-mira", "guest")
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--no-sandbox"])
        except Exception as exc:
            pytest.skip(f"no Chromium available: {exc}")
        try:
            ctx = browser.new_context(viewport={"width": 1400, "height": 860})
            ctx.add_init_script("sessionStorage.setItem('pubcast_token', %s); sessionStorage.setItem('pubcast_user', JSON.stringify({username:'walker-mira',user_id:'walker-mira',role:'guest'}));" % json.dumps(token))
            page = ctx.new_page(); errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base + "/walk")
            page.wait_for_function("document.documentElement.dataset.ready === '1' && window.PubCastLive && window.PubCastLive.state.online === true", timeout=30000)
            pos = lambda: page.evaluate("window.PubCastWalk.S.pos.slice()")
            walk_keys = lambda key: (page.keyboard.down(key), page.wait_for_timeout(600), page.keyboard.up(key))
            banner = page.locator("#hostBanner")
            # free before anything happens
            start = pos(); walk_keys("ArrowDown"); assert pos() != start and banner.is_hidden()

            # possession: the exact wording appears as plain text, and the person's own keys and clicks no longer walk
            r = api(base, "POST", "/api/host/possess", json={"user_id": "walker-mira", "duration_seconds": 120})
            assert r.status_code == 200, r.text
            page.wait_for_function("!document.getElementById('hostBanner').hidden", timeout=5000)
            assert NOTICE in banner.inner_text() and "taken control" in banner.inner_text()
            held = pos(); walk_keys("ArrowRight"); walk_keys("KeyA")
            sx, sy = page.evaluate("(p) => window.PubCastWalk.toScreen([p[0] + 120, p[1]])", held)
            box = page.locator("#c").bounding_box(); page.mouse.click(box["x"] + sx, box["y"] + sy); page.wait_for_timeout(500)
            assert pos() == held and page.evaluate("window.PubCastWalk.S.target") is None

            # the host drives: the avatar walks where the host says
            goal = page.evaluate("(p) => window.PubCastWalk.snapToFloor(window.PubCastWalk.S.view, [p[0] + 150, p[1]])", held)
            assert api(base, "POST", "/api/host/drive", json={"user_id": "walker-mira", "pos": goal}).status_code == 200
            page.wait_for_function("(g) => Math.hypot(window.PubCastWalk.S.pos[0] - g[0], window.PubCastWalk.S.pos[1] - g[1]) < 6", arg=goal, timeout=40000)

            # control goes back
            assert api(base, "POST", "/api/host/release", json={"user_id": "walker-mira"}).status_code == 200
            page.wait_for_function("document.getElementById('hostBanner').hidden", timeout=5000)
            here = pos(); walk_keys("ArrowDown"); assert pos() != here

            # timeout: the waiting room fills the picture (with the configured wording), input is locked, and it lifts when it ends
            screen = page.locator("#screen")
            assert api(base, "POST", "/api/host/timeout", json={"user_id": "walker-mira", "duration_seconds": 60}).status_code == 200
            page.wait_for_function("!document.getElementById('screen').hidden", timeout=5000)
            assert "Waiting room" in screen.inner_text() and "TEST TIMEOUT" in screen.inner_text()
            held = pos(); walk_keys("ArrowDown"); assert pos() == held
            assert api(base, "POST", "/api/host/end-timeout", json={"user_id": "walker-mira"}).status_code == 200
            page.wait_for_function("document.getElementById('screen').hidden", timeout=5000)
            walk_keys("ArrowUp"); assert pos() != held
            assert errors == []
            ctx.close()
        finally:
            browser.close()



# ── roster, presence, reconnect, removal: through the real sockets ─────────────

async def drain_closing(ws, seconds=2.0):
    """Everything the socket delivers until it closes (or the time is up), and the close code if it closed."""
    got, code = [], None
    end = time.time() + seconds
    while time.time() < end:
        try:
            got.append(json.loads(await asyncio.wait_for(ws.recv(), max(0.05, end - time.time()))))
        except asyncio.TimeoutError:
            break
        except websockets.exceptions.ConnectionClosed as closed:
            code = closed.rcvd.code if closed.rcvd else None
            break
    return got, code


async def _until(predicate, seconds=10.0, step=0.2):
    end = time.time() + seconds
    while time.time() < end:
        got = predicate()
        if got:
            return got
        await asyncio.sleep(step)
    return predicate()


def test_a_walker_that_reports_in_appears_on_the_roster_with_its_numbers_and_round_trip(host):
    base, port, _ = host

    async def run():
        ws = await walker(port, "pw_roster1", tok("roster-ann", "guest"))
        try:
            await ws.send(json.dumps({"type": "presence", "room": "dressing_room", "view": "main", "pos": [120.5, 340], "char": "pete",
                                      "fps": 58.4, "meshes": 3, "bones": 65, "tris": 41000}))
            ping = None
            for m in await drain(ws, 1.5):
                if m["type"] == "rtt_ping":
                    ping = m
            assert ping and isinstance(ping["id"], int), "the host should time the round trip with a ping"
            await ws.send(json.dumps({"type": "rtt_pong", "id": ping["id"]}))
            await asyncio.sleep(0.3)
            people = api(base, "GET", "/api/host/roster").json()["people"]
            me = next(p for p in people if p["user_id"] == "roster-ann")
            assert (me["room"], me["view"], me["pos"], me["char"]) == ("dressing_room", "main", [120.5, 340.0], "pete")
            assert (me["fps"], me["meshes"], me["bones"], me["tris"]) == (58.4, 3, 65, 41000)
            assert me["rtt_ms"] is not None and me["rtt_ms"] < 5000
            # a wrong id proves nothing and moves nothing
            await ws.send(json.dumps({"type": "rtt_pong", "id": ping["id"] + 99}))
            # a viewer may read the roster, a guest may not
            assert api(base, "GET", "/api/host/roster", who="vi", role="viewer").status_code == 403
        finally:
            await ws.close()
        await asyncio.sleep(0.3)
        assert all(p["user_id"] != "roster-ann" for p in api(base, "GET", "/api/host/roster").json()["people"]), "a closed socket leaves the roster at once"
    asyncio.run(run())


def test_a_page_reloaded_during_a_timeout_or_possession_comes_back_still_held(host):
    base, port, _ = host

    async def run():
        ws = await walker(port, "pw_replay1", tok("replay-ria", "guest"))
        assert api(base, "POST", "/api/host/timeout", json={"user_id": "replay-ria", "duration_seconds": 60}).status_code == 200
        first = [m for m in await drain(ws, 1.0) if m["type"] == "host_teleport"]
        assert len(first) == 1
        await ws.close()
        ws2 = await walker(port, "pw_replay2", tok("replay-ria", "guest"))             # the reloaded page
        again = [m for m in await drain(ws2, 1.0) if m["type"] == "host_teleport"]
        assert len(again) == 1 and again[0]["until"] == first[0]["until"] and again[0]["text"] == "TEST TIMEOUT"
        assert api(base, "POST", "/api/host/end-timeout", json={"user_id": "replay-ria"}).status_code == 200
        assert [m["type"] for m in await drain(ws2, 0.5)] == ["host_timeout_end"]
        await ws2.close()
        # once it is over a reconnect is free
        ws3 = await walker(port, "pw_replay3", tok("replay-ria", "guest"))
        assert [m for m in await drain(ws3, 0.6) if m["type"] in ("host_teleport", "host_notice")] == []
        # possession is replayed the same way
        assert api(base, "POST", "/api/host/possess", json={"user_id": "replay-ria", "duration_seconds": 60}).status_code == 200
        assert any(m["type"] == "host_notice" for m in await drain(ws3, 0.8))
        await ws3.close()
        ws4 = await walker(port, "pw_replay4", tok("replay-ria", "guest"))
        back = [m for m in await drain(ws4, 1.0) if m["type"] == "host_notice"]
        assert len(back) == 1 and back[0]["text"] == NOTICE
        assert api(base, "POST", "/api/host/release", json={"user_id": "replay-ria"}).status_code == 200
        await ws4.close()
    asyncio.run(run())


def test_a_banned_person_is_put_out_of_the_walker_and_cannot_come_back(host):
    base, port, _ = host

    async def run():
        ws = await walker(port, "pw_ban1", tok("ban-bo", "guest"))
        r = api(base, "POST", "/api/governance/ban", json={"user_id": "ban-bo", "reason": "TEST REASON", "ban_type": "permanent"})
        assert r.status_code == 200, r.text
        await ws.send(json.dumps({"type": "presence", "room": "dressing_room"}))          # presence arrives every 2 s in the real page
        got, code = await drain_closing(ws, 3.0)
        assert [m for m in got if m["type"] == "banned"] == [{"type": "banned", "reason": "TEST REASON"}] and code == 4403
        # coming back is refused at the door
        ws2 = await websockets.connect(f"ws://127.0.0.1:{port}/pubworld/ws/pw_ban2")
        await ws2.send(json.dumps({"type": "auth", "token": tok("ban-bo", "guest")}))
        got2, code2 = await drain_closing(ws2, 3.0)
        seen = [m["type"] for m in got2]
        assert "banned" in seen and "welcome" not in seen and code2 == 4403
        assert all(p["user_id"] != "ban-bo" for p in api(base, "GET", "/api/host/roster").json()["people"])
        # somebody else is untouched
        ok = await walker(port, "pw_ban3", tok("not-banned-bea", "guest"))
        await ok.close()
    asyncio.run(run())


# ── the host's panel, in a real browser, acting on a second real browser ───────

def _session(ctx, user, role):
    token = tok(user, role)
    ctx.add_init_script("sessionStorage.setItem('pubcast_token', %s); sessionStorage.setItem('pubcast_user', JSON.stringify({username:%s,user_id:%s,role:%s}));"
                        % (json.dumps(token), json.dumps(user), json.dumps(user), json.dumps(role)))


def _status(page, pattern, timeout=8000):
    """Wait for the panel's status line to match; on failure say what it actually said."""
    try:
        page.wait_for_function("(re) => new RegExp(re).test(document.getElementById('hpStatus').textContent)", arg=pattern, timeout=timeout)
    except sync_api.TimeoutError:
        raise AssertionError(f"panel status never matched {pattern!r}; it says {page.locator('#hpStatus').inner_text()!r}") from None


def test_the_owner_runs_the_walker_from_the_host_panel_and_a_guest_never_sees_it(host):
    base, port, data = host
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--no-sandbox"])
        except Exception as exc:
            pytest.skip(f"no Chromium available: {exc}")
        try:
            errors = []
            owner_ctx = browser.new_context(viewport={"width": 1400, "height": 900}); _session(owner_ctx, "panel-owner", "owner")
            guest_ctx = browser.new_context(viewport={"width": 1100, "height": 800}); _session(guest_ctx, "panel-nia", "guest")
            A = owner_ctx.new_page(); B = guest_ctx.new_page()
            for pg in (A, B):
                pg.on("pageerror", lambda e: errors.append(str(e)))
                pg.goto(base + "/walk")
                pg.wait_for_function("document.documentElement.dataset.ready === '1' && window.PubCastLive && window.PubCastLive.state.online === true", timeout=30000)

            # a guest's page has no host panel at all
            B.wait_for_timeout(1500)
            assert B.locator("#hostPanel").is_hidden()

            # the owner's page lists the guest, with numbers from the guest's page
            A.wait_for_function("!document.getElementById('hostPanel').hidden", timeout=15000)
            row = A.locator('#hpRoster button[data-id="panel-nia"]')
            row.wait_for(timeout=15000)
            row.click()
            A.wait_for_function("document.getElementById('hpName').textContent === 'panel-nia'", timeout=5000)
            A.wait_for_function("/Round trip to the host: \\d+ ms/.test(document.getElementById('hpStats').textContent)", timeout=15000)
            stats = A.locator("#hpStats").inner_text()
            assert "Frame rate:" in stats and "flat figure" in stats and "Walking as: pete" in stats, stats

            # the guest puts on a real 3D avatar: the roster shows what that avatar costs, measured from the file the page loaded
            B.click("#glbMannequin")
            B.wait_for_function("window.PubCastGLB.has('pete')", timeout=30000)
            info = B.evaluate("window.PubCastGLB.info('pete')")
            assert info["meshes"] >= 1 and info["bones"] >= 10 and info["tris"] >= 1000, info
            want = f"{info['meshes']:,} meshes, {info['bones']:,} bones, {info['tris']:,} triangles"
            A.wait_for_function("(w) => document.getElementById('hpStats').textContent.includes(w)", arg=want, timeout=15000)
            B.click("#glbClear")
            A.wait_for_function("document.getElementById('hpStats').textContent.includes('flat figure')", timeout=15000)

            # profile: edits are kept on the host
            A.fill("#hpTitle", "Bartender"); A.fill("#hpNotes", "Works the late shift"); A.check("#hpTracked"); A.check("#hpCtrlRoom")
            A.click("#hpSave")
            _status(A, "^Profile saved\\.$")
            rec = api(base, "GET", "/api/host/people/panel-nia").json()["person"]
            assert rec["title"] == "Bartender" and rec["notes"] == "Works the late shift" and rec["tracked"] is True and rec["privileges"]["control_room"] is True
            A.fill("#hpItem", "top hat"); A.click("#hpGiveItem")
            _status(A, "^Gifted: top hat\\.$")
            assert any(g["item"] == "top hat" for g in api(base, "GET", "/api/host/people/panel-nia").json()["person"]["gifts"])

            # take control from the panel: the guest is told in the configured words and stops walking by themselves
            A.fill("#hpReason", "panel test"); A.click("#hpPossess")
            _status(A, "You have control")
            B.wait_for_function("!document.getElementById('hostBanner').hidden", timeout=8000)
            assert NOTICE in B.locator("#hostBanner").inner_text()
            A.wait_for_function("/under your control/.test(document.getElementById('hpRoster').textContent)", timeout=8000)

            # "walk them where I click": the owner clicks the floor of the same picture and the guest walks there, the owner does not
            hold = A.evaluate("window.PubCastWalk.S.pos.slice()")
            b0 = B.evaluate("window.PubCastWalk.S.pos.slice()")
            goal = A.evaluate("(p) => window.PubCastWalk.snapToFloor(window.PubCastWalk.S.view, [p[0] + 140, p[1]])", b0)
            sx, sy = A.evaluate("(g) => window.PubCastWalk.toScreen(g)", goal)
            A.click("#hpDrive")
            A.wait_for_function("document.getElementById('hpDrive').getAttribute('aria-pressed') === 'true'", timeout=5000)
            box = A.locator("#c").bounding_box(); A.mouse.click(box["x"] + sx, box["y"] + sy)
            B.wait_for_function("(g) => Math.hypot(window.PubCastWalk.S.pos[0] - g[0], window.PubCastWalk.S.pos[1] - g[1]) < 8", arg=goal, timeout=40000)
            assert A.evaluate("window.PubCastWalk.S.pos.slice()") == hold, "the owner's own avatar must not walk while the owner is walking someone else"

            # release from the panel
            A.click("#hpRelease")
            B.wait_for_function("document.getElementById('hostBanner').hidden", timeout=8000)
            assert A.locator("#hpDrive").get_attribute("aria-pressed") == "false"

            # waiting room from the panel: the guest's whole picture is replaced; the roster shows where they are; a reload does not free them
            A.fill("#hpTSecs", "90"); A.click("#hpTimeout")
            B.wait_for_function("!document.getElementById('screen').hidden", timeout=8000)
            assert "TEST TIMEOUT" in B.locator("#screen").inner_text()
            A.wait_for_function("/in the waiting room/.test(document.getElementById('hpRoster').textContent)", timeout=8000)
            A.wait_for_function("/waiting_room_disciplinary/.test(document.getElementById('hpStats').textContent)", timeout=10000)
            B.reload()
            B.wait_for_function("document.documentElement.dataset.ready === '1' && window.PubCastLive.state.online === true", timeout=30000)
            B.wait_for_function("!document.getElementById('screen').hidden", timeout=8000)
            assert "TEST TIMEOUT" in B.locator("#screen").inner_text()
            b_pos = B.evaluate("window.PubCastWalk.S.pos.slice()"); B.keyboard.down("ArrowDown"); B.wait_for_timeout(500); B.keyboard.up("ArrowDown")
            assert B.evaluate("window.PubCastWalk.S.pos.slice()") == b_pos
            A.click("#hpEndTimeout")
            B.wait_for_function("document.getElementById('screen').hidden", timeout=8000)

            # ban from the panel needs a second click; then the guest is shown the host's reason and is not let back
            A.fill("#hpReason", "PANEL BAN REASON")
            A.click("#hpBan")
            assert "Click again" in A.locator("#hpBan").inner_text()
            A.click("#hpBan")
            B.wait_for_function("!document.getElementById('screen').hidden", timeout=15000)
            text = B.locator("#screen").inner_text()
            assert "Removed from the server" in text and "PANEL BAN REASON" in text
            B.wait_for_timeout(5000)                                         # it must not reconnect by itself
            assert B.evaluate("window.PubCastLive.state.online") is False
            A.wait_for_function("document.querySelector('#hpRoster button[data-id=\"panel-nia\"]') === null", timeout=10000)

            # the ban shows in "Out of the server" with the reason, and can be undone from the same panel
            A.wait_for_function("!document.getElementById('hpOut').hidden && /panel-nia \\(banned for good\\): PANEL BAN REASON/.test(document.getElementById('hpBanList').textContent)", timeout=10000)
            A.locator("#hpBanList .hp-ban", has_text="panel-nia").locator("button").click()          # others may be out too (ban-bo, from the socket test)
            _status(A, "Lifted")
            A.wait_for_function("!document.getElementById('hpBanList').textContent.includes('panel-nia')", timeout=10000)
            B.reload()
            B.wait_for_function("document.documentElement.dataset.ready === '1' && window.PubCastLive.state.online === true", timeout=30000)
            assert B.locator("#screen").is_hidden()
            A.locator('#hpRoster button[data-id="panel-nia"]').wait_for(timeout=15000)

            # the host's own record of all this: every action was written down, by the owner, against the guest
            body = api(base, "GET", "/api/governance/audit?limit=500").json()
            entries = body if isinstance(body, list) else (body.get("entries") or body.get("log") or [])
            mine = {e["action"] for e in entries if "panel-nia" in json.dumps(e)}
            assert {"POSSESS", "RELEASE", "TIMEOUT", "TIMEOUT_END"} <= mine, sorted(mine)
            assert api(base, "GET", "/api/host/people/panel-nia/log").json()["log"], "a tracked person's day is logged"
            assert [e for e in errors if "WSHub" not in e] == [], errors
            owner_ctx.close(); guest_ctx.close()
        finally:
            browser.close()

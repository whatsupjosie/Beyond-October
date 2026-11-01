"""The walkable world (static/world_walk.html) inside the real PubCast host.

Boots the real ``main.app`` with uvicorn in a separate process against a disposable data directory, then checks:
the /walk routes; the Counter, legacy Foresight and launcher entries; and, in real Chromium, that the walker joins the
same PubWorld socket world.html uses, reports rooms by their live ids (and the host acknowledges them), moves the room
audio runtime with it, runs dressing-room hotspots through /pubworld/api/hotspot, and hops to and from the classic page.
No user data is touched. Browser checks skip when Playwright/Chromium is unavailable.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def host(tmp_path_factory):
    data = tmp_path_factory.mktemp("walk_host_data")
    port = _free_port()
    env = dict(os.environ, PUBCAST_DATA_DIR=str(data), PYTHONUNBUFFERED="1")
    env.pop("PUBCAST_ENFORCE_AUTH", None)
    log = open(data / "host.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            if proc.poll() is not None:
                log.flush()
                raise AssertionError("PubCast host exited during startup:\n" + (data / "host.log").read_text(encoding="utf-8")[-4000:])
            try:
                if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                    break
            except httpx.RequestError:
                pass
            time.sleep(0.2)
        else:
            raise AssertionError("PubCast host did not come up within 90 s")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(15)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(5)
        log.close()


# ── HTTP: the host serves the walker and everything it loads ────────────────

@pytest.fixture(scope="module")
def owner(host):
    """The first-run owner account, created through the real setup route (pages need a Reach session)."""
    import secrets
    password = secrets.token_urlsafe(24)
    r = httpx.post(host + "/api/auth/setup", json={"username": "walk-owner", "password": password, "confirm_password": password}, timeout=10)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    assert data.get("access_token")
    return data


@pytest.mark.parametrize("route", ["/walk", "/world-walk"])
def test_the_host_serves_the_walkable_world(host, route):
    r = httpx.get(host + route, timeout=10)
    assert r.status_code == 200
    page = r.text
    assert "<title>Bella Faux Pas Studio</title>" in page
    for script in ("/static/reach_auth.js", "/static/world_walk_glb.js", "/static/world_walk_live.js"):
        assert f'src="{script}"' in page, script
        assert httpx.get(host + script, timeout=10).status_code == 200, script
    # the room audio runtime is loaded by the live link once it knows the host is there
    assert httpx.get(host + "/static/program_audio_runtime.js", timeout=10).status_code == 200
    world = httpx.get(host + "/static/world/world.json", timeout=10)
    assert world.status_code == 200 and world.json()["rooms"]
    for f in ("build/three.module.js", "examples/jsm/loaders/GLTFLoader.js", "examples/jsm/utils/SkeletonUtils.js"):
        assert httpx.get(host + "/static/vendor/three-0.160.0/" + f, timeout=10).status_code == 200, f


def test_the_walk_is_on_every_way_into_the_program():
    counter = (STATIC / "foresight_programs.js").read_text(encoding="utf-8")
    assert "{id: 'bella_faux_pas', title: 'Bella Faux Pas Studio', short: 'Studio', group: 'Programs', kind: 'page', url: '/walk'" in counter
    legacy = (STATIC / "foresight.html").read_text(encoding="utf-8")
    assert "{id:'bella_faux_pas',label:'Bella Faux Pas Studio',group:'Studio Rooms', kind:'iframe', url:'/walk'" in legacy
    assert '<a href="/walk" class="nav-pill">Bella Faux Pas</a>' in (STATIC / "launch.html").read_text(encoding="utf-8")
    classic = (STATIC / "world.html").read_text(encoding="utf-8")
    assert '<a id="walk-link" href="/walk"' in classic
    assert "a.href = '/walk?live=' + encodeURIComponent(e.detail.room)" in classic


def test_every_live_room_id_the_walker_reports_is_one_the_program_already_uses():
    """The walker reports rooms by live_id; those must be ids the classic page and the room audio runtime know."""
    import json, re
    world = json.loads((STATIC / "world" / "world.json").read_text(encoding="utf-8"))
    classic = (STATIC / "world.html").read_text(encoding="utf-8")
    classic_ids = set(re.findall(r"^  ([a-z_]+): \{$", classic[classic.index("const ROOMS = {"):classic.index("GAME STATE")], re.M))
    live = {r["live_id"] for r in world["rooms"] if r["live_id"]}
    assert live and live <= classic_ids | {"palace_theater"}, live - classic_ids
    # the dressing room is where the audio rule applies: its id must match the runtime's
    assert next(r for r in world["rooms"] if r["id"] == "dressing_room")["live_id"] == "dressing"


# ── Browser: the walker inside the real host ─────────────────────────────────

sync_api = pytest.importorskip("playwright.sync_api")

SPY = """
(() => {
  const Native = window.WebSocket;
  window.__wsSent = []; window.__wsGot = [];
  window.WebSocket = class extends Native {
    constructor(...a) {
      super(...a);
      this.addEventListener('message', e => { try { window.__wsGot.push(JSON.parse(e.data)); } catch (err) {} });
    }
    send(d) { try { window.__wsSent.push(JSON.parse(d)); } catch (err) {} return super.send(d); }
  };
})();
"""


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(args=["--no-sandbox"])
        except Exception as exc:  # no browser installed for this Playwright
            pytest.skip(f"no Chromium available: {exc}")
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    pg = browser.new_page(viewport={"width": 1400, "height": 860})
    pg.problems = []
    pg.on("pageerror", lambda e: pg.problems.append(str(e)))
    pg.add_init_script(SPY)
    yield pg
    pg.close()


@pytest.fixture()
def signed_in(page, owner):
    """A page whose Reach session is the owner's, saved the way login.html saves it (ReachAuth.saveSession)."""
    import json
    session = json.dumps({"token": owner["access_token"], "user": owner.get("username") or "walk-owner", "role": owner.get("role") or "owner"})
    page.add_init_script(f"""
      (s => {{
        if (!sessionStorage.getItem('pubcast_token')) {{
          sessionStorage.setItem('pubcast_token', s.token);
          sessionStorage.setItem('pubcast_user', JSON.stringify({{username: s.user, user_id: s.user, role: s.role}}));
        }}
      }})({session});
    """)
    return page


def _open(page, url):
    page.goto(url)
    page.wait_for_function("document.documentElement.dataset.ready === '1' && !!window.PubCastLive", timeout=30000)


def _use_hotspot(page, hotspot_id, button):
    page.evaluate("(id) => { const W = window.PubCastWalk; W.showHotspotBubble(W.S.view.hotspots.find(h => h.id === id)); }", hotspot_id)
    page.get_by_role("button", name=button, exact=True).click()
    page.wait_for_function("() => { const b = document.getElementById('bubble'); return !b.hidden && !/Working/.test(b.textContent); }", timeout=15000)
    return page.evaluate("() => ({ title: document.querySelector('#bubble h3').textContent, body: (document.querySelector('#bubble p') || {}).textContent || '' })")


def test_the_walker_joins_the_pubworld_socket_and_the_host_acknowledges_its_rooms(host, signed_in):
    page = signed_in
    _open(page, host + "/walk?live=dressing")
    assert page.evaluate("window.PubCastWalk.S.room.id") == "dressing_room"
    page.wait_for_function("window.PubCastLive.state.online === true", timeout=15000)
    assert page.locator("#chipLive").inner_text().endswith("Connected")
    page.wait_for_function("window.__wsGot.some(m => m.type === 'room_ack' && m.room === 'dressing')", timeout=10000)
    # walking through a door is a room change the host hears about, under the id the rest of PubCast uses
    page.evaluate("window.PubCastWalk.goTo('green_room', 'dressing_room')")
    page.wait_for_function("window.__wsGot.some(m => m.type === 'room_ack' && m.room === 'greenroom')", timeout=10000)
    sent = page.evaluate("window.__wsSent.filter(m => m.type === 'room_change').map(m => [m.room, m.world_room])")
    assert ["greenroom", "green_room"] in sent
    assert page.problems == []


def test_the_room_audio_rule_follows_the_walker(host, signed_in):
    page = signed_in
    _open(page, host + "/walk?live=greenroom")
    page.wait_for_function("window.PubCastLive.state.online === true && !!window.PubcastProgramAudio", timeout=15000)
    page.wait_for_function("window.PubcastProgramAudio.room === 'greenroom'", timeout=10000)
    page.evaluate("window.PubCastWalk.goTo('dressing_room', 'green_room')")
    page.wait_for_function("window.PubcastProgramAudio.room === 'dressing'", timeout=10000)
    assert page.evaluate("window.PubcastProgramAudio.allowed()") is False                      # only director announcements
    assert page.evaluate("window.PubcastProgramAudio.allowed({directorAnnouncement: true})") is True
    # a close-up inside the dressing room is the same room: no new room change
    before = page.evaluate("window.__wsSent.filter(m => m.type === 'room_change').length")
    page.evaluate("window.PubCastWalk.setView('dressing_room', 'corkboard', {})")
    page.wait_for_function("window.PubCastWalk.S.view.id === 'corkboard'")
    assert page.evaluate("window.PubcastProgramAudio.room") == "dressing"
    assert page.evaluate("window.__wsSent.filter(m => m.type === 'room_change').length") == before + 1  # view update, same room
    assert page.evaluate("window.__wsSent.filter(m => m.type === 'room_change').pop().room") == "dressing"
    assert page.problems == []


def test_dressing_room_hotspots_run_on_the_host(host, signed_in):
    page = signed_in
    _open(page, host + "/walk?live=dressing")
    page.wait_for_function("window.PubCastLive.state.online === true", timeout=15000)
    typed = _use_hotspot(page, "typewriter", "Use it here")
    assert typed["title"] == "Typewriter" and "Script draft" in typed["body"]
    page.get_by_role("button", name="My scripts", exact=True).click()
    page.wait_for_function("document.querySelector('#bubble h3').textContent === 'Scripts'", timeout=15000)
    assert "Draft" in page.evaluate("document.querySelector('#bubble p').textContent")
    worn = _use_hotspot(page, "wardrobe", "Use")
    assert worn["title"] == "Wardrobe"
    page.get_by_role("button", name="Formal Suit", exact=True).click()
    page.wait_for_function("/Wearing: Formal Suit/.test(document.querySelector('#bubble p').textContent)", timeout=15000)
    board = _use_hotspot(page, "message-board", "Use it here")      # it also opens the corkboard close-up
    assert board["title"] == "Message board" and "Stage Manager" in board["body"]
    look = _use_hotspot(page, "makeup-station", "Use it here")
    assert look["title"] == "Hair and makeup" and "Natural" in look["body"]
    # the walker sends the same hotspot call world.html makes
    calls = page.evaluate("window.__wsSent.filter(m => m.type === 'hotspot').map(m => [m.action, m.room])")
    assert ["typewriter", "dressing"] in calls and ["wardrobe", "dressing"] in calls
    assert page.problems == []


def test_sitting_and_the_tv_in_the_green_room(host, signed_in):
    page = signed_in
    _open(page, host + "/walk?live=greenroom")
    page.wait_for_function("window.PubCastLive.state.online === true", timeout=15000)
    sat = _use_hotspot(page, "couch-sit-left", "Use")
    assert sat["title"] == "Take a seat" and "left curve" in sat["body"]
    tv = _use_hotspot(page, "tv", "Use")
    assert tv["title"] == "TV" and tv["body"].startswith("Channel: ")
    first = tv["body"]
    page.get_by_role("button", name="Flip channel", exact=True).click()
    page.wait_for_function("(b) => document.querySelector('#bubble p').textContent !== b", arg=first, timeout=15000)
    assert page.problems == []


def test_hotspots_the_host_has_no_action_for_stay_local(host, signed_in):
    page = signed_in
    _open(page, host + "/walk?live=controlroom")
    page.evaluate("() => { const W = window.PubCastWalk; W.showHotspotBubble(W.S.view.hotspots.find(h => h.id === 'director-console')); }")
    assert page.get_by_role("button", name="Use", exact=True).count() == 0
    assert "Not wired yet" in page.locator("#bubble p").inner_text()
    assert page.problems == []


def test_classic_pubworld_and_the_walker_hop_to_each_other_at_the_same_room(host, signed_in):
    page = signed_in
    page.goto(host + "/world?room=greenroom")
    page.wait_for_function("document.getElementById('walk-link').getAttribute('href') === '/walk?live=greenroom'", timeout=15000)
    page.click("#walk-link")
    page.wait_for_function("document.documentElement.dataset.ready === '1' && !!window.PubCastWalk", timeout=30000)
    assert page.evaluate("window.PubCastWalk.S.room.id") == "green_room"
    assert page.locator("#classicLink").get_attribute("href") == "/world?room=greenroom"
    assert page.problems == []


def test_without_the_host_behind_it_the_walker_says_so_and_keeps_walking(page, tmp_path):
    # the same page served by a plain file server: no socket, no hotspot API
    port = _free_port()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=str(ROOT),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                httpx.get(f"http://127.0.0.1:{port}/static/world_walk.html", timeout=0.3); break
            except httpx.RequestError:
                time.sleep(0.1)
        _open(page, f"http://127.0.0.1:{port}/static/world_walk.html?live=dressing")
        page.wait_for_function("window.PubCastLive.state.host === false", timeout=10000)
        assert page.evaluate("window.PubCastLive.state.online") is False
        assert page.evaluate("!window.PubcastProgramAudio")                # no host: no room-audio polling
        assert page.locator("#chipLive").inner_text().endswith("Offline")
        got = _use_hotspot(page, "wardrobe", "Use")
        assert got["title"] == "Not connected" and "Walking still works" in got["body"]
        assert page.problems == []
    finally:
        srv.terminate(); srv.wait(5)


@pytest.fixture
def fresh_studio_progress(host, owner):
    # Earlier tests intentionally save the owner's room on the same host.
    # These default-entry tests require a fresh progress record; preserving
    # real resume behavior must not depend on test collection order.
    response = httpx.put(host + "/api/studio/progress", headers={"Authorization": "Bearer " + owner["access_token"]},
                         json={"progress": {}}, timeout=10)
    assert response.status_code == 200


def test_bella_faux_pas_studio_opens_from_the_foresight_counter_in_the_dressing_room(host, browser, owner, fresh_studio_progress):
    """The Counter is the program's front door: its menu opens the walker in a tray, live, under the same session.
    Uses a plain page (no WebSocket recorder: the Counter does not start under it)."""
    import json
    page = browser.new_page(viewport={"width": 1400, "height": 860})
    page.problems = []
    page.on("pageerror", lambda e: page.problems.append(str(e)))
    page.add_init_script("sessionStorage.setItem('pubcast_token', %s); sessionStorage.setItem('pubcast_user', JSON.stringify({username: 'walk-owner', user_id: 'walk-owner', role: 'owner'}));" % json.dumps(owner["access_token"]))
    # ?once: no continuous animation loop (software graphics here cannot keep up with it); fresh, nosave: a clean Counter
    page.goto(host + "/foresight-counter?once&fresh&nosave")
    try:
        page.wait_for_function("!!window.__programs && !!window.__counter", timeout=30000)
    except Exception:
        pytest.fail(f"the Counter did not start: now at {page.url}; page errors {page.problems}")
    # File > Open... is the Counter's way to open a program: its picker must offer the walker
    page.evaluate("window.__counter.openPicker(null)")
    entry = page.get_by_text("Bella Faux Pas Studio", exact=True)
    entry.first.wait_for(timeout=10000)
    assert entry.count() == 1
    entry.first.evaluate("el => (el.closest('button,[role=button],li') || el).click()")
    page.wait_for_function("() => [...document.querySelectorAll('iframe')].some(f => /\\/walk(\\?|$)/.test(f.getAttribute('src') || ''))", timeout=20000)
    frame = next(f for f in page.frames if "/walk" in f.url)
    frame.wait_for_function("document.documentElement.dataset.ready === '1' && !!window.PubCastLive", timeout=30000)
    frame.wait_for_function("window.PubCastLive.state.online === true", timeout=15000)
    assert frame.evaluate("window.PubCastWalk.S.view.zones.length") > 0
    assert frame.evaluate("window.PubCastWalk.S.room.id") == "dressing_room"        # the studio starts in the dressing room
    assert frame.evaluate("window.PubCastLive.state.room") == "dressing"
    assert page.problems == []
    page.close()



def test_the_studio_starts_in_the_dressing_room_with_no_start_given(host, signed_in, fresh_studio_progress):
    page = signed_in
    _open(page, host + "/walk")
    assert page.evaluate("window.PubCastWalk.S.room.id") == "dressing_room"
    assert page.evaluate("window.PubCastWalk.S.world.start") == "dressing_room"
    page.wait_for_function("window.PubCastLive.state.online === true", timeout=15000)
    page.wait_for_function("window.__wsGot.some(m => m.type === 'room_ack' && m.room === 'dressing')", timeout=10000)
    assert page.problems == []

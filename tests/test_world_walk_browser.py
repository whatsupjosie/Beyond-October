"""static/world_walk.html in a real browser (skipped where Playwright + Chromium are not installed).

Checks that the page's JavaScript gives the same answers as modules/pubcast_world_placement.py (zones,
altitude, avatar size, snapping, draw order) and that the walk, door bubbles and tuner behave.
"""
import functools
import http.server
import json
import math
import os
import threading
from pathlib import Path

import pytest

from modules import pubcast_world_placement as P

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = None
        for kwargs in ({}, {"executable_path": os.environ.get("PLAYWRIGHT_CHROMIUM", "/opt/pw-browsers/chromium")}):
            try:
                b = p.chromium.launch(args=["--no-sandbox"], **kwargs)
                break
            except Exception:
                continue
        if b is None:
            pytest.skip("no Chromium available")
        yield b
        b.close()


@pytest.fixture()
def page(server, browser):
    pg = browser.new_page(viewport={"width": 1500, "height": 860})
    pg.problems = []
    # served without the PubCast host, the live link asks /health once to find out; that one 404 is expected
    pg.on("console", lambda m: pg.problems.append(m.text)
          if m.type in ("error", "warning") and not (m.location or {}).get("url", "").endswith("/health") else None)
    pg.on("pageerror", lambda e: pg.problems.append(str(e)))
    pg.open = lambda key: (pg.goto(f"{server}/static/world_walk.html?view={key}"),
                           pg.wait_for_function("document.documentElement.dataset.ready==='1'", timeout=15000))
    yield pg
    pg.close()


def sample_points(view):
    pts = []
    for z in view["zones"]:
        poly = z["points"]
        pts += [tuple(p) for p in poly]
        pts.append((sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)))
    allp = [p for z in view["zones"] for p in z["points"]]
    x0, x1 = min(p[0] for p in allp), max(p[0] for p in allp)
    y0, y1 = min(p[1] for p in allp), max(p[1] for p in allp)
    for i in range(7):
        for j in range(7):
            pts.append((x0 - 40 + (x1 - x0 + 80) * i / 6, y0 - 40 + (y1 - y0 + 80) * j / 6))
    return [(round(x, 3), round(y, 3)) for x, y in pts]


def close(a, b):
    if a is None or b is None:
        return a is b or (a is None and b is None)
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def test_the_pages_maths_matches_the_python_module_everywhere(page):
    page.open("green_room/main")
    world = P.merged_world()
    checked = 0
    for room in world["rooms"]:
        for view in room["views"]:
            if not view["zones"]:
                continue
            key = f"{room['id']}/{view['id']}"
            pts = sample_points(view)
            got = page.evaluate("""([key, pts]) => {
                const W = window.PubCastWalk, [r, v] = key.split('/');
                const view = W.S.rooms[r].views.find(x => x.id === v);
                return pts.map(p => {
                    const zone = W.zoneAt(view, p), alt = zone ? W.altitudeAt(zone, p) : null;
                    const snap = W.snapToFloor(view, p);
                    return { zone: zone ? zone.id : null, alt,
                             ppi: W.ppiFor({camera: view.camera, scale: view.scale}, p[1], alt, zone),
                             snap, inside: W.floorContains(view, p) };
                });
            }""", [key, pts])
            floor = [P.zone_points(z) for z in view["zones"]]
            for p, g in zip(pts, got):
                zone = P.zone_at(view["zones"], p)
                alt = P.altitude_at(zone, p) if zone else None
                assert g["zone"] == (zone["id"] if zone else None), (key, p)
                assert close(g["alt"], alt), (key, p, g["alt"], alt)
                assert close(g["ppi"], P.ppi_for(view, p[1], alt, zone)), (key, p, g["ppi"])
                sn = P.snap_to_floor(floor, p)
                assert math.isclose(g["snap"][0], sn[0], abs_tol=1e-6) and math.isclose(g["snap"][1], sn[1], abs_tol=1e-6), (key, p)
                assert g["inside"] == P.floor_contains(floor, p), (key, p)
                checked += 1
            for o in view["occluders"]:
                rows = [0, 9999] + ([o["base_y"] - 1, o["base_y"], o["base_y"] + 1] if "base_y" in o else [])
                for y in rows:
                    assert page.evaluate("([o, y]) => window.PubCastWalk.occluderInFront(o, y)", [o, y]) == P.occluder_in_front(o, y), (key, o["id"], y)
    assert checked > 800


def test_every_picture_loads_and_a_start_position_is_on_its_floor(page):
    page.open("green_room/main")
    keys = page.evaluate("[...document.querySelectorAll('#viewSel option')].map(o => o.value)")
    assert len(keys) >= 20
    for k in keys:
        r, v = k.split("/")
        page.evaluate("([r, v]) => window.PubCastWalk.setView(r, v, {instant: true})", [r, v])
        info = page.evaluate("""() => { const W = window.PubCastWalk, S = W.S;
            return {key: S.key, zones: S.view.zones.length, inside: S.view.zones.length ? W.floorContains(S.view, S.pos) : null,
                    H: S.view.zones.length ? W.avatarPx('pete', S.pos[1], W.zoneAt(S.view, S.pos), S.pos) : null}; }""")
        if info["zones"]:
            assert info["inside"] is True and info["H"] and info["H"] > 5, info
    assert page.problems == []


def test_walking_stays_on_the_floor_and_a_click_off_the_floor_snaps_onto_it(page):
    page.open("green_room/main")
    def click(x, y):
        sx, sy = page.evaluate("([x, y]) => window.PubCastWalk.toScreen([x, y])", [x, y])
        page.mouse.click(sx, sy)
    def settle():
        page.wait_for_function("window.PubCastWalk.S.target === null", timeout=30000)
    click(300, 560); settle()
    x, y = page.evaluate("window.PubCastWalk.S.pos")
    assert abs(x - 300) < 8 and abs(y - 560) < 8
    click(800, 60); settle()
    assert page.evaluate("() => window.PubCastWalk.floorContains(window.PubCastWalk.S.view, window.PubCastWalk.S.pos)")


def test_door_one_is_one_bubble_with_both_choices_and_the_theater_is_locked(page):
    page.open("green_room/main")
    sx, sy = page.evaluate("() => window.PubCastWalk.toScreen([343, 252])")
    page.mouse.click(sx, sy)
    page.wait_for_selector("#bubble:not([hidden])", timeout=30000)
    assert page.eval_on_selector_all("#bubble button", "bs => bs.map(b => b.textContent)") == \
        ["Palace Hall (theater lobby hallway)", "Writers' Room", "Stay here"]
    page.click("#bubble button:has-text(\"Writers' Room\")")
    page.wait_for_function("window.PubCastWalk.S.key === 'writers_room/main'", timeout=10000)
    page.open("palace_hallway/main")
    sx, sy = page.evaluate("() => window.PubCastWalk.toScreen([520, 405])")
    page.mouse.click(sx, sy)
    page.wait_for_selector("#bubble:not([hidden])", timeout=30000)
    states = page.eval_on_selector_all("#bubble button", "bs => bs.map(b => [b.textContent, b.disabled])")
    assert any("theater" in t.lower() and d for t, d in states), states


def test_the_tuner_changes_only_the_picture_it_is_on_and_reset_restores_it(page):
    page.open("studio_director/main")
    height = "() => { const W = window.PubCastWalk; return W.avatarPx('pete', W.S.pos[1], W.zoneAt(W.S.view, W.S.pos), W.S.pos); }"
    before = page.evaluate(height)
    page.evaluate("() => { const r = document.querySelectorAll('#tuner input[type=range]')[2]; r.value = 90; r.dispatchEvent(new Event('input')); }")
    assert page.evaluate(height) < before
    assert list(page.evaluate("window.PubCastWalk.S.tune").keys()) == ["studio_director/main"]
    page.click("#tuneReset")
    assert page.evaluate(height) == pytest.approx(before)
    assert page.problems == []


def _pete_px_at(page, y):
    return page.evaluate("(y) => { const W = window.PubCastWalk; return W.avatarPx('pete', y, W.zoneAt(W.S.view, [W.S.pos[0], y]), [W.S.pos[0], y]); }", y)


@pytest.mark.parametrize("key", ["studio_director/main", "writers_room/main"])
def test_the_overall_size_multiplier_scales_every_avatar_in_that_picture_only(page, key):
    page.open(key)
    y = page.evaluate("window.PubCastWalk.S.pos[1]")
    before = _pete_px_at(page, y)
    page.evaluate("() => { const r = document.querySelector('#tuner input[type=range]'); r.value = 1.5; r.dispatchEvent(new Event('input')); }")
    assert _pete_px_at(page, y) == pytest.approx(before * 1.5, rel=1e-6)
    assert list(page.evaluate("window.PubCastWalk.S.tune").keys()) == [key]
    page.click("#tuneReset")
    assert _pete_px_at(page, y) == pytest.approx(before)
    assert page.problems == []


def test_a_coke_can_sizes_the_avatars_from_what_the_user_says_looks_right(page):
    page.open("writers_room/main")
    W = "window.PubCastWalk"
    before = _pete_px_at(page, 700)
    page.click("#canAdd")
    sx, sy = page.evaluate(f"() => {W}.toScreen([600, 700])")
    page.mouse.click(sx, sy)
    cans = page.evaluate(f"() => {W}.S.cans['writers_room/main']")
    assert len(cans) == 1 and cans[0]["y"] == pytest.approx(700, abs=1) and cans[0]["fy"] is None
    # drag the yellow handle: the can's height follows the pointer
    s = page.evaluate(f"() => {W}.S.fit.s")
    can = cans[0]
    ry = max(1.2, can["h"] * 2.6 / 4.83 * 0.12)
    hx, hy = page.evaluate(f"() => {W}.toScreen([{can['x']}, {can['y'] - can['h'] - ry - 10 / s}])")
    page.mouse.move(hx, hy)
    page.mouse.down()
    tx, ty = page.evaluate(f"() => {W}.toScreen([{can['x']}, {can['y'] - 20 - 10 / s}])")
    page.mouse.move(tx, ty)
    page.mouse.up()
    can = page.evaluate(f"() => {W}.S.cans['writers_room/main'][0]")
    assert can["h"] == pytest.approx(20, abs=0.6)
    # not used yet: nothing changed
    assert _pete_px_at(page, 700) == pytest.approx(before)
    page.check("#canUse")
    assert _pete_px_at(page, 700) == pytest.approx(68 * 20 / 4.83, rel=0.03)
    # one can = a flat scale: the same everywhere
    assert _pete_px_at(page, 900) == pytest.approx(_pete_px_at(page, 700), rel=1e-6)
    # a can on a raised surface counts at the floor row under it
    page.evaluate(f"() => {{ const k = {W}.S.cans['writers_room/main'][0]; k.fy = 760; }}")
    page.evaluate("() => { const r = document.querySelector('#canList input[type=range]'); r.dispatchEvent(new Event('input')); }")
    rows = page.evaluate(f"() => {W}.S.tune['writers_room/main'].canScale")
    assert rows[0]["y"] == 760 and rows[0]["ppi"] == pytest.approx(20 / 4.83, rel=0.03)
    page.uncheck("#canUse")
    assert _pete_px_at(page, 700) == pytest.approx(before)
    assert page.problems == []


def test_a_click_across_the_room_walks_round_the_furniture_and_arrives(page):
    page.open("writers_room/main")
    page.evaluate("() => { const S = window.PubCastWalk.S; S.pos = [880, 730]; S.target = null; }")
    sx, sy = page.evaluate("(p) => window.PubCastWalk.toScreen(p)", [420, 955])
    page.mouse.click(sx, sy)
    page.wait_for_function("window.PubCastWalk.S.path && window.PubCastWalk.S.path.length >= 1", timeout=3000)
    page.wait_for_function("!window.PubCastWalk.S.target", timeout=60000)
    x, y = page.evaluate("window.PubCastWalk.S.pos")
    assert abs(x - 420) < 12 and abs(y - 955) < 12, (x, y)                       # got there, not stuck behind the table
    assert page.problems == []


def test_a_click_with_no_route_still_creeps_towards_the_goal_without_leaving_the_floor(page):
    page.open("writers_room/main")
    ok = page.evaluate("""() => { const W = window.PubCastWalk, S = W.S; const v = S.view; let bad = 0;
        S.pos = [880, 730]; W.S.target = [420, 955]; S.path = [];                 // no planned route: head straight, creep round
        return true; }""")
    page.wait_for_function("!window.PubCastWalk.S.target", timeout=60000)
    assert page.evaluate("(p) => window.PubCastWalk.floorContains(window.PubCastWalk.S.view, window.PubCastWalk.S.pos)", None)
    assert page.problems == []


def test_arrow_keys_walk_and_stay_on_the_floor(page):
    page.open("writers_room/main")
    page.evaluate("""() => { const W = window.PubCastWalk, S = W.S; S.target = null;
        S.pos = W.snapToFloor(S.view, [880, 730]); }""")                            # open floor at the back right
    y0 = page.evaluate("window.PubCastWalk.S.pos[1]")
    page.keyboard.down("ArrowDown")
    page.wait_for_timeout(700)
    assert page.evaluate("window.PubCastWalk.S.moving") is True
    page.keyboard.up("ArrowDown")
    page.wait_for_timeout(200)
    assert page.evaluate("window.PubCastWalk.S.pos[1]") > y0 + 15
    assert page.evaluate("window.PubCastWalk.S.moving") is False
    page.keyboard.down("ArrowLeft")                                              # hold it long enough to hit the room's edge
    page.wait_for_timeout(3500)
    page.keyboard.up("ArrowLeft")
    assert page.evaluate("() => { const W = window.PubCastWalk; return W.floorContains(W.S.view, W.S.pos); }")
    assert page.problems == []

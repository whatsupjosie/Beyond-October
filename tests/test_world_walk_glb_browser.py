"""3D avatars in static/world_walk.html: a GLB is sized to the picture's pixel height, stands on the feet point,
turns to face where it walks, plays its walk clip and sits behind the cut-outs. Skipped where there is no Chromium with WebGL."""
import functools
import http.server
import os
import threading
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
GL_ARGS = ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]


@pytest.fixture(scope="module")
def server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = None
        for kwargs in ({}, {"executable_path": os.environ.get("PLAYWRIGHT_CHROMIUM", "/opt/pw-browsers/chromium")}):
            try:
                b = p.chromium.launch(args=GL_ARGS, **kwargs)
                break
            except Exception:
                continue
        if b is None:
            pytest.skip("no Chromium available")
        yield b
        b.close()


@pytest.fixture()
def page(server, browser):
    pg = browser.new_page(viewport={"width": 1500, "height": 900})
    pg.problems = []
    pg.on("pageerror", lambda e: pg.problems.append(str(e)))
    pg.goto(f"{server}/static/world_walk.html?view=writers_room/main")
    pg.wait_for_function("document.documentElement.dataset.ready==='1' && !!window.PubCastGLB", timeout=20000)
    yield pg
    pg.close()


BBOX = """async ({H}) => {
  const G = window.PubCastGLB;
  const c = document.createElement('canvas'); c.width = 600; c.height = 700; const x = c.getContext('2d');
  G.draw(x, 'pete', 300, 600, H, {vx: 0, vy: 1, moving: false, dt: 0.016, pxScale: 1});
  const d = x.getImageData(0, 0, 600, 700).data; let top = 1e9, bot = -1, l = 1e9, r = -1;
  for (let j = 0; j < 700; j++) for (let i = 0; i < 600; i++) if (d[(j * 600 + i) * 4 + 3] > 40) { top = Math.min(top, j); bot = Math.max(bot, j); l = Math.min(l, i); r = Math.max(r, i); }
  return {top, bot, l, r};
}"""


def load_mannequin(page):
    page.click("#glbMannequin")
    page.wait_for_function("window.PubCastGLB.has('pete')", timeout=30000)


def test_a_glb_is_sized_to_the_requested_pixel_height_and_stands_on_the_feet_point(page):
    load_mannequin(page)
    info = page.evaluate("window.PubCastGLB.info('pete')")
    assert "walk" in info["clips"] and "idle" in info["clips"] and info["skinned"]
    for H in (120, 300, 520):
        b = page.evaluate(BBOX, {"H": H})
        assert b["bot"] == pytest.approx(600, abs=max(3, H * 0.02)), (H, b)           # feet on the feet row
        assert b["bot"] - b["top"] == pytest.approx(H, rel=0.04), (H, b)               # exactly that tall
        assert abs((b["l"] + b["r"]) / 2 - 300) < H * 0.12, (H, b)                      # centred on the feet x
    assert page.problems == []


def test_walking_turns_the_avatar_and_the_picture_keeps_drawing_it(page):
    load_mannequin(page)
    before = page.evaluate("window.PubCastWalk.S.pos")
    far = page.evaluate("""() => { const W = window.PubCastWalk, S = W.S, p = S.pos;
        const xs = S.view.zones[0].points.map(q => q[0]); const x = p[0] - (Math.max(...xs) - Math.min(...xs)) * 0.3;
        return W.snapToFloor(S.view, [x, p[1] - 40]); }""")
    sx, sy = page.evaluate("(p) => window.PubCastWalk.toScreen(p)", far)
    page.mouse.click(sx, sy)
    page.wait_for_function("window.PubCastWalk.S.moving === true", timeout=3000)
    assert page.evaluate("window.PubCastWalk.S.vel[0]") < -0.2                # heading left
    page.wait_for_function("!window.PubCastWalk.S.target", timeout=30000)
    after = page.evaluate("window.PubCastWalk.S.pos")
    assert after[0] < before[0] - 60
    assert page.evaluate("window.PubCastWalk.S.moving") is False
    assert page.problems == []


def test_a_broken_file_is_refused_and_the_flat_figure_stays(page):
    page.evaluate("() => window.PubCastGLB.load('pete', '/static/world/rooms/writers_room.jpg', 'bad').catch(() => {})")
    page.wait_for_timeout(800)
    assert page.evaluate("window.PubCastGLB.has('pete')") is False
    assert page.problems == []


@pytest.mark.parametrize("button,label,expected_clip", [
    ("glbDemoFemale", "MakeHuman female", "Wave"),
    ("glbDemoMale", "MakeHuman male", "Wave"),
    ("glbDemoHusky", "Husky (3 ft)", "Walk"),
])
def test_bundled_demo_bodies_load_in_the_real_walker(page, button, label, expected_clip):
    page.click("#" + button)
    page.wait_for_function("window.PubCastGLB.has('pete')", timeout=30000)
    info = page.evaluate("window.PubCastGLB.info('pete')")
    assert info["label"] == label
    assert info["skinned"] > 0 and info["bones"] > 0 and info["tris"] > 0
    assert any(expected_clip.lower() in name.lower() for name in info["clips"])
    assert info["proceduralWalk"] is (button != "glbDemoHusky")
    if button == "glbDemoHusky":
        page.wait_for_function("window.PubCastWalk.S.demoHeights.pete === 36")
        height = page.evaluate("""() => {
          const W = window.PubCastWalk, S = W.S, zone = W.zoneAt(S.view, S.pos);
          const actual = W.avatarPx("pete", S.pos[1], zone, S.pos);
          const ppi = W.ppiFor(W.sizingOf(S.view), S.pos[1],
            zone ? W.altitudeAt(zone, S.pos) : null, zone);
          return {actual, expected: 36 * ppi, override: S.demoHeights.pete};
        }""")
        assert height["override"] == 36
        assert height["actual"] == pytest.approx(height["expected"], abs=0.01)
    else:
        assert page.evaluate("window.PubCastWalk.S.demoHeights.pete") is None
    assert page.problems == []


def test_husky_walks_across_green_room_and_enters_writers_room(page):
    page.goto(page.url.split("?")[0] + "?view=green_room/main")
    page.wait_for_function("document.documentElement.dataset.ready==='1' && !!window.PubCastGLB")
    page.click("#glbDemoHusky")
    page.wait_for_function("window.PubCastGLB.has('pete') && window.PubCastWalk.S.demoHeights.pete === 36", timeout=30000)
    page.wait_for_function("window.PubCastGLB.info('pete').clips.some(c => /walk/i.test(c))")
    origin = page.evaluate("window.PubCastWalk.S.pos")
    sx, sy = page.evaluate("() => window.PubCastWalk.toScreen([343, 252])")
    page.mouse.click(sx, sy)
    page.wait_for_selector("#bubble:not([hidden])", timeout=30000)
    assert page.evaluate("window.PubCastWalk.S.pos") != origin
    page.click('#bubble button:has-text("Writers\' Room")')
    page.wait_for_function("window.PubCastWalk.S.key === 'writers_room/main'", timeout=15000)
    assert page.evaluate("window.PubCastGLB.has('pete')")
    assert page.evaluate("window.PubCastWalk.S.demoHeights.pete") == 36
    assert page.evaluate("window.PubCastWalk.floorContains(window.PubCastWalk.S.view, window.PubCastWalk.S.pos)")
    assert page.problems == []

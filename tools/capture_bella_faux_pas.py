"""Capture *actual* Bella Faux Pas pixels and movement, or fail without artifacts.

Uses the shipped world_walk.html, original room pictures, GLB renderer, and browser input.
Nothing here constructs replacement room pictures or a simulated character.
Run from the repository root: python tools/capture_bella_faux_pas.py
Requires Playwright with Chromium installed. Writes to artifacts/bella-faux-pas-proof/.
"""
from __future__ import annotations

import http.server
import json
import shutil
import subprocess
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "bella-faux-pas-proof"
GL_ARGS = [
    "--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
]


def ready(page):
    page.wait_for_function(
        "document.documentElement.dataset.ready === '1' && !!window.PubCastGLB",
        timeout=30000,
    )
    info = page.evaluate("""() => ({
      room: window.PubCastWalk.S.room.id,
      view: window.PubCastWalk.S.view.id,
      artwork: window.PubCastWalk.S.img?.src,
      loaded: window.PubCastWalk.S.img?.complete &&
              window.PubCastWalk.S.img?.naturalWidth > 0
    })""")
    if not info["loaded"]:
        raise AssertionError("The original room artwork has not loaded: " + repr(info))
    return info


def husky(page):
    page.locator("#shPads").uncheck()
    page.locator("#glbDemoHusky").click()
    page.wait_for_function(
        "window.PubCastGLB.has('pete') && window.PubCastWalk.S.demoHeights.pete === 36",
        timeout=30000,
    )
    info = page.evaluate("window.PubCastGLB.info('pete')")
    if not info["skinned"] or not any("walk" in c.lower() for c in info["clips"]):
        raise AssertionError("Real Husky GLB with its native walk clip did not load: " + repr(info))
    page.wait_for_timeout(300)
    return info


def door(page, coords, destination, expected_room):
    screen = page.evaluate("(pt) => window.PubCastWalk.toScreen(pt)", coords)
    page.mouse.click(*screen)
    page.locator("#bubble:not([hidden])").wait_for(timeout=60000)
    buttons = page.locator("#bubble button")
    labels = buttons.all_text_contents()
    for idx, label in enumerate(labels):
        if destination.lower() in label.lower():
            buttons.nth(idx).click()
            page.wait_for_function(
                "expected => window.PubCastWalk.S.room.id === expected",
                arg=expected_room, timeout=15000,
            )
            ready(page)
            if not page.evaluate("window.PubCastGLB.has('pete')"):
                raise AssertionError("The 3D Husky was lost at the doorway")
            return
    raise AssertionError("No door to %s; choices: %r" % (destination, labels))


def record_walk(browser, origin):
    """A separate real-browser take so the clip focuses on the Husky moving."""
    temp = OUTPUT / "_playwright_recording"
    temp.mkdir(exist_ok=True)
    ctx = browser.new_context(
        viewport={"width": 1500, "height": 900},
        record_video_dir=str(temp),
        record_video_size={"width": 1500, "height": 900},
    )
    page = ctx.new_page()
    page.goto(origin + "/static/world_walk.html?view=green_room/main", wait_until="domcontentloaded")
    ready(page)
    husky(page)
    start = page.evaluate("window.PubCastWalk.S.pos")
    # This is a genuine pointer click passed to the existing path finder.
    point = [300, 560]
    x, y = page.evaluate("(p) => window.PubCastWalk.toScreen(p)", point)
    page.mouse.click(x, y)
    page.wait_for_function("window.PubCastWalk.S.moving", timeout=10000)
    page.wait_for_timeout(7600)
    finish = page.evaluate("window.PubCastWalk.S.pos")
    if abs(finish[0] - start[0]) + abs(finish[1] - start[1]) < 20:
        raise AssertionError("The real avatar did not move across the floor")
    video = page.video
    ctx.close()
    target = OUTPUT / "actual_husky_green_room.webm"
    video.save_as(str(target))
    if shutil.which("ffmpeg"):
        # Copy frames rather than inventing any: trim the genuine browser capture.
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-8",
             "-i", str(target), "-t", "8", "-c:v", "libx264",
             "-pix_fmt", "yuv420p", str(OUTPUT / "actual_husky_green_room_8s.mp4")],
            check=True,
        )
    return {"start": start, "finish": finish, "recording": str(target)}


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    class RequestHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT), **kwargs)
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = "http://127.0.0.1:" + str(server.server_address[1])
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=GL_ARGS)
            page = browser.new_page(viewport={"width": 1500, "height": 900})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(origin + "/static/world_walk.html?view=dressing_room/wide")
            dressing = ready(page)
            avatar = husky(page)
            page.screenshot(path=str(OUTPUT / "01_dressing_room.png"))
            door(page, [951, 435], "Green Room", "green_room")
            green = ready(page)
            page.screenshot(path=str(OUTPUT / "02_green_room.png"))
            door(page, [343, 252], "Writers' Room", "writers_room")
            writers = ready(page)
            page.screenshot(path=str(OUTPUT / "03_writers_room.png"))
            if errors:
                raise AssertionError("Browser errors: " + repr(errors))
            page.close()
            movement = record_walk(browser, origin)
            browser.close()
            print(json.dumps({
                "status": "captured in real Chromium",
                "route": [dressing, green, writers],
                "avatar": avatar,
                "movement": movement,
                "screenshots": ["01_dressing_room.png", "02_green_room.png", "03_writers_room.png"],
            }, indent=2))
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()

"""Capture *real Chromium output* of the checked-out Bella Faux Pas walker.

No mocked images, avatar, movement, or door navigation. Every PNG and WEBM
comes from the actual app, running against its checked-out static assets.
Raises on failures; retains intermediate captures and a diagnostic JSON file.
"""
from __future__ import annotations

import functools
import http.server
import json
import math
import os
import pathlib
import threading
import time
import traceback
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "bella_live"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    errors = []
    console_errors = []
    report = {"real_browser": True, "static_assets": str(ROOT), "ok": False, "steps": []}
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=[
                "--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
            ])
            context = browser.new_context(
                viewport={"width": 1600, "height": 900},
                device_scale_factor=1,
                record_video_dir=str(OUT),
                record_video_size={"width": 1600, "height": 900},
            )
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
            try:
                page.goto(base + "/static/world_walk.html?view=green_room/main", wait_until="load")
                page.wait_for_function(
                    "document.documentElement.dataset.ready === '1' && !!window.PubCastGLB && !!window.PubCastWalk.S.img",
                    timeout=30000,
                )
                room = page.evaluate("""() => {
                  const S=window.PubCastWalk.S;
                  return {room:S.room.id,view:S.view.id,image:S.view.image,loaded:S.img.complete && S.img.naturalWidth>0,
                          imageWidth:S.img.naturalWidth,imageHeight:S.img.naturalHeight,
                          canvasWidth:document.querySelector('#c').width,canvasHeight:document.querySelector('#c').height,
                          doors:S.view.doors.map(d=>({to:d.to,at:d.at}))};
                }""")
                assert room["room"] == "green_room" and room["loaded"], room
                assert "/static/world/rooms/" in room["image"], room
                report["steps"].append({"loaded_real_room_art": room})

                page.locator("#shPads").uncheck()
                page.locator("#glbDemoHusky").click()
                page.wait_for_function(
                    "window.PubCastGLB.has('pete') && window.PubCastWalk.S.demoHeights.pete === 36",
                    timeout=30000,
                )
                dog = page.evaluate("""() => {
                  const W=window.PubCastWalk,G=window.PubCastGLB, S=W.S, info=G.info('pete');
                  const a=document.createElement('canvas'); a.width=700;a.height=700;
                  const c=a.getContext('2d');
                  const drawn=G.draw(c,'pete',350,610,180,{vx:0,vy:1,moving:true,dt:0.033,pxScale:1});
                  const pixels=c.getImageData(0,0,700,700).data;
                  let visible=0;for(let i=3;i<pixels.length;i+=4)if(pixels[i]>40)visible++;
                  return {info,drawn,visiblePixels:visible,heightOverride:S.demoHeights.pete,renderError:G.state.lastError};
                }""")
                assert dog["drawn"] and dog["visiblePixels"] > 1000, dog
                assert dog["info"]["skinned"] > 0 and any("Walk" in s for s in dog["info"]["clips"]), dog
                assert dog["heightOverride"] == 36, dog
                report["steps"].append({"real_3d_husky_renders": dog})
                page.wait_for_timeout(500)
                page.screenshot(path=str(OUT / "01-green-room-real-husky.png"), full_page=True)

                origin = page.evaluate("window.PubCastWalk.S.pos.slice()")
                # The existing real browser test uses this Green Room floor destination.
                dest = page.evaluate("""() => window.PubCastWalk.snapToFloor(window.PubCastWalk.S.view,[343,252])""")
                sx, sy = page.evaluate("(p)=>window.PubCastWalk.toScreen(p)", dest)
                page.mouse.click(sx,sy)
                page.wait_for_function("window.PubCastWalk.S.moving === true", timeout=5000)
                page.wait_for_timeout(2000)
                moved = page.evaluate("window.PubCastWalk.S.pos.slice()")
                delta = math.dist(origin,moved)
                assert delta > 8, (origin, moved, delta)
                report["steps"].append({"real_walk":{"start":origin,"end":moved,"distance_pixels":round(delta,1)}})
                page.screenshot(path=str(OUT / "02-green-room-real-husky-walking.png"), full_page=True)

                # Door must actually be reachable: walk to its clickable floor anchor,
                # then choose the real room-transition button generated by the walker.
                page.wait_for_function("window.PubCastWalk.S.moving === false", timeout=30000)
                page.evaluate("window.PubCastWalk.hideBubble()")
                target = page.evaluate("""() => {
                  const W=window.PubCastWalk,S=W.S;
                  const d=S.view.doors.find(d=>d.to==='writers_room');
                  if(!d)throw Error('Green Room has no door to Writers Room');
                  return d.at;
                }""")
                sx,sy = page.evaluate("(p)=>window.PubCastWalk.toScreen(p)",target)
                page.mouse.click(sx,sy)
                page.wait_for_selector("#bubble:not([hidden])", timeout=30000)
                button = page.get_by_role("button",name="Writers' Room")
                assert button.count() > 0, page.locator("#bubble").inner_text()
                button.first.click()
                page.wait_for_function("window.PubCastWalk.S.key === 'writers_room/main'", timeout=20000)
                page.wait_for_function("window.PubCastWalk.S.img.complete && window.PubCastWalk.S.img.naturalWidth > 0",timeout=10000)
                assert page.evaluate("window.PubCastGLB.has('pete')"), "Husky did not persist across the door"
                assert page.evaluate("window.PubCastWalk.S.demoHeights.pete") == 36
                page.wait_for_timeout(700)
                page.screenshot(path=str(OUT / "03-writers-room-real-husky.png"), full_page=True)
                report["steps"].append({"door_transition":page.evaluate("""() => {
                  const S=window.PubCastWalk.S;
                  return {room:S.room.id,view:S.view.id,image:S.view.image,loaded:S.img.complete,
                          huskyStillLoaded:window.PubCastGLB.has('pete')};
                }""")})
                assert not errors, errors
                report["ok"] = True
            except Exception as exc:
                report["failure"] = f"{type(exc).__name__}: {exc}"
                report["traceback"] = traceback.format_exc()
                page.screenshot(path=str(OUT / "failure-actual-browser.png"), full_page=True)
                raise
            finally:
                report["page_errors"] = errors
                report["console_errors"] = console_errors
                (OUT / "run-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
                page.close()
                context.close()
                browser.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()

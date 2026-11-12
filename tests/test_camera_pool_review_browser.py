"""Fault injection at real asynchronous/browser/media boundaries."""
import io
import json
import time

from PIL import Image, ImageChops, ImageStat

from modules import auth as auth_module
from tests.test_camera_pool_browser import pool_server, context, make_pool
from tests.test_production25d_browser import production_browser, wait_for_actors
from tests.test_studio25d_media_routes import JPEG


def worker_page(server, browser, sid, actor="review-buddy", script=None):
    token = auth_module.create_access_token({"sub": actor, "role": "viewer"})
    ctx = context(browser, actor, "viewer", token)
    if script:
        ctx.add_init_script(script)
    page = ctx.new_page()
    page.goto(server[0] + "/static/camera_pool_worker.html?pool=" + sid)
    page.wait_for_function("!!window.PubCastCameraPoolWorker")
    return ctx, page


def join_and_assign(page, api, sid, headers, source):
    page.check("#workerAgree")
    page.click("#workerJoin")
    page.wait_for_function("PubCastCameraPoolWorker.status().active")
    pid = page.evaluate("PubCastCameraPoolWorker.status().participant_id")
    result = api.post(f"/api/camera-pool/sessions/{sid}/assignments", headers=headers,
                      json={"participant_id": pid, "source_id": source, "fps": 2})
    result.raise_for_status()
    return pid


def close(server, sid, headers, *contexts):
    server[2].delete("/api/camera-pool/sessions/" + sid, headers=headers)
    for ctx in reversed(contexts):
        ctx.close()


def test_withdrawing_consent_before_join_reply_never_activates_worker(pool_server, production_browser):
    host_ctx, host, sid, sources, headers = make_pool(pool_server, production_browser)
    script = """const native=window.fetch;window.fetch=async(...args)=>{const response=await native(...args);
      if(String(args[0]).endsWith('/join'))return new Promise(resolve=>{window.joinReplyReady=true;window.releaseJoin=()=>resolve(response);});return response;};"""
    ctx, page = worker_page(pool_server, production_browser, sid, script=script)
    try:
        page.check("#workerAgree");page.click("#workerJoin")
        page.wait_for_function("window.joinReplyReady===true")
        page.uncheck("#workerAgree")
        page.evaluate("releaseJoin()")
        page.wait_for_function("!PubCastCameraPoolWorker.status().joining")
        assert page.evaluate("PubCastCameraPoolWorker.status().active") is False
        assert page.evaluate("PubCastCameraPoolWorker.status().frames") == 0
        members = pool_server[2].get("/api/camera-pool/sessions/" + sid, headers=headers).json()["members"]
        assert len(members) == 1 and members[0]["active"] is False
    finally:
        close(pool_server, sid, headers, host_ctx, ctx)


def test_stop_cancels_a_hung_encoder_and_discards_its_late_callback(pool_server, production_browser):
    host_ctx, host, sid, sources, headers = make_pool(pool_server, production_browser)
    script = """const native=HTMLCanvasElement.prototype.toBlob;HTMLCanvasElement.prototype.toBlob=function(callback,...args){
      window.encoderWaiting=true;window.finishOldEncode=()=>native.call(this,callback,...args);};"""
    ctx, page = worker_page(pool_server, production_browser, sid, script=script)
    try:
        join_and_assign(page, pool_server[2], sid, headers, sources[1])
        page.wait_for_function("window.encoderWaiting===true", timeout=15000)
        page.click("#workerLeave")
        page.wait_for_function("!PubCastCameraPoolWorker.status().in_flight")
        page.evaluate("finishOldEncode()")
        page.wait_for_timeout(300)
        result = page.evaluate("PubCastCameraPoolWorker.status()")
        assert not result["active"] and result["frames"] == 0 and result["loaded_actors"] == 0
        assert pool_server[2].get("/api/studio25d/media/frames/" + sources[1], headers=headers).status_code == 503
    finally:
        close(pool_server, sid, headers, host_ctx, ctx)


def test_never_finishing_encoder_times_out_without_wedging_worker(pool_server, production_browser):
    host_ctx, host, sid, sources, headers = make_pool(pool_server, production_browser)
    ctx, page = worker_page(pool_server, production_browser, sid, script="HTMLCanvasElement.prototype.toBlob=function(){window.encoderWaiting=true;};")
    try:
        join_and_assign(page, pool_server[2], sid, headers, sources[1])
        page.wait_for_function("window.encoderWaiting===true", timeout=15000)
        page.wait_for_function("!PubCastCameraPoolWorker.status().in_flight&&PubCastCameraPoolWorker.status().performance.state==='paused'", timeout=6000)
        assert page.evaluate("PubCastCameraPoolWorker.status().frames") == 0
        assert "timed out" in page.locator("#poolWorkerStatus").inner_text().lower()
    finally:
        close(pool_server, sid, headers, host_ctx, ctx)


def test_stopping_pending_glb_load_discards_the_late_asset(pool_server, production_browser):
    scene = {"package": "news", "performers": [{"id": "review-actor", "slot": "anchor", "avatar": "female", "position": [.5, .8]}]}
    host_ctx, host, sid, sources, headers = make_pool(pool_server, production_browser, scene=scene)
    script = """const native=window.fetch;window.fetch=async(...args)=>{const response=await native(...args);
      if(String(args[0]).includes('MakeHuman_Female.glb'))return new Promise(resolve=>{window.assetHeld=true;window.releaseAsset=()=>resolve(response);});return response;};"""
    ctx, page = worker_page(pool_server, production_browser, sid, script=script)
    try:
        join_and_assign(page, pool_server[2], sid, headers, sources[1])
        page.wait_for_function("window.assetHeld===true", timeout=15000)
        page.click("#workerLeave")
        page.wait_for_function("!PubCastCameraPoolWorker.status().preparing")
        page.evaluate("releaseAsset()")
        page.wait_for_timeout(300)
        assert page.evaluate("PubCastCameraPoolWorker.status().loaded_actors") == 0
        assert not page.evaluate("PubCastGLB.has('pool-1-review-actor')")
        assert page.evaluate("PubCastCameraPoolWorker.status().frames") == 0
    finally:
        close(pool_server, sid, headers, host_ctx, ctx)


def test_failed_limits_change_cannot_resume_under_old_consent(pool_server, production_browser):
    host_ctx, host, sid, sources, headers = make_pool(pool_server, production_browser)
    ctx, page = worker_page(pool_server, production_browser, sid)
    try:
        join_and_assign(page, pool_server[2], sid, headers, sources[1])
        page.wait_for_function("PubCastCameraPoolWorker.status().frames>=2", timeout=15000)
        page.route("**/participants/*/limits", lambda route: route.fulfill(status=503, json={"detail": "review limits failure"}))
        page.fill("#workerFps", "1")
        page.click("#workerLimits")
        page.wait_for_function("document.querySelector('#poolWorkerStatus').textContent.includes('work remains paused')")
        count = page.evaluate("PubCastCameraPoolWorker.status().frames")
        page.wait_for_timeout(2200)
        assert page.evaluate("PubCastCameraPoolWorker.status().frames") == count
        assert not page.evaluate("PubCastCameraPoolWorker.status().in_flight")
        page.unroute("**/participants/*/limits")
        page.click("#workerLimits")
        page.wait_for_function("document.querySelector('#poolWorkerStatus').textContent.includes('Waiting for a camera assignment')", timeout=10000)
        assert pool_server[2].get("/api/camera-pool/sessions/" + sid, headers=headers).json()["assignments"] == []
    finally:
        close(pool_server, sid, headers, host_ctx, ctx)


def test_pool_controls_fit_a_phone_viewport_and_have_usable_touch_targets(pool_server, production_browser, tmp_path):
    host_ctx, host, sid, sources, headers = make_pool(pool_server, production_browser)
    ctx, page = worker_page(pool_server, production_browser, sid)
    try:
        for target in (host, page):
            target.set_viewport_size({"width": 390, "height": 844})
        for selector in ("#poolContribute", "#poolOpen", "#poolSource", "#poolAssign", "#poolClose"):
            assert host.locator(selector).bounding_box()["height"] >= 44
        for selector in ("#workerJoin", "#workerLeave", "#workerFps"):
            assert page.locator(selector).bounding_box()["height"] >= 44
        assert host.evaluate("cameraPoolPanel.getBoundingClientRect().right <= innerWidth")
        assert host.evaluate("cameraPoolPanel.scrollWidth <= cameraPoolPanel.clientWidth + 1")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        host.locator("#cameraPoolPanel").screenshot(path=str(tmp_path / "phone-pool-panel.png"))
        page.screenshot(path=str(tmp_path / "phone-consent.png"), full_page=True)
    finally:
        close(pool_server, sid, headers, host_ctx, ctx)


def test_busy_baseline_admits_no_camera_work_then_recovers(pool_server, production_browser):
    host_ctx, host, sid, sources, headers = make_pool(pool_server, production_browser)
    ctx, page = worker_page(pool_server, production_browser, sid)
    try:
        page.evaluate("""() => {window.reviewBusy=true;function busy(){if(reviewBusy){const until=performance.now()+95;while(performance.now()<until){}}requestAnimationFrame(busy);}requestAnimationFrame(busy);}""")
        join_and_assign(page, pool_server[2], sid, headers, sources[1])
        page.wait_for_function("PubCastCameraPoolWorker.status().performance.baseline_p95_ms>75", timeout=15000)
        result = page.evaluate("PubCastCameraPoolWorker.status()")
        assert result["performance"]["work_scale"] == 0 and result["frames"] == 0 and not result["renderCalls"]
        page.evaluate("reviewBusy=false")
        page.wait_for_function("PubCastCameraPoolWorker.status().frames>=2", timeout=15000)
    finally:
        close(pool_server, sid, headers, host_ctx, ctx)


def test_one_worker_renders_actual_bundled_3d_without_a_heavy_source_browser(pool_server, production_browser, tmp_path):
    scene = {"package": "news", "performers": [{"id": "review-actor", "slot": "anchor", "avatar": "female", "position": [.5, .8]}]}
    host_ctx, host, sid, sources, headers = make_pool(pool_server, production_browser, scene=scene)
    ctx, page = worker_page(pool_server, production_browser, sid)
    try:
        page.check("#workerQuality")
        join_and_assign(page, pool_server[2], sid, headers, sources[1])
        # Capture a fresh accepted image at the time of its upload, before a
        # correctly paused slow worker's latest-frame lease can expire.
        accepted = []
        def observed(response):
            if response.status == 200 and response.request.method == "POST" and "/media/frames/" in response.url:
                image = pool_server[2].get("/api/studio25d/media/frames/" + sources[1], headers=headers)
                if image.status_code == 200:
                    accepted.append((int(image.headers["X-Pool-Scene-Version"]), image.content))
        page.on("response", observed)
        page.wait_for_function("PubCastCameraPoolWorker.status().frames>=1", timeout=30000)
        assert page.evaluate("PubCastCameraPoolWorker.status().loaded_actors") == 1
        assert accepted
        actor_version, actor_bytes = accepted[-1]
        image = Image.open(io.BytesIO(actor_bytes)).convert("RGB")
        assert image.size in ((640, 360), (320, 180))
        assert page.evaluate("PubCastGLB.info('pool-1-review-actor')?.meshes > 0")
        # Pair the same camera with and without its actor. A GLB in memory or a
        # bright procedural background alone cannot satisfy this pixel oracle.
        host.evaluate("reviewScene.performers=[]")
        api_scene = {"package": "news", "performers": []}
        pool_server[2].put(f"/api/camera-pool/sessions/{sid}/scene", headers=headers, json=api_scene).raise_for_status()
        page.wait_for_function("PubCastCameraPoolWorker.status().loaded_actors===0", timeout=20000)
        deadline = time.monotonic() + 30
        while not any(version > actor_version for version, _ in accepted):
            if time.monotonic() > deadline:
                raise AssertionError("No accepted empty-stage frame after actor removal")
            page.wait_for_timeout(100)
        empty_bytes = next(data for version, data in reversed(accepted) if version > actor_version)
        empty = Image.open(io.BytesIO(empty_bytes)).convert("RGB").resize(image.size)
        region = (int(image.width*.25), int(image.height*.15), int(image.width*.75), int(image.height*.95))
        difference = ImageChops.difference(image, empty).crop(region)
        assert max(ImageStat.Stat(difference).mean) > 8
        (tmp_path / "real-3d-actor.jpg").write_bytes(actor_bytes)
        (tmp_path / "same-camera-empty.jpg").write_bytes(empty_bytes)
    finally:
        close(pool_server, sid, headers, host_ctx, ctx)


def test_failed_close_stays_retryable_and_does_not_report_success(pool_server, production_browser):
    host_ctx, host, sid, sources, headers = make_pool(pool_server, production_browser)
    try:
        url = pool_server[0] + "/api/camera-pool/sessions/" + sid
        host.route(url, lambda route: route.fulfill(status=503, json={"detail": "review failure"}) if route.request.method == "DELETE" else route.continue_())
        host.click("#poolClose")
        host.wait_for_function("document.querySelector('#poolMessage').textContent.includes('unconfirmed')")
        assert host.locator("#poolClose").is_enabled()
        assert pool_server[2].get("/api/camera-pool/sessions/" + sid, headers=headers).status_code == 200
        host.unroute(url)
        host.click("#poolClose")
        host.wait_for_function("document.querySelector('#poolMessage').textContent.includes('Pool closed')")
        assert pool_server[2].get("/api/camera-pool/sessions/" + sid, headers=headers).status_code == 404
    finally:
        close(pool_server, sid, headers, host_ctx)


def test_late_decoded_image_cannot_reappear_after_pool_close(pool_server, production_browser):
    host_ctx, host, sid, sources, headers = make_pool(pool_server, production_browser)
    ctx, page = worker_page(pool_server, production_browser, sid)
    try:
        host.evaluate("""() => {const native=Image.prototype.decode;Image.prototype.decode=function(){const loaded=native.call(this);
          if(!this.dataset.poolAssignment)return loaded;return loaded.then(()=>new Promise(resolve=>{window.poolDecodeHeld=true;window.releasePoolDecode=resolve;}));};}""")
        join_and_assign(page, pool_server[2], sid, headers, sources[1])
        host.wait_for_function("window.poolDecodeHeld===true", timeout=20000)
        host.click("#poolClose")
        host.wait_for_function("PubCastCameraPool.state()===null")
        host.evaluate("releasePoolDecode()")
        host.wait_for_timeout(300)
        assert host.locator("#poolTasks img").count() == 0
        assert host.evaluate("PubCastCameraPool.previewFor('p25d_news_anchor')===null")
    finally:
        close(pool_server, sid, headers, host_ctx, ctx)


def test_receiver_does_not_call_corrupted_jpeg_a_usable_preview(pool_server, production_browser):
    host_ctx, host, sid, sources, headers = make_pool(pool_server, production_browser)
    ctx, page = worker_page(pool_server, production_browser, sid)
    try:
        join_and_assign(page, pool_server[2], sid, headers, sources[1])
        task = pool_server[2].get("/api/camera-pool/sessions/" + sid, headers=headers).json()["assignments"][0]
        host.route("**/api/studio25d/media/frames/" + sources[1], lambda route: route.fulfill(status=200, body=b'broken JPEG', headers={
            "Content-Type": "image/jpeg", "X-Studio-Frame-Age-Ms": "0", "X-Pool-Scene-Version": "1", "X-Pool-Assignment": task["assignment_id"]}))
        page.wait_for_function("PubCastCameraPoolWorker.status().frames>=2", timeout=15000)
        host.wait_for_function("document.querySelector('#poolTasks').textContent.includes('decode failed')", timeout=10000)
        assert host.locator("#poolTasks img:not([hidden])").count() == 0
        assert host.evaluate("PubCastCameraPool.previewFor('p25d_news_anchor')===null")
    finally:
        close(pool_server, sid, headers, host_ctx, ctx)


def test_source_heartbeat_survives_view_switch_and_program_cannot_be_delegated(pool_server, production_browser, tmp_path):
    base, owner, api = pool_server
    headers = {"Authorization": "Bearer " + owner["access_token"]}
    other = api.post("/api/camera-pool/sessions", headers=headers, json={"package": "news"}).json()["id"]
    ctx = context(production_browser, "engineer", "owner", owner["access_token"])
    host = ctx.new_page()
    host.goto(base + "/static/production25d.html")
    sid = None
    try:
        host.wait_for_function("document.documentElement.dataset.production25d==='ready'")
        wait_for_actors(host)
        host.click("#poolCreate")
        host.wait_for_function("PubCastCameraPool.state()?.scene_fresh")
        sid = host.evaluate("PubCastCameraPool.state().id")
        member = api.post(f"/api/camera-pool/sessions/{sid}/join", headers=headers,
                          json={"consent": True, "label": "control-flow fixture"}).json()["participant_id"]
        assert api.post(f"/api/camera-pool/sessions/{sid}/assignments", headers=headers,
                        json={"source_id": "p25d_news_wide", "participant_id": member}).status_code == 409
        api.post(f"/api/camera-pool/sessions/{sid}/assignments", headers=headers,
                 json={"source_id": "p25d_news_anchor", "participant_id": member}).raise_for_status()
        before = api.get(f"/api/camera-pool/sessions/{sid}", headers=headers).json()
        task = before["assignments"][0]
        frame_headers = headers | {"Content-Type": "image/jpeg", "X-Studio-Session": member, "X-Camera-Pool": sid,
                                   "X-Pool-Participant": member, "X-Pool-Grant": task["grant"], "X-Pool-Scene-Version": str(before["sequence"])}
        # A real JPEG fixture tests the control-plane handover; the separate
        # 3D-worker case establishes rendered actor pixels.
        api.post("/api/studio25d/media/frames/p25d_news_anchor", headers=frame_headers, content=JPEG).raise_for_status()
        host.select_option("#poolSessions", other)
        host.click("#poolOpen")
        host.wait_for_function("id=>PubCastCameraPool.state()?.id===id", arg=other)
        host.wait_for_timeout(6500)
        live = api.get(f"/api/camera-pool/sessions/{sid}", headers=headers).json()
        assert live["scene_fresh"] and live["scene_age_ms"] < 2500
        assert len(live["assignments"]) == 1
        host.click("#cut")
        host.wait_for_function("PubCast25DStudio.state().program==='anchor'")
        assert api.get(f"/api/camera-pool/sessions/{sid}", headers=headers).json()["assignments"] == []
        # Model a delayed old preview-assignment response indefinitely. Program
        # must publish locally regardless of this stale client-side cache.
        host.evaluate("PubCastCameraPool.assignedSources=()=>['p25d_news_anchor']")
        api.post("/api/production/panic", headers=headers).raise_for_status()
        host.wait_for_function("[...program.getContext('2d').getImageData(640,360,1,1).data.slice(0,3)].every(x=>x===0)")
        deadline = time.monotonic() + 15
        extrema = None
        while True:
            host.wait_for_timeout(200)
            remote = api.get("/api/studio25d/media/frames/p25d_news_anchor", headers=headers)
            if remote.status_code == 200 and not remote.headers.get("X-Pool-Assignment"):
                image = Image.open(io.BytesIO(remote.content)).convert("RGB")
                extrema = image.getextrema()
                if all(high <= 3 for low, high in extrema):
                    (tmp_path / "remote-program-panic.jpg").write_bytes(remote.content)
                    break
            if time.monotonic() > deadline:
                if remote.status_code == 200:
                    (tmp_path / "failed-remote-program-panic.jpg").write_bytes(remote.content)
                raise AssertionError(f"PANIC did not reach actual local Program confidence: HTTP {remote.status_code}, pixel extrema {extrema}")
        host.click("#stop")
        host.wait_for_function("!PubCast25DStudio.state().session")
        assert api.get(f"/api/camera-pool/sessions/{sid}", headers=headers).status_code == 404
        assert api.get(f"/api/camera-pool/sessions/{other}", headers=headers).status_code == 200
    finally:
        if sid:
            api.delete(f"/api/camera-pool/sessions/{sid}", headers=headers)
        api.delete(f"/api/camera-pool/sessions/{other}", headers=headers)
        ctx.close()

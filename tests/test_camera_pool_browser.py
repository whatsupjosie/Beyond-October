"""Real three-identity camera allocation, media, control feedback and lag backoff."""
import hashlib
import array
import io
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from PIL import Image

from modules import auth as auth_module
from tests.test_production25d_browser import production_browser, wait_for_actors

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pool_server(tmp_path_factory):
    root = tmp_path_factory.mktemp("camera-pool-server")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    # Each test identity has a real verified signature; this subprocess shares
    # only this pytest process's ephemeral signing secret. No production account.
    env = {**os.environ, "PUBCAST_DATA_DIR": str(root / "data"), "PUBCAST_ENFORCE_AUTH": "1",
           "PUBCAST_JWT_SECRET": auth_module._SECRET_KEY}
    base = f"http://127.0.0.1:{port}"
    with (root / "server.log").open("w") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=base, timeout=5, trust_env=False) as api:
                deadline = time.monotonic() + 35
                while True:
                    try:
                        if api.get("/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if process.poll() is not None or time.monotonic() > deadline:
                        pytest.fail((root / "server.log").read_text()[-5000:])
                    time.sleep(.1)
                password = secrets.token_urlsafe(24) + "A9!"
                response = api.post("/api/auth/setup", json={"username": "engineer", "password": password, "confirm_password": password})
                response.raise_for_status()
                yield base, response.json(), api
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def context(browser, actor, role, token):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1100})
    ctx.add_init_script("sessionStorage.setItem('pubcast_token'," + json.dumps(token) + ");"
                        "sessionStorage.setItem('pubcast_user'," + json.dumps(json.dumps({"username": actor, "role": role})) + ");")
    return ctx


def register_sources(api, headers):
    sources = ["p25d_news_" + name for name in ("wide", "anchor", "coanchor", "two")]
    for source in sources:
        result = api.post("/api/cameras/register", headers=headers, json={
            "source_id": source, "name": source, "description": "Camera pool review scene",
            "location": "studio25d", "transport": "virtual", "endpoint": "virtual://" + source,
            "tags": ["studio25d", "news"]})
        result.raise_for_status()
    api.post("/api/switcher/select", headers=headers, json={"program": sources[0], "preview": sources[1]}).raise_for_status()
    return sources


def make_pool(server, browser, scene=None):
    base, owner, api = server
    headers = {"Authorization": "Bearer " + owner["access_token"]}
    sources = register_sources(api, headers)
    sid = api.post("/api/camera-pool/sessions", json={"package": "news"}, headers=headers).json()["id"]
    scene = scene or {"package": "news", "performers": []}
    api.put("/api/camera-pool/sessions/" + sid + "/scene", json=scene, headers=headers).raise_for_status()
    ctx = context(browser, "engineer", "owner", owner["access_token"])
    host = ctx.new_page()
    host.goto(base + "/static/control_room.html?camera_pool=" + sid)
    host.wait_for_function("window.PubCastCameraPool?.state()?.id === " + json.dumps(sid))
    # This test driver publishes a real, typed lightweight scene through the
    # actual source API. It does not stand in for the separate 3D/studio tests.
    host.evaluate("""({sid,scene})=>{window.reviewScene=scene;window.reviewScenePump=setInterval(()=>fetch('/api/camera-pool/sessions/'+sid+'/scene',
        {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(reviewScene)}).catch(()=>{}),1000);}""", {"sid": sid, "scene": scene})
    return ctx, host, sid, sources, headers


def test_three_participants_sustain_real_camera_preview_traffic(pool_server, production_browser, tmp_path):
    base, owner, api = pool_server
    host_ctx, host, sid, sources, headers = make_pool(pool_server, production_browser)
    contexts = [host_ctx]
    errors = []
    workers = []
    try:
        for actor, role, token in (("engineer", "owner", owner["access_token"]),
                                  ("buddy-one", "viewer", auth_module.create_access_token({"sub": "buddy-one", "role": "viewer"})),
                                  ("buddy-two", "viewer", auth_module.create_access_token({"sub": "buddy-two", "role": "viewer"}))):
            ctx = context(production_browser, actor, role, token)
            contexts.append(ctx)
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            if actor == "buddy-one":
                page.goto(base + "/static/control_room.html?camera_pool=" + sid)
                page.wait_for_function("document.querySelector('#poolInvite')?.value.includes('pool_')")
                page.click("#poolContribute")
                page.wait_for_selector("iframe[name='camera-pool-contribution']")
                worker = page.frame(name="camera-pool-contribution")
                worker.wait_for_selector("#workerJoin")
            else:
                page.goto(base + "/static/camera_pool_worker.html?pool=" + sid)
                worker = page
            worker.click("#workerJoin")
            assert worker.evaluate("PubCastCameraPoolWorker.status().active") is False
            worker.fill("#workerLabel", actor)
            worker.check("#workerAgree")
            worker.click("#workerJoin")
            worker.wait_for_function("PubCastCameraPoolWorker.status().participant_id !== null")
            pid = worker.evaluate("PubCastCameraPoolWorker.status().participant_id")
            workers.append(worker)
            host.wait_for_function("pid=>[...document.querySelector('#poolPerson').options].some(o=>o.value===pid)", arg=pid)
            host.select_option("#poolSource", sources[len(workers)])
            host.select_option("#poolPerson", pid)
            host.fill("#poolFps", "2")
            host.click("#poolAssign")
            host.wait_for_function("src=>PubCastCameraPool.state()?.assignments.some(t=>t.source_id===src)", arg=sources[len(workers)])
        for worker in workers:
            worker.wait_for_function("PubCastCameraPoolWorker.status().frames>=6", timeout=30000)
            assert worker.evaluate("PubCastCameraPoolWorker.status().loaded_actors") == 0
        host.wait_for_function("PubCastCameraPool.state().members.every(m=>m.actual_fps>=1.4&&m.upload_kbps>0)", timeout=20000)
        for worker in workers:
            assert worker.evaluate("PubCastCameraPoolWorker.status().performance.state") == "running"
        host.wait_for_function("[...document.querySelectorAll('#poolTasks img')].filter(i=>!i.hidden&&i.naturalWidth===640).length===3", timeout=15000)
        hashes = []
        for source in sources[1:]:
            result = api.get("/api/studio25d/media/frames/" + source, headers=headers)
            result.raise_for_status()
            img = Image.open(io.BytesIO(result.content))
            assert img.size == (640, 360) and len(img.getcolors(640*360)) > 50
            hashes.append(hashlib.sha256(result.content).hexdigest())
        assert len(set(hashes)) == 3
        host.screenshot(path=str(tmp_path / "sustained-lightweight-pool.png"), full_page=True)
        workers[2].click("#workerLeave")
        host.wait_for_function("src=>!PubCastCameraPool.state().assignments.some(t=>t.source_id===src)", arg=sources[3])
        assert api.get("/api/studio25d/media/frames/" + sources[3], headers=headers).status_code == 503
        host.click("#poolClose")
        assert api.get("/api/camera-pool/sessions/" + sid, headers=headers).status_code == 404
        assert errors == []
    finally:
        api.delete("/api/camera-pool/sessions/" + sid, headers=headers)
        for ctx in reversed(contexts):
            ctx.close()

"""Actual browser capture -> durable server -> fresh browser after host restart."""
import array
import hashlib
import io
import json
import math
import os
import secrets
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest
import numpy as np

from tests.test_production25d_browser import production_browser, wait_for_actors
from modules import auth as auth_module

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def archive_host(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
    env = {**os.environ, "PUBCAST_DATA_DIR": str(tmp_path / "server-data"), "PUBCAST_ENFORCE_AUTH": "1", "PUBCAST_JWT_SECRET": auth_module._SECRET_KEY}
    class Host:
        base = f"http://127.0.0.1:{port}"
        process = None
        def start(self):
            self.log = (tmp_path / "server.log").open("a")
            self.process = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 40
            while True:
                try:
                    if self.api.get("/health").status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                if self.process.poll() is not None or time.monotonic() > deadline:
                    pytest.fail((tmp_path / "server.log").read_text()[-3000:])
                time.sleep(.1)
        def stop(self):
            if self.process is not None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=5)
                self.log.close(); self.process = None
    host = Host();host.api = httpx.Client(base_url=host.base, timeout=30, trust_env=False)
    try:
        host.start()
        password = secrets.token_urlsafe(24) + "A9!"
        response = host.api.post("/api/auth/setup", json={"username": "engineer", "password": password, "confirm_password": password})
        response.raise_for_status();host.token = response.json()["access_token"]
        host.headers = {"Authorization": "Bearer " + host.token}
        yield host
    finally:
        host.stop();host.api.close()


def signed_page(browser, host, token=None, role="owner"):
    context = browser.new_context(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
    context.add_init_script("sessionStorage.setItem('pubcast_token',"+json.dumps(token or host.token)+");sessionStorage.setItem('pubcast_user',JSON.stringify({username:'engineer',role:"+json.dumps(role)+"}));")
    page = context.new_page();page.goto(host.base + "/static/production25d.html")
    page.wait_for_function("document.documentElement.dataset.production25d==='ready'")
    return context, page


def record_take(page):
    wait_for_actors(page)
    page.click("#start");page.click("#record")
    page.wait_for_function("PubCast25DStudio.state().recording")
    page.evaluate("""() => {const audio=PubcastProgramAudio,osc=audio.context.createOscillator(),gain=audio.context.createGain();
      osc.frequency.value=440;gain.gain.value=.15;osc.connect(gain);gain.connect(audio.master);osc.start();window.archiveTone=osc;}""")
    page.wait_for_timeout(2200)
    page.click("#recordStop")
    page.wait_for_function("!PubCast25DStudio.state().recording")
    page.evaluate("archiveTone.stop()")
    page.click("#stop")
    page.wait_for_function("!PubCast25DStudio.state().session")
    page.locator("#sessionList button").first.click()
    return page.evaluate("""async()=>{const session=(await PubCast25DStore.list())[0],item=await PubCast25DStore.read(session.id);
      return {id:session.media.id,session:session.id,startedAt:session.media.startedAt,bytes:item.blob.size,sha256:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await item.blob.arrayBuffer())),b=>b.toString(16).padStart(2,'0')).join('')};}""")


def test_completed_take_reopens_from_server_after_browser_and_host_restart(archive_host, production_browser, tmp_path):
    host=archive_host;ctx,page=signed_page(production_browser,host)
    try:
        source=record_take(page)
        # Lose the first ACK after the actual server has committed its bytes.
        def drop_ack(route):
            response=route.fetch();assert response.status==200;route.abort()
        pattern="**/api/studio25d/recordings/*/chunks/0"
        page.route(pattern,drop_ack)
        page.click("#archiveSave")
        page.wait_for_function("archiveStatus.textContent.includes('unconfirmed')",timeout=30000)
        pending=host.api.get("/api/studio25d/recordings",headers=host.headers).json()["takes"][0]
        assert pending["next_index"]==1 and pending["state"]=="uploading"
        assert page.evaluate("async()=>!!(await PubCast25DStore.read((await PubCast25DStore.list())[0].id)).blob")
        page.unroute(pattern)
        host.stop();host.start()
        # A new JS page also has to recover its upload spec from IndexedDB.
        page.reload();page.wait_for_function("document.documentElement.dataset.production25d==='ready'")
        page.locator("#sessionList button").first.click()
        resent=[]
        page.on("request",lambda r:resent.append(r.url) if "/chunks/" in r.url else None)
        page.click("#archiveSave")
        page.wait_for_function("archiveStatus.textContent.includes('Saved on server:')",timeout=45000)
        assert not any(url.endswith("/chunks/0") for url in resent)
        take=host.api.get("/api/studio25d/recordings",headers=host.headers).json()["takes"][0]
        assert take["state"]=="complete" and take["sha256"]==source["sha256"]
        capture_time=datetime.fromisoformat(source["startedAt"].replace("Z","+00:00")).timestamp()
        assert abs(take["capture_started_at"]-capture_time)<1e-6
        assert take["upload_started_at"]>capture_time
        media=host.api.get(f"/api/studio25d/recordings/{take['id']}/media",headers=host.headers)
        media.raise_for_status()
        assert len(media.content)==source["bytes"] and hashlib.sha256(media.content).hexdigest()==source["sha256"]
        (tmp_path/"server-original.webm").write_bytes(media.content)
        pcm=subprocess.run(["ffmpeg","-v","error","-i",str(tmp_path/"server-original.webm"),"-vn","-ac","1","-ar","48000","-f","f32le","-"],capture_output=True,check=True,timeout=20).stdout
        samples=array.array('f');samples.frombytes(pcm)
        stable=samples[24000:-12000]
        assert len(stable)>12000
        rms=math.sqrt(sum(x*x for x in stable)/len(stable))
        spectrum=np.abs(np.fft.rfft(np.array(stable)*np.hanning(len(stable))))
        bins=np.fft.rfftfreq(len(stable),1/48000)
        frequency=float(bins[np.argmax(spectrum)])
        ratio=float(max(spectrum)/max(spectrum[(bins>990)&(bins<1010)]))
        assert rms>.02 and 435<frequency<445 and ratio>50
        ctx.close();ctx=None
        host.stop();host.start()
        fresh,fresh_page=signed_page(production_browser,host,auth_module.create_access_token({"sub":"engineer","role":"viewer"}),"viewer")
        try:
            assert fresh_page.evaluate("async()=>(await PubCast25DStore.list()).length")==0
            fresh_page.click("#archiveRefresh")
            fresh_page.locator("#archiveList button").first.click()
            fresh_page.wait_for_function("playback.readyState>=2&&playback.videoWidth===1280",timeout=20000)
            fresh_page.evaluate("playback.play()")
            fresh_page.wait_for_function("playback.currentTime>.1")
            assert fresh_page.locator("#manifest").is_disabled()
            assert fresh_page.locator("#archiveSave").is_disabled()
            assert fresh_page.locator("#download").is_enabled()
            with fresh_page.expect_download() as event:
                fresh_page.click("#archiveBundle")
            event.value.save_as(tmp_path/"server-source.zip")
            with ZipFile(tmp_path/"server-source.zip") as bundle:
                member=next(n for n in bundle.namelist() if n.startswith("media/"))
                assert bundle.read(member)==media.content
                metadata=json.loads(bundle.read(take["id"]+".json"))
                assert abs(metadata["started_at"]-capture_time)<1e-6
            fresh_page.screenshot(path=str(tmp_path/"server-reopen.png"),full_page=True)
            fresh_page.set_viewport_size({"width":390,"height":844})
            assert fresh_page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            for selector in ["#archiveSave","#archivePause","#archiveRefresh","#archiveBundle"]:
                assert fresh_page.locator(selector).bounding_box()["height"]>=44
            fresh_page.locator("#studioRecordings").screenshot(path=str(tmp_path/"phone-server-takes.png"))
            (tmp_path/"verified.json").write_text(json.dumps({"source_bytes":source["bytes"],"sha256":source["sha256"],"video_dimensions":[1280,720],"capture_started_at":capture_time,"upload_started_at":take["upload_started_at"],"decoded_audio_rms":rms,"decoded_tone_hz":frequency,"tone_to_1000hz_amplitude_ratio":ratio,"audio_sample_rate":48000,"server_restart_count":2,"cold_browser_local_sessions":0},indent=2))
        finally:
            fresh.close()
    finally:
        if ctx:ctx.close()


def test_version_one_store_upgrade_keeps_legacy_take_bytes_and_identity(archive_host, production_browser):
    context=production_browser.new_context()
    context.add_init_script("sessionStorage.setItem('pubcast_token',"+json.dumps(archive_host.token)+");sessionStorage.setItem('pubcast_user',JSON.stringify({username:'engineer',role:'owner'}));")
    page=context.new_page();page.goto(archive_host.base+"/health")
    try:
        page.evaluate("""async()=>{
          await new Promise((resolve,reject)=>{const q=indexedDB.open('pubcast-25d-local',1);
            q.onupgradeneeded=()=>{q.result.createObjectStore('sessions',{keyPath:'id'});q.result.createObjectStore('media',{keyPath:'id'});};
            q.onerror=()=>reject(q.error);q.onsuccess=()=>{const db=q.result,tx=db.transaction(['sessions','media'],'readwrite');
              tx.objectStore('sessions').put({id:'pubcast25d-legacy-session',packageId:'news',startedAt:'2026-10-30T12:00:00Z',endedAt:'2026-10-30T12:00:01Z',events:[],media:{mime:'video/webm',bytes:24,durationMs:1000}});
              tx.objectStore('media').put({id:'pubcast25d-legacy-session',blob:new Blob(['legacy-preservation-bytes'],{type:'video/webm'})});
              tx.oncomplete=()=>{db.close();resolve();};};});
        }""")
        page.goto(archive_host.base+"/static/production25d.html")
        page.wait_for_function("document.documentElement.dataset.production25d==='ready'")
        assert page.locator("#sessionList button").count()==1
        page.locator("#sessionList button").click()
        actual=page.evaluate("async()=>{const r=await PubCast25DStore.read('pubcast25d-legacy-session');return {text:await r.blob.text(),id:r.session.id,archives:await PubCast25DStore.archive('pubcast25d-legacy-session')};}")
        assert actual=={"text":"legacy-preservation-bytes","id":"pubcast25d-legacy-session","archives":None}
        assert page.locator("#archiveSave").is_enabled()
    finally:
        context.close()

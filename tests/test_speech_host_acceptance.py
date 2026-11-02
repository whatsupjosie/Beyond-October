"""Real launcher, HTTP, CPU models, browser recording and local mic dictation.

The microphone fixture is generated speech, not a physical-device claim. The
browser's MediaRecorder, upload, recognizer, review UI and mixer all run for real.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
import secrets
import subprocess
import sys
import time
import wave
from pathlib import Path

import httpx
import pytest

from tests.test_data_checkpoint_host_recovery import Host, GL_ARGS, _inventory, _ok
from tests.test_speech_system import PHRASE
from modules.tts_engine import wav_info

ROOT = Path(__file__).resolve().parents[1]


def speech_env():
    value = os.environ.get("PUBCAST_SPEECH_TEST_MODELS")
    if not value:
        pytest.skip("Set PUBCAST_SPEECH_TEST_MODELS to explicitly installed model containers")
    models = Path(value)
    return {"PUBCAST_TTS_ENGINE": "kokoro", "PUBCAST_STT_MODEL_PATH": str(models / "whisper-tiny.en/assets"),
            "PUBCAST_KOKORO_MODEL": str(models / "kokoro/assets/model.onnx"),
            "PUBCAST_KOKORO_VOICES": str(models / "kokoro/assets/voices.bin")}


async def disconnect_inflight(base, token):
    async with httpx.AsyncClient(base_url=base, headers={"Authorization":"Bearer " + token}, trust_env=False, timeout=30) as client:
        task = asyncio.create_task(client.post("/api/tts/synthesize", json={"text": (PHRASE + " ") * 22}))
        try:
            for _ in range(100):
                state = (await client.get("/api/tts/status")).json()
                if state["busy"]:
                    break
                assert not task.done(), "Cancellation probe completed before observing active model work"
                await asyncio.sleep(.02)
            assert state["busy"]
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        deadline = time.monotonic() + 10
        while (await client.get("/api/tts/status")).json()["busy"]:
            assert time.monotonic() < deadline, "Disconnected caller left model work busy"
            await asyncio.sleep(.05)
        assert not (await client.get("/api/tts/status")).json()["loaded"]


def test_real_host_browser_dictation_recordable_speech_stop_and_restart(tmp_path, monkeypatch):
    from playwright.sync_api import sync_playwright
    from modules import auth

    before = _inventory(ROOT / "data")
    env = speech_env()
    data = tmp_path / "data"; data.mkdir()
    host = Host(data, tmp_path / "speech-host.log", env)
    username, password = "speech-owner", secrets.token_urlsafe(24) + "Aa9!"
    evidence = {"platform": sys.platform, "python": sys.version.split()[0], "fixture": "Generated Kokoro speech; no physical microphone"}
    try:
        host.start()
        with httpx.Client(base_url=host.base, trust_env=False, timeout=60) as api:
            for method, path in [("GET","/api/stt/status"),("GET","/api/tts/status"),("GET","/api/tts/voices"),
                                 ("GET","/api/tts/preferences"),("POST","/api/stt/transcribe"),("POST","/api/tts/synthesize")]:
                assert api.request(method,path).status_code == 401
            session = _ok(api.post("/api/auth/setup", json={"username":username,"password":password,"confirm_password":password}),201)
            token = session["access_token"]
            api.headers["Authorization"] = "Bearer " + token
            assert not _ok(api.get("/api/tts/status"))["loaded"]
            assert not _ok(api.get("/api/stt/status"))["loaded"]
            catalogue = _ok(api.get("/api/tts/voices"))
            assert catalogue["engine"] == "kokoro" and len(catalogue["voices"]) == 28
            selected = {"voice_id":"af_heart","speed":1,"language":"en","expected_revision":0}
            saved = _ok(api.put("/api/tts/preferences",json=selected))
            assert api.put("/api/tts/preferences",json=selected).status_code == 409
            assert api.put("/api/tts/preferences",json={**selected,"language":[]}).status_code == 400
            # Verified JWT subject wins over a spoofed header; another subject has its own choices.
            monkeypatch.setattr(auth,"_SECRET_KEY",(data / "secure/jwt_secret.txt").read_text().strip())
            other = auth.create_access_token({"sub":"other-speech-owner","role":"owner"})
            assert _ok(api.get("/api/tts/preferences", headers={"Authorization":"Bearer " + other,"X-Client-Id":username}))["revision"] == 0
            assert api.post("/api/tts/synthesize",json={"text":"hello","voice_id":"missing"}).status_code == 400
            assert api.post("/api/tts/synthesize",json={"text":"x"*2001}).status_code == 413
            assert api.post("/api/tts/synthesize",content=b"x"*17000).status_code == 413
            speech = api.post("/api/tts/synthesize",json={"text":PHRASE})
            assert speech.status_code == 200, speech.text[:500]
            info = wav_info(speech.content)
            assert float(speech.headers["X-Duration"]) == info["duration"]
            assert int(speech.headers["X-Audio-Samples"]) == info["sample_count"]
            assert speech.headers["X-Voice"] == "af_heart" and speech.headers["Cache-Control"] == "no-store"
            result = _ok(api.post("/api/stt/transcribe",content=speech.content,headers={"Content-Type":"audio/wav"}))
            assert result["text"] == PHRASE and result["segments"][0]["words"]
            assert api.post("/api/stt/transcribe",content=b"#EXTM3U\nhttp://localhost/private",headers={"Content-Type":"audio/webm"}).status_code == 415
            assert api.post("/api/stt/transcribe",content=b"x"*(8*1024*1024+1),headers={"Content-Type":"audio/webm"}).status_code == 413
            multipart = api.post("/api/stt/transcribe",files={"audio":("fixture.wav",speech.content,"audio/wav")})
            assert _ok(multipart)["text"] == PHRASE
            asyncio.run(disconnect_inflight(host.base,token))
            assert api.post("/api/tts/synthesize",json={"text":PHRASE}).status_code == 200
            # Pad the actual generated fixture so MediaRecorder captures the full phrase once.
            fixture = tmp_path / "microphone.wav"
            original = tmp_path / "generated.wav"; original.write_bytes(speech.content)
            rendered = subprocess.run(["ffmpeg","-v","error","-i",str(original),"-af","adelay=500,apad=pad_dur=3",
                                       "-ar","48000","-ac","1",str(fixture)],capture_output=True,timeout=20)
            assert rendered.returncode == 0, rendered.stderr

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=GL_ARGS + ["--use-fake-ui-for-media-stream","--use-fake-device-for-media-stream",
                                                                  "--use-file-for-fake-audio-capture=" + str(fixture)])
            try:
                context = browser.new_context(viewport={"width":1440,"height":1000},permissions=["microphone"],reduced_motion="reduce")
                context.route("**/*",lambda route: route.continue_() if route.request.url.startswith(host.base + "/") or route.request.url.startswith("blob:") else route.abort())
                page = context.new_page()
                page.goto(host.base + "/login?next=/writers-room")
                page.fill("#loginUser",username); page.fill("#loginPass",password); page.click("#loginBtn")
                page.wait_for_url("**/writers-room"); page.wait_for_function("window.reachStarted !== undefined")
                original_words = "Keep my existing words."
                page.fill("#chatInput",original_words)
                page.click("#chatMicBtn")
                page.wait_for_function("document.querySelector('#chatMicBtn').classList.contains('listening')")
                # Wait for actual recorder media time; the model fixture is ~4.63 s plus padding.
                page.wait_for_timeout(6200)
                page.click("#chatMicBtn")
                draft = page.locator('[data-dictation-review] textarea')
                page.wait_for_function("document.querySelector('[data-dictation-review] textarea').value.includes('studio lights are ready')",timeout=30000)
                recognized = draft.input_value()
                assert page.input_value("#chatInput") == original_words
                assert page.locator(".chat-msg.you").count() == 0
                draft.fill(recognized + " Reviewed.")
                page.locator('[data-dictation-review] button').filter(has_text="Insert").click()
                assert original_words in page.input_value("#chatInput") and "Reviewed." in page.input_value("#chatInput")
                assert page.locator(".chat-msg.you").count() == 0
                evidence["dictation"] = {"recognized":recognized,"preview_preserved_existing_text":True,"manual_insert_no_autosend":True}

                # Failure-path injection only: delay permission after acquiring a real fixture stream.
                # Cancel must stop tracks even when permission resolves after the user's cancellation.
                page.evaluate("""async () => {
                  window.nativeGetUserMedia=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
                  window.lateMicrophone=await nativeGetUserMedia({audio:true});
                  navigator.mediaDevices.getUserMedia=()=>new Promise(resolve=>window.resolveLatePermission=resolve);
                }""")
                page.click("#chatMicBtn");page.wait_for_function("!!window.resolveLatePermission")
                page.click("#chatMicBtn")
                page.evaluate("resolveLatePermission(lateMicrophone)")
                page.wait_for_function("lateMicrophone.getTracks().every(track=>track.readyState==='ended')")
                page.evaluate("() => { navigator.mediaDevices.getUserMedia=nativeGetUserMedia; }")
                assert "Reviewed." in page.input_value("#chatInput")
                evidence["late_permission_cancel_released_real_fixture_tracks"] = True

                # Exercise real 2i reading, rather than calling the client in isolation.
                page.click("#modeBadge")
                page.evaluate("pool = ['The studio lights are ready.']; pointer = 0; reading = null; render();")
                page.click("#playBtn")
                page.wait_for_function("window.PubcastProgramAudio.status().dialogueActive === 1",timeout=30000)
                page.click("#stopBtn")
                page.wait_for_function("window.PubcastProgramAudio.status().activeSources === 0")
                assert page.evaluate("playing") is False

                page.goto(host.base + "/control")
                page.click('.nav-btn[data-room="control"]')
                page.wait_for_function("document.querySelector('#tts-voice').options.length === 28")
                page.click("#drawer-tab")
                page.select_option("#tts-voice","am_michael")
                page.wait_for_function("document.querySelector('#tts-status').textContent.includes('saved')")
                # Record the actual canonical mixed output, then decode and measure it independently.
                page.evaluate("""() => {
                  const stream = PubcastProgramAudio.captureOutputStream();
                  window.captureParts=[]; window.speechEvents=[];
                  window.addEventListener('pubcast:speech-start',e=>speechEvents.push(e.detail));
                  window.captureRecorder=new MediaRecorder(stream);
                  captureRecorder.ondataavailable=e=>captureParts.push(e.data);
                  captureRecorder.onstop=async()=>{const blob=new Blob(captureParts); const bytes=new Uint8Array(await blob.arrayBuffer());
                    let binary='';for(const value of bytes)binary+=String.fromCharCode(value);window.capturedProgram=btoa(binary);};
                  captureRecorder.start();
                }""")
                page.fill("#tts-text",PHRASE); page.click("#tts-say")
                page.wait_for_function("document.querySelector('#tts-status').textContent === 'Speech finished'",timeout=30000)
                page.evaluate("captureRecorder.stop()")
                page.wait_for_function("!!window.capturedProgram")
                capture = tmp_path / "program-dialogue.webm"
                capture.write_bytes(base64.b64decode(page.evaluate("capturedProgram")))
                decoded = subprocess.run(["ffmpeg","-v","error","-i",str(capture),"-f","f32le","-ac","1","-ar","24000","-"],capture_output=True,timeout=20)
                assert decoded.returncode == 0,decoded.stderr
                import numpy as np
                samples=np.frombuffer(decoded.stdout,dtype="<f4")
                rms=float(np.sqrt(np.mean(samples*samples)))
                assert len(samples)>24000 and rms>.005
                with httpx.Client(base_url=host.base,trust_env=False,timeout=30,headers={"Authorization":"Bearer " + token}) as api:
                    recorded_words = _ok(api.post("/api/stt/transcribe",content=capture.read_bytes(),headers={"Content-Type":"audio/webm"}))["text"]
                assert recorded_words == PHRASE
                evidence["recorded_dialogue"]={"bytes":capture.stat().st_size,"decoded_samples":len(samples),"rms":rms,"recognized_recording":recorded_words,"sha256":hashlib.sha256(capture.read_bytes()).hexdigest(),"events":page.evaluate("speechEvents")}
                page.fill("#tts-text",PHRASE*2); page.click("#tts-say")
                page.wait_for_function("PubcastProgramAudio.status().dialogueActive === 1",timeout=30000)
                page.click("#tts-stop")
                page.wait_for_function("PubcastProgramAudio.status().activeSources === 0")
                assert page.evaluate("PubcastProgramAudio.status().dialogueActive") == 0
                # Abort while the real provider is computing; no late playback may start.
                starts = page.evaluate("speechEvents.length")
                page.fill("#tts-text",(PHRASE + " ")*22);page.click("#tts-say")
                page.wait_for_function("async () => (await (await fetch('/api/tts/status')).json()).busy")
                page.click("#tts-stop")
                page.wait_for_function("async () => !(await (await fetch('/api/tts/status')).json()).busy")
                assert page.evaluate("speechEvents.length") == starts
                assert page.evaluate("PubcastProgramAudio.status().activeSources") == 0
                page.reload()
                page.wait_for_function("document.querySelector('#tts-voice').value === 'am_michael'")
                evidence["browser_stop_and_saved_voice_after_reload"] = True
                context.close()
            finally:
                browser.close()
        host.stop()
        host = Host(data,tmp_path / "speech-host-restarted.log",env); host.start()
        with httpx.Client(base_url=host.base,trust_env=False,timeout=30,headers={"Authorization":"Bearer " + token}) as api:
            assert _ok(api.get("/api/tts/preferences"))["voice_id"] == "am_michael"
            assert not _ok(api.get("/api/tts/status"))["loaded"]
            assert api.post("/api/tts/synthesize",json={"text":"The saved voice survives a host restart."}).headers["X-Voice"] == "am_michael"
        evidence["authenticated_http_bounds_multipart_cancel_recovery_restart"] = True
        output = os.environ.get("PUBCAST_SPEECH_EVIDENCE_DIR")
        if output:
            destination=Path(output);destination.mkdir(parents=True,exist_ok=True)
            (destination / "host-browser.json").write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8")
    finally:
        host.stop()
        assert _inventory(ROOT / "data") == before

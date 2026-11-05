"""Real MediaRecorder checkpoints, renderer crash, and startup cancellation races."""
import array
import hashlib
import json
import math
import subprocess

import numpy as np
import pytest
from playwright.sync_api import Error as BrowserError

from tests.test_production25d_browser import production_browser, production_server, studio, wait_for_actors, GL_ARGS


def start(page):
    wait_for_actors(page)
    page.click('#start')
    page.wait_for_function("switcherLink.textContent==='VIDEO: SHARED SWITCHER'")


def test_actual_renderer_crash_recovers_committed_video_and_program_audio(studio, production_server, tmp_path):
    page, context = studio
    start(page)
    page.click('#record')
    page.wait_for_function('PubCast25DStudio.state().recording')
    page.evaluate("""() => {
      const audio=PubcastProgramAudio,osc=audio.context.createOscillator(),gain=audio.context.createGain();
      osc.frequency.value=440;gain.gain.value=.15;osc.connect(gain);gain.connect(audio.master);osc.start();
    }""")
    page.wait_for_function("PubCast25DStudio.state().journal.chunks>=3", timeout=15000)
    pending=page.evaluate("async()=>{const r=(await PubCast25DStore.listCaptures())[0];return {id:r.id,bytes:r.bytes};}")
    assert pending['bytes'] > 1000
    assert page.evaluate('async()=>(await PubCast25DStore.list())[0].media||null') is None
    # Chromium terminates the renderer without dispatching Stop or unload handlers.
    with page.expect_event('crash'):
        try:
            page.goto('chrome://crash', timeout=5000)
        except BrowserError:
            pass
    fresh=context.new_page();fresh.goto(production_server[0]+'/static/production25d.html')
    fresh.wait_for_function("document.documentElement.dataset.production25d==='ready'")
    original=fresh.evaluate("""async id=>{const r=await PubCast25DStore.readCapture(id),b=await PubCast25DCapture.assemble(r);
      return {bytes:b.size,sha256:await PubCast25DCapture.digest(b),chunks:r.chunks.length,startedAt:r.capture.startedAt};}""", pending['id'])
    assert original['bytes'] >= pending['bytes']
    recovery=fresh.locator('#captureRecoveryList button')
    recovery.wait_for()
    fresh.wait_for_function("!document.querySelector('#captureRecoveryList button').disabled", timeout=25000)
    recovery.click()
    fresh.wait_for_function("playback.readyState>=2&&playback.videoWidth===1280", timeout=20000)
    fresh.evaluate('playback.play()');fresh.wait_for_function('playback.currentTime>.1')
    actual=fresh.evaluate("""async()=>{const s=(await PubCast25DStore.list())[0],r=await PubCast25DStore.read(s.id);
      return {bytes:r.blob.size,sha256:await PubCast25DCapture.digest(r.blob),take:s.media,count:s.recordings.length,pending:(await PubCast25DStore.listCaptures()).length};}""")
    assert actual['bytes']==original['bytes'] and actual['sha256']==original['sha256']
    assert actual['take']['incomplete'] is True and actual['take']['recovered'] is True
    assert actual['take']['startedAt']==original['startedAt']
    assert actual['count']==1 and actual['pending']==0
    assert 'INCOMPLETE' in fresh.locator('#sessionList').inner_text()
    fresh.click('#archiveSave')
    fresh.wait_for_function("archiveStatus.textContent.includes('Saved on server:')",timeout=45000)
    _,auth,api=production_server
    archived=api.get('/api/studio25d/recordings',headers={'Authorization':'Bearer '+auth['access_token']}).json()['takes']
    saved=next(t for t in archived if t['take_id']==pending['id'])
    assert saved['sha256']==original['sha256'] and saved['capture_incomplete'] is True
    with fresh.expect_download() as download:
        fresh.click('#download')
    media=tmp_path/'recovered-interrupted.webm';download.value.save_as(media)
    assert hashlib.sha256(media.read_bytes()).hexdigest()==original['sha256']
    pcm=subprocess.run(['ffmpeg','-v','error','-i',str(media),'-vn','-ac','1','-ar','48000','-f','f32le','-'],capture_output=True,check=True,timeout=20).stdout
    samples=array.array('f');samples.frombytes(pcm);stable=np.array(samples[24000:-12000])
    assert len(stable)>12000
    rms=float(np.sqrt(np.mean(stable**2)));spectrum=np.abs(np.fft.rfft(stable*np.hanning(len(stable))))
    frequency=float(np.fft.rfftfreq(len(stable),1/48000)[np.argmax(spectrum)])
    assert rms>.02 and 435<frequency<445
    fresh.screenshot(path=str(tmp_path/'interrupted-take-recovered.png'),full_page=True)
    (tmp_path/'verified.json').write_text(json.dumps({'renderer_crashed_before_stop':True,**original,'decoded_audio_rms':rms,'decoded_tone_hz':frequency,'video_dimensions':[1280,720]},indent=2))
    fresh.reload();fresh.wait_for_function("document.documentElement.dataset.production25d==='ready'")
    assert fresh.locator('#sessionList button').count()==1
    assert fresh.evaluate('async()=>(await PubCast25DStore.listCaptures()).length')==0


def test_active_other_tab_cannot_be_claimed_and_old_writer_is_fenced_after_completion(studio, production_server):
    page, context=studio;start(page);page.click('#record')
    page.wait_for_function('PubCast25DStudio.state().journal?.bytes>0')
    row=page.evaluate('async()=>(await PubCast25DStore.listCaptures())[0]')
    other=context.new_page();other.goto(production_server[0]+'/static/production25d.html')
    other.wait_for_function("document.documentElement.dataset.production25d==='ready'")
    rejection=other.evaluate("async id=>{try{await PubCast25DStudio.recoverCapture(id);return 'claimed';}catch(e){return e.message;}}",row['id'])
    assert 'active in another' in rejection
    assert page.evaluate('PubCast25DStudio.state().recording')
    page.click('#recordStop');page.wait_for_function('!PubCast25DStudio.state().recording')
    # Completed journal and media are one transaction; stale owners cannot append.
    result=other.evaluate("""async row=>{try{await PubCast25DStore.appendCapture(row.id,row.owner,{index:row.nextIndex,blob:new Blob(['bad']),sha256:'a'.repeat(64),durationMs:9},row.session);return 'accepted';}catch(e){return e.message;}}""",row)
    assert 'ownership changed' in result
    assert other.evaluate('async()=>(await PubCast25DStore.listCaptures()).length')==0


def hold_microphone(page):
    page.evaluate("""() => {
      const ctx=new AudioContext(),stream=ctx.createMediaStreamDestination().stream;
      window.lateMicrophone=stream;window.microphoneRequests=0;
      navigator.mediaDevices.getUserMedia=()=>{microphoneRequests++;return new Promise((r,j)=>{
        window.releaseMicrophone=()=>r(stream);window.rejectMicrophone=()=>j(new DOMException('Old microphone permission denied','NotAllowedError'));});};
      const Native=MediaRecorder;window.recorderStarts=0;
      window.MediaRecorder=class extends Native{start(...a){recorderStarts++;return super.start(...a);}};
    }""")
    page.check('#mic');page.click('#record');page.wait_for_function('microphoneRequests===1')
    assert page.evaluate('PubCast25DStudio.state().recordingStarting')


def test_cancel_pending_microphone_then_new_take_ignores_and_closes_late_stream(studio):
    page,_=studio;start(page);hold_microphone(page)
    result=page.evaluate("async()=>{try{await PubCast25DStudio.startRecording();return 'started';}catch(e){return e.message;}}")
    assert 'Already recording or preparing' in result
    page.click('#recordStop')
    assert not page.evaluate('PubCast25DStudio.state().recordingStarting')
    page.uncheck('#mic');page.click('#record');page.wait_for_function('PubCast25DStudio.state().recording')
    page.evaluate('releaseMicrophone()')
    page.wait_for_function("lateMicrophone.getTracks().every(t=>t.readyState==='ended')")
    assert page.evaluate('recorderStarts')==1
    assert page.evaluate('PubCast25DStudio.state().recording')
    page.wait_for_function('PubCast25DStudio.state().journal.bytes>0')
    page.click('#recordStop');page.wait_for_function('!PubCast25DStudio.state().recording')
    assert page.evaluate('async()=>(await PubCast25DStore.list())[0].recordings.length')==1
    assert page.problems==[]


def test_panic_cancels_pending_microphone_without_late_recording(studio, production_server):
    page,_=studio;start(page);hold_microphone(page)
    _,auth,api=production_server
    response=api.post('/api/production/panic',headers={'Authorization':'Bearer '+auth['access_token']})
    assert response.status_code==200 and response.json()['ok']
    page.wait_for_function('!PubCast25DStudio.state().recordingStarting')
    page.evaluate('releaseMicrophone()')
    page.wait_for_function("lateMicrophone.getTracks().every(t=>t.readyState==='ended')")
    assert page.evaluate('recorderStarts')==0
    assert not page.evaluate('PubCast25DStudio.state().recording')
    assert 'PANIC' in page.locator('#state').inner_text()
    assert page.evaluate('async()=>(await PubCast25DStore.listCaptures()).length')==0


def test_late_rejection_from_canceled_start_does_not_mark_new_recording_as_failed(studio):
    page,_=studio;start(page);hold_microphone(page);page.click('#recordStop')
    page.uncheck('#mic');page.click('#record');page.wait_for_function('PubCast25DStudio.state().recording')
    page.evaluate('async()=>{rejectMicrophone();await new Promise(r=>setTimeout(r,0));}')
    assert page.locator('#alert').inner_text()==''
    assert page.evaluate('PubCast25DStudio.state().recording')
    assert page.problems==[]
    page.evaluate("lateMicrophone.getTracks().forEach(t=>t.stop())")
    page.wait_for_function('PubCast25DStudio.state().journal.bytes>0')
    page.click('#recordStop');page.wait_for_function('!PubCast25DStudio.state().recording')


def test_slow_storage_stops_capture_without_discarding_uncommitted_bytes(studio):
    page,_=studio;start(page)
    page.evaluate("""()=>{
      const create=PubCast25DCapture.create;
      PubCast25DCapture.create=options=>create({...options,maxPendingChunks:2});
      const append=PubCast25DStore.appendCapture;let first=true;
      PubCast25DStore.appendCapture=async(...args)=>{if(first){first=false;await new Promise(r=>window.releaseDisk=r);}return append(...args);};
      const Native=MediaRecorder;window.originalPieces=[];window.recorderStopped=false;
      window.MediaRecorder=class extends Native{constructor(...args){super(...args);
        this.addEventListener('dataavailable',e=>{if(e.data.size)originalPieces.push(e.data);});
        this.addEventListener('stop',()=>{recorderStopped=true;});}};
    }""")
    page.click('#record');page.wait_for_function('PubCast25DStudio.state().recording')
    page.wait_for_function('recorderStopped',timeout=12000)
    assert 'cannot keep up' in page.locator('#captureStatus').inner_text()
    assert page.evaluate('PubCast25DStudio.state().journal.pendingChunks')<=4
    page.evaluate('releaseDisk()')
    page.wait_for_function('!PubCast25DStudio.state().recording')
    actual=page.evaluate("""async()=>{const s=(await PubCast25DStore.list())[0],r=await PubCast25DStore.read(s.id);
      return {hash:await PubCast25DCapture.digest(r.blob),original:await PubCast25DCapture.digest(new Blob(originalPieces)),incomplete:s.media.incomplete};}""")
    assert actual['hash']==actual['original'] and actual['incomplete'] is True


def test_version_two_store_upgrade_preserves_completed_take_and_server_receipt(production_browser, production_server):
    base,auth,_=production_server;ctx=production_browser.new_context()
    ctx.add_init_script("sessionStorage.setItem('pubcast_token',"+json.dumps(auth['access_token'])+");sessionStorage.setItem('pubcast_user',JSON.stringify({username:'engineer',role:'owner'}));")
    page=ctx.new_page();page.goto(base+'/health')
    try:
        page.evaluate("""async()=>{await new Promise((resolve,reject)=>{
          const q=indexedDB.open('pubcast-25d-local',2);
          q.onupgradeneeded=()=>{for(const n of ['sessions','media','archives'])q.result.createObjectStore(n,{keyPath:'id'});};
          q.onerror=()=>reject(q.error);q.onsuccess=()=>{const db=q.result,tx=db.transaction(['sessions','media','archives'],'readwrite');
            tx.objectStore('sessions').put({id:'pubcast25d-v2',startedAt:'2026-10-31T12:00:00Z',packageId:'news',events:[],media:{id:'take-v2',mime:'video/webm'}});
            tx.objectStore('media').put({id:'take-v2',blob:new Blob(['original v2 bytes'],{type:'video/webm'})});
            tx.objectStore('archives').put({id:'take-v2',state:'complete',owner:'engineer',serverId:'saved-v2'});
            tx.oncomplete=()=>{db.close();resolve();};};});}""")
        page.goto(base+'/static/production25d.html');page.wait_for_function("document.documentElement.dataset.production25d==='ready'")
        actual=page.evaluate("""async()=>{const r=await PubCast25DStore.read('pubcast25d-v2');return {text:await r.blob.text(),receipt:await PubCast25DStore.archive('take-v2'),journals:await PubCast25DStore.listCaptures()};}""")
        assert actual=={'text':'original v2 bytes','receipt':{'id':'take-v2','state':'complete','owner':'engineer','serverId':'saved-v2'},'journals':[]}
    finally:
        ctx.close()


def test_full_browser_process_crash_preserves_take_in_reopened_profile(production_browser, production_server, tmp_path):
    base,auth,_=production_server;profile=tmp_path/'browser-profile';contexts=[]
    def reopen():
        ctx=production_browser.browser_type.launch_persistent_context(str(profile),args=GL_ARGS,viewport={'width':1280,'height':1000})
        contexts.append(ctx)
        ctx.add_init_script("sessionStorage.setItem('pubcast_token',"+json.dumps(auth['access_token'])+");sessionStorage.setItem('pubcast_user',JSON.stringify({username:'engineer',role:'owner'}));")
        page=ctx.new_page();page.goto(base+'/static/production25d.html')
        page.wait_for_function("document.documentElement.dataset.production25d==='ready'")
        return ctx,page
    try:
        context,page=reopen();start(page);page.click('#record')
        page.wait_for_function('PubCast25DStudio.state().journal?.chunks>=2')
        before=page.evaluate('async()=>(await PubCast25DStore.listCaptures())[0]')
        # This kills Chromium itself, rather than closing the recording page cleanly.
        try:
            context.new_cdp_session(page).send('Browser.crash')
        except BrowserError:
            pass
        context,fresh=reopen()
        original=fresh.evaluate("""async id=>{const r=await PubCast25DStore.readCapture(id),b=await PubCast25DCapture.assemble(r);return {bytes:b.size,hash:await PubCast25DCapture.digest(b)};}""",before['id'])
        assert original['bytes']>=before['bytes']>1000
        fresh.wait_for_function("document.querySelector('#captureRecoveryList button')&&!document.querySelector('#captureRecoveryList button').disabled",timeout=25000)
        fresh.locator('#captureRecoveryList button').click()
        fresh.wait_for_function('playback.videoWidth===1280&&playback.readyState>=2')
        fresh.evaluate('playback.play()');fresh.wait_for_function('playback.currentTime>.1')
        recovered=fresh.evaluate("""async()=>{const s=(await PubCast25DStore.list())[0],r=await PubCast25DStore.read(s.id);return {bytes:r.blob.size,hash:await PubCast25DCapture.digest(r.blob)};}""")
        assert recovered==original
        (tmp_path/'verified.json').write_text(json.dumps({'entire_browser_crashed_before_stop':True,**recovered},indent=2))
    finally:
        for context in contexts:
            try:context.close()
            except BrowserError:pass

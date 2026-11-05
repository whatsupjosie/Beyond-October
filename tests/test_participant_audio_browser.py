"""Real Chromium peers, real socket audio, decoded program/stems and crash recovery.

Oscillators replace physical microphones only; signaling, PCM relay, Web Audio,
MediaRecorder, IndexedDB, HTTP ingest and ffmpeg decoding are all real.
"""
import base64
import hashlib
import io
import json
import subprocess
from zipfile import ZipFile
from datetime import datetime

import numpy as np
from playwright.sync_api import Error as BrowserError

from tests.test_production25d_browser import production_browser, production_server, studio, wait_for_actors


def contributor(browser, base, auth, room, frequency):
    context = browser.new_context()
    context.add_init_script("sessionStorage.setItem('pubcast_token',"+json.dumps(auth['access_token'])+");")
    page = context.new_page()
    page.goto(base+'/static/participant_audio.html?room='+room)
    page.evaluate("""frequency=>{
      const ctx=new AudioContext(),osc=ctx.createOscillator(),gain=ctx.createGain(),dest=ctx.createMediaStreamDestination();
      osc.frequency.value=frequency;gain.gain.value=.12;osc.connect(gain);gain.connect(dest);osc.start();ctx.resume();
      window.microphone=dest.stream;window.tone={ctx,osc};
      navigator.mediaDevices.getUserMedia=async()=>dest.stream;
    }""", frequency)
    page.check('#consent');page.click('#connect')
    return context, page


def meter(page):
    page.evaluate("""()=>{
      const mix=PubcastProgramAudio;window.probe=mix.context.createAnalyser();probe.fftSize=8192;probe.smoothingTimeConstant=0;
      mix.context.createMediaStreamSource(mix.captureOutputStream()).connect(probe);
      window.bands=()=>{const data=new Float32Array(probe.frequencyBinCount);probe.getFloatFrequencyData(data);
        return [440,880].map(f=>{const i=Math.round(f*probe.fftSize/mix.context.sampleRate);return Math.max(...data.slice(i-2,i+3));});};
    }""")


def bytes_for(page, session_id, take_id):
    encoded=page.evaluate("""async([session,take])=>{
      const {blob}=await PubCast25DStore.read(session,take);const data=new Uint8Array(await blob.arrayBuffer());
      let s='';for(let i=0;i<data.length;i+=8192)s+=String.fromCharCode(...data.subarray(i,i+8192));return btoa(s);
    }""", [session_id,take_id])
    return base64.b64decode(encoded)


def decode(path):
    result=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-vn','-ac','1','-ar','48000','-f','f32le','pipe:1'],capture_output=True,check=True,timeout=30)
    return np.frombuffer(result.stdout,dtype='<f4')


def amplitude(samples, freq):
    samples=samples[:min(len(samples),48000)]
    return abs(np.sum(samples*np.exp(-2j*np.pi*freq*np.arange(len(samples))/48000)))/max(1,len(samples))


def test_two_peers_mix_controls_separate_durable_stems_and_original_server_export(studio, production_browser, production_server, tmp_path):
    page,_=studio;base,auth,api=production_server
    wait_for_actors(page);page.click('#start');page.click('#audioOpen')
    page.wait_for_function("audioInvite.value.includes('room=')")
    room=page.evaluate('PubCastAudioDesk.reservation.room')
    page.evaluate("()=>{window.audioReports=[];const f=PubCastAudioDesk.onState;PubCastAudioDesk.onState=(...a)=>{audioReports.push(a[0]);f(...a);};}")
    contexts=[]
    try:
        ctx,one=contributor(production_browser,base,auth,room,440);contexts.append(ctx)
        try:
            page.wait_for_function('PubcastProgramAudio.inputs.size===1',timeout=12000)
        except Exception:
            print('HOST',page.locator('#participantAudioStatus').inner_text(),page.problems)
            print('GUEST',one.locator('#status').inner_text())
            raise
        first=page.evaluate('Array.from(PubcastProgramAudio.inputs.keys())[0]')
        ctx,two=contributor(production_browser,base,auth,room,880);contexts.append(ctx)
        page.wait_for_function('PubcastProgramAudio.inputs.size===2')
        second=page.evaluate('Array.from(PubcastProgramAudio.inputs.keys())[1]')
        meter(page);page.wait_for_function('bands().every(n=>n>-35)')
        page.click('#record');page.wait_for_function('PubCast25DStudio.state().recording')
        page.wait_for_function('PubCast25DStudio.state().journal.chunks>=2',timeout=15000)
        page.evaluate('()=>{const until=performance.now()+900;while(performance.now()<until){};}')
        assert page.evaluate('PubcastProgramAudio.inputs.size')==2
        page.wait_for_function('bands().every(n=>n>-35)')
        baseline=page.evaluate('bands()')
        page.evaluate('id=>PubcastProgramAudio.configureInput(id,{volume:.25})',first)
        page.wait_for_function('target=>bands()[0]<target',arg=baseline[0]-11)
        quiet=page.evaluate('bands()');assert 9 < baseline[0]-quiet[0] < 16
        page.evaluate('id=>PubcastProgramAudio.configureInput(id,{muted:true})',first)
        page.wait_for_function('bands()[0]<-70 && bands()[1]>-35')
        page.evaluate('id=>PubcastProgramAudio.configureInput(id,{muted:false,volume:1,solo:true,eq:[0,12,0]})',first)
        page.wait_for_function('target=>bands()[1]<-70 && bands()[0]>target',arg=baseline[0]+1.5)
        page.evaluate('id=>PubcastProgramAudio.configureInput(id,{solo:false,eq:[0,0,0]})',first)
        page.wait_for_function('bands().every(n=>n>-35)')
        page.evaluate("PubcastProgramAudio.setMuted('dialogue',true)")
        page.wait_for_function('bands().every(n=>n<-70)')
        muted_at=page.evaluate('Date.now()')
        page.wait_for_timeout(1200)
        page.evaluate("PubcastProgramAudio.setMuted('dialogue',false)")
        # Disconnect one source mid-take, then explicitly reconnect it. The old
        # stem remains a separate segment, with no stale or doubled mixer input.
        one.click('#leave');page.wait_for_function('PubcastProgramAudio.inputs.size===1')
        page.wait_for_function('bands()[0]<-70 && bands()[1]>-35')
        one.evaluate('()=>{const d=tone.ctx.createMediaStreamDestination(),g=tone.ctx.createGain();g.gain.value=.12;tone.osc.connect(g);g.connect(d);microphone=d.stream;navigator.mediaDevices.getUserMedia=async()=>d.stream;}')
        one.click('#connect');page.wait_for_function('PubcastProgramAudio.inputs.size===2')
        page.wait_for_function('bands().every(n=>n>-35)')
        page.wait_for_timeout(1500)
        page.click('#recordStop');page.wait_for_function('!PubCast25DStudio.state().recording',timeout=20000)
        session=page.evaluate('async()=>(await PubCast25DStore.list())[0]')
        assert len(session['sourceTracks'])==3
        assert all(s['preFader'] and not s['incomplete'] and s['parentTakeId']==session['media']['id'] for s in session['sourceTracks'])
        assert page.evaluate('async()=>(await PubCast25DStore.listCaptures()).length')==0
        # Sources decode independently: the 440 source contains no 880 voice,
        # including the interval while its program channel was muted.
        for track in session['sourceTracks']:
            path=tmp_path/(track['id']+'.webm');path.write_bytes(bytes_for(page,session['id'],track['id']))
            samples=decode(path);a,b=amplitude(samples,440),amplitude(samples,880)
            assert max(a,b)>.01 and min(a,b)<max(a,b)*.05, (a,b)
            assert len(samples)/48000>.5
            if track['sourceId']==first:
                start=round((muted_at+500-datetime.fromisoformat(track['startedAt'].replace('Z','+00:00')).timestamp()*1000)*48)
                assert np.sqrt(np.mean(samples[start:start+14400]**2))>.05
        video=tmp_path/'program.webm';video.write_bytes(bytes_for(page,session['id'],session['media']['id']))
        audio=decode(video);assert amplitude(audio,440)>.01 and amplitude(audio,880)>.01
        start=round((muted_at+500-datetime.fromisoformat(session['media']['startedAt'].replace('Z','+00:00')).timestamp()*1000)*48)
        assert np.sqrt(np.mean(audio[start:start+14400]**2))<.005
        track=session['sourceTracks'][0]
        # Exercise the actual UI-selected voice -> resumable server save -> ZIP.
        page.locator('#sessionList button').filter(has_text='VOICE:').first.click()
        page.click('#archiveSave');page.wait_for_function("archiveStatus.textContent.startsWith('Saved on server:')",timeout=30000)
        headers={'Authorization':'Bearer '+auth['access_token']}
        takes=api.get('/api/studio25d/recordings',headers=headers).json()['takes']
        saved=next(t for t in takes if t['take_id']==track['id'])
        assert saved['state']=='complete'
        assert saved['media']['streams'][0]['codec_type']=='audio'
        assert abs(saved['capture_started_at']*1000-datetime.fromisoformat(track['startedAt'].replace('Z','+00:00')).timestamp()*1000)<1
        response=api.post('/api/studio25d/recordings/'+saved['id']+'/bundle',headers=headers)
        assert response.status_code==200,response.text[:200] if response.status_code!=200 else ''
        with ZipFile(io.BytesIO(response.content)) as bundle:
            candidates=[bundle.read(n) for n in bundle.namelist() if n.endswith('.webm')]
            assert bytes_for(page,session['id'],track['id']) in candidates
        # A stalled capture clock is removed on its own; another participant keeps playing.
        two.evaluate('PubCastAudioContribution.context.suspend()')
        page.wait_for_function('PubcastProgramAudio.inputs.size===1')
        page.wait_for_function('bands()[1]<-70 && bands()[0]>-35')
        two.wait_for_function('PubCastAudioContribution.closed')
        assert page.evaluate('!PubCastAudioDesk.closed')
        page.evaluate("PubcastProgramAudio.consume({action:'stop',bus:'dialogue'})")
        one.wait_for_function('PubCastAudioContribution.closed')
        assert page.evaluate('PubcastProgramAudio.inputs.size===0 && PubCastAudioDesk.closed')
        assert page.problems==[]
    finally:
        print('AUDIO REPORTS',page.evaluate('audioReports'))
        for context in contexts:context.close()


def test_renderer_crash_recovers_independent_voice_and_program_without_overwriting(studio, production_browser, production_server, tmp_path):
    page,context=studio;base,auth,_=production_server
    wait_for_actors(page);page.click('#start');page.click('#audioOpen');page.wait_for_function("audioInvite.value.includes('room=')")
    guest_context,guest=contributor(production_browser,base,auth,page.evaluate('PubCastAudioDesk.reservation.room'),440)
    try:
        page.wait_for_function('PubcastProgramAudio.inputs.size===1');meter(page);page.wait_for_function('bands()[0]>-35')
        page.click('#record');page.wait_for_function('PubCast25DStudio.state().journal?.chunks>=3',timeout=15000)
        with page.expect_event('crash'):
            try:page.goto('chrome://crash',timeout=5000)
            except BrowserError:pass
        fresh=context.new_page();fresh.goto(base+'/static/production25d.html')
        fresh.wait_for_function("document.documentElement.dataset.production25d==='ready'")
        rows=fresh.evaluate('async()=>await PubCast25DStore.listCaptures()')
        assert len(rows)==2 and {r.get('kind','program') for r in rows}=={'program','audio-source'}
        source=next(r for r in rows if r.get('kind')=='audio-source');program=next(r for r in rows if r.get('kind')!='audio-source')
        proof=fresh.evaluate('''async id=>{const record=await PubCast25DStore.readCapture(id),blob=await PubCast25DCapture.assemble(record);
          return {bytes:blob.size,sha256:await PubCast25DCapture.digest(blob)};}''',source['id'])
        fresh.wait_for_function("document.querySelectorAll('#captureRecoveryList button').length===2 && Array.from(document.querySelectorAll('#captureRecoveryList button')).every(b=>!b.disabled)",timeout=25000)
        fresh.evaluate('id=>PubCast25DStudio.recoverCapture(id)',source['id'])
        fresh.evaluate('id=>PubCast25DStudio.recoverCapture(id)',program['id'])
        saved=fresh.evaluate('async()=>(await PubCast25DStore.list())[0]')
        assert len(saved['recordings'])==1 and len(saved['sourceTracks'])==1
        assert saved['media']['incomplete'] and saved['sourceTracks'][0]['incomplete']
        assert saved['sourceTracks'][0]['parentTakeId']==saved['media']['id']
        data=bytes_for(fresh,saved['id'],source['id'])
        assert len(data)==proof['bytes'] and hashlib.sha256(data).hexdigest()==proof['sha256']
        path=tmp_path/'recovered-voice.webm';path.write_bytes(data);assert amplitude(decode(path),440)>.01
        guest.wait_for_function('PubCastAudioContribution.closed',timeout=25000)
        assert guest.evaluate("microphone.getTracks().every(t=>t.readyState==='ended')")
    finally:guest_context.close()


def test_local_microphone_enters_canonical_bus_and_preserves_raw_voice(studio):
    page,_=studio;wait_for_actors(page);page.click('#start')
    page.evaluate('''()=>{const ctx=new AudioContext(),osc=ctx.createOscillator(),gain=ctx.createGain(),dest=ctx.createMediaStreamDestination();
      osc.frequency.value=440;gain.gain.value=.12;osc.connect(gain);gain.connect(dest);osc.start();ctx.resume();
      navigator.mediaDevices.getUserMedia=async()=>dest.stream;}''')
    page.check('#mic');page.click('#record');page.wait_for_function('PubCast25DStudio.state().recording')
    assert page.evaluate("PubcastProgramAudio.inputs.has('local-microphone')")
    meter(page);page.wait_for_function('bands()[0]>-35')
    page.evaluate("PubcastProgramAudio.setMuted('dialogue',true)");page.wait_for_function('bands()[0]<-70')
    # Raw capture still has source samples, while program bus is silenced.
    page.evaluate('''()=>{window.rawProbe=PubcastProgramAudio.context.createAnalyser();
      PubcastProgramAudio.context.createMediaStreamSource(PubcastProgramAudio.inputs.get('local-microphone').rawStream).connect(rawProbe);
      window.rawPower=()=>{const a=new Float32Array(rawProbe.fftSize);rawProbe.getFloatTimeDomainData(a);return Math.sqrt(a.reduce((s,x)=>s+x*x,0)/a.length);};}''')
    page.wait_for_function('rawPower()>.05');page.wait_for_function('PubCast25DStudio.state().journal.chunks>=2',timeout=15000)
    page.evaluate("PubcastProgramAudio.consume({action:'stop',bus:'dialogue'})")
    page.wait_for_function("audioBadge.textContent==='MIC OFF'")
    assert page.evaluate('PubcastProgramAudio.inputs.size')==0
    page.click('#recordStop');page.wait_for_function('!PubCast25DStudio.state().recording')
    saved=page.evaluate('async()=>(await PubCast25DStore.list())[0]')
    assert len(saved['sourceTracks'])==1 and saved['sourceTracks'][0]['preFader']
    assert page.evaluate('PubcastProgramAudio.context.state')=='running'
    assert page.evaluate('PubcastProgramAudio.inputs.size')==0


def test_late_permission_after_cancel_cannot_close_new_participant_connection(studio, production_browser, production_server):
    page,_=studio;base,auth,_=production_server
    wait_for_actors(page);page.click('#start');page.click('#audioOpen');page.wait_for_function("audioInvite.value.includes('room=')")
    room=page.evaluate('PubCastAudioDesk.reservation.room')
    context=production_browser.new_context();context.add_init_script("sessionStorage.setItem('pubcast_token',"+json.dumps(auth['access_token'])+");")
    guest=context.new_page();guest.goto(base+'/static/participant_audio.html?room='+room)
    try:
        guest.evaluate('''()=>{const c=new AudioContext();window.oldStream=c.createMediaStreamDestination().stream;
          navigator.mediaDevices.getUserMedia=()=>new Promise(r=>window.grantOld=()=>r(oldStream));}''')
        guest.check('#consent');guest.click('#connect');guest.wait_for_function('typeof grantOld===\"function\"')
        guest.click('#leave');guest.wait_for_function('PubCastAudioContribution.closed')
        guest.evaluate('''()=>{const c=new AudioContext(),d=c.createMediaStreamDestination(),o=c.createOscillator();o.connect(d);o.start();c.resume();
          window.newStream=d.stream;navigator.mediaDevices.getUserMedia=async()=>d.stream;}''')
        guest.click('#connect');page.wait_for_function('PubcastProgramAudio.inputs.size===1')
        guest.evaluate('grantOld()');guest.wait_for_function("oldStream.getTracks().every(t=>t.readyState==='ended')")
        assert guest.evaluate('!PubCastAudioContribution.closed && newStream.getAudioTracks()[0].readyState===\"live\"')
        assert page.evaluate('PubcastProgramAudio.inputs.size')==1
        guest.evaluate("dispatchEvent(new CustomEvent('pubcast:room',{detail:{room:'dressing'}}))")
        page.wait_for_function('PubcastProgramAudio.inputs.size===0')
        assert guest.evaluate("newStream.getTracks().every(t=>t.readyState==='ended')")
    finally:context.close()

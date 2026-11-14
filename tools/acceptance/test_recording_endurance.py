"""Explicit 30-minute acceptance; excluded from ordinary tests/ collection.

Run explicitly with pytest -s. Virtual audio and isolated Chromium processes are
reported as such; this never certifies physical devices or a scene master.
"""
import hashlib
import json
import time
import os
import subprocess
import math
from pathlib import Path
from contextlib import contextmanager

import numpy as np

from tests.test_production25d_browser import production_browser,production_server,studio,wait_for_actors,GL_ARGS
from tests.test_human_profile_onboarding_browser import fresh_host
from tests.test_independent_guest_hosts import setup
from tests.test_guest_identity import CONSENTS
from tests.test_participant_audio_browser import contributor,meter,amplitude


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def media_duration(video, info):
    """Read the encoded duration even when MediaRecorder omits the WebM header field."""
    container_duration = info["format"].get("duration")
    if container_duration not in (None, "N/A"):
        return float(container_duration), "container"

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_packets", "-show_entries",
         "packet=pts_time,duration_time", "-of", "json", str(video)],
        capture_output=True, text=True, check=True, timeout=90,
    )
    packets = [
        (float(packet["pts_time"]), float(packet.get("duration_time", 0)))
        for packet in json.loads(result.stdout)["packets"]
        if "pts_time" in packet
    ]
    assert packets, "Encoded take has no timestamped packets"
    start = min(pts for pts, _ in packets)
    end = max(pts + duration for pts, duration in packets)
    assert end > start, "Encoded take has no positive timestamp span"
    return end - start, "packets"


def download_selected(page, selection, destination):
    previous_url = page.locator("#playback").get_attribute("src")
    selection.click()
    page.wait_for_function(
        "previous => document.querySelector('#playback').getAttribute('src')?.startsWith('blob:') && document.querySelector('#playback').getAttribute('src') !== previous",
        arg=previous_url,
    )
    with page.expect_download(timeout=120000) as download:
        page.click("#download")
    download.value.save_as(destination)


def test_thirty_minute_program_two_admitted_peers_and_reload(studio,production_browser,production_server,tmp_path):
    page,context=studio;base,owner,host=production_server
    headers={'Authorization':'Bearer '+owner['access_token']}
    target_seconds=int(os.environ.get('PUBCAST_ENDURANCE_SECONDS','1800'));assert 60<=target_seconds<=1800
    report={'target_seconds':target_seconds,'scope':'Linux software WebGL, independent Chromium processes, generated audio; no physical-device or multicamera scene-master claim','minutes':[],'faults':[]}
    path=tmp_path/'endurance.json'
    def save():path.write_text(json.dumps(report,indent=2)+'\n')
    wait_for_actors(page);page.click('#start');page.evaluate('''()=>{window.enduranceAudioReports=[];const report=PubCastAudioDesk.onState;PubCastAudioDesk.onState=(message,...args)=>{enduranceAudioReports.push({at:performance.now(),message});report(message,...args)};}''');page.click('#audioOpen')
    page.wait_for_function("audioInvite.value.includes('room=')")
    room=page.evaluate('PubCastAudioDesk.reservation.room')
    peers=[];browsers=[]
    try:
        for index,frequency in enumerate([440,880]):
            with contextmanager(fresh_host.__wrapped__)(tmp_path/f'home-{index}') as (_,home):
                person,own=setup(home,f'endurance-{index}')
                invitation=host.post('/api/guests/invites',headers=headers,json={}).json()['invite_code']
                challenge=host.post('/api/guests/challenge',json={'invite_code':invitation}).json()
                proof=home.post('/api/guests/sign',headers=own,json={'challenge':challenge['challenge'],'consents':CONSENTS})
                entry=host.post('/api/guests/request',json=proof.json()).json()['entry_id']
                pending=next(p for p in host.get('/api/guests/pending',headers=headers).json()['pending'] if p['entry_id']==entry)
                assert host.post('/api/guests/entries/'+entry+'/approve',headers=headers,json={'fingerprint':pending['fingerprint']}).status_code==200
                lease=host.post('/api/guests/status',json={'poll_token':challenge['poll_token']}).json()
                assert person['user_id']==lease['user_id']
            browser=production_browser.browser_type.launch(args=GL_ARGS);browsers.append(browser)
            ctx,peer=contributor(browser,base,lease,room,frequency);peers.append((ctx,peer))
        page.wait_for_function('PubcastProgramAudio.inputs.size===2');meter(page)
        page.wait_for_function('bands().every(n=>n>-35)');page.click('#record')
        page.wait_for_function('PubCast25DStudio.state().journal?.chunks>=2',timeout=20000)
        started=time.monotonic();report['started_monotonic']=started;previous=0
        for minute in range(1,math.ceil(target_seconds/60)+1):
            while time.monotonic()-started<min(minute*60,target_seconds):
                page.wait_for_timeout(1000)
                if not page.evaluate('PubCast25DStudio.state().recording'):
                    report['faults'].append({'elapsed':time.monotonic()-started,'alert':page.locator('#alert').inner_text()});save()
                    raise AssertionError('Recording stopped before the endurance interval; see endurance.json')
            sample=page.evaluate('''()=>({state:PubCast25DStudio.state(),peers:PubcastProgramAudio.inputs.size,bands:bands(),heap:performance.memory?.usedJSHeapSize||null,audioReports:enduranceAudioReports,receiverFault:PubCastAudioDesk.lastFault??null,deskStatus:document.getElementById('participantAudioStatus')?.textContent})''')
            sample['elapsed_seconds']=time.monotonic()-started;sample['minute']=minute
            sample['peer_status']=[peer.locator('#status').inner_text() for ctx,peer in peers]
            report['minutes'].append(sample);save();print('ENDURANCE',minute,sample['state']['journal'],flush=True)
            assert sample['state']['journal']['bytes']>previous
            previous=sample['state']['journal']['bytes']
            if sample['peers'] != 2:
                report['faults'].append({'elapsed': sample['elapsed_seconds'], 'peer_count': sample['peers'],
                                         'receiver_fault': sample['receiverFault']})
                save()
                raise AssertionError('A guest audio input dropped before the end; see endurance.json')
            if minute==5:
                page.evaluate('()=>{const until=performance.now()+900;while(performance.now()<until){};}')
                report['main_thread_stall_ms']=900;save()
            if minute==15:
                peer=peers[1][1];peer.evaluate('PubCastAudioContribution.context.suspend()')
                page.wait_for_function('PubcastProgramAudio.inputs.size===1',timeout=15000)
                peer.wait_for_function('PubCastAudioContribution.closed',timeout=15000)
                peer.evaluate('''()=>{const d=tone.ctx.createMediaStreamDestination(),g=tone.ctx.createGain();g.gain.value=.12;tone.osc.connect(g);g.connect(d);microphone=d.stream;navigator.mediaDevices.getUserMedia=async()=>d.stream;}''')
                peer.click('#connect');page.wait_for_function('PubcastProgramAudio.inputs.size===2')
                page.wait_for_function('bands().every(n=>n>-35)');report['explicit_rejoin']=True;save()
            buttons=page.locator('[data-shot]')
            shot = buttons.nth(minute % buttons.count())
            target = shot.get_attribute('data-shot')
            shot.click()
            page.wait_for_function('id => PubCast25DStudio.state().preview === id', arg=target)
            page.click('#cut')
            page.wait_for_function('id => PubCast25DStudio.state().program === id', arg=target)
        report['recording_observed_seconds']=time.monotonic()-started
        page.click('#recordStop');page.wait_for_function('!PubCast25DStudio.state().recording',timeout=120000)
        page.click('#stop');page.wait_for_function('PubCast25DStudio.state().session===null',timeout=30000)
        session=page.evaluate('async()=>(await PubCast25DStore.list())[0]')
        report['session']=session
        assert not session['media'].get('incomplete')
        voices=[s for s in session['sourceTracks'] if s['kind']!='sync-reference']
        assert len(voices)==(3 if target_seconds>=900 else 2) and all(not s.get('incomplete') for s in voices)
        select = page.locator('#sessionList button').filter(has_text='Take 1')
        video = tmp_path / 'endurance.webm'
        download_selected(page, select, video)
        report['media_sha256'] = digest(video)
        probe=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(video)],capture_output=True,text=True,check=True,timeout=90)
        info=json.loads(probe.stdout);report['ffprobe']=info
        duration, duration_source = media_duration(video, info)
        report['encoded_duration_seconds'] = duration
        report['encoded_duration_source'] = duration_source
        save()
        assert duration >= target_seconds
        for at in [1,duration*.4,max(1,duration-2)]:
            decoded=subprocess.run(['ffmpeg','-v','error','-ss',str(at),'-i',str(video),'-t','1','-vn','-ac','1','-ar','48000','-f','f32le','pipe:1'],capture_output=True,check=True,timeout=45)
            samples=np.frombuffer(decoded.stdout,dtype='<f4');values=[amplitude(samples,f) for f in [440,880]]
            report.setdefault('decoded_audio',[]).append({'at':at,'amplitudes':values});assert all(v>.01 for v in values)
        page.reload();page.wait_for_function("document.documentElement.dataset.production25d==='ready'")
        restored = tmp_path / 'endurance-reopened.webm'
        download_selected(page, page.locator('#sessionList button').filter(has_text='Take 1'), restored)
        report['reopened_sha256']=digest(restored);assert report['media_sha256']==report['reopened_sha256']
        reference=session['syncReferences'][0]
        audio={m['sequence'] for m in reference['audioMarks']};visual={m['sequence'] for m in reference['videoMarks']}
        report['sync_observations']={'audio_marks':len(audio),'video_marks':len(visual),'missing_visual_sequences':sorted(audio-visual),'encoded_pixel_alignment':'not inferred from paint timestamps'}
        report['status']='PASS_FOR_'+str(target_seconds)+'_SECOND_PROGRAM_AUDIO_ENDURANCE_ONLY';save();print('ENDURANCE_REPORT',path,flush=True)
    finally:
        try:
            report['last_audio_reports']=page.evaluate('window.enduranceAudioReports||[]')
            report['last_receiver_fault']=page.evaluate('PubCastAudioDesk.lastFault??null')
            if 'status' not in report:
                if page.evaluate('PubCast25DStudio.state().recording'):
                    if page.locator('#recordStop').is_enabled():
                        page.click('#recordStop')
                    page.wait_for_function('!PubCast25DStudio.state().recording',timeout=120000)
                take = page.locator('#sessionList button').filter(has_text='Take 1')
                if take.count():
                    report['session']=page.evaluate('async()=>(await PubCast25DStore.list())[0]')
                    downloads = [('retained-failed-run.webm', take)]
                    sources = page.locator('#sessionList button').filter(has_text=r'SYNC:')
                    voices = page.locator('#sessionList button').filter(has_text=r'VOICE:')
                    downloads.extend((f'retained-sync-{index + 1}.webm', item)
                                     for index, item in enumerate(sources.all()))
                    downloads.extend((f'retained-voice-{index + 1}.webm', item)
                                     for index, item in enumerate(voices.all()))
                    report['retained_files'] = []
                    for name, item in downloads:
                        download_selected(page, item, tmp_path / name)
                        report['retained_files'].append(name)
        except Exception as error:
            report['failure_capture_error']=str(error)
        save()
        for ctx,peer in peers:ctx.close()
        for browser in browsers:browser.close()

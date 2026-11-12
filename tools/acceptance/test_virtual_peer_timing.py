"""Real socket/worklet transport under virtual latency, jitter and clock skew.

This is a loopback, independent-browser-process check, not physical device sync.
"""
import asyncio
import json
import time
import uuid
import re
from urllib.parse import urlsplit

import pytest
from playwright.async_api import async_playwright

from tests.test_production25d_browser import production_server,GL_ARGS
from tests.test_guest_identity import profile,CONSENTS
from modules.guest_identity import sign_visit
from modules.credentials import CredentialStore


@pytest.mark.asyncio
async def test_virtual_peer_skew_jitter_and_explicit_stall( production_server,tmp_path):
    base,owner,api=production_server;headers={'Authorization':'Bearer '+owner['access_token']}
    guest=profile('u_'+uuid.uuid4().hex[:20])
    code=api.post('/api/guests/invites',headers=headers,json={}).json()['invite_code']
    challenge=api.post('/api/guests/challenge',json={'invite_code':code}).json()
    proof=sign_visit(CredentialStore(tmp_path/'own-copy-key'),guest,challenge['challenge'],CONSENTS)
    entry=api.post('/api/guests/request',json=proof).json()['entry_id']
    pending=next(p for p in api.get('/api/guests/pending',headers=headers).json()['pending'] if p['entry_id']==entry)
    assert api.post('/api/guests/entries/'+entry+'/approve',headers=headers,json={'fingerprint':pending['fingerprint']}).status_code==200
    lease=api.post('/api/guests/status',json={'poll_token':challenge['poll_token']}).json()
    state={'scope':'loopback TCP proxy; independent browser processes; signed guest; generated audio',
           'forwarded_chunks':0,'forwarded_bytes':0,'drop':False,'connections':0,'tasks':set()}
    target=urlsplit(base)
    async def proxy(reader,writer):
        current=asyncio.current_task();state['tasks'].add(current);remote_writer=None;tasks=[]
        try:
            remote_reader,remote_writer=await asyncio.open_connection(target.hostname,target.port)
            header=await reader.readuntil(b'\r\n\r\n')
            header=re.sub(br'(?im)^Host:[^\r\n]+',('Host: '+target.netloc).encode(),header)
            remote_writer.write(header);await remote_writer.drain()
            response=await remote_reader.readuntil(b'\r\n\r\n')
            writer.write(response);await writer.drain();state['connections']+=1
            async def uplink():
                while block:=await reader.read(65536):
                    remote_writer.write(block);await remote_writer.drain()
            async def downlink():
                while block:=await remote_reader.read(65536):
                    if state['drop']:continue
                    await asyncio.sleep([.04,.16,.07,.12][state['forwarded_chunks']%4])
                    if state['drop']:continue
                    writer.write(block);await writer.drain()
                    state['forwarded_chunks']+=1;state['forwarded_bytes']+=len(block)
            tasks=[asyncio.create_task(uplink()),asyncio.create_task(downlink())]
            await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            writer.close()
            if remote_writer:remote_writer.close()
            state['tasks'].discard(current)
    proxy_server=await asyncio.start_server(proxy,'127.0.0.1',0)
    proxy_port=proxy_server.sockets[0].getsockname()[1]
    async with async_playwright() as p:
        host_browser=await p.chromium.launch(args=GL_ARGS);guest_browser=await p.chromium.launch(args=GL_ARGS)
        try:
            hc=await host_browser.new_context();gc=await guest_browser.new_context()
            await hc.add_init_script('sessionStorage.setItem("pubcast_token",'+json.dumps(owner['access_token'])+');')
            await gc.add_init_script('sessionStorage.setItem("pubcast_token",'+json.dumps(lease['access_token'])+');Date.now=(()=>{const now=Date.now;return()=>now()+120000;})();')
            # Native worker sockets are outside Playwright's WebSocket routing.
            # Redirect only their URL through a real transparent TCP proxy;
            # original worker, protocol, backend and PCM worklets all still run.
            async def worker_script(route):
                response=await route.fetch()
                prefix="'use strict';const NativeSocket=WebSocket;self.WebSocket=class extends NativeSocket {constructor(url,...rest){const u=new URL(url);u.port='"+str(proxy_port)+"';super(u.href,...rest);}};\n"
                await route.fulfill(response=response,body=prefix+await response.text())
            await hc.route('**/static/participant_audio_worker.js',worker_script)
            page=await hc.new_page();await page.goto(base+'/static/production25d.html')
            await page.wait_for_function("document.documentElement.dataset.production25d==='ready'")
            await page.click('#start');await page.click('#audioOpen')
            await page.wait_for_function('!!window.PubCastAudioDesk.reservation')
            room=await page.evaluate('PubCastAudioDesk.reservation.room')
            peer=await gc.new_page();await peer.goto(base+'/static/participant_audio.html?room='+room)
            await peer.evaluate('''()=>{const ctx=new AudioContext(),osc=ctx.createOscillator(),gain=ctx.createGain(),dest=ctx.createMediaStreamDestination();osc.frequency.value=440;gain.gain.value=.12;osc.connect(gain);gain.connect(dest);osc.start();ctx.resume();window.tone={ctx,osc};navigator.mediaDevices.getUserMedia=async()=>dest.stream;}''')
            await peer.check('#consent');await peer.click('#connect')
            await page.wait_for_function('PubcastProgramAudio.inputs.size===1',timeout=15000)
            await page.evaluate('''()=>{const ctx=PubcastProgramAudio.context,probe=ctx.createAnalyser();probe.fftSize=8192;ctx.createMediaStreamSource(PubcastProgramAudio.captureOutputStream()).connect(probe);window.power440=()=>{const d=new Float32Array(probe.frequencyBinCount);probe.getFloatFrequencyData(d);const i=Math.round(440*probe.fftSize/ctx.sampleRate);return Math.max(...d.slice(i-2,i+3))};}''')
            await page.wait_for_function('power440()>-35',timeout=15000)
            observed=[]
            for _ in range(10):
                await asyncio.sleep(1)
                observed.append(await page.evaluate('({inputs:PubcastProgramAudio.inputs.size,power:power440()})'))
            assert state['connections']==1 and state['forwarded_bytes']>48000*2*5 and all(v['inputs']==1 and v['power']>-35 for v in observed)
            skew=await peer.evaluate('Date.now()')-await page.evaluate('Date.now()');assert 119000<skew<121000
            state['drop']=True
            await page.wait_for_function('PubcastProgramAudio.inputs.size===0',timeout=12000)
            await peer.wait_for_function('PubCastAudioContribution.closed',timeout=12000)
            report={key:value for key,value in state.items() if key!='tasks'}
            report.update(observed_power=observed,clock_skew_ms=skew,explicit_stall_disconnect=True,physical_device_alignment='NOT_VERIFIED',sample_accurate_video_sync='NOT_VERIFIED')
            (tmp_path/'virtual-timing.json').write_text(json.dumps(report,indent=2)+'\n')
        finally:
            await guest_browser.close();await host_browser.close()
            proxy_server.close();await proxy_server.wait_closed()
            remaining=list(state['tasks'])
            for task in remaining:task.cancel()
            await asyncio.gather(*remaining,return_exceptions=True)

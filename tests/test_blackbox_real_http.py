"""Real loopback HTTP/WebSocket -> durable WAV -> restart -> preservation.

The source is a generated 440 Hz waveform, not a microphone or browser.
"""
import asyncio
import os
import socket
import subprocess
import sys
import time
import wave
import json

import httpx
import pytest
import websockets

from modules import auth
from tests.test_communications_capture import pcm

SERVER = r'''
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
from modules.blackbox_runtime import create_blackbox_witness
from modules.blackbox_routes import create_blackbox_router
witness=create_blackbox_witness(Path(sys.argv[1]))
@asynccontextmanager
async def lifespan(app):
    yield
    witness.close()
app=FastAPI(lifespan=lifespan)
app.include_router(create_blackbox_router(witness))
uvicorn.run(app, host='127.0.0.1',port=int(sys.argv[2]),log_level='error')
'''


def test_real_socket_record_save_restart_preserve(tmp_path):
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    token=auth.create_access_token({'sub':'real-test','role':'owner'})
    headers={'Authorization':'Bearer '+token}
    env={**os.environ,'PUBCAST_JWT_SECRET':auth._SECRET_KEY}
    def start():
        process=subprocess.Popen([sys.executable,'-c',SERVER,str(tmp_path),str(port)],env=env,
                                  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            if process.poll() is not None:raise RuntimeError('Capture HTTP server exited')
            try:
                if httpx.get(base+'/api/operator/blackbox/health',headers=headers,timeout=.2).status_code==200:
                    return process
            except httpx.HTTPError:pass
            time.sleep(.03)
        process.terminate();process.wait(timeout=5)
        raise RuntimeError('Capture HTTP server did not start')
    process=start()
    try:
        async def stream():
            async with websockets.connect(f'ws://127.0.0.1:{port}/api/operator/blackbox/capture',additional_headers=headers) as ws:
                await ws.send(json.dumps({'source':'control-room-mix','encoding':'pcm-s16le','sample_rate':16000,'channels':1}))
                capture_id=json.loads(await ws.recv())['capture_id']
                await ws.send(pcm(seconds=.1))
                assert json.loads(await ws.recv())['frames']==1600
                await ws.send('stop')
                await ws.wait_closed()
                return capture_id
        capture_id=asyncio.run(stream())
        result=httpx.post(base+'/api/operator/blackbox/save',headers=headers).json()
        assert result['ok']
        process.terminate();process.wait(timeout=5)
        process=start()
        result=httpx.post(base+'/api/operator/blackbox/preserve',headers=headers,json={
            'capture_id':capture_id,'start_seconds':.025,'end_seconds':.075}).json()
        assert result['ok'],result
        with wave.open(str(tmp_path/'blackbox'/'media'/(result['artifact_id']+'.wav'))) as copied:
            assert copied.readframes(copied.getnframes())==pcm(seconds=.1)[800:2400]
    finally:
        process.terminate();process.wait(timeout=5)

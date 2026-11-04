"""A page reload drops the Blackbox capture socket without a close frame; the host must handle that quietly.

Before the fix, the handler's final `ws.close()` raised WebSocketDisconnect into the server ("Exception in ASGI
application") every time the control room was reloaded mid-capture. The audio already committed was kept either way;
this test pins that the server stays quiet and keeps serving. Real loopback server and sockets; the audio is generated.
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest
import websockets

from modules import auth
from tests.test_blackbox_real_http import SERVER
from tests.test_communications_capture import pcm


@pytest.fixture()
def server(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    headers = {"Authorization": "Bearer " + auth.create_access_token({"sub": "disconnect-test", "role": "owner"})}
    env = {**os.environ, "PUBCAST_JWT_SECRET": auth._SECRET_KEY}
    errors = tmp_path / "server.log"
    log = open(errors, "w", encoding="utf-8")
    # Same server as the other real-socket test, but with warnings and tracebacks left switched on.
    process = subprocess.Popen([sys.executable, "-c", SERVER.replace("log_level='error'", "log_level='warning'"), str(tmp_path), str(port)],
                               env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(200):
            if process.poll() is not None:
                raise RuntimeError("Capture HTTP server exited")
            try:
                if httpx.get(f"http://127.0.0.1:{port}/api/operator/blackbox/health", headers=headers, timeout=.3).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(.05)
        else:
            raise RuntimeError("Capture HTTP server did not start")
        yield port, headers, errors
    finally:
        process.terminate()
        process.wait(timeout=5)
        log.close()


async def _capture(port, headers, how):
    ws = await websockets.connect(f"ws://127.0.0.1:{port}/api/operator/blackbox/capture", additional_headers=headers)
    await ws.send(json.dumps({"source": "control-room-mix", "encoding": "pcm-s16le", "sample_rate": 16000, "channels": 1}))
    capture_id = json.loads(await ws.recv())["capture_id"]
    await ws.send(pcm(seconds=.1))
    assert json.loads(await ws.recv())["frames"] == 1600
    if how == "dropped":
        ws.transport.abort()          # what a page reload does: the socket vanishes, no close frame
    elif how == "closed":
        await ws.close()              # closed politely but without the final 'stop' message
    return capture_id


@pytest.mark.parametrize("how", ["dropped", "closed"])
def test_a_capture_socket_that_goes_away_mid_stream_is_handled_quietly(server, how):
    port, headers, errors = server
    asyncio.run(_capture(port, headers, how))
    time.sleep(1.0)
    assert errors.read_text(encoding="utf-8").count("Traceback") == 0, errors.read_text(encoding="utf-8")[-2000:]
    # And the host carries on: a second capture works.
    asyncio.run(_capture(port, headers, "closed"))
    assert httpx.get(f"http://127.0.0.1:{port}/api/operator/blackbox/health", headers=headers, timeout=2).status_code == 200

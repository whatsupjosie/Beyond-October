"""End-to-end HTTP persistence through a real bound socket, not TestClient.

All writes use a disposable tmp_path and a separate process; no user data touched.
"""
import multiprocessing
import socket
import time

import httpx
import uvicorn
from fastapi import FastAPI

from modules.writers_room import create_writers_room_router


def _serve(data_dir, port):
    app = FastAPI()
    app.include_router(create_writers_room_router(data_dir))
    uvicorn.run(app, host='127.0.0.1', port=port, log_level='error', access_log=False)


def test_manuscript_survives_real_http_process_restart(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    path = '/api/writers-room/documents/first-session'

    def launch():
        proc = multiprocessing.get_context('spawn').Process(target=_serve, args=(tmp_path, port), daemon=True)
        proc.start()
        for _ in range(100):
            if not proc.is_alive():
                raise AssertionError('2i server exited during startup')
            try:
                if httpx.get(base + '/openapi.json', timeout=.2).status_code == 200:
                    return proc
            except httpx.RequestError:
                pass
            time.sleep(.05)
        proc.terminate(); proc.join(5)
        raise AssertionError('2i server did not become reachable')

    proc = launch()
    try:
        payload = {'title': 'First session', 'expected_revision': 0, 'state': {
            'committed': ['Actual words, saved over HTTP.'], 'buffer': [], 'pool': [],
            'conversations': {'alex': [{'role': 'user', 'content': 'Hello'}]},
            'conversationIds': {'alex': 'session-one'},
        }}
        with httpx.Client(base_url=base, timeout=5) as client:
            created = client.put(path, json=payload)
            assert created.status_code == 200, created.text
            assert created.json()['revision'] == 1
            stale = client.put(path, json=payload)
            assert stale.status_code == 409, stale.text
            saved = client.get(path)
            assert saved.status_code == 200, saved.text
            assert saved.json()['state'] == payload['state']
    finally:
        proc.terminate(); proc.join(10)
        if proc.is_alive():
            proc.kill(); proc.join(5)

    restarted = launch()
    try:
        with httpx.Client(base_url=base, timeout=5) as client:
            restored = client.get(path)
            assert restored.status_code == 200, restored.text
            assert restored.json()['revision'] == 1
            assert restored.json()['state'] == payload['state']
            revised = {**payload, 'expected_revision': 1,
                       'state': {**payload['state'], 'committed': ['Revised and saved.']}}
            updated = client.put(path, json=revised)
            assert updated.status_code == 200, updated.text
            assert client.get(path).json()['state']['committed'] == ['Revised and saved.']
    finally:
        restarted.terminate(); restarted.join(10)
        if restarted.is_alive():
            restarted.kill(); restarted.join(5)

"""Real file and protocol tests, not microphone/provider certification."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import math
import struct
import time
import wave

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from blackbox_recorder import AppendOnlyBlackBoxRecorder, record_pubcast_event
from modules.auth import create_access_token
from modules.blackbox_media import BlackBoxMedia
from modules.blackbox_routes import create_blackbox_router
from modules.blackbox_runtime import create_blackbox_witness


def pcm(rate=16000, seconds=1):
    return b''.join(struct.pack('<h', round(12000 * math.sin(2 * math.pi * 440 * i / rate)))
                    for i in range(round(rate * seconds)))


def test_concurrent_event_log_is_one_valid_chain(tmp_path):
    recorder = AppendOnlyBlackBoxRecorder(tmp_path / 'test.bbx', 'test')
    with ThreadPoolExecutor(max_workers=8) as workers:
        list(workers.map(lambda i: record_pubcast_event(recorder, {'event_type': 'runtime.test', 'data': {'n': i}}), range(160)))
    result = recorder.verify()
    assert result.ok, result.errors
    assert result.checked >= 160


def test_capture_preserves_exact_samples_and_survives_restart(tmp_path):
    media = BlackBoxMedia(tmp_path)
    sink = media.start(16000, 1)
    raw = pcm()
    sink.append(raw)
    before = hashlib.sha256(sink.path.read_bytes()).digest()
    result = media.preserve(sink.id, .25, .75)
    assert result['frames'] == 8000
    with wave.open(str(media.root / (result['artifact_id'] + '.wav'))) as copy:
        assert copy.readframes(copy.getnframes()) == raw[8000:24000]
    assert hashlib.sha256(sink.path.read_bytes()).digest() == before
    media.close()
    recovered = BlackBoxMedia(tmp_path)
    assert recovered.preserve(sink.id, 0, 1)['frames'] == 16000


def test_health_does_not_confuse_events_and_media(tmp_path, monkeypatch):
    witness = create_blackbox_witness(tmp_path)
    assert witness.health()['connection'] == 'running'
    assert witness.health()['recording'] == 'inactive'
    sink = witness.media.start(16000, 1)
    sink.append(pcm(seconds=.1))
    assert witness.health()['recording'] == 'running'
    sink.last_progress = time.monotonic() - 8
    assert witness.health()['recording'] == 'crashed'
    monkeypatch.setattr(witness.recorder, 'append', lambda **event: (_ for _ in ()).throw(OSError('disk full')))
    assert witness.health()['connection'] == 'crashed'
    sink.close()


def test_capture_and_control_never_grant_anonymous_uploads(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '0')
    witness = create_blackbox_witness(tmp_path)
    app = FastAPI(); app.include_router(create_blackbox_router(witness))
    with TestClient(app) as client:
        assert client.post('/api/operator/blackbox/save').status_code == 403
        assert client.get('/api/operator/blackbox/health').status_code == 401
        with pytest.raises(Exception):
            with client.websocket_connect('/api/operator/blackbox/capture') as ws:
                ws.receive_json()
        token = create_access_token({'sub': 'director', 'role': 'owner'})
        headers = {'Authorization': 'Bearer ' + token}
        assert client.post('/api/operator/blackbox/save', headers=headers).json()['ok']
        with client.websocket_connect('/api/operator/blackbox/capture', headers=headers) as ws:
            ws.send_json({'source': 'control-room-mix', 'encoding': 'pcm-s16le', 'sample_rate': 16000, 'channels': 1})
            capture_id = ws.receive_json()['capture_id']
            ws.send_bytes(pcm(seconds=.1))
            assert ws.receive_json()['frames'] == 1600
            assert client.get('/api/operator/blackbox/health', headers=headers).json()['recording'] == 'running'
            response = client.post('/api/operator/blackbox/preserve', headers=headers, json={
                'capture_id': capture_id, 'start_seconds': .025, 'end_seconds': .075})
            assert response.status_code == 200, response.text
            assert response.json()['frames'] == 800
            ws.send_text('stop')
            try: ws.receive_json()
            except Exception: pass
        assert client.post('/api/operator/blackbox/preserve', headers=headers, json={
            'capture_id': capture_id, 'start_seconds': 0, 'end_seconds': 100}).status_code == 400
        assert client.get('/api/operator/blackbox/recordings', headers=headers).status_code == 404


def test_shutdown_is_idempotent_and_records_final_marker(tmp_path):
    witness = create_blackbox_witness(tmp_path)
    witness.close(); witness.close()
    assert witness.health()['connection'] == 'inactive'
    assert 'runtime.blackbox_stopped' in witness.path.read_text()
    witness.reopen()
    assert witness.health()['connection'] == 'running'
    witness.close()
    assert witness.verify().ok


def test_preserve_rejects_ambiguous_clock_ranges():
    from modules.blackbox_routes import PreserveRequest
    from pydantic import ValidationError
    for fields in [dict(start_at='2026-10-20T18:36:00', end_at='2026-10-20T20:49:00'),
                   dict(start_seconds=0),dict(start_seconds=0,end_seconds=1,start_at='2026-10-20T18:36:00-07:00')]:
        with pytest.raises(ValidationError): PreserveRequest(capture_id='a'*32, **fields)
    request=PreserveRequest(capture_id='a'*32,start_at='2026-10-20T18:36:00-07:00',end_at='2026-10-20T20:49:00-07:00')
    assert request.start_at.utcoffset() is not None

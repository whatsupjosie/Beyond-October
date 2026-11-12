"""Failure-focused checks for the real coded ledger and durable audio sink."""
import json
from itertools import count
import pytest
from blackbox_event_language.schema import BlackBoxValidationError, decode_record
from blackbox_recorder import AppendOnlyBlackBoxRecorder, map_pubcast_event
from modules.blackbox_runtime import create_blackbox_witness
from modules.blackbox_media import BlackBoxMedia


def test_slow_storage_emits_one_pressure_record_without_recursing(tmp_path, monkeypatch):
    import blackbox_recorder.append_only_recorder as module
    ticks = count()
    monkeypatch.setattr(module, 'perf_counter', lambda: next(ticks) * .01)
    recorder = AppendOnlyBlackBoxRecorder(tmp_path / 'slow.bbx', 'slow')
    recorder.append(ch='REC', src='REC', act='SYS', ev='DCP', cov='F')
    assert recorder.verify().ok
    assert recorder.verify().checked == 2


def test_reopen_checks_the_whole_chain_and_preserves_corrupt_source(tmp_path):
    path = tmp_path / 'source.bbx'
    recorder = AppendOnlyBlackBoxRecorder(path, 'source')
    for value in ['first', 'final']:
        recorder.append(ch='REC', src='REC', act='SYS', ev='DCP', cov='F', payload={'value':value})
    source = path.read_bytes(); assert b'value:first' in source
    damaged = source.replace(b'value:first', b'value:other', 1)
    path.write_bytes(damaged)
    with pytest.raises(BlackBoxValidationError):
        AppendOnlyBlackBoxRecorder(path, 'source')
    assert path.read_bytes() == damaged


def test_reopen_rejects_a_different_session_id(tmp_path):
    path=tmp_path/'session.bbx'
    recorder=AppendOnlyBlackBoxRecorder(path,'original')
    recorder.append(ch='REC',src='REC',act='SYS',ev='DCP',cov='F')
    with pytest.raises(BlackBoxValidationError):AppendOnlyBlackBoxRecorder(path,'different')


def test_recovered_unfinished_audio_is_reported_as_interrupted(tmp_path):
    media=BlackBoxMedia(tmp_path);sink=media.start(16000,1)
    sink.append(b'\x01\x00'*1600)
    original=sink.path.read_bytes()
    recovered=BlackBoxMedia(tmp_path)
    try:
        status=recovered.status()
        assert status['state']=='crashed'
        assert status['captures'][0]['interrupted'] is True
        assert status['captures'][0]['frames']==1600
        assert sink.path.read_bytes()==original
    finally:media.close();recovered.close()


def test_clean_audio_close_is_durable_and_not_interrupted(tmp_path):
    media=BlackBoxMedia(tmp_path);sink=media.start(16000,1)
    sink.append(b'\x01\x00'*1600);media.close()
    recovered=BlackBoxMedia(tmp_path)
    assert recovered.status()['state']=='inactive'
    assert recovered.status()['captures'][0]['interrupted'] is False


def test_damaged_capture_metadata_is_visible_without_rewriting_source(tmp_path):
    media=BlackBoxMedia(tmp_path);sink=media.start(16000,1);sink.append(b'\0\0'*1600);media.close()
    sink.path.with_suffix('.json').write_text('{broken')
    before=sink.path.read_bytes()
    recovered=BlackBoxMedia(tmp_path)
    assert recovered.status()['state']=='crashed'
    assert recovered.status()['recovery_issues']
    assert sink.path.read_bytes()==before


def test_real_recording_receipts_are_not_classified_as_unknown_errors():
    event=map_pubcast_event({'event_type':'recording.artifact','source':'recording','data':{'sha256':'a'*64}})
    assert event.ch=='REC' and event.cov=='F'


def test_closed_witness_refuses_access_and_crash_writes(tmp_path):
    witness=create_blackbox_witness(tmp_path);witness.close();before=witness.path.read_bytes()
    assert witness.access('operator','status') is None
    assert witness.crash_position('late') is False
    assert witness.path.read_bytes()==before


def test_storage_failure_halts_append_until_explicit_reopen(tmp_path, monkeypatch):
    import os
    path=tmp_path/'write.bbx';recorder=AppendOnlyBlackBoxRecorder(path,'write')
    def fail(_):raise OSError('full')
    with monkeypatch.context() as m:
        m.setattr(os,'fsync',fail)
        with pytest.raises(OSError):recorder.append(ch='REC',src='REC',act='SYS',ev='DCP',cov='F')
    before=path.read_bytes()
    with pytest.raises(OSError):recorder.append(ch='REC',src='REC',act='SYS',ev='DCP',cov='F')
    assert path.read_bytes()==before


def test_closed_audio_tampering_is_detected_on_recovery(tmp_path):
    media=BlackBoxMedia(tmp_path);sink=media.start(16000,1);sink.append(b'\x01\0'*1600);media.close()
    with sink.path.open('r+b') as handle:handle.seek(-1,2);handle.write(b'\x01')
    recovered=BlackBoxMedia(tmp_path)
    assert recovered.status()['state']=='crashed'
    assert recovered.status()['recovery_issues']


def test_offline_inspector_detects_pcm_tampering_even_if_sidecar_is_rewritten(tmp_path):
    from tools.blackbox_inspect import inspect
    import hashlib
    witness=create_blackbox_witness(tmp_path)
    sink=witness.media.start(16000,1);data=b'\x01\0'*1600;sink.append(data)
    witness.record_event('capture.chunk_committed',data={'capture_id':sink.id,'first_frame':0,'frames':1600,'sha256':hashlib.sha256(data).hexdigest()})
    witness.close()
    assert inspect(tmp_path)['ok'] and inspect(tmp_path)['coverage_complete']
    with sink.path.open('r+b') as handle:handle.seek(-1,2);handle.write(b'\x01')
    metadata=json.loads(sink.path.with_suffix('.json').read_text())
    metadata['sha256']=hashlib.sha256(sink.path.read_bytes()).hexdigest()
    sink.path.with_suffix('.json').write_text(json.dumps(metadata))
    report=inspect(tmp_path)
    assert not report['ok']
    assert 'packet receipt' in report['captures'][0]['error']


def test_pcm_is_never_acknowledged_without_its_durable_witness_receipt(tmp_path, monkeypatch):
    from fastapi import FastAPI, WebSocketDisconnect
    from fastapi.testclient import TestClient
    from modules.auth import create_access_token
    from modules.blackbox_routes import create_blackbox_router
    witness=create_blackbox_witness(tmp_path);original=witness.record_event
    monkeypatch.setattr(witness,'record_event',lambda kind,**kwargs:None if kind=='capture.chunk_committed' else original(kind,**kwargs))
    app=FastAPI();app.include_router(create_blackbox_router(witness))
    headers={'Authorization':'Bearer '+create_access_token({'sub':'test-operator','role':'owner'})}
    with TestClient(app) as client:
        with client.websocket_connect('/api/operator/blackbox/capture',headers=headers) as ws:
            ws.send_json({'source':'control-room-mix','encoding':'pcm-s16le','sample_rate':16000,'channels':1})
            capture_id=ws.receive_json()['capture_id']
            ws.send_bytes(b'\0\0'*1600)
            with pytest.raises(WebSocketDisconnect):ws.receive_json()
    sink=witness.media.captures[capture_id]
    assert sink.frames==1600 and sink.error and sink.closed
    assert witness.verify().ok

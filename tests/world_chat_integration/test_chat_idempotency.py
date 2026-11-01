"""A stable client send UUID must commit one room-log entry even after a lost receipt."""
from __future__ import annotations

import asyncio
import concurrent.futures
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from modules.auth import create_access_token
from modules.chat_rooms import create_chat_router
from modules.hub import Hub
from modules.route_security import current_identity


def _api(hub):
    app = FastAPI()
    app.include_router(create_chat_router(hub, current_identity))
    return TestClient(app)


def _send(client, sender, text, key):
    return client.post('/api/chat/rooms/world/send', headers={
        'Authorization': 'Bearer ' + create_access_token({'sub': sender, 'role': 'guest'})
    }, json={'text': text, 'client_message_id': key})


def test_duplicate_http_retry_is_one_commit_one_bot_invocation_across_hubs(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    first, second = Hub(tmp_path), Hub(tmp_path)
    seen = []
    async def callback(message):
        seen.append(message['message_id'])
    first.on_chat_callback = callback
    second.on_chat_callback = callback
    key = str(uuid.uuid4())
    a = _send(_api(first), 'alice', '  Exact draft.\n', key)
    b = _send(_api(second), 'alice', '  Exact draft.\n', key)
    assert a.status_code == b.status_code == 200
    assert a.json()['message_id'] == b.json()['message_id']
    assert a.json()['duplicate'] is False and b.json()['duplicate'] is True
    assert len(asyncio.run(first.get_recent_history('world', 100))) == 1
    assert seen == [a.json()['message_id']]
    # Same text is allowed as a genuinely new message when its key is new.
    c = _send(_api(first), 'alice', '  Exact draft.\n', str(uuid.uuid4()))
    assert c.status_code == 200
    assert c.json()['message_id'] != a.json()['message_id']
    assert len(asyncio.run(first.get_recent_history('world', 100))) == 2


def test_reusing_key_for_different_text_is_conflict_not_silent_replay(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    client = _api(Hub(tmp_path))
    key = str(uuid.uuid4())
    assert _send(client, 'alice', 'one', key).status_code == 200
    conflict = _send(client, 'alice', 'two', key)
    assert conflict.status_code == 409
    assert 'different' in conflict.json()['detail'].lower()
    invalid = _send(client, 'alice', 'text', 'not-a-uuid')
    assert invalid.status_code == 400


def test_simultaneous_retry_uses_one_committed_record(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    hubs = [Hub(tmp_path) for _ in range(6)]
    key = str(uuid.uuid4())
    def send(hub):
        return _send(_api(hub), 'alice', 'same concurrent submission', key)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(send, hubs))
    assert all(response.status_code == 200 for response in results)
    assert len({response.json()['message_id'] for response in results}) == 1
    assert sum(not response.json()['duplicate'] for response in results) == 1
    assert len(asyncio.run(hubs[0].get_recent_history('world', 100))) == 1


def test_legacy_unkeyed_send_keeps_existing_behavior(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    client = _api(Hub(tmp_path))
    for _ in range(2):
        response = _send(client, 'alice', 'legitimate repeated sentence', None)
        assert response.status_code == 200
    assert len(asyncio.run(Hub(tmp_path).get_recent_history('world', 100))) == 2


def test_append_completed_then_receipt_commit_failed_recovers_without_duplicate(tmp_path, monkeypatch):
    """Simulate the failure window after fsync but before durable ledger commit."""
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    from modules.chat_commit_store import ChatCommitStore
    hub = Hub(tmp_path)
    client = _api(hub)
    client_id = str(uuid.uuid4())
    original_append = ChatCommitStore._append_durable
    seen = []
    async def callback(message):
        seen.append(message['message_id'])
    hub.on_chat_callback = callback
    def append_then_fail(path, entry):
        original_append(path, entry)
        raise OSError('Injected process/storage interruption after durable log append')
    monkeypatch.setattr(ChatCommitStore, '_append_durable', staticmethod(append_then_fail))
    # FastAPI will propagate the injected fatal write error. The caller did not
    # receive a receipt even though its original line reached the log.
    with __import__('pytest').raises(OSError):
        _send(client, 'alice', 'Important exactly preserved text', client_id)
    monkeypatch.setattr(ChatCommitStore, '_append_durable', staticmethod(original_append))
    assert len(asyncio.run(hub.get_recent_history('world', 100))) == 1
    response = _send(_api(Hub(tmp_path)), 'alice', 'Important exactly preserved text', client_id)
    assert response.status_code == 200
    assert response.json()['duplicate'] is True
    history = asyncio.run(hub.get_recent_history('world', 100))
    assert len(history) == 1
    assert response.json()['message_id'] == history[0]['message_id']
    assert seen == []  # Side effects cannot be asserted to have succeeded.


def test_idempotency_key_is_scoped_to_author_and_room(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    client = _api(Hub(tmp_path))
    key = str(uuid.uuid4())
    a = _send(client, 'alice', 'hello', key)
    b = _send(client, 'bob', 'hello', key)
    assert a.status_code == b.status_code == 200
    assert a.json()['message_id'] != b.json()['message_id']
    assert not a.json()['duplicate'] and not b.json()['duplicate']


def test_prepared_request_can_be_retried_after_append_failure(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    from modules.chat_commit_store import ChatCommitStore
    hub = Hub(tmp_path)
    original_append = ChatCommitStore._append_durable
    def fail_before_append(*_args):
        raise OSError('Injected unavailable archive before write')
    monkeypatch.setattr(ChatCommitStore, '_append_durable', staticmethod(fail_before_append))
    key = str(uuid.uuid4())
    with __import__('pytest').raises(OSError):
        _send(_api(hub), 'alice', 'Preserved and eventually delivered', key)
    assert asyncio.run(hub.get_recent_history('world', 10)) == []
    monkeypatch.setattr(ChatCommitStore, '_append_durable', staticmethod(original_append))
    retry = _send(_api(Hub(tmp_path)), 'alice', 'Preserved and eventually delivered', key)
    assert retry.status_code == 200
    assert not retry.json()['duplicate']
    assert len(asyncio.run(hub.get_recent_history('world', 10))) == 1


def test_private_permissions_on_new_durable_receipt_database(tmp_path, monkeypatch):
    import os
    import stat
    from pathlib import Path
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    if os.name != 'posix':
        __import__('pytest').skip('POSIX mode check; Windows ACLs require separate platform review')
    old_umask = os.umask(0o022)
    try:
        assert _send(_api(Hub(tmp_path)), 'alice', 'Private content', str(uuid.uuid4())).status_code == 200
    finally:
        os.umask(old_umask)
    root = tmp_path / 'global'
    database = root / 'chat_commit_receipts.sqlite3'
    assert stat.S_IMODE(database.stat().st_mode) == 0o600
    for suffix in ('-wal', '-shm'):
        sidecar = Path(str(database) + suffix)
        if sidecar.exists():
            assert stat.S_IMODE(sidecar.stat().st_mode) & 0o077 == 0


def test_concurrent_independent_messages_remain_distinct_and_verbatim(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    hubs = [Hub(tmp_path) for _ in range(4)]
    submitted = [(f'  sentence {i}  \n', str(uuid.uuid4())) for i in range(24)]
    def send(entry):
        (index, (text, key)) = entry
        reply = _send(_api(hubs[index % len(hubs)]), 'writer', text, key)
        return text, key, reply
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(send, enumerate(submitted)))
    assert all(result.status_code == 200 and not result.json()['duplicate']
               for _, _, result in responses)
    records = asyncio.run(hubs[0].get_recent_history('world', 100))
    assert len(records) == len(submitted)
    assert {r['message_id'] for r in records} == {r.json()['message_id'] for _, _, r in responses}
    assert {(r['text'], r['client_message_id']) for r in records} == set(submitted)


def test_commit_store_rejects_unsafe_room_path_before_disk_write(tmp_path):
    import pytest
    from modules.chat_commit_store import ChatCommitStore
    store = ChatCommitStore(tmp_path)
    for room in ('../../outside', '../world', '/world', 'a/b', 'a\\b', 'x' * 260):
        with pytest.raises(ValueError):
            store.commit(room, 'alice', 'content', str(uuid.uuid4()), 'Alice')
    assert not (tmp_path.parent / 'outside.jsonl').exists()
    assert not (tmp_path / 'logs').exists()


def test_new_and_legacy_chat_room_logs_are_private_and_durable(tmp_path, monkeypatch):
    import os
    import stat
    import pytest
    if os.name != 'posix':
        pytest.skip('POSIX permissions; Windows ACL review is a separate release gate')
    monkeypatch.setenv('PUBCAST_ENFORCE_AUTH', '1')
    hub = Hub(tmp_path)
    path = hub._log_path('world')
    old_umask = os.umask(0o022)
    try:
        assert _send(_api(hub), 'alice', 'legacy no-key text', None).status_code == 200
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        # Upgrade an older, owner-readable archive without exposing new text.
        path.chmod(0o644)
        assert _send(_api(hub), 'alice', 'durable keyed text', str(uuid.uuid4())).status_code == 200
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        path.chmod(0o644)
        assert _send(_api(hub), 'alice', 'legacy again', None).status_code == 200
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert [entry['text'] for entry in hub._read_history_sync(path, 100)] == [
            'legacy no-key text', 'durable keyed text', 'legacy again'
        ]
    finally:
        os.umask(old_umask)

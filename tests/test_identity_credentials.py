"""Human identity keys use the existing encrypted vault and cannot race-rotate."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from modules.credentials import CredentialStore, CredentialError


def test_competing_vaults_share_master_and_identity_secret(tmp_path, monkeypatch):
    monkeypatch.delenv('PUBCAST_MASTER_KEY', raising=False)
    def create(index):
        store = CredentialStore(tmp_path)
        return store.identity_secret('u_human', lambda: bytes([index]) * 32)
    with ThreadPoolExecutor(max_workers=12) as pool:
        values = list(pool.map(create, range(12)))
    assert len(set(values)) == 1
    reopened = CredentialStore(tmp_path)
    assert reopened.identity_secret('u_human', lambda: b'new') == values[0]
    encrypted = next((tmp_path/'secure'/'identities').glob('*.key')).read_bytes()
    assert values[0] not in encrypted
    assert reopened.list_models('u_human') == []
    assert not list((tmp_path/'secure').rglob('.key-*'))


def test_damaged_identity_key_is_not_silently_replaced(tmp_path):
    store = CredentialStore(tmp_path)
    store.identity_secret('u_human', lambda: b'private')
    path = next((tmp_path/'secure'/'identities').glob('*.key'))
    path.write_bytes(b'damaged')
    with pytest.raises(CredentialError):
        store.identity_secret('u_human', lambda: b'replacement')
    assert path.read_bytes() == b'damaged'

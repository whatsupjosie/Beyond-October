"""Document storage safety across platforms and malformed persisted state."""
import json
import pytest
from modules import documents

@pytest.mark.parametrize('owner', ['../other', 'a/b', 'a\\b', 'CON', 'com1.txt', 'LPT9', 'name.', 'name ', 'a:b', 'a?b', 'a\x00b'])
def test_invalid_owner_rejected_before_disk_access(tmp_path, owner):
    with pytest.raises(ValueError):
        documents.load_state(tmp_path, owner)
    assert not (tmp_path / 'documents').exists()

@pytest.mark.parametrize('bad', [
    {'folders': 'not-a-list', 'documents': [], 'messages': []},
    {'folders': [{'name':'bad'}], 'documents': [], 'messages': []},
    {'folders': [], 'documents': [None], 'messages': []},
    {'folders': [], 'documents': [], 'messages': {}},
    {'folders': [], 'documents': [], 'messages': [], 'provider': []},
])
def test_invalid_existing_collections_never_overwritten(tmp_path, bad):
    path = tmp_path / 'documents' / 'owner.json'
    path.parent.mkdir()
    raw = json.dumps(bad)
    path.write_text(raw, encoding='utf-8')
    with pytest.raises(ValueError):
        documents.load_state(tmp_path, 'owner')
    assert path.read_text(encoding='utf-8') == raw

def test_valid_document_roundtrip_and_isolation(tmp_path):
    original = 'Line 1\n\n  line 2\t✨\n'
    doc = documents.upsert_document(tmp_path, 'owner', {'title': 'Poem', 'content': original})
    assert documents.get_document(tmp_path, 'owner', doc['doc_id'])['content'] == original
    assert documents.export_document(tmp_path, 'owner', doc['doc_id'])['content'] == original
    assert all(x['doc_id'] != doc['doc_id'] for x in documents.list_documents(tmp_path, 'other'))

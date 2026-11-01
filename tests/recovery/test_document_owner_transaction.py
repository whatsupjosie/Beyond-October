"""Real concurrent persistence checks for the shared 2i document store."""
from concurrent.futures import ThreadPoolExecutor
import json
import pytest

from modules import documents


def test_concurrent_creates_do_not_lose_documents(tmp_path):
    documents.load_state(tmp_path, 'owner')
    def create(i):
        return documents.upsert_document(tmp_path, 'owner', {'title': f'Document {i}', 'content': f'body-{i}'})
    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(create, range(60)))
    stored = documents.list_documents(tmp_path, 'owner')
    assert len({d['doc_id'] for d in results}) == 60
    assert {d['doc_id'] for d in results}.issubset({d['doc_id'] for d in stored})
    assert {d['content'] for d in stored if d['title'].startswith('Document ')} == {f'body-{i}' for i in range(60)}


def test_concurrent_messages_preserved(tmp_path):
    documents.load_state(tmp_path, 'owner')
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda i: documents.send_message(tmp_path, 'owner', {'subject': f'notice-{i}'}), range(30)))
    assert sum(m['folder_id'] == 'sent' for m in documents.list_messages(tmp_path, 'owner')) == 30


def test_existing_empty_or_corrupt_state_never_reset(tmp_path):
    path = tmp_path / 'documents' / 'owner.json'
    path.parent.mkdir()
    for content in ('{}', 'null', '{not json'):
        path.write_text(content, encoding='utf-8')
        with pytest.raises((ValueError, json.JSONDecodeError)):
            documents.load_state(tmp_path, 'owner')
        assert path.read_text(encoding='utf-8') == content


def test_distinct_owners_isolated(tmp_path):
    documents.upsert_document(tmp_path, 'a', {'title':'secret', 'content':'alpha'})
    assert not any(d['title']=='secret' for d in documents.list_documents(tmp_path, 'b'))

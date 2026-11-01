"""Regression tests for transcript export and document owner storage boundaries."""
from pathlib import Path
import pytest

from modules.conversation_archive import ConversationArchive
from modules.documents import _state_path, upsert_document, get_document


def test_repeated_conversation_exports_never_overwrite(tmp_path):
    archive = ConversationArchive(tmp_path / 'conversations.sqlite3')
    cid = archive.create_conversation(title='Repeated export')
    archive.append_message(cid, speaker='User', exact_text='first version')
    first = archive.export_documents(cid, tmp_path / 'exports')
    first_contents = {kind: path.read_bytes() for kind, path in first.items()}
    archive.append_message(cid, speaker='User', exact_text='second version')
    second = archive.export_documents(cid, tmp_path / 'exports')
    assert all(first[kind] != second[kind] for kind in first)
    assert all(first[kind].read_bytes() == first_contents[kind] for kind in first)
    assert 'second version' in second['txt'].read_text(encoding='utf-8')


@pytest.mark.parametrize('owner', ['../escape', '..', 'a/b', 'a\\b', 'a\x00b', ''])
def test_document_owner_cannot_escape_storage_directory(tmp_path, owner):
    with pytest.raises(ValueError, match='invalid document owner identity'):
        _state_path(tmp_path, owner)
    assert not (tmp_path / 'escape.json').exists()


def test_safe_document_owner_retains_existing_path_and_round_trip(tmp_path):
    assert _state_path(tmp_path, 'owner_12') == tmp_path / 'documents' / 'owner_12.json'
    saved = upsert_document(tmp_path, 'owner_12', {'title': 'Live manuscript', 'content': 'verbatim\n  indentation'})
    loaded = get_document(tmp_path, 'owner_12', saved['doc_id'])
    assert loaded['content'] == 'verbatim\n  indentation'

"""Cross-process regression for the recovered owner-level document lock."""
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

from modules import documents


def _write_documents(args):
    root, worker, count = args
    for i in range(count):
        documents.upsert_document(Path(root), 'shared_owner', {
            'title': f'worker_{worker}_document_{i}',
            'content': f'verbatim:{worker}:{i}',
        })
    return count


def test_parallel_processes_do_not_lose_updates(tmp_path):
    work = [(str(tmp_path), worker, 15) for worker in range(4)]
    with ProcessPoolExecutor(max_workers=4, mp_context=get_context('spawn')) as pool:
        assert sum(pool.map(_write_documents, work)) == 60
    docs = documents.list_documents(tmp_path, 'shared_owner')
    actual = {d['content'] for d in docs}
    expected = {f'verbatim:{w}:{i}' for w in range(4) for i in range(15)}
    assert expected <= actual

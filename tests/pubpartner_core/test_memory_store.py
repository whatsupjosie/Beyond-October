from datetime import datetime, timedelta, timezone

import pytest

from pubpartner.memory_store import MemoryStore, MemoryStoreError


def test_add_and_count(tmp_path):
    store = MemoryStore(tmp_path / "m.db")
    store.add("Alex once compared the ocean to a held breath.", "episodic")
    store.add("Alex prefers tea over coffee.", "personal")
    assert store.count() == 2
    store.close()


def test_add_rejects_invalid_type(tmp_path):
    store = MemoryStore(tmp_path / "m.db")
    with pytest.raises(MemoryStoreError, match="Invalid memory_type"):
        store.add("text", "not_a_real_type")
    store.close()


def test_add_rejects_empty_text(tmp_path):
    store = MemoryStore(tmp_path / "m.db")
    with pytest.raises(MemoryStoreError, match="empty"):
        store.add("   ", "episodic")
    store.close()


def test_add_rejects_bad_importance(tmp_path):
    store = MemoryStore(tmp_path / "m.db")
    with pytest.raises(MemoryStoreError, match="importance"):
        store.add("text", "episodic", importance=1.5)
    store.close()


def test_persistence_across_reopen(tmp_path):
    db_path = tmp_path / "m.db"
    store = MemoryStore(db_path)
    store.add("Alex loves tide pools.", "personal")
    store.close()

    store2 = MemoryStore(db_path)
    assert store2.count() == 1
    assert store2.all()[0].text == "Alex loves tide pools."
    store2.close()


def test_query_ranks_relevant_memory_higher(tmp_path):
    store = MemoryStore(tmp_path / "m.db")
    store.add("Alex spent the afternoon reorganizing the record collection.", "episodic")
    store.add("Alex is terrified of spiders and always has been.", "emotional")
    store.add("Alex's favorite synth pad sound is a warm analog saw wave.", "personal")

    results = store.query("synth pad sound", top_k=3)
    assert results  # non-empty
    top = results[0]
    assert "synth" in top.memory.text


def test_query_empty_store_returns_empty_list(tmp_path):
    store = MemoryStore(tmp_path / "m.db")
    assert store.query("anything") == []
    store.close()


def test_query_respects_memory_type_filter(tmp_path):
    store = MemoryStore(tmp_path / "m.db")
    store.add("Alex knows how to fix a bicycle chain.", "procedural")
    store.add("Alex feels calm near water.", "emotional")

    results = store.query("bicycle", memory_type="emotional", top_k=5)
    assert all(r.memory.memory_type == "emotional" for r in results)


def test_recency_influences_ranking(tmp_path):
    store = MemoryStore(tmp_path / "m.db")
    old_time = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    store.add("Alex mentioned a project once.", "project", importance=0.5, created_at=old_time)
    store.add("Alex mentioned a project again recently.", "project", importance=0.5)

    results = store.query("project", top_k=2)
    assert results[0].memory.text.endswith("recently.")


def test_seed_from_jsonl(tmp_path):
    jsonl_path = tmp_path / "seed.jsonl"
    jsonl_path.write_text(
        '{"text": "First memory.", "memory_type": "episodic"}\n'
        '{"text": "Second memory.", "memory_type": "semantic", "importance": 0.8}\n'
    )
    store = MemoryStore(tmp_path / "m.db")
    added = store.seed_from_jsonl(jsonl_path)
    assert added == 2
    assert store.count() == 2
    store.close()


def test_seed_from_jsonl_bad_line_raises_with_line_number(tmp_path):
    jsonl_path = tmp_path / "seed.jsonl"
    jsonl_path.write_text('{"text": "ok", "memory_type": "episodic"}\n{not valid json\n')
    store = MemoryStore(tmp_path / "m.db")
    with pytest.raises(MemoryStoreError, match="line 2"):
        store.seed_from_jsonl(jsonl_path)
    store.close()

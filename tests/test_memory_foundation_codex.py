from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from starlette.testclient import TestClient

from modules import memory_engine
from modules.context_retriever import ContextRetriever, RetrievedMemory
from modules.memory_ingestor import MemoryIngestor
from modules.personal_ai_memory_api import configure_personal_memory_api, router as personal_memory_router
from modules.prompt_context_builder import PromptContextBuilder
from modules.universal_memory_system import UniversalMemorySystem


def test_universal_memory_adapters_store_recent_and_search(tmp_path: Path):
    system = UniversalMemorySystem(data_dir=tmp_path)

    entry_id = system.store("pete", "Josie prefers shorter punchier segments", "preference", 0.9)

    assert isinstance(entry_id, str)
    recent = system.get_recent("pete", 5)
    assert recent[0]["content"] == "Josie prefers shorter punchier segments"
    assert recent[0]["memory_type"] == "preference"
    assert system.search("pete", "punchier", 5)[0]["content"] == recent[0]["content"]


def test_character_memory_persists_through_recreation(tmp_path: Path):
    first = UniversalMemorySystem(data_dir=tmp_path)
    first.store("pete", "The opening should start with music", "preference", 0.8)
    first.store("pete", "Recording stopped unexpectedly yesterday", "event", 0.7)
    first.store("pete", "Keep replies gentle when the user is tired", "instruction", 0.9)

    second = UniversalMemorySystem(data_dir=tmp_path)
    second.get_or_create_bank("pete")
    loaded = second.load_from_db(tmp_path)
    recent = second.get_recent("pete", 10)

    assert loaded >= 3
    contents = {item["content"] for item in recent}
    assert "The opening should start with music" in contents
    assert "Recording stopped unexpectedly yesterday" in contents
    assert "Keep replies gentle when the user is tired" in contents


def test_context_retriever_ranks_and_deduplicates(tmp_path: Path):
    memory_engine.record_event(
        tmp_path,
        session_id="s1",
        project_id="pubcast",
        user_id="josie",
        room_id="studio",
        feature_id="test",
        event_type="preference",
        summary="Josie wants short punchy show segments",
        payload={"importance": 0.9},
    )
    memory_engine.record_event(
        tmp_path,
        session_id="s1",
        project_id="pubcast",
        user_id="josie",
        room_id="studio",
        feature_id="test",
        event_type="event",
        summary="The lobby lights were checked",
        payload={"importance": 0.4},
    )

    results = ContextRetriever(tmp_path).retrieve("short segments", "josie", "pubcast", limit=5)

    assert len(results) == 1
    assert results[0].content == "Josie wants short punchy show segments"
    assert results[0].final_score > 0


def test_prompt_context_builder_respects_budget_and_drops_lowest_score():
    memories = [
        RetrievedMemory("high value memory about music", "test", "preference", 0.9, 1.0, 2.0, 8.0, "just now"),
        RetrievedMemory("low value memory " * 80, "test", "event", 0.1, 0.1, 0.1, 0.5, "3 weeks ago"),
    ]

    text = PromptContextBuilder().build(
        {"display_name": "Pete", "role": "director", "voice_notes": "Direct and warm."},
        memories,
        max_tokens=80,
    )

    assert "high value memory about music" in text
    assert "low value memory" not in text
    assert len(text) // 4 <= 80


def test_personal_memory_api_scopes_queries_to_current_identity(tmp_path: Path):
    memory_system = UniversalMemorySystem(data_dir=tmp_path)
    ingestor = MemoryIngestor(tmp_path, memory_system=memory_system, project_id="pubcast")
    configure_personal_memory_api(data_dir=tmp_path, memory_system=memory_system, ingestor=ingestor)

    app = FastAPI()
    app.include_router(personal_memory_router)
    client = TestClient(app)

    a = client.post(
        "/api/personal-memory/write",
        json={
            "user_id": "mallory",
            "content": "Alice prefers short punchy segments",
            "memory_type": "preference",
            "importance": 0.9,
            "session_id": "s1",
        },
        headers={"X-Client-Id": "alice"},
    )
    b = client.post(
        "/api/personal-memory/write",
        json={
            "user_id": "alice",
            "content": "Bob prefers long reflective openings",
            "memory_type": "preference",
            "importance": 0.9,
            "session_id": "s1",
        },
        headers={"X-Client-Id": "bob"},
    )

    assert a.status_code == 200
    assert b.status_code == 200

    alice = client.get("/api/personal-memory/query?query=segments", headers={"X-Client-Id": "alice"})
    bob = client.get("/api/personal-memory/query?query=openings", headers={"X-Client-Id": "bob"})

    assert alice.status_code == 200
    assert alice.json()["count"] == 1
    assert alice.json()["memories"][0]["content"] == "Alice prefers short punchy segments"
    assert bob.status_code == 200
    assert bob.json()["count"] == 1
    assert bob.json()["memories"][0]["content"] == "Bob prefers long reflective openings"

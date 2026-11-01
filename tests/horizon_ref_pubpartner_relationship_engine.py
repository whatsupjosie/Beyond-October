from __future__ import annotations

import asyncio
from pathlib import Path

from modules.pubpartner_core import PubPartnerSpine
from modules.pubpartner_relationship import RelationshipEngine


def test_explicit_preference_is_learned_and_applied_next_turn(tmp_path: Path):
    spine = PubPartnerSpine(tmp_path)
    first = asyncio.run(spine.run_turn(
        user_id="josie",
        session_id="s1",
        message="I prefer concise answers.",
        friend="craig",
        provider={"provider": "mock"},
        project_id="pubpartner",
    ))
    learned = first["relationship"]["learned_lessons"]
    assert learned
    assert learned[0]["status"] == "confirmed"
    assert "concise answers" in learned[0]["text"].lower()

    second = asyncio.run(spine.build_turn_packet(
        user_id="josie",
        session_id="s1",
        message="Tell me what we are doing next.",
        friend="craig",
        provider={"provider": "mock"},
        project_id="pubpartner",
    ))
    guidance = second["fcp1"]["guide"]
    assert any(row.get("source") == "relationship" and "concise" in row.get("text", "").lower() for row in guidance)


def test_never_instruction_becomes_boundary_and_is_reviewable(tmp_path: Path):
    engine = RelationshipEngine(tmp_path)
    encounter = engine.record_encounter(
        user_id="josie", friend_id="craig", session_id="s1", project_id="pubpartner",
        source_id="src1", source_sha256="abc", user_excerpt="Never rewrite my lyrics.",
        raw_response="ok", friend_response="ok", provider="mock", model="mock",
    )
    lessons = engine.extract_explicit_lessons(
        user_id="josie", friend_id="craig", text="Never rewrite my lyrics.",
        encounter_id=encounter["encounter_id"], project_id="pubpartner", session_id="s1",
    )
    assert lessons[0]["kind"] == "boundary"
    assert lessons[0]["status"] == "confirmed"
    lesson_id = lessons[0]["lesson_id"]
    rejected = engine.update_lesson(
        user_id="josie", friend_id="craig", lesson_id=lesson_id,
        patch={"status": "rejected"},
    )["lesson"]
    assert rejected["status"] == "rejected"
    assert not engine.compact(user_id="josie", friend_id="craig", project_id="pubpartner")


def test_encounter_chain_detects_tampering(tmp_path: Path):
    engine = RelationshipEngine(tmp_path)
    for idx in range(2):
        engine.record_encounter(
            user_id="u", friend_id="f", session_id="s", project_id="p",
            source_id=f"src{idx}", source_sha256="abc", user_excerpt=f"turn {idx}",
            raw_response="raw", friend_response="friend", provider="mock", model="mock",
        )
    assert engine.verify_encounters(user_id="u", friend_id="f")["ok"] is True
    path = engine._encounters_path("u", "f")
    text = path.read_text(encoding="utf-8").replace('"user_excerpt":"turn 0"', '"user_excerpt":"tampered"', 1)
    path.write_text(text, encoding="utf-8")
    assert engine.verify_encounters(user_id="u", friend_id="f")["ok"] is False

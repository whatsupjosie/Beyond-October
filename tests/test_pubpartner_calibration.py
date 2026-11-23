"""Focused calibration contract checks. Run: pytest -q tests/test_pubpartner_calibration.py"""
from __future__ import annotations

import pytest

from modules.pubpartner_calibration import CalibrationError, CalibrationStore


def test_limits_and_optional_followups(tmp_path):
    store = CalibrationStore(tmp_path)
    interview = store.start(user_id="user-a", partner_id="alex", mode="system")
    interview_id = interview["id"]
    for index in range(5):
        result = store.record(user_id="user-a", interview_id=interview_id,
                              action="main_question", text=f"Concrete moment {index}?")
        question_id = result["questions"][-1]["id"]
        result = store.record(user_id="user-a", interview_id=interview_id,
                              action="answer", question_id=question_id, text="No")
        result = store.record(user_id="user-a", interview_id=interview_id,
                              action="follow_up", question_id=question_id,
                              text="Was it what I said?")
        with pytest.raises(CalibrationError):
            store.record(user_id="user-a", interview_id=interview_id,
                         action="follow_up", question_id=question_id, text="Another?")
        store.record(user_id="user-a", interview_id=interview_id,
                     action="follow_up_answer", question_id=question_id, text="Yes")
    with pytest.raises(CalibrationError):
        store.record(user_id="user-a", interview_id=interview_id,
                     action="main_question", text="Sixth question forbidden")
    open_state = store.finish_formal(user_id="user-a", interview_id=interview_id)
    assert open_state["state"] == "open"
    assert open_state["main_questions_asked"] == 5
    result = store.record(user_id="user-a", interview_id=interview_id,
                          action="clarification", text="Was it the timing?")
    assert result["main_questions_asked"] == 5
    assert result["continuation"][-1]["kind"] == "clarification"
    result = store.record(user_id="user-a", interview_id=interview_id,
                          action="continuation", text="I was upset about something else.")
    assert len(result["continuation"]) == 2


def test_user_isolation_and_closed_state(tmp_path):
    store = CalibrationStore(tmp_path)
    doc = store.start(user_id="owner", partner_id="friend", mode="user")
    with pytest.raises(FileNotFoundError):
        store.get(user_id="intruder", interview_id=doc["id"])
    with pytest.raises(FileNotFoundError):
        store.record(user_id="intruder", interview_id=doc["id"],
                     action="main_question", text="Wrong user")
    store.finish_formal(user_id="owner", interview_id=doc["id"])
    with pytest.raises(CalibrationError):
        store.record(user_id="owner", interview_id=doc["id"],
                     action="main_question", text="Not allowed")
    store.close(user_id="owner", interview_id=doc["id"])
    with pytest.raises(CalibrationError):
        store.record(user_id="owner", interview_id=doc["id"],
                     action="continuation", text="Not allowed after close")


def test_explicit_source_refs_and_no_fake_audio(tmp_path):
    store = CalibrationStore(tmp_path)
    doc = store.start(user_id="owner", partner_id="alex", mode="user")
    result = store.record(user_id="owner", interview_id=doc["id"],
                          action="main_question", text="Were you upset here?",
                          evidence={"session_id": "s1", "turn_id": "t2", "raw_audio": "DROP"},
                          modality="text")
    assert result["questions"][0]["evidence"] == {"session_id": "s1", "turn_id": "t2"}
    assert result["questions"][0]["modality"] == "text"
    assert store.list_interviews(user_id="owner")[0]["id"] == doc["id"]


def test_reject_bad_mode_and_empty_question(tmp_path):
    store = CalibrationStore(tmp_path)
    with pytest.raises(CalibrationError):
        store.start(user_id="u", partner_id="alex", mode="made-up")
    doc = store.start(user_id="u", partner_id="alex", mode="system")
    with pytest.raises(CalibrationError):
        store.record(user_id="u", interview_id=doc["id"], action="main_question", text=" ")

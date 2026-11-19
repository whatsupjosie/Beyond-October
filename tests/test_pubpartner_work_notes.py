"""Project work notes: detection, autosave lifecycle, immutability, spine and HTTP wiring.

All tests run offline against temporary directories. No provider, network, or
CI service is contacted.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from modules.pubpartner_core import PubPartnerSpine
from modules.pubpartner_provider import ProviderResult
from modules.pubpartner_work_notes import (
    WorkNoteNotFound,
    WorkNotesError,
    WorkNotesStore,
    detect_notes,
)


class Clock:
    def __init__(self, start: float = 1_800_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _turn(store, text, *, session="s1", turn="t1", reply="", project="p", user="u"):
    return store.record_turn(user_id=user, project_id=project, session_id=session, turn_id=turn,
                             user_text=text, source_id="src_" + turn, source_sha256="h" * 64,
                             reply_text=reply)


# ── detection ────────────────────────────────────────────────────────────────

def test_detected_notes_are_exact_unaltered_sentences_with_spans():
    text = ("Okay, we decided to keep the five files separate.  I still need to test the voice file.\n"
            "Look at main.py and v12 again. Let's go with v12!")
    found = detect_notes(text, origin="user_message")
    assert [n["kind"] for n in found] == ["decided", "open", "worked_on", "decided"]
    for note in found:
        assert text[note["span_start"]:note["span_end"]] == note["text"]
    assert found[0]["text"] == "Okay, we decided to keep the five files separate."


def test_quotes_fences_and_urls_are_never_notes():
    text = ('She said "we decided to delete everything." \n'
            "```\nwe decided inside code.py\n```\n"
            "> we decided in a quote block\n"
            "Read https://example.com/build/main.py for context.")
    assert detect_notes(text, origin="user_message") == []


def test_decisions_and_open_items_come_only_from_the_user():
    reply = "We decided to rewrite your design. I still need to check it."
    assert detect_notes(reply, origin="assistant_reply") == []
    mixed = "I changed modules/pubpartner_core.py. Then I changed it again in modules/pubpartner_core.py."
    found = detect_notes(mixed, origin="assistant_reply")
    assert [n["text"] for n in found] == ["I changed modules/pubpartner_core.py."]


def test_detection_rejects_unknown_origin():
    with pytest.raises(WorkNotesError):
        detect_notes("we decided", origin="someone_else")


# ── store lifecycle ──────────────────────────────────────────────────────────

def test_one_autosave_per_session_and_save_commits_only_that_session(tmp_path):
    store = WorkNotesStore(tmp_path)
    first = _turn(store, "We decided to use SQLite.", session="s1", turn="t1")
    second = _turn(store, "Let's go with v3.", session="s1", turn="t2")
    other = _turn(store, "I still need to export the notes.", session="s2", turn="t3")
    assert first["autosave_id"] == second["autosave_id"] != other["autosave_id"]
    assert second["drafts_this_session"] == 2 and second["drafts_from_earlier_sessions"] == 0
    assert store.context_for_model(user_id="u", project_id="p")["notes"] == []

    saved = store.save(user_id="u", project_id="p", session_id="s1")
    assert saved["count"] == 2
    context = store.context_for_model(user_id="u", project_id="p")
    assert {n["text"] for n in context["notes"]} == {"We decided to use SQLite.", "Let's go with v3."}
    drafts = store.drafts(user_id="u", project_id="p", session_id="s3")
    assert drafts["this_session"] is None
    assert [n["text"] for g in drafts["earlier_sessions"] for n in g["notes"]] == [
        "I still need to export the notes."]


def test_repeat_mentions_do_not_duplicate(tmp_path):
    store = WorkNotesStore(tmp_path)
    _turn(store, "We decided to use SQLite.", turn="t1")
    again = _turn(store, "we decided to use sqlite", turn="t2")
    assert again["added"] == [] and again["duplicates_skipped"] == 1


def test_note_words_and_provenance_cannot_be_changed_or_saved_notes_deleted(tmp_path):
    store = WorkNotesStore(tmp_path)
    note = _turn(store, "We decided to use SQLite.")["added"][0]
    store.save(user_id="u", project_id="p", note_ids=[note["note_id"]])
    with closing(sqlite3.connect(store.path_for("u"))) as raw:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            raw.execute("UPDATE notes SET text = 'We decided to use JSON.' WHERE note_id = ?", (note["note_id"],))
        with pytest.raises(sqlite3.IntegrityError, match="only unsaved drafts"):
            raw.execute("DELETE FROM notes WHERE note_id = ?", (note["note_id"],))
        with pytest.raises(sqlite3.IntegrityError, match="cannot become a draft"):
            raw.execute("UPDATE notes SET status = 'draft' WHERE note_id = ?", (note["note_id"],))
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            raw.execute("DELETE FROM audit")
    assert store.note(user_id="u", note_id=note["note_id"])["text"] == "We decided to use SQLite."
    assert store.verify(user_id="u")["ok"] is True


def test_fixing_a_saved_note_adds_a_new_one_and_keeps_the_old_on_record(tmp_path):
    store = WorkNotesStore(tmp_path)
    note = _turn(store, "We decided to use SQLite.")["added"][0]
    store.save(user_id="u", project_id="p", session_id="s1")
    fixed = store.replace(user_id="u", note_id=note["note_id"], text="We decided to use SQLite with WAL off.")
    assert fixed["note"]["status"] == "saved" and fixed["note"]["replaces"] == note["note_id"]
    assert fixed["replaced"]["status"] == "replaced"
    assert fixed["replaced"]["text"] == "We decided to use SQLite."
    assert fixed["replaced"]["replaced_by"] == fixed["note"]["note_id"]
    texts = [n["text"] for n in store.context_for_model(user_id="u", project_id="p")["notes"]]
    assert texts == ["We decided to use SQLite with WAL off."]
    with pytest.raises(WorkNotesError):
        store.replace(user_id="u", note_id=note["note_id"], text="again")


def test_fixing_a_draft_replaces_it_as_a_draft_in_the_same_autosave(tmp_path):
    store = WorkNotesStore(tmp_path)
    added = _turn(store, "We decided to use SQLite.")
    fixed = store.replace(user_id="u", note_id=added["added"][0]["note_id"], text="We decided on SQLite.",
                          kind="decided")
    assert fixed["note"]["status"] == "draft"
    assert fixed["note"]["autosave_id"] == added["autosave_id"]
    with pytest.raises(WorkNoteNotFound):
        store.note(user_id="u", note_id=added["added"][0]["note_id"])


def test_drop_withdraw_and_their_limits(tmp_path):
    store = WorkNotesStore(tmp_path)
    a, b = _turn(store, "We decided to use SQLite. I still need to test it.")["added"]
    store.drop(user_id="u", note_id=a["note_id"])
    store.save(user_id="u", project_id="p", note_ids=[b["note_id"]])
    with pytest.raises(WorkNotesError):
        store.drop(user_id="u", note_id=b["note_id"])
    store.withdraw(user_id="u", note_id=b["note_id"])
    assert store.context_for_model(user_id="u", project_id="p")["notes"] == []
    assert store.list_notes(user_id="u", project_id="p", status="withdrawn")["count"] == 1
    with pytest.raises(WorkNoteNotFound):
        store.withdraw(user_id="u", note_id="note_missing")


def test_unsaved_drafts_expire_after_a_week_but_saved_notes_stay(tmp_path):
    clock = Clock()
    store = WorkNotesStore(tmp_path, clock=clock)
    keep = _turn(store, "We decided to use SQLite.", session="s1", turn="t1")["added"][0]
    store.save(user_id="u", project_id="p", note_ids=[keep["note_id"]])
    _turn(store, "I still need to test it.", session="s1", turn="t2")
    clock.advance(6 * 24 * 3600)
    assert store.expire(user_id="u")["expired_drafts"] == 0
    clock.advance(1 * 24 * 3600 + 1)
    assert store.expire(user_id="u")["expired_drafts"] == 1
    assert store.list_notes(user_id="u", project_id="p", status="draft")["count"] == 0
    assert store.list_notes(user_id="u", project_id="p", status="saved")["count"] == 1
    assert store.verify(user_id="u")["ok"] is True


def test_working_in_a_session_keeps_its_autosave_alive(tmp_path):
    clock = Clock()
    store = WorkNotesStore(tmp_path, clock=clock)
    _turn(store, "I still need to test it.", session="s1", turn="t1")
    clock.advance(5 * 24 * 3600)
    _turn(store, "We decided to ship v2.", session="s1", turn="t2")
    clock.advance(5 * 24 * 3600)
    assert store.expire(user_id="u")["expired_drafts"] == 0


def test_only_the_newest_fifty_autosaves_keep_their_drafts(tmp_path):
    clock = Clock()
    store = WorkNotesStore(tmp_path, clock=clock)
    for index in range(51):
        clock.advance(1)
        _turn(store, f"I still need to finish part {index} of the build.", session=f"s{index}", turn=f"t{index}")
    drafts = store.drafts(user_id="u", project_id="p")
    sessions = {g["session_id"] for g in drafts["earlier_sessions"]}
    assert len(sessions) == 50 and "s0" not in sessions and "s50" in sessions


def test_context_never_clips_a_note_and_counts_what_was_left_out(tmp_path):
    store = WorkNotesStore(tmp_path)
    long_text = "We decided " + "x" * 3000 + "."
    store.add_note(user_id="u", project_id="p", kind="decided", text=long_text, save=True)
    store.add_note(user_id="u", project_id="p", kind="open", text="Short open item.", save=True)
    context = store.context_for_model(user_id="u", project_id="p", char_budget=100)
    assert [n["text"] for n in context["notes"]] == ["Short open item."]
    assert context["saved_total"] == 2 and context["not_shown"] == 1


def test_user_written_notes_are_kept_exactly_as_written(tmp_path):
    store = WorkNotesStore(tmp_path)
    text = "  keep the egg carton:\nfive separate files  "
    note = store.add_note(user_id="u", project_id="p", kind="decided", text=text, save=True)["note"]
    assert note["text"] == text and note["origin"] == "user_entry"
    with pytest.raises(WorkNotesError):
        store.add_note(user_id="u", project_id="p", kind="decided", text="unsaved without session")
    with pytest.raises(WorkNotesError):
        store.add_note(user_id="u", project_id="p", kind="mood", text="x", save=True)
    with pytest.raises(WorkNotesError):
        store.add_note(user_id="u", project_id="p", kind="decided", text="   ", save=True)


def test_each_user_has_a_separate_file_even_when_names_clean_alike(tmp_path):
    store = WorkNotesStore(tmp_path)
    store.add_note(user_id="a.b", project_id="p", kind="decided", text="One.", save=True)
    store.add_note(user_id="a_b", project_id="p", kind="decided", text="Two.", save=True)
    assert store.path_for("a.b") != store.path_for("a_b")
    assert [n["text"] for n in store.list_notes(user_id="a.b", project_id="p")["notes"]] == ["One."]
    assert [n["text"] for n in store.list_notes(user_id="a_b", project_id="p")["notes"]] == ["Two."]


def test_tampered_audit_is_reported(tmp_path):
    store = WorkNotesStore(tmp_path)
    store.add_note(user_id="u", project_id="p", kind="decided", text="One.", save=True)
    with closing(sqlite3.connect(store.path_for("u"))) as raw:
        raw.execute("DROP TRIGGER audit_is_append_only_update")
        raw.execute("UPDATE audit SET detail = '{}'")
        raw.commit()
    result = store.verify(user_id="u")
    assert result["ok"] is False and result["problems"]


def test_export_is_plain_text_grouped_by_kind(tmp_path):
    store = WorkNotesStore(tmp_path)
    store.add_note(user_id="u", project_id="p", kind="open", text="Still testing.", save=True)
    store.add_note(user_id="u", project_id="p", kind="decided", text="Five files.", save=True)
    text = store.export_text(user_id="u", project_id="p")
    assert text.index("Decided") < text.index("Five files.") < text.index("Still open") < text.index("Still testing.")


# ── spine wiring ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_spine_records_drafts_points_back_to_exact_source_and_feeds_only_saved_notes(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    reply = "I updated modules/pubpartner_core.py for that."
    spine.provider_dispatcher.dispatch = AsyncMock(
        return_value=ProviderResult(ok=True, provider="ollama", raw_response=reply))
    message = "Okay, we decided the cartridge holds five separate files."
    result = await spine.run_turn(user_id="u", session_id="s", message=message, project_id="pp",
                                  room_id="phone", provider={"provider": "ollama"})
    added = result["work_notes"]["added"]
    assert [(n["kind"], n["origin"]) for n in added] == [("decided", "user_message"),
                                                         ("worked_on", "assistant_reply")]
    for note in added:
        source = spine.work_note_source(user_id="u", note_id=note["note_id"])
        assert source["verified"] is True and source["excerpt"] == note["text"]

    unsaved = await spine.build_turn_packet(user_id="u", session_id="s", message="what next?",
                                            project_id="pp", room_id="phone")
    assert "notes=" not in unsaved["llm_prompt_text"]
    assert "notes" not in unsaved["fcp1"]

    spine.work_notes.save(user_id="u", project_id="pp", session_id="s")
    saved = await spine.build_turn_packet(user_id="u", session_id="s2", message="what next?",
                                          project_id="pp", room_id="phone")
    assert message in saved["llm_prompt_text"]
    items = saved["fcp1"]["notes"]["items"]
    assert {i["from"] for i in items} == {"user", "assistant"}
    assert saved["work_notes_context"]["in_context"] == 2

    shared = await spine.build_turn_packet(user_id="u", session_id="s3", message="what next?",
                                           project_id="pp", room_id="stage")
    assert "notes" not in shared["fcp1"]
    assert shared["work_notes_context"]["status"] == "not_private"

    logged = spine.list_turns(user_id="u", session_id="s2", limit=5)["turns"][-1]
    assert logged["fcp1"]["notes"]["text_status"] == "omitted_turn_log_ref_only"
    assert all(set(item) == {"id", "kind"} for item in logged["fcp1"]["notes"]["items"])

    other_project = await spine.build_turn_packet(user_id="u", session_id="s4", message="what next?",
                                                  project_id="elsewhere", room_id="phone")
    assert "notes" not in other_project["fcp1"]


@pytest.mark.asyncio
async def test_diagnostic_replies_and_pasted_code_are_not_mined(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    mock = await spine.run_turn(user_id="u", session_id="s", message="Can you look at app.py?",
                                provider={"provider": "mock"})
    assert [n["origin"] for n in mock["work_notes"]["added"]] == ["user_message"]
    code = "def main():\n    # we decided to keep main.py\n    return 1\n"
    pasted = await spine.run_turn(user_id="u", session_id="s", message=code, content_kind="code",
                                  provider={"provider": "mock"})
    assert pasted["work_notes"]["added"] == []


@pytest.mark.asyncio
async def test_notes_follow_the_project_saved_on_the_session(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    await spine.create_session(user_id="u", session_id="s", project_id="saved-project", room_id="phone")
    result = await spine.run_turn(user_id="u", session_id="s", message="We decided on v4.",
                                  provider={"provider": "mock"})
    assert [n["project_id"] for n in result["work_notes"]["added"]] == ["saved-project"]


@pytest.mark.asyncio
async def test_a_broken_notes_file_reports_but_never_blocks_the_turn(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    spine.work_notes.record_turn = lambda **_: (_ for _ in ()).throw(sqlite3.OperationalError("disk I/O error"))
    result = await spine.run_turn(user_id="u", session_id="s", message="We decided on v2.",
                                  provider={"provider": "mock"})
    assert result["work_notes"]["ok"] is False and "disk I/O error" in result["work_notes"]["error"]
    assert result["friend_response"]


# ── HTTP routes ──────────────────────────────────────────────────────────────

def test_work_note_routes_end_to_end(tmp_path, monkeypatch):
    import pubpartner_app

    monkeypatch.setattr(pubpartner_app, "DATA_DIR", tmp_path)
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")
    headers = {"X-Client-Id": "owner"}
    with TestClient(pubpartner_app.app) as client:
        turn = client.post("/api/pubpartner/turns/live", headers=headers, json={
            "user_id": "owner", "session_id": "notes-s", "project_id": "pubpartner", "room_id": "phone",
            "message": "We decided to keep five separate files. I still need to test the voice file.",
            "friend": "alex", "provider": {"provider": "mock"},
        })
        assert turn.status_code == 200
        assert len(turn.json()["work_notes"]["added"]) == 2

        drafts = client.get("/api/pubpartner/work-notes/drafts", headers=headers,
                            params={"project_id": "pubpartner", "session_id": "notes-s"}).json()
        here = drafts["this_session"]["notes"]
        assert len(here) == 2 and drafts["earlier_sessions"] == []

        dropped = client.post(f"/api/pubpartner/work-notes/{here[1]['note_id']}/drop", headers=headers, json={})
        assert dropped.status_code == 200
        saved = client.post("/api/pubpartner/work-notes/save", headers=headers,
                            json={"project_id": "pubpartner", "session_id": "notes-s"}).json()
        assert saved["count"] == 1

        source = client.get(f"/api/pubpartner/work-notes/{here[0]['note_id']}/source", headers=headers).json()
        assert source["verified"] is True

        added = client.post("/api/pubpartner/work-notes", headers=headers, json={
            "project_id": "pubpartner", "kind": "open", "text": "Decide where plain mode keeps chats.",
            "save": True}).json()
        fixed = client.post(f"/api/pubpartner/work-notes/{added['note']['note_id']}/replace", headers=headers,
                            json={"text": "Decide whether plain mode also keeps chats in the Blackbox."}).json()
        assert fixed["replaced"]["status"] == "replaced"

        listed = client.get("/api/pubpartner/work-notes", headers=headers,
                            params={"project_id": "pubpartner"}).json()
        assert [n["text"] for n in listed["notes"]] == [
            "We decided to keep five separate files.",
            "Decide whether plain mode also keeps chats in the Blackbox.",
        ]
        withdrawn = client.post(f"/api/pubpartner/work-notes/{listed['notes'][0]['note_id']}/withdraw",
                                headers=headers, json={})
        assert withdrawn.json()["note"]["status"] == "withdrawn"

        export = client.get("/api/pubpartner/work-notes/export", headers=headers,
                            params={"project_id": "pubpartner"})
        assert export.status_code == 200 and export.headers["content-type"].startswith("text/plain")
        assert "plain mode also keeps chats" in export.text

        assert client.get("/api/pubpartner/work-notes/verify", headers=headers).json()["ok"] is True
        assert client.post("/api/pubpartner/work-notes/note_missing/drop", headers=headers,
                           json={}).status_code == 404
        assert client.post("/api/pubpartner/work-notes", headers=headers,
                           json={"kind": "decided", "text": "", "save": True}).status_code == 400
        assert client.post("/api/pubpartner/work-notes/save", headers=headers,
                           json={"note_ids": "not-a-list"}).status_code == 400
        other = client.get("/api/pubpartner/work-notes", headers={"X-Client-Id": "someone"},
                           params={"project_id": "pubpartner"}).json()
        assert other["notes"] == []

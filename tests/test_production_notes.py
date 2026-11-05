"""Production notes and the PubCast profile, against the real routes and a real SQLite store in a throwaway folder.

Covers: permanent user IDs (made at setup, for crew, and for accounts that predate profiles), profile edits and
validation, adding crew (who may), sending to people / the whole production / yourself, To-beats-CC-beats-BCC,
BCC visible only to the sender, read / save / trash per person, spots (the mirror always), projects, replies,
attachments (stored, served only to the people on the note, limits enforced), and that nothing works unsigned.
"""
from __future__ import annotations

import io
import json
import sqlite3

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from modules import auth, userdb
from modules import production_notes as pn

SPOTS = {"spots": {"mirror": {"label": "Makeup mirror"}, "audio_console": {"label": "Audio console"}}}
PW = "Str0ng-Production-Pass!"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(userdb, "_DB_PATH", tmp_path / "users.db")
    userdb._sync_init_db()
    assert userdb._sync_create_owner_via_setup("josie", PW, "josie@example.com", "Josie")
    # an account made the old way, before profiles existed: it must get a profile without anyone doing anything
    conn = sqlite3.connect(tmp_path / "users.db")
    conn.execute("INSERT INTO users (username, hashed_password, role) VALUES ('oldtimer', ?, 'guest')", (auth.get_password_hash(PW),))
    conn.commit(); conn.close()
    spots = tmp_path / "note_spots.json"
    spots.write_text(json.dumps(SPOTS), encoding="utf-8")
    app = FastAPI()
    app.include_router(pn.create_production_notes_router(tmp_path / "data", spots))
    client = TestClient(app)

    def as_(username, role):
        return {"Authorization": "Bearer " + auth.create_access_token({"sub": username, "role": role})}

    owner = as_("josie", "owner")
    # Legacy local accounts remain usable; new installations admit independent visitors.
    for name, display in (("repete", "RePete"), ("pete", "Pete")):
        assert userdb._sync_create_member(name, PW, 'guest', display, f'{name}@example.com')
    people = {p["username"]: p for p in client.get("/api/production/people", headers=owner).json()["people"]}
    return client, as_, people, tmp_path


def test_profiles_have_permanent_ids_and_validate(env):
    client, as_, people, _ = env
    assert set(people) == {"josie", "oldtimer", "repete", "pete"}
    ids = {p["user_id"] for p in people.values()}
    assert len(ids) == 4 and all(i.startswith("u_") and len(i) == 22 for i in ids)
    me = client.get("/api/profile/me", headers=as_("josie", "owner")).json()
    assert me["email"] == "josie@example.com" and me["display_name"] == "Josie" and me["role"] == "owner"
    assert me["user_id"] == people["josie"]["user_id"]
    # editing keeps the ID
    r = client.patch("/api/profile/me", headers=as_("pete", "guest"), json={"display_name": "  Pete   B ", "email": "p@ex.co"})
    assert r.status_code == 200 and r.json()["display_name"] == "Pete B" and r.json()["user_id"] == people["pete"]["user_id"]
    assert client.patch("/api/profile/me", headers=as_("pete", "guest"), json={"email": "not an email"}).status_code == 400
    assert client.patch("/api/profile/me", headers=as_("pete", "guest"), json={"role": "owner"}).status_code == 400
    assert client.patch("/api/profile/me", headers=as_("pete", "guest"), json={"display_name": "x" * 81}).status_code == 400


def test_local_crew_creation_is_retired_without_changing_legacy_accounts(env):
    client, as_, _, _ = env
    body = {"username": "kay", "password": PW, "role": "guest"}
    assert client.post("/api/production/people", headers=as_("pete", "guest"), json=body).status_code == 403
    for payload in [body, dict(body, username='pete'), dict(body, role='owner'), dict(body, password='short')]:
        result = client.post('/api/production/people', headers=as_('josie', 'owner'), json=payload)
        assert result.status_code == 410 and 'own PubCast identity' in result.json()['detail']
    # nothing half-made by the failures above
    assert "kay" not in {p["username"] for p in client.get("/api/production/people", headers=as_("josie", "owner")).json()["people"]}


def test_password_change_needs_the_current_password(env):
    client, as_, _, _ = env
    h = as_("pete", "guest")
    assert client.post("/api/profile/password", headers=h, json={"current_password": "wrong", "new_password": "N3w-Password-Ok!"}).status_code == 403
    assert client.post("/api/profile/password", headers=h, json={"current_password": PW, "new_password": "weak"}).status_code == 400
    assert client.post("/api/profile/password", headers=h, json={"current_password": PW, "new_password": "N3w-Password-Ok!"}).status_code == 200
    assert auth.verify_password("N3w-Password-Ok!", userdb._sync_get_user("pete")["hashed_password"])


def test_nothing_without_signing_in(env):
    client, as_, people, _ = env
    assert client.get("/api/notes").status_code == 401
    assert client.get("/api/notes", headers={"X-Client-Id": "josie"}).status_code == 401      # the dev header is not enough
    assert client.get("/api/profile/me", headers=as_("nobody", "owner")).status_code == 403    # a token for no account


def test_send_read_save_trash_and_bcc_privacy(env):
    client, as_, people, _ = env
    josie, pete, repete = as_("josie", "owner"), as_("pete", "guest"), as_("repete", "guest")
    r = client.post("/api/notes", headers=pete, json={
        "subject": "Rehearsal 11/10", "body": "Running 45 minutes late.\nStart without me.", "project": "Episode 3",
        "to": [people["repete"]["user_id"]], "cc": [people["josie"]["user_id"], people["repete"]["user_id"]],
        "bcc": [people["oldtimer"]["user_id"]], "spots": ["audio_console"]})
    assert r.status_code == 201, r.text
    nid = r.json()["id"]
    assert r.json()["spots"] == ["mirror", "audio_console"] and r.json()["recipients"] == 3

    inbox = client.get("/api/notes", headers=repete).json()
    assert inbox["unread"] == 1 and inbox["notes"][0]["subject"] == "Rehearsal 11/10"
    n = inbox["notes"][0]
    assert n["from"]["display_name"] == "Pete" and n["kind"] == "to" and n["project"] == "Episode 3"
    assert n["spots"] == ["mirror", "audio_console"]

    full = client.get(f"/api/notes/{nid}", headers=repete).json()
    assert full["body"] == "Running 45 minutes late.\nStart without me."
    assert [p["display_name"] for p in full["to"]] == ["RePete"] and [p["display_name"] for p in full["cc"]] == ["Josie"]
    assert full["bcc"] == [] and full["unread"] is True                         # a recipient never sees BCC
    assert client.get(f"/api/notes/{nid}", headers=as_("oldtimer", "guest")).json()["you_were_bcc"] is True
    sent = client.get(f"/api/notes/{nid}", headers=pete).json()
    assert sent["is_sender"] and [p["user_id"] for p in sent["bcc"]] == [people["oldtimer"]["user_id"]]

    assert client.get(f"/api/notes/{nid}?mark_read=1", headers=repete).json()["unread"] is False
    assert client.get("/api/notes", headers=repete).json()["unread"] == 0
    assert client.get("/api/notes", headers=josie).json()["unread"] == 1           # reading is per person

    assert client.post(f"/api/notes/{nid}/save", headers=josie).json()["changed"]
    assert [x["id"] for x in client.get("/api/notes?box=saved", headers=josie).json()["notes"]] == [nid]
    assert client.get("/api/notes", headers=josie).json()["unread"] == 0           # saving counts as having seen it
    assert client.post(f"/api/notes/{nid}/trash", headers=josie).json()["changed"]
    assert client.get("/api/notes", headers=josie).json()["notes"] == []
    assert client.get(f"/api/notes/{nid}", headers=josie).status_code == 404      # gone for her...
    assert client.get(f"/api/notes/{nid}", headers=repete).status_code == 200     # ...not for anyone else
    assert [x["id"] for x in client.get("/api/notes?box=sent", headers=pete).json()["notes"]] == [nid]
    assert client.get(f"/api/notes/{nid}", headers=as_("nobody-else", "guest")).status_code == 403


def test_production_group_self_notes_replies_and_validation(env):
    client, as_, people, _ = env
    pete = as_("pete", "guest")
    r = client.post("/api/notes", headers=pete, json={"subject": "Call time 6 am", "to": ["@production"]})
    assert r.status_code == 201 and r.json()["recipients"] == 3                  # everyone but the sender
    assert client.get("/api/notes", headers=pete).json()["notes"] == []
    first = r.json()["id"]
    r = client.post("/api/notes", headers=pete, json={"subject": "Buy more coffee", "to": [people["pete"]["user_id"]]})
    assert r.status_code == 201
    assert [n["subject"] for n in client.get("/api/notes", headers=pete).json()["notes"]] == ["Buy more coffee"]
    r = client.post("/api/notes", headers=as_("repete", "guest"),
                    json={"subject": "Re: Call time 6 am", "to": [people["pete"]["user_id"]], "reply_to": first})
    assert r.status_code == 201
    reply = client.get(f"/api/notes/{r.json()['id']}", headers=pete).json()
    assert reply["reply_to"] == first and reply["thread_id"] == first
    bad = [
        {"to": [people["pete"]["user_id"]]},                                      # no subject
        {"subject": "x", "to": []},                                               # nobody
        {"subject": "x", "to": ["u_00000000000000000000"]},                       # not in the production
        {"subject": "x", "to": [people["josie"]["user_id"]], "spots": ["the moon"]},
        {"subject": "x" * 121, "to": [people["josie"]["user_id"]]},
        {"subject": "x", "to": [people["josie"]["user_id"]], "project": "p" * 61},
        {"subject": "x", "to": "everyone"},
    ]
    for body in bad:
        assert client.post("/api/notes", headers=pete, json=body).status_code == 400, body
    # replying to a note you cannot see
    assert client.post("/api/notes", headers=as_("oldtimer", "guest"),
                       json={"subject": "x", "to": [people["josie"]["user_id"]], "reply_to": first}).status_code == 201
    hidden = client.post("/api/notes", headers=pete, json={"subject": "private", "to": [people["pete"]["user_id"]]}).json()["id"]
    assert client.post("/api/notes", headers=as_("repete", "guest"),
                       json={"subject": "x", "to": [people["pete"]["user_id"]], "reply_to": hidden}).status_code == 404


def test_attachments_are_stored_served_privately_and_limited(env):
    client, as_, people, tmp = env
    pete, repete = as_("pete", "guest"), as_("repete", "guest")
    note = {"subject": "Blocking", "to": [people["repete"]["user_id"]]}
    pdf = b"%PDF-1.4 fake schedule\n" * 100
    r = client.post("/api/notes", headers=pete, data={"note": json.dumps(note)},
                    files=[("files", ("../../Schedule Nov 10.pdf", io.BytesIO(pdf), "application/pdf")),
                           ("files", ("sketch.jpg", io.BytesIO(b"\xff\xd8 jpeg"), "image/jpeg"))])
    assert r.status_code == 201, r.text
    nid = r.json()["id"]
    full = client.get(f"/api/notes/{nid}", headers=repete).json()
    assert [f["name"] for f in full["files"]] == ["Schedule Nov 10.pdf", "sketch.jpg"]   # path parts dropped
    got = client.get(full["files"][0]["url"], headers=repete)
    assert got.status_code == 200 and got.content == pdf
    assert got.headers["content-type"] == "application/octet-stream" and "attachment" in got.headers["content-disposition"]
    assert got.headers["x-content-type-options"] == "nosniff"
    assert client.get(full["files"][0]["url"], headers=as_("josie", "owner")).status_code == 404     # not on this note
    assert client.get(f"/api/notes/{nid}/files/f_00000000000000000000", headers=repete).status_code == 404
    # too big: refused, and nothing left behind
    before = sorted(p.name for p in (tmp / "data" / "notes").rglob("*") if p.is_file())
    big = io.BytesIO(b"\0" * (pn.FILE_BYTES_MAX + 1))
    r = client.post("/api/notes", headers=pete, data={"note": json.dumps(note)}, files=[("files", ("big.bin", big, "application/octet-stream"))])
    assert r.status_code == 413
    after = sorted(p.name for p in (tmp / "data" / "notes").rglob("*") if p.is_file())
    assert [p for p in after if p not in before and not p.endswith(("-wal", "-shm"))] == []
    assert len(client.get("/api/notes", headers=repete).json()["notes"]) == 1


def test_notes_survive_a_new_store_on_the_same_folder(env):
    client, as_, people, tmp = env
    r = client.post("/api/notes", headers=as_("pete", "guest"), json={"subject": "Still here?", "to": [people["josie"]["user_id"]]})
    assert r.status_code == 201
    app = FastAPI()                                                     # a restart: a fresh router on the same data
    app.include_router(pn.create_production_notes_router(tmp / "data", tmp / "note_spots.json"))
    again = TestClient(app).get("/api/notes", headers=as_("josie", "owner")).json()
    assert [n["subject"] for n in again["notes"]] == ["Still here?"]


def test_spot_catalog_always_has_the_mirror(env):
    client, as_, _, tmp = env
    cat = client.get("/api/notes/spots", headers=as_("pete", "guest")).json()
    assert cat["always"] == "mirror" and {s["id"] for s in cat["spots"]} == {"mirror", "audio_console"}


def test_the_store_closes_every_database_connection_it_opens(tmp_path):
    """sqlite3's `with connection:` never closes; a lingering handle keeps notes.db open (Windows: blocks moving it)."""
    import gc
    import warnings
    store = pn.NotesStore(tmp_path / "notes")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        store.create("u_sender", "subject", "body", [("u_a", "to")], [], None, [])
        with pytest.raises(sqlite3.IntegrityError):       # the same person twice: the write fails and rolls back
            store.create("u_sender", "subject", "body", [("u_a", "to"), ("u_a", "cc")], [], None, [])
        gc.collect()
    assert [str(w.message) for w in caught if "unclosed database" in str(w.message)] == []


def test_email_addresses_are_shown_only_to_their_owner_and_to_those_who_run_the_production(env):
    client, as_, people, _ = env
    # The owner (who adds the crew) sees every address.
    seen_by_owner = {p["username"]: p.get("email") for p in client.get("/api/production/people", headers=as_("josie", "owner")).json()["people"]}
    assert seen_by_owner["pete"] == "pete@example.com" and seen_by_owner["repete"] == "repete@example.com"
    # An ordinary member sees everyone's name and ID, but only their own address.
    seen_by_pete = client.get("/api/production/people", headers=as_("pete", "guest")).json()["people"]
    by_name = {p["username"]: p for p in seen_by_pete}
    assert set(by_name) == {"josie", "oldtimer", "repete", "pete"}
    assert by_name["pete"]["email"] == "pete@example.com"
    assert all("email" not in p for name, p in by_name.items() if name != "pete")
    # The address is not leaked anywhere else in what a member receives.
    assert "repete@example.com" not in client.get("/api/production/people", headers=as_("pete", "guest")).text
    # A moderator runs the production and sees all of them.
    seen_by_mod = {p["username"]: p.get("email") for p in client.get("/api/production/people", headers=as_("josie", "mod")).json()["people"]}
    assert seen_by_mod["repete"] == "repete@example.com"

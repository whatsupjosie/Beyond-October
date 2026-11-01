"""Host control (modules/host_control.py): possession, release, drive, timeout, profile, privileges, gifts, tracker log.

Run against the real governance engine on a throwaway folder and a recording stand-in for the hub, so what is checked is
what the host would send and to whom: the private notice must go to the target only.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.governance import GovernanceEngine
from modules.host_control import DETENTION_ROOM, create_host_control_router

NOTICE = "TEST NOTICE: the host is controlling your avatar."          # test wording only, never Josie's


class FakeHub:
    def __init__(self):
        self.private, self.public, self.connected = [], [], True

    async def send_private_event(self, user_ids, event):
        self.private.append((set(user_ids), event))
        return len(user_ids) if self.connected else 0           # 0 = no verified socket for them, as the real hub reports

    async def broadcast_system_event(self, event):
        self.public.append(event)


def tok(user, role="owner"):
    return {"Authorization": "Bearer " + create_access_token({"sub": user, "role": role})}


@pytest.fixture()
def rig(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    gov, hub = GovernanceEngine(tmp_path), FakeHub()
    app = FastAPI()
    router = create_host_control_router(gov, hub, tmp_path)
    app.include_router(router)
    with TestClient(app) as client:
        client.gov, client.hub, client.dir, client.host = gov, hub, tmp_path, router.host
        yield client


def set_notices(rig, **texts):
    d = rig.dir / "host_control"; d.mkdir(exist_ok=True)
    (d / "messages.json").write_text(json.dumps(texts), encoding="utf-8")


# ── permission: the server decides, not the panel ───────────────────────────────

@pytest.mark.parametrize("method, path, body", [
    ("post", "/api/host/possess", {"user_id": "mira"}), ("post", "/api/host/release", {"user_id": "mira"}),
    ("post", "/api/host/timeout", {"user_id": "mira"}), ("post", "/api/host/drive", {"user_id": "mira", "pos": [1, 2]}),
    ("get", "/api/host/people/mira", None), ("patch", "/api/host/people/mira", {"title": "x"}),
    ("put", "/api/host/people/mira/privileges/control_room", {"value": True}),
    ("post", "/api/host/people/mira/gifts", {"kind": "accessory", "item": "hat"}), ("get", "/api/host/people/mira/log", None),
    ("get", "/api/host/state", None), ("post", "/api/host/end-timeout", {"user_id": "mira"}),
])
def test_a_viewer_is_refused_everywhere(rig, method, path, body):
    r = getattr(rig, method)(path, headers=tok("someone", "viewer"), **({"json": body} if body is not None else {}))
    assert r.status_code == 403
    assert rig.hub.private == [] and rig.hub.public == []


# ── possession ──────────────────────────────────────────────────────────────────

def test_possession_will_not_send_words_nobody_approved(rig):
    r = rig.post("/api/host/possess", headers=tok("josie"), json={"user_id": "mira"})
    assert r.status_code == 409 and r.json()["detail"] == "possession_notice_not_set"
    assert rig.gov.is_frozen("mira")[0] is False and rig.hub.private == []


def test_possession_notice_goes_to_the_target_only_and_everyone_sees_the_mark(rig):
    set_notices(rig, possession_notice=NOTICE)
    r = rig.post("/api/host/possess", headers=tok("josie"), json={"user_id": "mira", "reason": "testing", "duration_seconds": 60})
    assert r.status_code == 200 and r.json()["notice_delivered"] is True
    assert rig.gov.is_frozen("mira")[0] is True
    (to, ev), = rig.hub.private
    assert to == {"mira"} and ev["type"] == "host_notice" and ev["text"] == NOTICE         # exactly the configured wording
    assert [e["type"] for e in rig.hub.public] == ["avatar_possessed"]
    assert NOTICE not in json.dumps(rig.hub.public)                                         # the private words never go public
    assert rig.host.state()["possessed"]["mira"]["by"] == "josie"


def test_one_possession_at_a_time_and_release_returns_control(rig):
    set_notices(rig, possession_notice=NOTICE)
    h = tok("josie")
    assert rig.post("/api/host/possess", headers=h, json={"user_id": "mira"}).status_code == 200
    assert rig.post("/api/host/possess", headers=h, json={"user_id": "mira"}).status_code == 409
    assert rig.post("/api/host/release", headers=h, json={"user_id": "mira"}).status_code == 200
    assert rig.gov.is_frozen("mira")[0] is False
    assert rig.hub.private[-1][1] == {"type": "host_release"} and rig.hub.private[-1][0] == {"mira"}
    assert rig.hub.public[-1]["type"] == "avatar_released"
    assert rig.post("/api/host/release", headers=h, json={"user_id": "mira"}).status_code == 404


def test_only_the_person_in_control_can_drive_and_the_move_goes_to_the_target(rig):
    set_notices(rig, possession_notice=NOTICE)
    rig.post("/api/host/possess", headers=tok("josie"), json={"user_id": "mira"})
    assert rig.post("/api/host/drive", headers=tok("other-admin", "admin"), json={"user_id": "mira", "pos": [10, 20]}).status_code == 409
    assert rig.post("/api/host/drive", headers=tok("josie"), json={"user_id": "mira", "pos": [1, "x"]}).status_code == 400
    assert rig.post("/api/host/drive", headers=tok("josie"), json={"user_id": "nobody", "pos": [1, 2]}).status_code == 409
    n = len(rig.hub.private)
    assert rig.post("/api/host/drive", headers=tok("josie"), json={"user_id": "mira", "pos": [10, 20.5]}).status_code == 200
    assert rig.hub.private[n:] == [({"mira"}, {"type": "host_drive", "pos": [10.0, 20.5]})]


def test_possession_ends_by_itself(rig):
    set_notices(rig, possession_notice=NOTICE)

    async def run():
        host = rig.host
        await host.possess("josie", "mira", "", 1)
        assert "mira" in host.possessed
        await asyncio.sleep(1.4)
        return "mira" in host.possessed
    assert asyncio.run(run()) is False
    assert rig.gov.is_frozen("mira")[0] is False
    assert rig.hub.public[-1]["payload"]["automatic"] is True


@pytest.mark.parametrize("bad", [{}, {"user_id": "../x"}, {"user_id": "a" * 200}, {"user_id": "mira", "duration_seconds": 0},
                                 {"user_id": "mira", "duration_seconds": 99999}, {"user_id": "mira", "duration_seconds": True},
                                 {"user_id": "mira", "reason": "x" * 600}])
def test_bad_possession_requests_are_refused_and_nothing_happens(rig, bad):
    set_notices(rig, possession_notice=NOTICE)
    assert rig.post("/api/host/possess", headers=tok("josie"), json=bad).status_code == 400
    assert rig.hub.private == [] and rig.hub.public == [] and rig.gov.is_frozen("mira")[0] is False


# ── timeout ─────────────────────────────────────────────────────────────────────

def test_timeout_teleports_to_the_disciplinary_side_with_recording_on(rig):
    r = rig.post("/api/host/timeout", headers=tok("josie"), json={"user_id": "mira", "duration_seconds": 120, "reason": "glitching?"})
    assert r.status_code == 200 and r.json()["notice_sent"] is False                        # no wording set: none invented
    (to, ev), = rig.hub.private
    assert to == {"mira"} and ev["type"] == "host_teleport" and ev["room"] == DETENTION_ROOM and ev["recording"] is True
    assert "text" not in ev
    set_notices(rig, timeout_notice="TEST TIMEOUT WORDING")
    rig.post("/api/host/timeout", headers=tok("josie"), json={"user_id": "mira"})
    assert rig.hub.private[-1][1]["text"] == "TEST TIMEOUT WORDING"


# ── profile, privileges, gifts ──────────────────────────────────────────────────

def test_title_and_position_change_but_the_name_never_does(rig):
    h = tok("josie")
    assert rig.get("/api/host/people/mira", headers=h).json()["person"]["name"] == "mira"
    r = rig.patch("/api/host/people/mira", headers=h, json={"title": "Stage manager", "position": "Floor"})
    assert r.status_code == 200 and r.json()["person"]["title"] == "Stage manager"
    assert rig.patch("/api/host/people/mira", headers=h, json={"name": "Someone Else"}).status_code == 400
    assert rig.patch("/api/host/people/mira", headers=h, json={}).status_code == 400
    assert rig.patch("/api/host/people/mira", headers=h, json={"title": "x" * 200}).status_code == 400
    assert rig.get("/api/host/people/mira", headers=h).json()["person"]["name"] == "mira"


def test_privileges_and_gifts_are_granted_revoked_and_audited(rig):
    h = tok("josie")
    assert rig.put("/api/host/people/mira/privileges/control_room", headers=h, json={"value": True}).json()["person"]["privileges"]["control_room"] is True
    assert rig.put("/api/host/people/mira/privileges/control_room", headers=h, json={"value": False}).json()["person"]["privileges"]["control_room"] is False
    assert rig.put("/api/host/people/mira/privileges/root", headers=h, json={"value": True}).status_code == 404
    assert rig.put("/api/host/people/mira/privileges/control_room", headers=h, json={"value": "yes"}).status_code == 400
    r = rig.post("/api/host/people/mira/gifts", headers=h, json={"kind": "control_room_access"})
    assert r.status_code == 201 and r.json()["person"]["privileges"]["control_room"] is True
    r = rig.post("/api/host/people/mira/gifts", headers=h, json={"kind": "accessory", "item": "gold-cuffs"})
    assert [g["kind"] for g in r.json()["person"]["gifts"]] == ["control_room_access", "accessory"]
    assert rig.post("/api/host/people/mira/gifts", headers=h, json={"kind": "accessory"}).status_code == 400
    assert rig.post("/api/host/people/mira/gifts", headers=h, json={"kind": "pony"}).status_code == 400
    actions = [e["action"] for e in rig.gov.get_audit_log(50)]
    for a in ("PRIVILEGE_GRANT", "PRIVILEGE_REVOKE", "GIFT"):
        assert a in actions


def test_profile_is_kept_on_disk_and_reads_back_after_a_restart(rig, tmp_path):
    rig.patch("/api/host/people/mira", headers=tok("josie"), json={"title": "Lead", "tracked": True})
    fresh = TestClient(_app_on(tmp_path))
    assert fresh.get("/api/host/people/mira", headers=tok("josie")).json()["person"]["title"] == "Lead"


def _app_on(path):
    app = FastAPI(); app.include_router(create_host_control_router(GovernanceEngine(path), FakeHub(), path)); return app


# ── the tracker log ─────────────────────────────────────────────────────────────

def test_tracked_people_get_a_text_record_and_untracked_people_do_not(rig):
    set_notices(rig, possession_notice=NOTICE)
    h = tok("josie")
    rig.post("/api/host/possess", headers=h, json={"user_id": "plain"})                       # not tracked: no log
    rig.post("/api/host/release", headers=h, json={"user_id": "plain"})
    assert rig.get("/api/host/people/plain/log", headers=h).json()["log"] == ""
    rig.patch("/api/host/people/mira", headers=h, json={"tracked": True})
    rig.post("/api/host/possess", headers=h, json={"user_id": "mira"})
    rig.post("/api/host/release", headers=h, json={"user_id": "mira"})
    rig.post("/api/host/timeout", headers=h, json={"user_id": "mira"})
    log = rig.get("/api/host/people/mira/log", headers=h).json()["log"]
    assert log.startswith("# mira, ") and log.count("\n- ") == 4
    for word in ("profile_edit", "possessed", "released", "timeout"):
        assert word in log
    assert NOTICE not in log
    assert rig.get("/api/host/people/mira/log?date=yesterday", headers=h).status_code == 400
    assert rig.get("/api/host/people/..%2Fx/log", headers=h).status_code in (400, 404)


# ── corners that were cut the first time ───────────────────────────────────────

def test_a_moderator_can_read_but_not_take_control(rig):
    set_notices(rig, possession_notice=NOTICE)
    m = tok("mod-person", "mod")
    assert rig.get("/api/host/state", headers=m).status_code == 200
    assert rig.get("/api/host/people/mira", headers=m).status_code == 200
    for path, body in (("/api/host/possess", {"user_id": "mira"}), ("/api/host/timeout", {"user_id": "mira"}),
                       ("/api/host/people/mira/gifts", {"kind": "control_room_access"})):
        assert rig.post(path, headers=m, json=body).status_code == 403
    assert rig.hub.private == [] and rig.gov.is_frozen("mira")[0] is False


def test_possession_is_undone_when_the_person_never_got_the_notice(rig):
    set_notices(rig, possession_notice=NOTICE)
    rig.hub.connected = False
    r = rig.post("/api/host/possess", headers=tok("josie"), json={"user_id": "mira"})
    assert r.status_code == 409 and r.json()["detail"] == "target_not_connected"
    assert rig.gov.is_frozen("mira")[0] is False and rig.host.possessed == {} and rig.hub.public == []
    assert "POSSESS_UNDONE" in [e["action"] for e in rig.gov.get_audit_log(20)]


def test_someone_already_frozen_is_not_taken_over_silently(rig):
    set_notices(rig, possession_notice=NOTICE)
    rig.gov.freeze_avatar("mira", "someone-else", "other reasons")
    r = rig.post("/api/host/possess", headers=tok("josie"), json={"user_id": "mira"})
    assert r.status_code == 409 and r.json()["detail"] == "already_frozen"
    assert rig.gov.is_frozen("mira")[1].frozen_by == "someone-else" and rig.hub.private == []


def test_letter_case_does_not_make_two_people(rig):
    set_notices(rig, possession_notice=NOTICE)
    h = tok("josie")
    assert rig.post("/api/host/possess", headers=h, json={"user_id": "Mira"}).status_code == 200
    assert rig.post("/api/host/possess", headers=h, json={"user_id": "mira"}).status_code == 409
    rig.patch("/api/host/people/Mira", headers=h, json={"title": "Lead"})
    assert rig.get("/api/host/people/MIRA", headers=h).json()["person"]["title"] == "Lead"
    assert rig.post("/api/host/release", headers=h, json={"user_id": "MIRA"}).status_code == 200


def test_no_audit_entry_means_no_action(rig, monkeypatch):
    set_notices(rig, possession_notice=NOTICE)
    def broken(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(rig.gov, "_audit", broken)
    for path in ("/api/host/possess", "/api/host/timeout"):
        r = rig.post(path, headers=tok("josie"), json={"user_id": "mira"})
        assert r.status_code == 503 and r.json()["detail"] == "audit_unavailable"
    assert rig.hub.private == [] and rig.hub.public == [] and rig.gov.is_frozen("mira")[0] is False
    assert rig.patch("/api/host/people/mira", headers=tok("josie"), json={"title": "x"}).status_code == 503
    assert rig.get("/api/host/people/mira", headers=tok("josie")).json()["person"]["title"] == ""


def test_a_timeout_can_be_ended_and_ends_by_itself(rig):
    h = tok("josie")
    rig.post("/api/host/timeout", headers=h, json={"user_id": "mira", "duration_seconds": 60})
    assert "mira" in rig.host.timeouts
    assert rig.post("/api/host/end-timeout", headers=h, json={"user_id": "mira"}).status_code == 200
    assert rig.hub.private[-1] == ({"mira"}, {"type": "host_timeout_end", "room": DETENTION_ROOM})
    assert rig.post("/api/host/end-timeout", headers=h, json={"user_id": "mira"}).status_code == 404

    async def run():
        await rig.host.timeout("josie", "kay", DETENTION_ROOM, 1, "")
        await asyncio.sleep(1.4)
        return "kay" in rig.host.timeouts
    assert asyncio.run(run()) is False
    assert rig.hub.private[-1][1]["type"] == "host_timeout_end"


def test_a_possession_and_a_timeout_keep_separate_timers(rig):
    set_notices(rig, possession_notice=NOTICE)

    async def run():
        await rig.host.possess("josie", "mira", "", 5)
        await rig.host.timeout("josie", "mira", DETENTION_ROOM, 1, "")
        await asyncio.sleep(1.4)
        still = ("mira" in rig.host.possessed, "mira" in rig.host.timeouts)
        await rig.host.release("josie", "mira")
        return still
    assert asyncio.run(run()) == (True, False)               # the timeout ended; the possession was not cancelled by it


def test_two_possessions_at_once_cannot_both_win(rig):
    set_notices(rig, possession_notice=NOTICE)

    async def run():
        results = await asyncio.gather(rig.host.possess("a", "mira", "", 30), rig.host.possess("b", "MIRA", "", 30), return_exceptions=True)
        await rig.host.release("a", "mira")
        return results
    results = asyncio.run(run())
    assert sum(isinstance(r, dict) for r in results) == 1 and sum(getattr(r, "status_code", 0) == 409 for r in results) == 1


# ── rounds of attack: nothing the panel or an attacker sends may cause a server error ──────────

def test_odd_input_never_causes_a_server_error(rig):
    import random
    set_notices(rig, possession_notice=NOTICE, timeout_notice="T")
    rnd = random.Random(20261029)
    ids = ["mira", "Mira", "MIRA", "", " ", "a" * 121, "../etc", "mira/../x", "mi ra", "mira\n", "élève", "‮", "x" * 5000, "a.b@c-d_e", "0", "null"]
    junk = [None, True, False, 0, -1, 1e308, 10 ** 30, "", "x" * 700, [], {}, [1], [1, 2], ["a", "b"], [None, None], {"a": 1}, "\u0000"]
    h = tok("josie")
    for _ in range(300):
        uid = rnd.choice(ids)
        body = {"user_id": uid}
        for key in rnd.sample(["reason", "duration_seconds", "pos", "room", "title", "position", "notes", "tracked", "name", "kind", "item", "value", "date"], rnd.randint(0, 5)):
            body[key] = rnd.choice(junk)
        for method, path in (("post", "/api/host/possess"), ("post", "/api/host/release"), ("post", "/api/host/drive"), ("post", "/api/host/timeout"),
                             ("post", "/api/host/end-timeout"), ("patch", "/api/host/people/mira"), ("put", "/api/host/people/mira/privileges/control_room"),
                             ("post", "/api/host/people/mira/gifts")):
            r = getattr(rig, method)(path, headers=h, json=body)
            assert r.status_code < 500, (method, path, body, r.status_code, r.text[:200])
    for raw in (b"", b"not json", b"[1,2]", b'"s"', b"\xff\xfe"):
        for path in ("/api/host/possess", "/api/host/timeout", "/api/host/release"):
            r = rig.post(path, headers={**h, "Content-Type": "application/json"}, content=raw)
            assert r.status_code == 400, (path, raw, r.status_code)
    for raw in (b'{"user_id": "kay", "duration_seconds": Infinity}', b'{"user_id": "kay", "duration_seconds": NaN}'):
        for path in ("/api/host/possess", "/api/host/timeout"):
            assert rig.post(path, headers={**h, "Content-Type": "application/json"}, content=raw).status_code == 400, (path, raw)
    rig.post("/api/host/possess", headers=h, json={"user_id": "kay"})
    for raw in (b'{"user_id": "kay", "pos": [NaN, 1]}', b'{"user_id": "kay", "pos": [Infinity, 1]}'):
        assert rig.post("/api/host/drive", headers={**h, "Content-Type": "application/json"}, content=raw).status_code == 400, raw
    for path in ("/api/host/people/%00", "/api/host/people/" + "a" * 500, "/api/host/people/%2e%2e", "/api/host/people/mira/log?date=2026-13-45",
                 "/api/host/people/mira/log?date=" + "9" * 300):
        assert rig.get(path, headers=h).status_code < 500, path
    # whatever was thrown at it, nothing escaped the folders it owns
    outside = [p for p in rig.dir.rglob("*") if p.is_file() and not str(p.relative_to(rig.dir)).startswith(("people", "people_log", "host_control", "governance"))
               and p.suffix in (".json", ".md")]
    assert outside == [], outside


def test_the_walker_channel_counts_as_delivery(tmp_path, monkeypatch):
    """The hub reaches nobody here (as for the real walker socket); the extra sender does, so possession proceeds."""
    from modules.pubworld_private import PubWorldPrivate
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")

    class Sock:
        def __init__(self): self.sent = []
        async def send_text(self, text): self.sent.append(json.loads(text))

    gov, hub, reg, sock = GovernanceEngine(tmp_path), FakeHub(), PubWorldPrivate(), Sock()
    hub.connected = False
    reg.register("mira", sock)
    app = FastAPI(); app.include_router(create_host_control_router(gov, hub, tmp_path, senders=[reg.send]))
    d = tmp_path / "host_control"; d.mkdir(); (d / "messages.json").write_text(json.dumps({"possession_notice": NOTICE}))
    with TestClient(app) as c:
        assert c.post("/api/host/possess", headers=tok("josie"), json={"user_id": "mira"}).status_code == 200
        assert sock.sent[0]["type"] == "host_notice" and sock.sent[0]["text"] == NOTICE
        assert c.post("/api/host/possess", headers=tok("josie"), json={"user_id": "kay"}).status_code == 409   # kay has no socket anywhere


def test_the_roster_joins_what_walkers_say_with_what_the_host_knows(tmp_path, monkeypatch):
    from modules.pubworld_private import PubWorldPrivate
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")

    class S:
        async def send_text(self, t): pass
    reg = PubWorldPrivate(); reg.register("mira", S()); reg.update_presence("mira", {"room": "green_room", "pos": [1, 2], "fps": 30})
    gov, hub = GovernanceEngine(tmp_path), FakeHub()
    router = create_host_control_router(gov, hub, tmp_path, senders=[reg.send], roster=reg.roster)
    reg.on_room_change = router.host.on_room_change
    app = FastAPI(); app.include_router(router)
    d = tmp_path / "host_control"; d.mkdir(); (d / "messages.json").write_text(json.dumps({"possession_notice": NOTICE}))
    with TestClient(app) as c:
        h = tok("josie")
        assert c.get("/api/host/roster", headers=tok("v", "viewer")).status_code == 403
        assert c.get("/api/host/roster", headers=tok("m", "mod")).status_code == 200
        c.patch("/api/host/people/mira", headers=h, json={"title": "Lead", "position": "Floor", "tracked": True})
        (p,) = c.get("/api/host/roster", headers=h).json()["people"]
        assert p["user_id"] == "mira" and p["name"] == "mira" and p["title"] == "Lead" and p["position"] == "Floor" and p["tracked"] is True and p["room"] == "green_room"
        assert p["possessed"] is None and p["timeout"] is None
        c.post("/api/host/possess", headers=h, json={"user_id": "mira"})
        assert c.get("/api/host/roster", headers=h).json()["people"][0]["possessed"]["by"] == "josie"
        reg.update_presence("mira", {"room": "lobby"})                                          # tracked people get a line when they change room
        log = c.get("/api/host/people/mira/log", headers=h).json()["log"]
        assert "moved: green_room to lobby" in log
        assert c.get("/api/host/roster", headers=h).json()["people"][0]["room"] == "lobby"


def test_the_ban_list_shows_who_is_out_and_only_to_those_who_may_see_it(rig):
    from modules.governance import BanType
    assert rig.get("/api/host/bans", headers=tok("v", "viewer")).status_code == 403
    assert rig.get("/api/host/bans", headers=tok("m", "mod")).json()["bans"] == []
    rig.gov.ban_user("bo", "TEST REASON", "josie", BanType.PERMANENT)
    rig.gov.ban_user("cy", "later", "josie", BanType.SESSION)
    rig.gov.ban_user("di", "short", "josie", BanType.TEMPORARY, duration_hours=0.0001)       # runs out at once
    import time as _t; _t.sleep(0.5)
    bans = rig.get("/api/host/bans", headers=tok("m", "mod")).json()["bans"]
    assert [(b["user_id"], b["kind"], b["reason"], b["by"]) for b in bans] == [("bo", "permanent", "TEST REASON", "josie"), ("cy", "session", "later", "josie")]
    rig.gov.unban_user("bo", "josie")
    assert [b["user_id"] for b in rig.get("/api/host/bans", headers=tok("m", "mod")).json()["bans"]] == ["cy"]


def test_a_new_page_is_told_only_what_is_still_running(rig):
    set_notices(rig, possession_notice=NOTICE, timeout_notice="TEST TIMEOUT")
    host = rig.host
    assert host.pending_for("mira") == []
    asyncio.run(host.timeout("josie", "mira", DETENTION_ROOM, 60, "x"))
    (ev,) = host.pending_for("MIRA")                                                         # any letter case
    assert ev["type"] == "host_teleport" and ev["room"] == DETENTION_ROOM and ev["text"] == "TEST TIMEOUT" and ev["recording"] is True
    host.timeouts["mira"]["until"] = 1                                                       # long over
    assert host.pending_for("mira") == []
    assert host.pending_for("someone-else") == []

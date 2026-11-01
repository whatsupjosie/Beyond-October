"""Private delivery to walker sockets (modules/pubworld_private.py) and its wiring into host control."""
from __future__ import annotations

import asyncio
import json

from modules.pubworld_private import PubWorldPrivate


class Sock:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    async def send_text(self, text):
        if self.fail:
            raise RuntimeError("closed")
        self.sent.append(json.loads(text))


def run(coro):
    return asyncio.run(coro)


def test_only_the_named_person_gets_it_and_case_does_not_matter():
    reg, mira, kay = PubWorldPrivate(), Sock(), Sock()
    reg.register("Mira", mira); reg.register("kay", kay)
    assert run(reg.send({"MIRA"}, {"type": "host_notice"})) == 1
    assert mira.sent == [{"type": "host_notice"}] and kay.sent == []


def test_every_verified_socket_of_the_person_gets_it_once_and_strangers_none():
    reg, a, b = PubWorldPrivate(), Sock(), Sock()
    reg.register("mira", a); reg.register("mira", b)
    assert run(reg.send({"mira", "nobody"}, {"type": "x"})) == 2
    assert run(reg.send({"stranger"}, {"type": "x"})) == 0 and len(a.sent) == 1 and len(b.sent) == 1


def test_unregister_stops_delivery_and_a_dead_socket_is_dropped_not_fatal():
    reg, live, dead = PubWorldPrivate(), Sock(), Sock(fail=True)
    reg.register("mira", live); reg.register("mira", dead)
    assert run(reg.send({"mira"}, {"type": "x"})) == 1 and reg.connected("mira") == 1
    reg.unregister(live)
    assert reg.connected("mira") == 0 and run(reg.send({"mira"}, {"type": "x"})) == 0


def test_bad_ids_are_ignored():
    reg, s = PubWorldPrivate(), Sock()
    for bad in ("", "   ", None, 5):
        reg.register(bad, s)
    assert reg.connected("") == 0 and run(reg.send(["", None, 5], {"type": "x"})) == 0


# ── the roster: who is where, from verified walkers only ─────────────────────────

def test_only_a_verified_socket_appears_on_the_roster_with_cleaned_values():
    reg, s = PubWorldPrivate(), Sock()
    reg.update_presence("ghost", {"room": "lobby"}, now=100)                                    # never registered: ignored
    assert reg.roster(now=100) == []
    reg.register("Mira", s)
    reg.update_presence("Mira", {"room": "green_room", "view": "main", "pos": [10.5, 20], "char": "pete", "fps": 59.9, "meshes": 3, "bones": 67, "tris": 54000}, now=100)
    (e,) = reg.roster(now=101)
    assert e["user_id"] == "Mira" and e["room"] == "green_room" and e["pos"] == [10.5, 20.0] and e["fps"] == 59.9 and e["bones"] == 67 and e["age"] == 1.0
    reg.update_presence("mira", {"room": "x" * 500, "pos": [float("nan"), 1], "fps": -5, "tris": "many", "char": 7}, now=102)
    (e,) = reg.roster(now=102)
    assert len(e["room"]) == 80 and e["pos"] is None and e["fps"] is None and e["tris"] is None and e["char"] == "7"      # junk is dropped, never stored
    reg.update_presence("mira", {"pos": [1e9, 0]}, now=103); assert reg.roster(now=103)[0]["pos"] is None
    reg.update_presence("mira", "not a dict" if False else {}, now=104)


def test_the_roster_forgets_people_who_went_quiet_or_left_and_keeps_the_hosts_own_timing():
    reg, a, b = PubWorldPrivate(), Sock(), Sock()
    reg.register("mira", a); reg.register("mira", b)
    reg.update_presence("mira", {"room": "lobby"}, now=100); reg.set_rtt("mira", 42.46)
    assert reg.roster(now=100)[0]["rtt_ms"] == 42.5
    reg.update_presence("mira", {"room": "lobby"}, now=101); assert reg.roster(now=101)[0]["rtt_ms"] == 42.5          # a new report keeps the host's measurement
    assert reg.roster(now=130) == []                                                                                    # quiet for too long: off the roster
    reg.update_presence("mira", {"room": "lobby"}, now=200)
    reg.unregister(a); assert len(reg.roster(now=200)) == 1                                                             # one tab closed, still here
    reg.unregister(b); assert reg.roster(now=200) == []                                                                 # the last one closed
    for bad in (float("nan"), -1, "x", None, True): reg.set_rtt("mira", bad)                                            # no entry, nothing happens
    reg.register("kay", Sock()); reg.update_presence("kay", {}, now=1); reg.set_rtt("kay", float("inf")); assert reg.roster(now=1)[0]["rtt_ms"] is None


def test_a_change_of_room_is_announced_once_and_a_failing_listener_cannot_break_anything():
    reg, seen = PubWorldPrivate(), []
    reg.register("mira", Sock()); reg.on_room_change = lambda p, left, entered: seen.append((p, left, entered))
    reg.update_presence("mira", {"room": "lobby"}, now=1); reg.update_presence("mira", {"room": "lobby"}, now=2); reg.update_presence("mira", {"room": "green_room"}, now=3)
    assert seen == [("mira", "lobby", "green_room")]
    reg.on_room_change = lambda *a: 1 / 0
    reg.update_presence("mira", {"room": "bar"}, now=4); assert reg.roster(now=4)[0]["room"] == "bar"

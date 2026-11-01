"""Everything you can save in PubCast is still there after you quit and start it again.

This runs run_reach.py on one data folder and signs in as the owner. Through the real host it saves one of each kind:

- a 2i document (two revisions)
- a Foresight workspace file
- a PubPartner session and turn
- an archived conversation with messages
- a chat room message
- an avatar in the library
- a new PubPartner cartridge wearing that avatar
- Bella Faux Pas progress
- the Counter layout

Then it quits PubCast, starts it again on the same folder, and reads every one back. It also checks that the canonical
Alex vessel is untouched. The browser halves of these saves are covered in their own tests (studio progress, Counter
layout, cartridges, file workspace); this is the one place that proves all the stores together survive one restart.
"""
from __future__ import annotations

import base64
import os
import secrets
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

from modules.avatar_imports import INCH_M, measure_glb

ROOT = Path(__file__).resolve().parents[1]
MANNEQUIN = ROOT / "static" / "world" / "test_avatars" / "Xbot.glb"
ALEX_VESSEL = ROOT / "data" / "pubpartner" / "vessels" / "alex.pubpartner"
ALEX_BLOB = "96fa66a728d07d5ff43b0d3d7fc17a466765cec1"


def _blob(path: Path) -> str:
    return subprocess.run(["git", "hash-object", str(path)], capture_output=True, text=True, check=True).stdout.strip()


class Reach:
    def __init__(self, data: Path):
        self.data = data
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0)); self.port = s.getsockname()[1]
        self.base = f"http://127.0.0.1:{self.port}"

    def start(self):
        env = {k: v for k, v in os.environ.items() if k not in ("PUBCAST_ENFORCE_AUTH", "PUBCAST_JWT_SECRET", "PUBCAST_DATA_DIR")}
        self.log = open(self.data / "reach.log", "a", encoding="utf-8")
        self.proc = subprocess.Popen([sys.executable, "run_reach.py", "--port", str(self.port), "--data-dir", str(self.data),
                                      "--no-browser", "--no-legacy-2i"], cwd=str(ROOT), env=env, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + 120
        while time.time() < deadline:
            assert self.proc.poll() is None, "run_reach.py exited during startup"
            try:
                if httpx.get(self.base + "/health", timeout=0.5).status_code == 200:
                    return
            except httpx.RequestError:
                pass
            time.sleep(0.25)
        raise AssertionError("PubCast did not start")

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(20)
        except subprocess.TimeoutExpired:
            self.proc.kill(); self.proc.wait(5)
        self.log.close()


def _ok(r, *codes):
    assert r.status_code in (codes or (200, 201)), f"{r.request.method} {r.request.url.path}: {r.status_code} {r.text[:400]}"
    return r.json()


def test_every_kind_of_save_survives_a_quit_and_restart(tmp_path):
    assert _blob(ALEX_VESSEL) == ALEX_BLOB
    reach = Reach(tmp_path)
    reach.start()
    try:
        user, password = "josie-check", secrets.token_urlsafe(20)
        token = _ok(httpx.post(reach.base + "/api/auth/setup", json={"username": user, "password": password, "confirm_password": password}, timeout=10))["access_token"]
        c = httpx.Client(base_url=reach.base, headers={"Authorization": "Bearer " + token}, timeout=60)

        # 2i: a manuscript, saved twice
        doc = {"title": "Chapter One", "state": {"committed": ["It was the night the lantern went out."], "buffer": ["Draft line"], "pool": []},
               "expected_revision": 0}
        assert _ok(c.put("/api/writers-room/documents/chapter-one", json=doc))["revision"] == 1
        doc["state"]["committed"].append("Nobody noticed until morning.")
        doc["expected_revision"] = 1
        assert _ok(c.put("/api/writers-room/documents/chapter-one", json=doc))["revision"] == 2

        # Foresight: a workspace file
        text = "print('hello from the workspace')\n".encode()
        _ok(c.post("/api/foresight/workspace/file", json={"path": "Scripts/hello.py", "data": base64.b64encode(text).decode()}))

        # PubPartner: a session and a turn (echo provider: no model needed)
        _ok(c.post("/api/pubpartner/sessions", json={"session_id": "restart_check", "friend": "alex", "provider": "echo"}))
        _ok(c.post("/api/pubpartner/turns", json={"session_id": "restart_check", "message": "Remember this line exactly.", "friend": "alex", "provider": "echo"}))
        turns_before = _ok(c.get("/api/pubpartner/sessions/restart_check/turns"))

        # an archived conversation with two messages
        conv = _ok(c.post("/api/conversations", json={"title": "Pilot notes", "discussion_type": "project"}))["conversation_id"]
        _ok(c.post(f"/api/conversations/{conv}/messages", json={"speaker": "josie", "exact_text": "The pilot opens in the dressing room."}))
        _ok(c.post(f"/api/conversations/{conv}/messages", json={"speaker": "pete", "exact_text": "Then the green room."}))

        # chat: a message in the first room this owner can use
        room = _ok(c.get("/api/chat/rooms"))["rooms"][0]
        room_id = room["room_id"] if isinstance(room, dict) else room
        _ok(c.post(f"/api/chat/rooms/{room_id}/send", json={"text": "Saved before the restart", "client_message_id": str(uuid.uuid4())}))

        # an avatar, and a new PubPartner cartridge wearing it
        data = MANNEQUIN.read_bytes()
        avatar = _ok(c.post("/api/avatars/imports", params={"name": "Test mannequin", "height_in": round(measure_glb(data)["height_m"] / INCH_M, 2)},
                            content=data, headers={"Content-Type": "model/gltf-binary"}))["avatar"]["id"]
        _ok(c.post("/api/pubpartner/cartridges", json={"name": "Marlowe Finch", "summary": "A night-shift radio host.", "avatar_id": avatar}))

        # Bella Faux Pas progress and the Counter layout
        progress = {"room": "green_room", "view": "main", "pos": [800.0, 590.0], "char": "repeat", "avatars": {"repeat": avatar}, "hologram": True,
                    "tune": {"green_room/main": {"mult": 1.25}}, "cans": {}}
        _ok(c.put("/api/studio/progress", json={"progress": progress}))
        layout = {"v": 3, "theme": "tigereye", "inactivePolicy": "reduced", "selected": None,
                  "trays": [{"id": "tray1", "x": 720, "y": 440, "w": 980, "h": 620, "closed": False, "parked": False, "contents": [{"type": "twoi", "data": {}, "state": {}}]}]}
        _ok(c.put("/api/foresight/counter-layout", json={"layout": layout, "client_saved_at": 1761600000000}))
        c.close()

        # quit PubCast, then start it again on the same data
        reach.stop()
        reach.start()
        c = httpx.Client(base_url=reach.base, headers={"Authorization": "Bearer " + token}, timeout=60)

        got = _ok(c.get("/api/writers-room/documents/chapter-one"))
        assert got["revision"] == 2 and got["title"] == "Chapter One" and got["state"]["committed"][-1] == "Nobody noticed until morning."

        f = _ok(c.get("/api/foresight/workspace/file", params={"path": "Scripts/hello.py"}))
        assert base64.b64decode(f["data"]) == text

        turns_after = _ok(c.get("/api/pubpartner/sessions/restart_check/turns"))
        assert turns_after == turns_before and "Remember this line exactly." in str(turns_after)

        conversation = _ok(c.get(f"/api/conversations/{conv}"))["conversation"]
        assert "The pilot opens in the dressing room." in str(conversation) and "Then the green room." in str(conversation)

        recent = _ok(c.get(f"/api/chat/rooms/{room_id}", params={"limit": 50}))["recent_messages"]
        assert "Saved before the restart" in str(recent)

        assert avatar in [a["id"] for a in _ok(c.get("/api/avatars/imports"))["avatars"]]
        assert [(x["id"], x["avatar_id"]) for x in _ok(c.get("/api/pubpartner/cartridges"))["cartridges"]] == [("marlowe_finch", avatar)]
        assert _ok(c.get("/api/pubpartner/profiles/friend/marlowe_finch"))["profile"]["display_name"] == "Marlowe Finch"

        assert _ok(c.get("/api/studio/progress"))["progress"] == progress
        assert _ok(c.get("/api/foresight/counter-layout"))["layout"] == layout
        c.close()
    finally:
        reach.stop()
    assert _blob(ALEX_VESSEL) == ALEX_BLOB

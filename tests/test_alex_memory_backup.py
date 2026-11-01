"""Alex memory backup: local folder + Google Drive API backends, restore, read access, isolation."""
import asyncio
import json
import re

import pytest

import modules.alex_memory_backup as amb
from modules.alex_memory_backup import (
    AlexMemoryBackup, GoogleDriveBackend, LocalFolderBackend, MirroredBackend,
    build_alex_backup_from_env, valid_relpath,
)

MEM = {"id": "mem_1_aaaa", "content": "my sister is visiting friday", "timestamp": "2026-10-08T20:29:51",
       "keywords": ["sister", "visiting", "friday"]}


def seed(data_dir, user="u", n=2):
    base = data_dir / "alex" / user
    (base / "2026-10").mkdir(parents=True)
    for i in range(n):
        mem = {**MEM, "id": f"mem_{i}_aaaa", "content": MEM["content"] if i == 0 else f"unrelated note {i} gardening"}
        (base / "2026-10" / f"mem_{i}_aaaa.json").write_text(json.dumps(mem))
    (base / "_affect_state.json").write_text('{"baseline": 1}')
    (base / "_alex_state.json").write_text('{"state": "companion"}')
    # files that must NEVER be backed up
    (base / "config.json").write_text('{"api_key": "SECRET"}')
    (base / "2026-10" / "notes.json").write_text('{"x": 1}')
    (data_dir / "alex" / "affect").mkdir(exist_ok=True)
    (data_dir / "alex" / "affect" / "u.json").write_text('{"legacy": 1}')
    return base


class Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


# ---- fake Google Drive v3 service -----------------------------------------------------------

class _Req:
    def __init__(self, fn): self.fn = fn
    def execute(self): return self.fn()


class FakeDrive:
    def __init__(self):
        self.items = {}      # id -> dict(name, parent, folder, data)
        self.n = 0
        self.calls = {"create": 0, "update": 0, "list": 0}
    def files(self): return self
    def _new(self, **kw):
        self.n += 1
        fid = f"id{self.n}"
        self.items[fid] = kw
        return fid
    def list(self, q, **kw):
        self.calls["list"] += 1
        name = re.search(r"name = '((?:[^'\\]|\\.)*)'", q).group(1).replace("\\'", "'").replace("\\\\", "\\")
        parent = re.search(r"'((?:[^'\\]|\\.)*)' in parents", q).group(1)
        want_folder = "mimeType = " in q
        out = [{"id": i, "name": v["name"]} for i, v in self.items.items()
               if v["name"] == name and v["parent"] == parent and v["folder"] == want_folder]
        return _Req(lambda: {"files": out})
    def create(self, body, media_body=None, **kw):
        def run():
            self.calls["create"] += 1
            fid = self._new(name=body["name"], parent=body["parents"][0],
                            folder=body.get("mimeType") == amb.DRIVE_FOLDER_MIME, data=media_body)
            return {"id": fid}
        return _Req(run)
    def update(self, fileId, media_body, **kw):
        def run():
            self.calls["update"] += 1
            self.items[fileId]["data"] = media_body
            return {"id": fileId}
        return _Req(run)
    def get_media(self, fileId, **kw): return _Req(lambda: self.items[fileId]["data"])


def drive_backend(fake=None):
    fake = fake or FakeDrive()
    root = fake._new(name="Alex Persistent Memory AI", parent="", folder=True, data=None)
    return fake, GoogleDriveBackend(fake, root, media_factory=lambda data, mt: data)


# ---- local folder backend -------------------------------------------------------------------

def test_backup_copies_only_alex_files_and_is_incremental(tmp_path):
    seed(tmp_path)
    dest = tmp_path / "drive_sync"
    eng = AlexMemoryBackup(tmp_path, LocalFolderBackend(dest))
    r = eng.backup("u")
    assert r["uploaded"] == 4 and r["errors"] == []
    files = {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()}
    assert files == {"u/2026-10/mem_0_aaaa.json", "u/2026-10/mem_1_aaaa.json", "u/_affect_state.json",
                     "u/_alex_state.json", "u/_backup_manifest.json"}
    assert "SECRET" not in "".join(p.read_text() for p in dest.rglob("*") if p.is_file())
    manifest = json.loads((dest / "u/_backup_manifest.json").read_text())
    assert manifest["format"] == "AlexMemoryBackup.v1" and manifest["contains_secrets"] is False
    again = eng.backup("u")
    assert again["uploaded"] == 0 and again["unchanged"] == 4
    (tmp_path / "alex/u/_alex_state.json").write_text('{"state": "guide"}')
    assert eng.backup("u")["uploaded"] == 1


def test_backup_is_append_only_and_restore_recovers_deleted_files(tmp_path):
    base = seed(tmp_path)
    eng = AlexMemoryBackup(tmp_path, LocalFolderBackend(tmp_path / "bk"))
    eng.backup("u")
    (base / "2026-10" / "mem_0_aaaa.json").unlink()
    eng.backup("u")                                           # deletion must NOT propagate
    assert (tmp_path / "bk/u/2026-10/mem_0_aaaa.json").exists()
    out = eng.restore("u")
    assert out["restored"] == ["2026-10/mem_0_aaaa.json"] and out["errors"] == []
    assert len(out["skipped"]) == 3                           # existing files untouched
    (base / "_alex_state.json").write_text("changed locally")
    assert eng.restore("u")["restored"] == []                 # no overwrite by default
    assert "_alex_state.json" in eng.restore("u", overwrite=True)["restored"]


def test_restore_verifies_hashes_and_rejects_hostile_manifest_paths(tmp_path):
    seed(tmp_path)
    bk = tmp_path / "bk"
    eng = AlexMemoryBackup(tmp_path, LocalFolderBackend(bk))
    eng.backup("u")
    import shutil; shutil.rmtree(tmp_path / "alex" / "u")
    (bk / "u/_alex_state.json").write_text("TAMPERED")
    mp = bk / "u/_backup_manifest.json"
    m = json.loads(mp.read_text())
    m["files"]["../../evil.json"] = {"sha256": "0", "size": 1}
    mp.write_text(json.dumps(m))
    out = eng.restore("u")
    assert any("hash mismatch" in e for e in out["errors"]) and any("invalid path" in e for e in out["errors"])
    assert not (tmp_path / "alex/u/_alex_state.json").exists()
    assert not (tmp_path / "evil.json").exists() and not (tmp_path.parent / "evil.json").exists()


def test_read_and_search_backed_up_memories_and_integrity_check(tmp_path):
    seed(tmp_path)
    bk = tmp_path / "bk"
    eng = AlexMemoryBackup(tmp_path, LocalFolderBackend(bk))
    eng.backup("u")
    hit = eng.search("u", "is my sister still visiting?")
    assert hit and "sister" in hit[0]["text"] and hit[0]["path"].endswith(".json")
    assert eng.search("u", "completely different topic zebra") == []
    assert eng.read("u", "2026-10/mem_0_aaaa.json")["content"].startswith("my sister")
    for bad in ("../x.json", "/etc/passwd", "_backup_manifest.json", "2026-10/../../x.json", "config.json"):
        with pytest.raises(ValueError):
            eng.read("u", bad)
    (bk / "u/2026-10/mem_0_aaaa.json").write_text('{"content": "tampered sister"}')
    with pytest.raises(ValueError):
        eng.read("u", "2026-10/mem_0_aaaa.json")
    assert all("tampered" not in h["text"] for h in eng.search("u", "sister"))   # skipped, not trusted


def test_relpath_validation():
    assert valid_relpath("2026-10/mem_1_abc.json") and valid_relpath("_alex_state.json")
    for bad in ("../a.json", "a/b.json", "2026-10/x.json", ".hidden", "mem_1.json", "2026-10/mem_/../x.json", ""):
        assert not valid_relpath(bad)


# ---- throttling, background, failure isolation ---------------------------------------------

def test_notify_turn_is_throttled_background_and_never_raises(tmp_path):
    seed(tmp_path)
    clock = Clock()
    eng = AlexMemoryBackup(tmp_path, LocalFolderBackend(tmp_path / "bk"), min_interval=60, clock=clock)
    assert eng.notify_turn("u") is True
    eng.wait()
    assert (tmp_path / "bk/u/_backup_manifest.json").exists()
    assert eng.notify_turn("u") is False                      # inside the interval
    clock.t += 61
    assert eng.notify_turn("u", background=False) is True

    class Broken:
        name = "broken"
        def put_bytes(self, p, d): raise OSError("disk full")
        def get_bytes(self, p): raise OSError("disk full")
    eng2 = AlexMemoryBackup(tmp_path, Broken(), min_interval=0)
    rep = eng2.backup("u")                                    # reported, not raised
    assert rep["errors"] and rep["uploaded"] == 0
    assert eng2.restore_if_empty("u") is None                 # local files exist -> no restore attempt


def test_mirrored_backend_isolates_failures_and_reads_from_survivor(tmp_path):
    class Broken:
        name = "broken"
        def put_bytes(self, p, d): raise OSError("down")
        def get_bytes(self, p): raise OSError("down")
    good = LocalFolderBackend(tmp_path / "ok")
    m = MirroredBackend([Broken(), good])
    m.put_bytes("u/_alex_state.json", b"{}")
    assert "broken" in m.last_errors and m.get_bytes("u/_alex_state.json") == b"{}"
    with pytest.raises(RuntimeError):
        MirroredBackend([Broken()]).put_bytes("u/x", b"1")


# ---- Google Drive backend (fake Drive v3 service) -----------------------------------------

def test_drive_backend_creates_folders_once_updates_in_place_and_roundtrips(tmp_path):
    seed(tmp_path)
    fake, drive = drive_backend()
    eng = AlexMemoryBackup(tmp_path, drive)
    assert eng.backup("u")["uploaded"] == 4
    folders = [v["name"] for v in fake.items.values() if v["folder"]]
    assert sorted(folders) == ["2026-10", "Alex Persistent Memory AI", "u"]       # created once each
    creates = fake.calls["create"]
    (tmp_path / "alex/u/_alex_state.json").write_text('{"state": "guide"}')
    assert eng.backup("u")["uploaded"] == 1
    assert fake.calls["update"] >= 1 and fake.calls["create"] == creates          # updated in place, no duplicates
    names = [v["name"] for v in fake.items.values() if not v["folder"]]
    assert len(names) == len(set(names)) == 5
    # a fresh engine with a cold cache (new process) finds the existing files and does not duplicate
    cold = GoogleDriveBackend(fake, next(i for i, v in fake.items.items() if v["name"] == "Alex Persistent Memory AI"),
                              media_factory=lambda d, m: d)
    before = len(fake.items)
    assert AlexMemoryBackup(tmp_path, cold).backup("u")["uploaded"] == 0
    assert len(fake.items) == before
    import shutil; shutil.rmtree(tmp_path / "alex")
    out = AlexMemoryBackup(tmp_path, cold).restore("u")
    assert len(out["restored"]) == 4 and out["errors"] == []
    assert json.loads((tmp_path / "alex/u/2026-10/mem_0_aaaa.json").read_text())["id"] == "mem_0_aaaa"
    assert cold.get_bytes("u/nope.json") is None and cold.get_bytes("zzz/none.json") is None


def test_drive_query_escaping_and_unsafe_paths():
    assert amb._q("o'brien\\x") == "o\\'brien\\\\x"
    _, drive = drive_backend()
    for bad in ("../x", "/abs", "a//b", "a\\b", ""):
        with pytest.raises(ValueError):
            drive.put_bytes(bad, b"1")


# ---- environment configuration ------------------------------------------------------------------

def test_env_configuration(tmp_path, monkeypatch):
    assert build_alex_backup_from_env(tmp_path, {}) is None
    only_local = build_alex_backup_from_env(tmp_path, {"ALEX_BACKUP_LOCAL_DIR": str(tmp_path / "gd")})
    assert isinstance(only_local.backend, LocalFolderBackend)
    # Drive configured but credentials broken -> local backend still works (with a console note)
    def boom(*a, **k): raise RuntimeError("no token")
    monkeypatch.setattr(amb, "build_drive_service", boom)
    env = {"ALEX_BACKUP_LOCAL_DIR": str(tmp_path / "gd"), "ALEX_BACKUP_DRIVE_FOLDER_ID": "F",
           "ALEX_BACKUP_GOOGLE_CREDENTIALS": "c.json", "ALEX_BACKUP_MIN_INTERVAL": "5"}
    degraded = build_alex_backup_from_env(tmp_path, env)
    assert isinstance(degraded.backend, LocalFolderBackend) and degraded.min_interval == 5
    # both healthy -> mirrored
    fake = FakeDrive(); root = fake._new(name="root", parent="", folder=True, data=None)
    monkeypatch.setattr(amb, "build_drive_service", lambda *a, **k: fake)
    monkeypatch.setattr(GoogleDriveBackend, "_default_media", staticmethod(lambda d, m: d))
    both = build_alex_backup_from_env(tmp_path, {**env, "ALEX_BACKUP_DRIVE_FOLDER_ID": root})
    assert isinstance(both.backend, MirroredBackend) and len(both.backend.backends) == 2
    seed(tmp_path)
    assert both.backup("u")["uploaded"] == 4
    assert (tmp_path / "gd/u/_alex_state.json").exists() and len([v for v in fake.items.values() if not v["folder"]]) == 5


# ---- bridge / route integration -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bridge_backs_up_after_turns_and_restores_alex_when_local_is_wiped(tmp_path):
    from modules.alex_jeremy_bridge import AlexJeremyBridge
    data = tmp_path / "data"
    bk = tmp_path / "gdrive"
    b = AlexJeremyBridge(data_dir=data)
    b.alex_backup = AlexMemoryBackup(data, LocalFolderBackend(bk), min_interval=0)
    for i, t in enumerate(["my sister is visiting friday", "the rust build compiled", "that is enough for today"]):
        await b.process_user_turn(user_id="u", session_id="s", text=t, metadata={"message_id": f"m{i}"})
    b.alex_backup.wait()
    b.shutdown()
    assert list(bk.rglob("mem_*.json")) and (bk / "u/_backup_manifest.json").exists()
    import shutil; shutil.rmtree(data / "alex")                          # catastrophic local loss
    b2 = AlexJeremyBridge(data_dir=data)
    b2.alex_backup = AlexMemoryBackup(data, LocalFolderBackend(bk), min_interval=0)
    alex = b2.alex_for("u")                                              # restore happens before Alex loads
    assert [m for m in alex.memory.recall(query="sister visiting friday") if "sister" in m.content]
    b2.shutdown()


@pytest.mark.asyncio
async def test_backup_failure_never_breaks_a_turn_and_limited_text_never_reaches_backup(tmp_path):
    from modules.alex_jeremy_bridge import AlexJeremyBridge
    class Broken:
        name = "broken"
        def put_bytes(self, p, d): raise OSError("down")
        def get_bytes(self, p): raise OSError("down")
    data = tmp_path / "data"
    b = AlexJeremyBridge(data_dir=data)
    b.alex_backup = AlexMemoryBackup(data, Broken(), min_interval=0)
    pkt = await b.process_user_turn(user_id="u", session_id="s", text="hello there", metadata={"message_id": "m1"})
    assert pkt["alex_state"]
    b.alex_backup.wait()
    b.shutdown()
    bk = tmp_path / "gd"
    b3 = AlexJeremyBridge(data_dir=tmp_path / "d3")
    b3.alex_backup = AlexMemoryBackup(tmp_path / "d3", LocalFolderBackend(bk), min_interval=0)
    handling = {"classification": "LIMITED", "categories": ["HEALTH"], "subject_id": "u", "origin_event_id": "m"}
    await b3.process_user_turn(user_id="u", session_id="s", text="my private diagnosis zebra",
                               metadata={"message_id": "m1", "data_handling": handling})
    b3.alex_backup.wait()
    b3.alex_backup.backup("u")
    assert all("zebra" not in p.read_text() for p in bk.rglob("*.json"))
    b3.shutdown()


def test_routes_report_status_and_search_backup(tmp_path):
    import modules.alex_routes as routes
    from fastapi import HTTPException
    seed(tmp_path)
    eng = AlexMemoryBackup(tmp_path, LocalFolderBackend(tmp_path / "bk"))
    owner = {"user_id": "u", "role": "owner", "authenticated": True}
    stranger = {"user_id": "other", "role": "guest", "authenticated": True}
    anonymous = {"user_id": "u", "role": "owner", "authenticated": False}
    routes.set_alex_backup(None)
    assert asyncio.run(routes.backup_status(identity=owner)) == {"configured": False}
    routes.set_alex_backup(eng)
    eng.backup("u")
    st = asyncio.run(routes.backup_status(identity=owner))
    assert st["configured"] and st["last_report"]["uploaded"] == 4
    res = asyncio.run(routes.backup_search(q="sister friday", user_id="u", limit=5, identity=owner))
    assert res["results"] and "sister" in res["results"][0]["text"]
    for identity, user in ((anonymous, "u"), (stranger, "u")):
        with pytest.raises(HTTPException):
            asyncio.run(routes.backup_search(q="sister", user_id=user, limit=5, identity=identity))
    routes.set_alex_backup(None)


@pytest.mark.asyncio
async def test_direct_alex_turns_via_the_http_route_path_also_back_up(tmp_path):
    """/api/alex/message calls alex_for(user).process_message directly, not process_user_turn."""
    from modules.alex_jeremy_bridge import AlexJeremyBridge
    data = tmp_path / "data"
    b = AlexJeremyBridge(data_dir=data)
    alex = b.alex_for("u")                                   # created BEFORE the backup is attached
    b.alex_backup = AlexMemoryBackup(data, LocalFolderBackend(tmp_path / "bk"), min_interval=0)
    await alex.process_message("my sister is visiting friday", metadata={"session_id": "s"})
    b.alex_backup.wait()
    assert list((tmp_path / "bk").rglob("mem_*.json")) and (tmp_path / "bk/u/_backup_manifest.json").exists()
    b.alex_backup = None                                     # detaching must not break turns
    await alex.process_message("another turn", metadata={"session_id": "s"})
    b.shutdown()

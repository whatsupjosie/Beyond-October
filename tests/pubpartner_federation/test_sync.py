from pathlib import Path
from dataclasses import replace
from pubpartner_federation import SyncEngine, SyncStore

def make(tmp_path: Path, name: str):
    return SyncEngine(name, SyncStore(tmp_path / f"{name}.db"))

def test_offline_bidirectional_sync_converges(tmp_path):
    a,b=make(tmp_path,"travel"),make(tmp_path,"resident")
    a.upsert("memory","m1",{"text":"night filming","importance":3})
    b.upsert("preference","p1",{"tone":"direct"})
    b.receive(a.envelope()); a.receive(b.envelope())
    assert b.store.get("memory","m1").fields["text"]=="night filming"
    assert a.store.get("preference","p1").fields["tone"]=="direct"

def test_duplicate_delivery_is_idempotent(tmp_path):
    a,b=make(tmp_path,"travel"),make(tmp_path,"resident")
    a.upsert("memory","m1",{"text":"same change"}); env=a.envelope()
    assert b.receive(env)[0].applied is True
    assert b.receive(env)[0].duplicate is True

def test_non_overlapping_concurrent_fields_merge(tmp_path):
    a,b=make(tmp_path,"travel"),make(tmp_path,"resident")
    a.upsert("profile","alex",{"tone":"warm","pace":"slow"}); b.receive(a.envelope())
    a.upsert("profile","alex",{"tone":"direct"})
    b.upsert("profile","alex",{"pace":"fast"})
    b.receive(a.envelope()); a.receive(b.envelope())
    expected={"tone":"direct","pace":"fast"}
    assert a.store.get("profile","alex").fields==expected
    assert b.store.get("profile","alex").fields==expected

def test_same_field_conflict_is_not_silently_overwritten(tmp_path):
    a,b=make(tmp_path,"travel"),make(tmp_path,"resident")
    a.upsert("preference","p1",{"tone":"warm"}); b.receive(a.envelope())
    a.upsert("preference","p1",{"tone":"direct"})
    b.upsert("preference","p1",{"tone":"formal"})
    results=a.receive(b.envelope())
    # Relayed history may precede the new peer edit; inspect the actual conflict.
    assert sum(result.conflict is not None for result in results) == 1
    assert a.store.get("preference","p1").fields["tone"]=="direct"

def test_delete_is_tombstone(tmp_path):
    a,b=make(tmp_path,"travel"),make(tmp_path,"resident")
    a.upsert("memory","m1",{"text":"old"}); b.receive(a.envelope())
    a.delete("memory","m1"); b.receive(a.envelope())
    entity=b.store.get("memory","m1")
    assert entity.deleted is True and entity.fields=={}

def test_incompatible_protocol_rejected(tmp_path):
    a,b=make(tmp_path,"travel"),make(tmp_path,"resident")
    bad=replace(a.envelope(),protocol="pubpartner-sync/999")
    try:b.receive(bad)
    except ValueError as exc: assert "unsupported sync protocol" in str(exc)
    else: raise AssertionError("incompatible protocol was accepted")

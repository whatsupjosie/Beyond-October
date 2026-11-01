"""A user ID must never decide where Alex's memory is written outside its root.

Reproduced 2026-10-25: MemoryCore built ``data_dir / user_id``, so "../x" wrote
beside the memory root and "/abs" wrote to an absolute path.
"""
from __future__ import annotations

import pytest

from modules.alex_core import AlexCore, MemoryCore, memory_dir_name

HOSTILE = ["../escaped", "../../etc/x", "a/b", "/abs_user", "..", ".", "user:1", "user?1",
           "x\\y", "nul\x00byte", "a" * 500, "  "]


@pytest.mark.parametrize("uid", HOSTILE)
def test_memory_folder_stays_inside_root(tmp_path, uid):
    root = tmp_path / "alex"
    root.mkdir()
    m = MemoryCore(user_id=uid, data_dir=root)
    resolved = m.data_dir.resolve()
    assert root.resolve() in resolved.parents, (uid, resolved)
    assert resolved.parent == root.resolve(), "must be a direct child, never nested"
    assert not (tmp_path / "escaped").exists()


@pytest.mark.parametrize("uid", ["josie", "owner-test", "user_1", "Alex.Bourgeois", "a1"])
def test_ordinary_ids_keep_their_exact_folder_name(tmp_path, uid):
    assert memory_dir_name(uid) == uid
    assert MemoryCore(user_id=uid, data_dir=tmp_path).data_dir == tmp_path / uid


def test_different_unusual_ids_never_share_a_folder():
    names = {memory_dir_name(u) for u in ("a/b", "a_b", "a?b", "a:b", "../a", "a b")}
    assert len(names) == 6


def test_same_unusual_id_is_stable():
    assert memory_dir_name("a/b") == memory_dir_name("a/b")


def test_default_for_empty_id():
    assert memory_dir_name("") == "default"
    assert memory_dir_name(None) == "default"


def test_memories_written_under_hostile_id_round_trip(tmp_path):
    root = tmp_path / "alex"
    root.mkdir()
    a = AlexCore(user_id="../escaped", data_dir=root)
    a._monitor_active = False
    assert root.resolve() in a.memory.data_dir.resolve().parents
    assert not (tmp_path / "escaped").exists()

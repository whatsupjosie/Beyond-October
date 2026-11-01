from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from modules.persistence import read_json, write_json, write_json_async


def test_failed_serialization_preserves_previous_file(tmp_path: Path):
    path = tmp_path / "state.json"
    write_json(path, {"version": 1, "safe": True})

    with pytest.raises(TypeError):
        write_json(path, {"bad": object()})

    assert read_json(path) == {"version": 1, "safe": True}
    assert list(tmp_path.glob(".*.tmp")) == []


def test_concurrent_atomic_writers_leave_valid_complete_document(tmp_path: Path):
    path = tmp_path / "state.json"

    def writer(index: int):
        write_json(path, {"writer": index, "payload": "x" * 2048})

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(writer, range(40)))

    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["writer"] in range(40)
    assert result["payload"] == "x" * 2048
    assert list(tmp_path.glob(".*.tmp")) == []


def test_async_write_uses_same_atomic_contract(tmp_path: Path):
    path = tmp_path / "async.json"
    asyncio.run(write_json_async(path, {"ok": True, "rows": [1, 2, 3]}))
    assert read_json(path) == {"ok": True, "rows": [1, 2, 3]}

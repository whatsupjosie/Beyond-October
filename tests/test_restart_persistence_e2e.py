"""First integration milestone: a restart-persistent conversation through the
real supported runtime (no in-process shortcut).

    input -> capture (VerbatimVault) -> memory (Jeremy + Alex) -> Alex/Jeremy bridge
          -> AffectContextEngine / System Alex -> provider -> persisted turn log
          -> RESTART (new process, same data dir) -> retrieval

Honest scope: the provider is the explicit deterministic ``mock`` adapter, so this
proves capture/memory/EQ/persistence/retrieval wiring - not the quality of any real
model's reply. External chat-capture (e.g. a ChatGPT connection) is NOT simulated.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HELPER = Path(__file__).with_name("_e2e_proc.py")


def run_phase(data_dir: Path, phase: str) -> dict:
    env = dict(os.environ)
    env.pop("PUBCAST_DATA_DIR", None)
    proc = subprocess.run(
        [sys.executable, "-I", str(HELPER), str(ROOT), str(data_dir), phase],
        capture_output=True, text=True, timeout=240, env=env, cwd=str(ROOT),
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("E2E_RESULT ")]
    assert lines, f"phase {phase} produced no result\nSTDOUT:{proc.stdout[-1500:]}\nSTDERR:{proc.stderr[-2500:]}"
    return json.loads(lines[-1][len("E2E_RESULT "):])


@pytest.fixture
def data_dir(tmp_path):
    seed = ROOT / "data"
    dest = tmp_path / "data"
    if seed.exists():
        shutil.copytree(seed, dest, ignore=shutil.ignore_patterns("secure", "*.db", "emergency_saves"))
    else:
        dest.mkdir()
    return dest


def test_memory_survives_process_restart(data_dir):
    first = run_phase(data_dir, "write")
    assert first["health"] == 200
    for i in range(3):
        turn = first[f"turn{i}"]
        assert turn["status"] == 200 and turn["ok"] is True, turn
        assert turn["alex_source"] == "AlexCore.process_message", turn  # real Alex path, not the fallback
        assert turn["receipt_ok"] is True, turn
    # Technical frustration must not push Alex into a silent-support state.
    assert first["turn1"]["alex_state"] not in ("witness", "anchor"), first["turn1"]

    second = run_phase(data_dir, "recall")  # brand-new process, same data dir
    assert second["health"] == 200
    recall = second["recall"]
    assert recall["status"] == 200 and recall["ok"] is True
    assert recall["alex_source"] == "AlexCore.process_message"
    texts = " | ".join(t for t in recall["memory_texts"] if t)
    assert "Atlas Seven" in texts, recall  # retrieved after restart


def test_verbatim_original_is_byte_exact_on_disk(data_dir):
    run_phase(data_dir, "write")
    originals = list(data_dir.glob("pubpartner/verbatim/*/first-run/src_*.utf8"))
    assert originals, "VerbatimVault wrote no original records"
    bodies = {p.read_bytes() for p in originals}
    assert b"My red notebook is named Atlas Seven." in bodies  # original, not a generated summary


def test_restart_tolerates_truncated_turn_log_and_corrupt_bridge_state(data_dir):
    """Interrupted-write simulation: a half-written JSONL line and a garbage bridge file."""
    run_phase(data_dir, "write")
    for log in data_dir.glob("pubpartner/sessions/*_turns.jsonl"):
        with open(log, "ab") as fh:
            fh.write(b'{"turn_id": "turn_cut_off_mid_wri')  # torn write, no newline
    for state in data_dir.glob("alex_bridge/session_*.json"):
        state.write_bytes(b"\x00\xff not json at all")
    second = run_phase(data_dir, "recall")
    assert second["health"] == 200
    assert second["recall"]["status"] == 200, second
    assert "Atlas Seven" in " | ".join(t for t in second["recall"]["memory_texts"] if t)

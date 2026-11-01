# PubCast AI — test_doctor_paths.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""
tests/test_doctor_paths.py
Regression tests for the doctor DATA_DIR vs project-root path resolution bug.

Bug: _check_data_dirs / _check_write_access always prepended "data/" to their
input, so passing DATA_DIR (which is already the data directory) caused the
doctor to look for data/data/... and report a spurious required failure.

Fix: both functions now detect whether they received the project root or DATA_DIR
by checking for the presence of main.py / requirements.txt as sentinels.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.doctor import run_doctor, run_launch_gate


PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"


@pytest.fixture(autouse=True, scope="module")
def _bootstrapped_data_dirs():
    # data/secure is git-ignored (key material), so a clean checkout lacks it.
    # The app creates it at startup via ensure_runtime_dirs; do the same here so
    # these tests describe a started app rather than depending on leftover state.
    from modules.doctor import ensure_runtime_dirs
    ensure_runtime_dirs(DATA_DIR)
    yield


class TestDoctorPathResolution:
    """Both call conventions must produce zero required failures."""

    def test_project_root_no_required_failures(self):
        report = run_doctor(PROJECT_ROOT)
        required_fails = [
            c for c in report["checks"]
            if c["status"] == "fail" and c.get("required")
        ]
        assert required_fails == [], (
            f"run_doctor(project_root) has unexpected required failures: "
            f"{[f['name'] for f in required_fails]}"
        )

    def test_data_dir_no_required_failures(self):
        report = run_doctor(DATA_DIR)
        required_fails = [
            c for c in report["checks"]
            if c["status"] == "fail" and c.get("required")
        ]
        assert required_fails == [], (
            f"run_doctor(DATA_DIR) has unexpected required failures: "
            f"{[f['name'] for f in required_fails]}"
        )

    def test_project_root_launch_gate_allowed(self):
        gate = run_launch_gate(PROJECT_ROOT)
        assert gate["allowed"] is True, (
            f"launch_gate(project_root) is blocking: {gate['blocking_checks']}"
        )

    def test_data_dir_launch_gate_allowed(self):
        gate = run_launch_gate(DATA_DIR)
        assert gate["allowed"] is True, (
            f"launch_gate(DATA_DIR) is blocking: {gate['blocking_checks']}"
        )

    def test_both_modes_agree_on_data_dirs_check(self):
        """The data_dirs check must pass in both call modes."""
        root_report = run_doctor(PROJECT_ROOT)
        data_report = run_doctor(DATA_DIR)

        root_check = next(c for c in root_report["checks"] if c["check_id"] == "data_dirs")
        data_check = next(c for c in data_report["checks"] if c["check_id"] == "data_dirs")

        assert root_check["status"] == "pass", (
            f"data_dirs check failed via project root: {root_check['message']}"
        )
        assert data_check["status"] == "pass", (
            f"data_dirs check failed via DATA_DIR: {data_check['message']}"
        )

    def test_both_modes_agree_on_write_access(self):
        """The write_access check must pass in both call modes."""
        root_report = run_doctor(PROJECT_ROOT)
        data_report = run_doctor(DATA_DIR)

        root_check = next(c for c in root_report["checks"] if c["check_id"] == "write_access")
        data_check = next(c for c in data_report["checks"] if c["check_id"] == "write_access")

        assert root_check["status"] == "pass", (
            f"write_access check failed via project root: {root_check['message']}"
        )
        assert data_check["status"] == "pass", (
            f"write_access check failed via DATA_DIR: {data_check['message']}"
        )

    def test_report_structure(self):
        """Doctor report has required top-level keys."""
        report = run_doctor(PROJECT_ROOT)
        for key in ("status", "checks", "launch_gate", "summary", "next_steps"):
            assert key in report, f"Missing key in doctor report: {key}"

    def test_launch_gate_structure(self):
        """Launch-gate has required keys."""
        gate = run_launch_gate(PROJECT_ROOT)
        for key in ("allowed", "reason", "blocking_checks"):
            assert key in gate, f"Missing key in launch_gate: {key}"


def test_data_dir_doctor_finds_packaged_renderer_when_present():
    report = run_doctor(DATA_DIR)
    check = next(c for c in report["checks"] if c["check_id"] == "rust_bridge_binary")
    packaged = PROJECT_ROOT / "bin" / "ws_renderer"
    if packaged.exists() and packaged.stat().st_mode & 0o111:
        assert check["status"] == "pass"
        assert Path(check["detail"]["path"]).resolve() == packaged.resolve()


def test_managed_packaged_renderer_listener_is_not_reported_as_port_conflict(monkeypatch):
    import os
    from modules import doctor

    monkeypatch.setenv("PUBCAST_PORT", "8123")
    monkeypatch.setenv("PUBCAST_WS_PORT", "8765")
    packaged = str((PROJECT_ROOT / "bin" / "ws_renderer").resolve())

    def fake_probe(label, port):
        if label == "http":
            return doctor.PortProbeResult(port=port, label=label, listening=True,
                owner={"pid": os.getpid(), "name": "python", "command": "python run_reach.py", "source": "test"})
        return doctor.PortProbeResult(port=port, label=label, listening=True,
            owner={"pid": 4242, "name": "ws_renderer", "command": packaged, "source": "test"})

    monkeypatch.setattr(doctor, "_probe_port", fake_probe)
    check = doctor._check_default_ports()
    assert check.status == "pass"
    assert "Expected Rust bridge listener" in check.message
    assert not any("confirm the listener" in item for item in check.fix_instructions)


def test_ensure_runtime_dirs_creates_secure_owner_only_and_is_idempotent(tmp_path):
    from modules.doctor import ensure_runtime_dirs, REQUIRED_DATA_SUBDIRS

    root = tmp_path / "fresh_data"
    created = ensure_runtime_dirs(root)
    assert set(created) == set(REQUIRED_DATA_SUBDIRS)
    assert ensure_runtime_dirs(root) == []  # second call changes nothing
    import os, stat
    if os.name == "posix":
        assert stat.S_IMODE((root / "secure").stat().st_mode) == 0o700
    assert run_doctor(root)["checks"]  # report builds against the fresh tree
    failing = [c["name"] for c in run_doctor(root)["checks"] if c["status"] == "fail" and c.get("required") and c["check_id"] == "data_dirs"]
    assert failing == []

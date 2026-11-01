from pathlib import Path

import pytest

from blackbox_event_language.schema import (
    BLACKBOX_KEY,
    BlackBoxRecord,
    BlackBoxValidationError,
    decode_record,
    encode_record,
    parse_record,
)
from blackbox_decoder import build_known_record_report
from blackbox_recorder import AppendOnlyBlackBoxRecorder, map_pubcast_event, record_pubcast_event


def test_coded_record_round_trips_without_english_primary_record():
    wire = encode_record(
        BlackBoxRecord(
            seq=1,
            ch="AIT",
            src="ALEX",
            act="ai:alex",
            ev="DCP",
            cov="P",
            sid="s01",
            rid="r01",
            payload={"pkt": "d77", "conf": "0.71"},
        )
    )

    assert wire.startswith("BBX1|seq=1|")
    assert "decision packet captured" not in wire
    decoded = decode_record(wire)
    assert decoded["event"]["label"] == "decision packet captured"
    assert decoded["payload"]["pkt"] == "d77"


def test_unknown_codes_are_rejected():
    record = BlackBoxRecord(seq=1, ch="BAD", src="ALEX", act="ai:alex", ev="DCP", cov="P", sid="s01", rid="r01")
    with pytest.raises(BlackBoxValidationError):
        encode_record(record)


def test_append_only_recorder_hash_chain_and_access_record(tmp_path: Path):
    recorder = AppendOnlyBlackBoxRecorder(tmp_path / "blackbox.bbx", session_id="s01")
    first = recorder.append(ch="ACT", src="VPK", act="avatar:minotaur_01", ev="TCR", cov="F", payload={"tool": "chair_adapt"})
    second = recorder.append(ch="APP", src="USR", act="user:owner", ev="APR", cov="F", payload={"request": "chair_adapt"})

    first_hash = decode_record(first)["hash"]
    assert decode_record(second)["previous_hash"] == first_hash
    assert recorder.verify().ok is True

    records = recorder.read_records(actor="user:owner", reason="self_review")
    assert records[-1]["channel"]["code"] == "ACC"
    assert records[-1]["event"]["code"] == "ACS"


def test_hash_chain_detects_tampering(tmp_path: Path):
    path = tmp_path / "blackbox.bbx"
    recorder = AppendOnlyBlackBoxRecorder(path, session_id="s01")
    recorder.append(ch="ERR", src="SYS", act="SYS", ev="ERR", cov="F", payload={"code": "E1"})

    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("code:E1", "code:E2"), encoding="utf-8")

    result = recorder.verify()
    assert result.ok is False
    assert any("hash mismatch" in error for error in result.errors)


def test_crash_position_records_priority_snapshot(tmp_path: Path):
    recorder = AppendOnlyBlackBoxRecorder(tmp_path / "blackbox.bbx", session_id="s01")
    recorder.append(ch="BRT", src="REC", act="SYS", ev="DCP", cov="S", payload={"program": "cam_a"})
    wires = recorder.crash_position(
        "fatal_exception",
        {"program": "cam_a", "rec": "active", "err": "RuntimeError", "tool": "visual_patch_77"},
    )

    assert [decode_record(w)["event"]["code"] for w in wires] == ["CPI", "CPS"]
    snapshot = decode_record(wires[1])
    assert snapshot["channel"]["code"] == "CRS"
    assert snapshot["payload"]["program"] == "cam_a"
    assert snapshot["payload"]["err"] == "RuntimeError"


def test_key_declares_three_percent_budget():
    assert BLACKBOX_KEY["version"] == "BBX1"
    assert "PER" in BLACKBOX_KEY["channels"]


def test_disciplinary_log_records_conduct_and_response_without_motive(tmp_path: Path):
    recorder = AppendOnlyBlackBoxRecorder(tmp_path / "blackbox.bbx", session_id="shoot_01")
    conduct = recorder.append(
        ch="DSC",
        src="BBX",
        act="ai:agent_07",
        ev="CND",
        cov="F",
        payload={"kind": "profanity_burst", "output_hash": "abc123", "program_visible": "true"},
    )
    response = recorder.append(
        ch="DSC",
        src="JER",
        act="system:pub_manager",
        ev="RSP",
        cov="F",
        payload={"action": "mute_agent", "agent": "agent_07", "reason": "conduct_policy"},
    )

    assert "meant" not in conduct
    assert "guilt" not in conduct
    assert decode_record(conduct)["event"]["code"] == "CND"
    assert decode_record(response)["payload"]["action"] == "mute_agent"
    assert recorder.verify().ok is True


def test_decoder_report_keeps_known_record_separate_from_analysis(tmp_path: Path):
    path = tmp_path / "blackbox.bbx"
    recorder = AppendOnlyBlackBoxRecorder(path, session_id="shoot_01")
    recorder.append(ch="DSC", src="BBX", act="ai:agent_07", ev="CND", cov="F", payload={"kind": "profanity_burst"})
    recorder.crash_position("fatal_exception", {"program": "cam_a", "err": "RuntimeError"})

    report = build_known_record_report(path.read_text(encoding="utf-8").splitlines())
    text = report.to_markdown()

    assert "## Known Record" in text
    assert "conduct event recorded" in text
    assert "crash-position snapshot" in text
    assert "## Derived Analysis" in text
    assert "None included" in text
    assert report.derived_analysis == []
    assert report.open_questions


def test_iteration_wallet_rollover_requires_manual_user_record(tmp_path: Path):
    recorder = AppendOnlyBlackBoxRecorder(tmp_path / "blackbox.bbx", session_id="shoot_01")
    request = recorder.request_wallet_rollover("seq0-99")
    request_id = decode_record(request)["record_id"]
    approval = recorder.approve_wallet_rollover("user:owner", request_id)
    deposit = recorder.record_manual_wallet_package("user:owner", "iteration_2026_06_14", "def456", "seq0-99")

    assert decode_record(request)["event"]["code"] == "WLR"
    assert decode_record(approval)["event"]["code"] == "WLA"
    decoded_deposit = decode_record(deposit)
    assert decoded_deposit["source"]["code"] == "USR"
    assert decoded_deposit["actor"] == "user:owner"
    assert decoded_deposit["payload"]["package_hash"] == "def456"
    assert decoded_deposit["payload"]["method"] == "manual"
    assert recorder.verify().ok is True


def test_pubcast_event_adapter_maps_runtime_events_to_coded_records(tmp_path: Path):
    recorder = AppendOnlyBlackBoxRecorder(tmp_path / "blackbox.bbx", session_id="shoot_01")
    event = {
        "event_type": "ai.tool_requested",
        "source": "alex",
        "actor": "ai:alex",
        "data": {"tool": "visual_patch", "request_id": "tool_77", "details": {"large": True}},
    }
    mapped = map_pubcast_event(event)
    wire = record_pubcast_event(recorder, event)
    decoded = decode_record(wire)

    assert mapped.ch == "ACT"
    assert mapped.ev == "TCR"
    assert decoded["source"]["code"] == "ALEX"
    assert decoded["payload"]["tool"] == "visual_patch"
    assert decoded["payload"]["details_type"] == "dict"
    assert recorder.verify().ok is True

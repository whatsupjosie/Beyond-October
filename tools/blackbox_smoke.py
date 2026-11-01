"""No-dependency smoke check for the BlackBox event language."""

from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blackbox_event_language.schema import BlackBoxRecord, decode_record, encode_record
from blackbox_decoder import build_known_record_report
from blackbox_recorder import AppendOnlyBlackBoxRecorder, record_pubcast_event


def main() -> None:
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
            payload={"pkt": "d77"},
        )
    )
    assert wire.startswith("BBX1|seq=1|")
    assert "decision packet captured" not in wire
    assert decode_record(wire)["event"]["label"] == "decision packet captured"

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "blackbox.bbx"
        recorder = AppendOnlyBlackBoxRecorder(path, session_id="shoot_01")
        recorder.append(ch="DSC", src="BBX", act="ai:agent_07", ev="CND", cov="F", payload={"kind": "profanity_burst"})
        recorder.append(ch="DSC", src="JER", act="system:pub_manager", ev="RSP", cov="F", payload={"action": "mute_agent"})
        record_pubcast_event(
            recorder,
            {
                "event_type": "ai.tool_requested",
                "source": "alex",
                "actor": "ai:alex",
                "data": {"tool": "visual_patch", "request_id": "tool_77"},
            },
        )
        request = recorder.request_wallet_rollover("seq0-1")
        recorder.approve_wallet_rollover("user:owner", decode_record(request)["record_id"])
        recorder.record_manual_wallet_package("user:owner", "iteration_2026_06_14", "def456", "seq0-1")
        recorder.crash_position("fatal_exception", {"program": "cam_a", "err": "RuntimeError"})
        result = recorder.verify()
        assert result.ok, result.errors
        report = build_known_record_report(path.read_text(encoding="utf-8").splitlines())
        report_text = report.to_markdown()
        assert "## Known Record" in report_text
        assert "conduct event recorded" in report_text
        assert "tool call requested" in report_text
        assert "crash-position snapshot" in report_text
        assert "wallet rollover requested" in report_text
        assert "manual wallet package recorded" in report_text
        assert "## Derived Analysis" in report_text
        assert "None included" in report_text

    print("blackbox_smoke passed")


if __name__ == "__main__":
    main()

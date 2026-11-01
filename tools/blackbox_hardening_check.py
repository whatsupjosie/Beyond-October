"""No-dependency hardening checks for BlackBox records."""

from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blackbox_decoder import build_known_record_report
from blackbox_event_language.schema import BlackBoxRecord, BlackBoxValidationError, encode_record
from blackbox_recorder import AppendOnlyBlackBoxRecorder, record_pubcast_event


def assert_bad_record_raises() -> None:
    try:
        encode_record(BlackBoxRecord(seq=0, ch="BAD", src="SYS", act="SYS", ev="ERR", cov="F", sid="s", rid="r"))
    except BlackBoxValidationError:
        return
    raise AssertionError("unknown channel did not fail")


def build_chain(path: Path) -> AppendOnlyBlackBoxRecorder:
    recorder = AppendOnlyBlackBoxRecorder(path, session_id="s01")
    recorder.append(ch="AIT", src="ALEX", act="ai:alex", ev="DCP", cov="P", payload={"pkt": "d1"})
    record_pubcast_event(recorder, {"event_type": "ai.tool_requested", "source": "alex", "actor": "ai:alex", "data": {"tool": "visual_patch"}})
    recorder.append(ch="APP", src="USR", act="user:owner", ev="APR", cov="F", payload={"request": "tool_1"})
    return recorder


def assert_tamper_cases_fail() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "blackbox.bbx"
        recorder = build_chain(path)
        assert recorder.verify().ok

        original = path.read_text(encoding="utf-8").splitlines()

        path.write_text("\n".join(original[1:]) + "\n", encoding="utf-8")
        assert not recorder.verify().ok, "deleted first record was not detected"

        path.write_text("\n".join([original[1], original[0], *original[2:]]) + "\n", encoding="utf-8")
        assert not recorder.verify().ok, "reordered records were not detected"

        path.write_text("\n".join(line.replace("tool:visual_patch", "tool:other") for line in original) + "\n", encoding="utf-8")
        assert not recorder.verify().ok, "payload edit was not detected"


def assert_report_fact_boundary() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "blackbox.bbx"
        recorder = AppendOnlyBlackBoxRecorder(path, session_id="shoot_01")
        recorder.append(ch="DSC", src="BBX", act="ai:agent_07", ev="CND", cov="F", payload={"kind": "profanity_burst"})
        recorder.crash_position("fatal_exception", {"err": "RuntimeError"})
        report = build_known_record_report(path.read_text(encoding="utf-8").splitlines())
        text = report.to_markdown()
        assert "## Known Record" in text
        assert "## Derived Analysis" in text
        assert "None included" in text
        assert "meant harm" not in text.lower()
        assert "guilty" not in text.lower()


def main() -> None:
    assert_bad_record_raises()
    assert_tamper_cases_fail()
    assert_report_fact_boundary()
    print("blackbox_hardening_check passed")


if __name__ == "__main__":
    main()

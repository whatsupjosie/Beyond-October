"""Decode BlackBox coded records into human-readable reports.

The decoder is allowed to produce English, but it must keep known facts separate
from derived analysis. The primary record remains the compact BBX wire language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List

from blackbox_event_language.schema import decode_record


@dataclass(frozen=True)
class BlackBoxReport:
    known_record: List[str]
    derived_analysis: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    decoded_records: List[Dict[str, Any]] = field(default_factory=list)

    def to_markdown(self) -> str:
        sections = ["# BlackBox Decoded Report", "", "## Known Record"]
        sections.extend(f"- {line}" for line in self.known_record)
        sections.extend(["", "## Derived Analysis"])
        if self.derived_analysis:
            sections.extend(f"- {line}" for line in self.derived_analysis)
        else:
            sections.append("- None included. The primary report contains facts only.")
        sections.extend(["", "## Open Questions"])
        if self.open_questions:
            sections.extend(f"- {line}" for line in self.open_questions)
        else:
            sections.append("- None recorded by decoder.")
        return "\n".join(sections) + "\n"


def decode_lines(lines: Iterable[str]) -> List[Dict[str, Any]]:
    decoded: List[Dict[str, Any]] = []
    for line in lines:
        text = str(line).strip()
        if text:
            decoded.append(decode_record(text))
    return decoded


def _payload_phrase(payload: Dict[str, str]) -> str:
    if not payload:
        return "payload: none"
    parts = [f"{key}={value}" for key, value in sorted(payload.items())]
    return "payload: " + ", ".join(parts)


def _known_sentence(record: Dict[str, Any]) -> str:
    return (
        f"seq {record['seq']} at {record['timestamp']}: "
        f"{record['event']['label']} "
        f"on {record['channel']['label']} "
        f"from {record['source']['label']} "
        f"actor={record['actor']} "
        f"coverage={record['coverage']['code']} "
        f"{_payload_phrase(record['payload'])}."
    )


def build_known_record_report(records: Iterable[str] | Iterable[Dict[str, Any]]) -> BlackBoxReport:
    items = list(records)
    if not items:
        return BlackBoxReport(known_record=["No BlackBox records supplied."])
    if isinstance(items[0], str):
        decoded = decode_lines(items)  # type: ignore[arg-type]
    else:
        decoded = items  # type: ignore[assignment]
    known = [_known_sentence(record) for record in decoded]
    open_questions: List[str] = []
    if any(record["coverage"]["code"] in {"P", "S", "U"} for record in decoded):
        open_questions.append("Some records indicate partial, sampled, or unknown coverage.")
    return BlackBoxReport(known_record=known, open_questions=open_questions, decoded_records=decoded)


def report_from_file(path: Path | str) -> BlackBoxReport:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return build_known_record_report(lines)


__all__ = ["BlackBoxReport", "build_known_record_report", "decode_lines", "report_from_file"]

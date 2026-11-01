"""Command-line administration for PubPartner vessel files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .errors import VesselError
from .runtime import PubPartnerVesselRuntime


def _emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m modules.pubpartner_vessel",
        description="Create, verify, inspect, back up, and correct PubPartner vessels.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create a new vessel exclusively.")
    create.add_argument("path", type=Path)
    create.add_argument("--friend-id", default="alex")
    create.add_argument("--display-name", default="Alex")

    for name in ("verify", "inspect"):
        command = commands.add_parser(name, help=f"{name.title()} a vessel.")
        command.add_argument("path", type=Path)

    backup = commands.add_parser(
        "backup", help="Create a validated, transaction-consistent copy."
    )
    backup.add_argument("path", type=Path)
    backup.add_argument("destination", type=Path)

    claims = commands.add_parser(
        "claims", help="List reviewable memory claims for one user."
    )
    claims.add_argument("path", type=Path)
    claims.add_argument("--subject", required=True)
    claims.add_argument(
        "--status",
        default="all",
        choices=(
            "all",
            "tentative",
            "corroborated",
            "confirmed",
            "rejected",
            "superseded",
        ),
    )
    claims.add_argument("--limit", type=int, default=200)

    correct = commands.add_parser(
        "correct", help="Apply an attributable correction to a memory claim."
    )
    correct.add_argument("path", type=Path)
    correct.add_argument("claim_id")
    correct.add_argument(
        "--action",
        required=True,
        choices=("reject", "confirm", "prohibit_use", "allow_use", "replace", "narrow"),
    )
    correct.add_argument("--reason", required=True)
    correct.add_argument("--replacement-text", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            runtime = PubPartnerVesselRuntime.create(
                args.path,
                identity={
                    "friend_id": str(args.friend_id),
                    "display_name": str(args.display_name),
                },
            )
            _emit({"ok": True, "path": str(args.path.absolute()), **runtime.status()})
            return 0

        read_only = args.command in {"verify", "inspect", "claims"}
        runtime = PubPartnerVesselRuntime.open(args.path, read_only=read_only)
        if args.command == "verify":
            _emit(runtime.status())
        elif args.command == "inspect":
            _emit(
                {
                    "ok": True,
                    "manifest": runtime.store.manifest(),
                    "identity": runtime.store.identity(),
                    "validation": runtime.store.validate(),
                }
            )
        elif args.command == "backup":
            _emit(runtime.store.backup_to(args.destination))
        elif args.command == "claims":
            rows = runtime.memory.list_claims(
                subject_id=str(args.subject),
                status=str(args.status),
                limit=max(1, min(2_000, int(args.limit))),
            )
            _emit(
                {
                    "ok": True,
                    "subject_id": str(args.subject),
                    "claims": [row.to_dict() for row in rows],
                }
            )
        elif args.command == "correct":
            claim = runtime.memory.correct_claim(
                str(args.claim_id),
                action=str(args.action),
                reason=str(args.reason),
                replacement_text=str(args.replacement_text),
            )
            _emit({"ok": True, "claim": claim.to_dict()})
        return 0
    except (VesselError, FileNotFoundError, ValueError, OSError) as exc:
        _emit({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return 2


if __name__ == "__main__":
    sys.exit(main())

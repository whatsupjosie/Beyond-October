#!/usr/bin/env python3
"""Offline checkpoint/verify/restore for PubCast's configured host-data directory."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.data_checkpoint import (CheckpointError, Limits, create_checkpoint,
                                     restore_checkpoint, verify_checkpoint)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    create = subcommands.add_parser("create", help="Checkpoint a stopped host; includes private keys and media")
    create.add_argument("--data-dir", required=True, help="The exact --data-dir used by the host")
    create.add_argument("--output", required=True, help="A NEW ZIP outside that data directory")
    create.add_argument("--offline", action="store_true", help="Confirm every writer to this data directory is stopped")
    create.add_argument("--source-revision", default="", help="Known application revision; empty means unknown")
    verify = subcommands.add_parser("verify", help="Verify inventory, sizes, CRCs and every SHA-256")
    restore = subcommands.add_parser("restore", help="Restore into a NEW directory containing data/ and a receipt")
    for command in (verify, restore):
        command.add_argument("--archive", required=True)
        command.add_argument("--expected-sha256", help="Trusted SHA-256 from the creation receipt")
    restore.add_argument("--destination", required=True, help="A NEW container; the host data will be in its data/ child")
    defaults = Limits()
    for command in (create, verify, restore):
        command.add_argument("--max-files", type=int, default=defaults.max_files)
        command.add_argument("--max-bytes", type=int, default=defaults.max_bytes)
    args = parser.parse_args(argv)
    try:
        limits = Limits(max_files=args.max_files, max_bytes=args.max_bytes)
        if args.command == "create":
            result = create_checkpoint(args.data_dir, args.output, offline=args.offline,
                                       source_revision=args.source_revision, limits=limits)
        elif args.command == "verify":
            result = verify_checkpoint(args.archive, expected_sha256=args.expected_sha256, limits=limits)
        else:
            result = restore_checkpoint(args.archive, args.destination,
                                        expected_sha256=args.expected_sha256, limits=limits)
    except (CheckpointError, OSError, RuntimeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

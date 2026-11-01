"""Local-only command helpers for Iteration Wallet.

This CLI is intentionally conservative. It can talk only to loopback API hosts
and it exposes no delete command.
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import urlparse

import requests

VAULT_API = "http://127.0.0.1:7432/api/v21"
TIMEOUT = 5
LOCAL_API_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _assert_local_vault_api(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOCAL_API_HOSTS:
        raise ValueError(f"Refusing non-local Iteration Wallet API endpoint: {url}")


def _req(method: str, path: str, data=None):
    _assert_local_vault_api(VAULT_API)
    url = VAULT_API + path
    if method == "GET":
        response = requests.get(url, timeout=TIMEOUT)
    elif method == "POST":
        response = requests.post(url, json=data, timeout=TIMEOUT)
    else:
        raise ValueError("Iteration Wallet CLI supports only GET and POST; no DELETE transport path exists")
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    return response.json()


def cmd_status(_args):
    print(json.dumps(_req("GET", "/status"), indent=2))


def cmd_projects(_args):
    print(json.dumps(_req("GET", "/projects"), indent=2))


def cmd_create_project(args):
    print(json.dumps(_req("POST", "/projects", {"name": args.name, "root_path": args.root_path or ""}), indent=2))


def cmd_delete(_args):
    print("Iteration Wallet never deletes. Use remove/quarantine/release workflows with human intent.", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="iw", description="Iteration Wallet local CLI")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("projects").set_defaults(func=cmd_projects)
    p = sub.add_parser("create-project")
    p.add_argument("name")
    p.add_argument("--root-path", default="")
    p.set_defaults(func=cmd_create_project)
    sub.add_parser("delete").set_defaults(func=cmd_delete)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    result = args.func(args)
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())

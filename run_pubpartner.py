#!/usr/bin/env python3
"""Canonical PubPartner local launcher.

Secure defaults:
* binds to loopback unless --allow-network is explicit;
* enables authentication unless --unsafe-no-auth is explicit;
* creates a persistent signing secret without printing it;
* runs preflight before boot;
* opens the browser only after the HTTP server responds.
"""
from __future__ import annotations

import argparse
import os
import secrets
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def _persistent_secret(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        value = secrets.token_urlsafe(64)
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            pass
        try:
            path.chmod(0o600)
        except OSError:
            pass
    value = path.read_text(encoding="utf-8").strip()
    if len(value) < 48:
        raise RuntimeError(f"Signing secret at {path} is invalid or truncated")
    return value


def _open_when_ready(url: str, *, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.75) as response:  # noqa: S310 - fixed local URL
                if response.status < 500:
                    webbrowser.open(url)
                    return
        except Exception:
            time.sleep(0.25)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the PubPartner local friend layer")
    parser.add_argument("--host", default=os.environ.get("PUBPARTNER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PUBPARTNER_PORT", "8000")))
    parser.add_argument("--data-dir", default=os.environ.get("PUBPARTNER_DATA_DIR", "data"))
    parser.add_argument("--preflight", action="store_true", help="run diagnostics and exit")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--unsafe-no-auth", action="store_true", help="development only: disable route authentication")
    parser.add_argument("--allow-network", action="store_true", help="explicitly allow a non-loopback bind")
    args = parser.parse_args()

    if args.port < 1 or args.port > 65535:
        parser.error("--port must be between 1 and 65535")
    if args.host not in _LOOPBACK and not args.allow_network:
        parser.error("Non-loopback binding requires --allow-network")

    root = Path(__file__).resolve().parent
    os.chdir(root)
    data_dir = Path(args.data_dir).expanduser().resolve()
    os.environ.setdefault("PUBPARTNER_DATA_DIR", str(data_dir))
    os.environ.setdefault("PUBCAST_DATA_DIR", str(data_dir))
    os.environ.setdefault("PUBCAST_ENFORCE_AUTH", "0" if args.unsafe_no_auth else "1")
    os.environ.setdefault("PUBPARTNER_ONLY", "1")

    browser_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    local_origin = f"http://{browser_host}:{args.port}"
    os.environ.setdefault("PUBCAST_ALLOWED_ORIGINS", local_origin)
    os.environ.setdefault("PUBCAST_JWT_SECRET", _persistent_secret(data_dir / "pubpartner" / "secure" / "jwt_secret.txt"))

    from modules.pubpartner_preflight import run_preflight, write_report

    report = run_preflight(data_dir=data_dir, app_root=root, host=args.host, port=args.port)
    report_path = data_dir / "pubpartner" / "preflight_latest.json"
    write_report(report, report_path)
    print(report["human_summary"])
    print(f"\nReport: {report_path}")
    print(f"Security: {'RELAXED DEVELOPMENT' if args.unsafe_no_auth else 'AUTHENTICATED LOCAL OWNER MODE'}")

    if args.preflight:
        return 0 if report.get("ok") else 2
    if not report.get("ok"):
        print("\nPreflight found blocking issues. Fix them or run --preflight for details.", file=sys.stderr)
        return 2

    url = f"{local_origin}/pubpartner"
    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()

    import uvicorn

    uvicorn.run("pubpartner_app:app", host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

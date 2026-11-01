#!/usr/bin/env python3
"""Launch the full Reach host at its writing desk, with local owner auth."""
from __future__ import annotations

import argparse
import os
import socket
import shutil
import threading
from pathlib import Path

from run_pubpartner import _open_when_ready, _persistent_secret
from modules.foresight_sidecar import Legacy2iService


_BUILTIN_BOT_CONFIGS = ("pete.json", "jeremy.json", "repeat.json", "sir_purfluous.json")


def _seed_packaged_bot_configs(root: Path, data: Path) -> list[str]:
    """Seed first-run character configs without overwriting user-owned copies."""
    source = root / "data" / "bots"
    destination = data / "bots"
    seeded: list[str] = []
    if not source.is_dir():
        return seeded
    destination.mkdir(parents=True, exist_ok=True)
    for name in _BUILTIN_BOT_CONFIGS:
        src = source / name
        dst = destination / name
        if src.is_file() and not dst.exists():
            shutil.copy2(src, dst)
            seeded.append(name)
    return seeded


def main() -> int:
    parser = argparse.ArgumentParser(description="Open Reach’s writer’s room")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", default="reach_userdata")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--install-legacy-2i", action="store_true", help="explicitly allow installing optional Node utilities; normal startup never downloads them")
    parser.add_argument("--no-legacy-2i", action="store_true", help="skip optional original 2i Node utilities")
    parser.add_argument("--start-page", choices=("foresight", "foresight-counter", "foresight-legacy", "writers-room", "lobby"), default="foresight-counter",
                        help="page to open after Reach starts")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    # Reserve the endpoint before browser polling, so an occupied port cannot
    # send the author to another process while Reach itself fails to start.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if os.name == "nt":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", args.port))
        except OSError as error:
            print(f"Reach cannot use port {args.port}: {error}")
            print("Close the other Reach terminal if it is already running. If another app needs this port, start this installation with --port 8001.")
            return 1
        root = Path(__file__).resolve().parent
        os.chdir(root)
        data = Path(args.data_dir).expanduser().resolve()
        data.mkdir(parents=True, exist_ok=True)
        seeded_bots = _seed_packaged_bot_configs(root, data)
        if seeded_bots:
            print("Seeded built-in characters: " + ", ".join(Path(name).stem for name in seeded_bots))
        # Set these before importing runtime modules that capture their data paths.
        os.environ["PUBCAST_DATA_DIR"] = str(data)
        # Runtime modules and Doctor read PUBCAST_PORT at import/startup time.
        # Keep their status/banner contract aligned with the actual launcher port.
        os.environ["PUBCAST_PORT"] = str(args.port)
        os.environ["PUBCAST_ENFORCE_AUTH"] = "1"
        os.environ.setdefault("PUBCAST_JWT_SECRET", _persistent_secret(data / "secure" / "jwt_secret.txt"))
        os.environ.setdefault("PUBCAST_ALLOWED_ORIGINS", f"http://127.0.0.1:{args.port}")
        start_path = {"foresight": "/foresight", "foresight-counter": "/foresight-counter", "foresight-legacy": "/foresight", "writers-room": "/writers-room", "lobby": "/"}[args.start_page]
        url = f"http://127.0.0.1:{args.port}{start_path}"
        print(f"Reach: {url}\nYour work is saved in: {data}")
        if not args.no_browser:
            threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
        # The UI only speaks same-origin Reach. This subordinate utility process
        # is supervised here, not launched by a second user command.
        sidecar = Legacy2iService(root, data, args.port,
                                  install=args.install_legacy_2i and not args.no_legacy_2i)
        if not args.no_legacy_2i:
            sidecar.start()
        try:
            import uvicorn
            server = uvicorn.Server(uvicorn.Config("main:app", host="127.0.0.1", port=args.port, reload=False))
            # Only this supervised launcher exposes a true application Quit.
            import main
            main.app.state.foresight_request_exit = lambda: setattr(server, "should_exit", True)
            server.run(sockets=[listener])
            return 0 if server.started else 1
        finally:
            sidecar.stop()


if __name__ == "__main__":
    raise SystemExit(main())

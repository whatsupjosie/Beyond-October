"""Explicit owner-only host shell sessions and supervised Reach exit.

The shell is a real host process, not a sandbox or a terminal emulator. Processes
belong to their connection and are stopped on disconnect or application shutdown.
"""

from __future__ import annotations
import asyncio
import os
import signal
import subprocess
import sys
import uuid
import re
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    WebSocket,
)
from .auth import decode_access_token
from .route_security import current_identity


async def owner(identity=Depends(current_identity)):
    if not identity.get("authenticated") or identity.get("role") != "owner":
        raise HTTPException(403, "An authenticated owner is required for host controls")
    return identity


def terminate_tree(process):
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        # Reap the shell even if a child ignores SIGTERM; then kill its process group.
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def create_host_tools_router(data_dir: Path):
    from contextlib import asynccontextmanager

    processes = set()

    @asynccontextmanager
    async def lifecycle(app):
        try:
            yield
        finally:
            await stop_sessions()

    router = APIRouter(
        prefix="/api/foresight/host",
        tags=["Foresight host controls"],
        lifespan=lifecycle,
    )

    async def stop_sessions():
        for process in tuple(processes):
            await asyncio.to_thread(terminate_tree, process)
            processes.discard(process)

    @router.get("/status", dependencies=[Depends(owner)])
    def status(request: Request):
        return {
            "shell_sessions": len(processes),
            "quit_available": callable(
                getattr(request.app.state, "foresight_request_exit", None)
            ),
        }

    @router.post("/quit", dependencies=[Depends(owner)])
    def quit_host(request: Request, background: BackgroundTasks):
        callback = getattr(request.app.state, "foresight_request_exit", None)
        if not callable(callback):
            raise HTTPException(
                409,
                "This host was not started by the supervised Reach launcher. Stop it from its launch terminal.",
            )

        async def finish():
            await stop_sessions()
            callback()

        background.add_task(finish)
        return {"status": "quitting"}

    @router.websocket("/shell")
    async def shell(ws: WebSocket):
        origin = ws.headers.get("origin", "")
        allowed = {
            v.strip()
            for v in os.getenv("PUBCAST_ALLOWED_ORIGINS", "").split(",")
            if v.strip()
        }
        allowed.add(f"{ws.url.scheme.replace('ws', 'http')}://{ws.headers.get('host')}")
        if origin not in allowed:
            await ws.close(code=1008)
            return
        await ws.accept()
        process = None
        output = None
        lock = asyncio.Lock()

        async def send(data):
            async with lock:
                await ws.send_json(data)

        try:
            hello = await asyncio.wait_for(ws.receive_json(), timeout=10)
            if not isinstance(hello, dict):
                await ws.close(code=1008)
                return
            payload = decode_access_token(str(hello.get("token", "")))
            if not payload or payload.get("role") != "owner":
                await ws.close(code=1008)
                return
            work = Path(data_dir) / "workspace"
            work.mkdir(parents=True, exist_ok=True)
            command = (
                [os.environ.get("COMSPEC", "cmd.exe"), "/Q"]
                if os.name == "nt"
                else ["/bin/bash", "--noprofile", "--norc"]
            )
            mode = "shell-pipes"
            if hello.get("mode") == "python":
                source = hello.get("source")
                if not isinstance(source, str) or len(source) > 5 * 1024 * 1024:
                    await ws.close(code=1009)
                    return
                name = re.sub(
                    r"[^A-Za-z0-9_.-]", "_", str(hello.get("name") or "script.py")
                )[-120:]
                if not name.endswith(".py"):
                    name += ".py"
                work = work / "runs" / uuid.uuid4().hex
                work.mkdir(parents=True, exist_ok=True)
                script = work / name
                with script.open("w", encoding="utf-8", newline="") as f:
                    f.write(source)
                    f.flush()
                    os.fsync(f.fileno())
                command = [sys.executable, "-u", str(script)]
                mode = "python"
            options = (
                {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                if os.name == "nt"
                else {"start_new_session": True}
            )
            process = subprocess.Popen(
                command,
                cwd=work,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
                **options,
            )
            processes.add(process)
            await send(
                {
                    "type": "started",
                    "cwd": str(work),
                    "pid": process.pid,
                    "mode": mode,
                }
            )

            async def pump():
                import codecs

                decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
                while True:
                    chunk = await asyncio.to_thread(
                        os.read, process.stdout.fileno(), 4096
                    )
                    if not chunk:
                        break
                    await send({"type": "output", "text": decoder.decode(chunk)})
                tail = decoder.decode(b"", final=True)
                if tail:
                    await send({"type": "output", "text": tail})
                await asyncio.to_thread(process.wait)
                await send({"type": "exited", "code": process.returncode})
                await ws.close()

            output = asyncio.create_task(pump())
            while True:
                message = await ws.receive_json()
                if not isinstance(message, dict):
                    await ws.close(code=1008)
                    break
                if message.get("type") == "stop":
                    break
                if message.get("type") != "input":
                    continue
                text = message.get("text")
                if not isinstance(text, str) or len(text) > 65536:
                    await ws.close(code=1009)
                    break
                if process.poll() is not None:
                    break
                await asyncio.to_thread(process.stdin.write, text.encode("utf-8"))
        except (asyncio.TimeoutError, ValueError, RuntimeError, OSError):
            pass
        except Exception as exc:
            from starlette.websockets import WebSocketDisconnect

            if not isinstance(exc, WebSocketDisconnect):
                raise
        finally:
            # Disconnect cancels the request scope. Cleanup must outlive that cancellation.
            import anyio

            with anyio.CancelScope(shield=True):
                if output:
                    output.cancel()
                    await asyncio.gather(output, return_exceptions=True)
                if process is not None:
                    await asyncio.to_thread(terminate_tree, process)
                    processes.discard(process)
                    for pipe in (process.stdin, process.stdout):
                        if pipe:
                            pipe.close()
                try:
                    await ws.close()
                except (RuntimeError, OSError):
                    pass

    router.stop_owned_sessions = stop_sessions
    return router

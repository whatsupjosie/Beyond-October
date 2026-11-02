"""Bounded, reusable speech workers with real cancellation and no startup load.

One process belongs to one engine configuration. Requests never queue behind an
unknown amount of model work. Cancellation/timeout terminates only that request's
worker; the next request can start a fresh process. No model download occurs here.
"""
from __future__ import annotations

import asyncio
import contextlib
import multiprocessing
import os
import signal
import subprocess
import threading
import time
import uuid
from typing import Any


class SpeechInputError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def failure(message: str, status: int, code: str) -> dict:
    return {"ok": False, "error": message, "status_code": status, "code": code}


def _run(connection, provider: str, config: dict) -> None:
    if os.name != "nt":
        os.setsid()  # Native provider subprocesses belong to this owned group.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["OMP_NUM_THREADS"] = str(config.get("threads", 2))
    # Static imports only: callers cannot nominate a module or callable.
    if provider == "stt":
        from .stt_engine import _transcribe_worker as handler
    elif provider == "tts":
        from .tts_engine import _synthesize_worker as handler
    else:
        connection.close()
        return
    try:
        while True:
            try:
                message = connection.recv()
            except EOFError:
                return
            if message is None:
                return
            try:
                result = handler(message["payload"], config)
            except SpeechInputError as error:
                result = failure(str(error), error.status, "invalid_input")
            except ImportError:
                result = failure("The selected local speech dependency is unavailable", 503, "dependency_missing")
            except Exception as error:
                # Library messages can include private text or filesystem paths.
                # Keep the concrete exception type, never log the request itself.
                result = failure(f"Local speech backend failed ({type(error).__name__})", 503, "backend_failure")
            connection.send({"request_id": message["request_id"], "result": result})
    except (BrokenPipeError, EOFError, OSError):
        return
    finally:
        connection.close()


class SpeechWorker:
    def __init__(self, provider: str, config: dict, *, timeout: float = 90):
        self.provider = provider
        self.config = dict(config)
        self.timeout = timeout
        self._lock = threading.RLock()
        self._process = None
        self._connection = None
        self._request_id: str | None = None
        self._canceled_id: str | None = None
        self.loaded = False
        self.last_error: str | None = None

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._request_id is not None

    @property
    def pid(self) -> int | None:
        with self._lock:
            return self._process.pid if self._process and self._process.is_alive() else None

    def state(self) -> dict:
        with self._lock:
            if self._process is not None and not self._process.is_alive():
                self.loaded = False
            return {"loaded": self.loaded, "busy": self._request_id is not None,
                    "last_error": self.last_error}

    def _start_locked(self) -> None:
        if self._process is not None and self._process.is_alive():
            return
        self._dispose_locked()
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(target=_run, args=(child, self.provider, self.config), daemon=True,
                                  name="pubcast-" + self.provider)
        try:
            process.start()
        except BaseException:
            parent.close()
            child.close()
            raise
        child.close()
        self._connection, self._process = parent, process

    def _dispose_locked(self) -> None:
        process, connection = self._process, self._connection
        self._process, self._connection = None, None
        self.loaded = False
        if process is not None:
            if process.is_alive():
                if os.name == "nt":
                    try:
                        subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                                       capture_output=True, timeout=5)
                    except (OSError, subprocess.SubprocessError):
                        pass
                else:
                    with contextlib.suppress(ProcessLookupError, PermissionError):
                        os.killpg(process.pid, signal.SIGTERM)
                if process.is_alive():
                    process.terminate()
            process.join(timeout=3)
            if os.name != "nt":
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(process.pid, signal.SIGKILL)
            if process.is_alive():
                process.kill()
                process.join(timeout=3)
            if not process.is_alive():
                process.close()
        if connection is not None:
            connection.close()

    def cancel(self, request_id: str) -> None:
        with self._lock:
            # A late cancellation must never kill a newer request's process.
            if self._request_id == request_id:
                self._canceled_id = request_id
                self._dispose_locked()

    def _call_sync(self, request_id: str, payload: dict) -> dict:
        started = time.monotonic()
        try:
            with self._lock:
                if self._request_id != request_id or self._canceled_id == request_id:
                    return failure("Speech request canceled", 499, "canceled")
                self._start_locked()
                connection = self._connection
            # Do not hold the lifecycle lock during pipe I/O: cancellation must
            # be able to terminate a worker that stalls before reading input.
            connection.send({"request_id": request_id, "payload": payload})
            if not connection.poll(self.timeout):
                self.cancel(request_id)
                return failure("Local speech request exceeded its time limit", 504, "timeout")
            message = connection.recv()
            if message.get("request_id") != request_id:
                self.cancel(request_id)
                return failure("Speech worker returned an invalid receipt", 503, "invalid_receipt")
            result = message["result"]
            with self._lock:
                if self._request_id != request_id or self._canceled_id == request_id or self._connection is not connection:
                    return failure("Speech request canceled", 499, "canceled")
                self.loaded = bool(result.pop("_loaded", self.loaded))
                self.last_error = (result.get("code", "backend_failure")
                                   if not result.get("ok") and result.get("status_code", 500) >= 500 else None)
            result["latency_ms"] = round((time.monotonic() - started) * 1000)
            return result
        except (OSError, EOFError, BrokenPipeError, ValueError) as error:
            self.cancel(request_id)
            return failure(f"Speech worker stopped ({type(error).__name__})", 503, "worker_stopped")
        finally:
            with self._lock:
                if self._request_id == request_id:
                    self._request_id = None
                if self._canceled_id == request_id:
                    self._canceled_id = None

    async def call(self, payload: dict) -> dict:
        request_id = uuid.uuid4().hex
        with self._lock:
            if self._request_id is not None:
                return failure("Local speech engine is busy; try again shortly", 429, "busy")
            self._request_id = request_id
        try:
            future = asyncio.get_running_loop().run_in_executor(None, self._call_sync, request_id, payload)
        except BaseException:
            with self._lock:
                if self._request_id == request_id:
                    self._request_id = None
            raise
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            # Shield keeps the supervising thread alive to clean up its receipt.
            await asyncio.to_thread(self.cancel, request_id)
            with contextlib.suppress(Exception):
                await asyncio.shield(future)
            raise

    async def close(self) -> None:
        def reset():
            with self._lock:
                self._canceled_id = self._request_id
                # Let an idle provider release its own native resources first.
                if self._request_id is None and self._connection is not None:
                    with contextlib.suppress(OSError, EOFError):
                        self._connection.send(None)
                        self._process.join(timeout=2)
                self._dispose_locked()
        await asyncio.to_thread(reset)


async def run_for_request(request, operation) -> Any:
    """Stop actual model computation when the HTTP caller disconnects."""
    task = asyncio.create_task(operation)

    async def disconnected():
        # Routes consume the complete body before entering here. Await the next
        # receive directly: is_disconnected's zero-time CancelScope can cancel
        # a BaseHTTPMiddleware memory channel before it delivers a disconnect.
        while True:
            message = await request.receive()
            if message["type"] == "http.disconnect":
                return
            await asyncio.sleep(0)

    watcher = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait((task, watcher), return_when=asyncio.FIRST_COMPLETED)
        if watcher in done:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            return failure("Speech request canceled", 499, "canceled")
        return await task
    finally:
        watcher.cancel()
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        with contextlib.suppress(asyncio.CancelledError):
            await watcher

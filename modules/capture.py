"""
modules/capture.py  —  PubCast AI FFmpeg Capture Engine
=========================================================
Sits alongside RecordingService. When a session is ACTIVE,
FFmpegCaptureEngine spawns one FFmpeg process per source,
writes real media files into the session directory, and
registers them as RecordingArtifacts when stopped.

Transport → FFmpeg input mapping
---------------------------------
  virtual      → lavfi testsrc (safe fallback, always works)
  file         → -i <endpoint>
  rtmp         → -i rtmp://...
  srt          → -i srt://...
  ndi          → -i 'device_name()=<endpoint>' via libndi_newtek (if available)
  voxel_3d     → -i <endpoint> (TCP stream from Rust renderer)

Environment:
  PUBCAST_FFMPEG   path to ffmpeg binary  (default: ffmpeg on PATH)
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
import time
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .recording import RecordingState

logger = logging.getLogger(__name__)

# ── FFmpeg resolution ──────────────────────────────────────────────────────────
def _ffmpeg_bin() -> str:
    env = os.environ.get("PUBCAST_FFMPEG", "")
    if env and Path(env).is_file():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise EnvironmentError(
        "ffmpeg not found. Install ffmpeg and ensure it is on PATH, "
        "or set the PUBCAST_FFMPEG environment variable to the binary path."
    )


# ── Transport → FFmpeg input builder ─────────────────────────────────────────
def _build_ffmpeg_input(transport: str, endpoint: str) -> List[str]:
    """Return the FFmpeg input argument list for a given camera source."""
    t = transport.lower()

    if t == "virtual":
        # Lavfi test pattern — reliable fallback that always works
        return ["-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30"]

    if t == "file":
        return ["-re", "-i", endpoint]          # -re = real-time read-back

    if t in ("rtmp", "srt"):
        return ["-i", endpoint]

    if t == "ndi":
        # Requires FFmpeg built with libndi_newtek
        return ["-f", "libndi_newtek", "-i", endpoint]

    if t == "voxel_3d":
        # TCP stream from the Rust/Voxel renderer
        return ["-i", endpoint]

    # Unknown — try as raw input and hope for the best
    logger.warning("Unknown transport '%s' for endpoint '%s' — using raw -i", t, endpoint)
    return ["-i", endpoint]


def _ffmpeg_bitrate(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    clean = str(value).strip()
    lower = clean.lower()
    if lower.endswith("mbps"):
        return clean[:-4] + "M"
    if lower.endswith("kbps"):
        return clean[:-4] + "k"
    return clean


# ── Encoding profile → FFmpeg output args ─────────────────────────────────────
def _build_ffmpeg_output(profile, output_path: Path) -> List[str]:
    """Return FFmpeg codec/output arguments from an EncodingProfile."""
    args: List[str] = []

    if profile.video_codec and not profile.is_audio_only:
        video_codec = "libx264" if profile.video_codec == "h264" else profile.video_codec
        args += ["-c:v", video_codec]
        video_bitrate = _ffmpeg_bitrate(profile.video_bitrate)
        if video_bitrate:
            args += ["-b:v", video_bitrate]
        if profile.resolution:
            w, h = profile.resolution.split("x")
            args += ["-s", f"{w}x{h}"]
        if profile.frame_rate:
            args += ["-r", profile.frame_rate]
        if video_codec == "libx264":
            args += ["-pix_fmt", "yuv420p"]
    else:
        args += ["-vn"]   # no video

    if profile.audio_codec:
        args += ["-c:a", profile.audio_codec]
        audio_bitrate = _ffmpeg_bitrate(profile.audio_bitrate)
        if audio_bitrate:
            args += ["-b:a", audio_bitrate]
    else:
        args += ["-an"]

    args.append(str(output_path))
    return args


# ── Per-source process handle ─────────────────────────────────────────────────
@dataclass
class _CaptureProcess:
    source_id: str
    output_path: Path
    proc: asyncio.subprocess.Process
    started_at: float = field(default_factory=time.time)

    paused: bool = False

    def set_paused(self, paused: bool) -> None:
        if self.paused == paused:
            return
        if self.proc.returncode is not None:
            raise RuntimeError(f"Encoder for {self.source_id} has already stopped")
        sig = getattr(signal, "SIGSTOP" if paused else "SIGCONT", None)
        if sig is None:
            raise NotImplementedError("This platform cannot suspend an active FFmpeg capture")
        self.proc.send_signal(sig)
        self.paused = paused

    async def terminate(self) -> None:
        if self.proc.returncode is None:
            try:
                if self.paused:
                    try:
                        self.set_paused(False)
                    except ProcessLookupError:
                        pass
                if self.proc.stdin:
                    self.proc.stdin.write(b"q")
                    await self.proc.stdin.drain()
                await asyncio.wait_for(self.proc.wait(), timeout=8.0)
            except asyncio.TimeoutError:
                try:
                    self.proc.terminate()
                    await asyncio.wait_for(self.proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self.proc.kill()
                    await self.proc.wait()
            except (BrokenPipeError, ConnectionResetError):
                await self.proc.wait()
        logger.info("Capture process for %s finished (rc=%s)", self.source_id, self.proc.returncode)


# ── Capture Engine ────────────────────────────────────────────────────────────
class FFmpegCaptureEngine:
    """
    Manages FFmpeg processes for active recording sessions.
    One engine instance lives for the lifetime of the server.
    """

    def __init__(self) -> None:
        self.errors: Dict[str, Dict[str, str]] = {}
        self._active: Dict[str, List[_CaptureProcess]] = {}   # session_id → [processes]
        try:
            self._bin = _ffmpeg_bin()
            logger.info("FFmpegCaptureEngine ready: %s", self._bin)
        except EnvironmentError as e:
            self._bin = None
            logger.warning("FFmpegCaptureEngine: %s  —  capture disabled.", e)

    @property
    def available(self) -> bool:
        return self._bin is not None

    # ── Public API ─────────────────────────────────────────────────────────────
    async def start(
        self,
        session_id: str,
        sources,          # list of CameraSource objects
        profile,          # EncodingProfile object
        session_dir: Path,
    ) -> List[Path]:
        """
        Spawn one FFmpeg process per source.
        Returns list of output file paths (one per source).
        """
        if not self.available:
            logger.warning("FFmpeg not available — session %s will have no media.", session_id)
            return []

        if session_id in self._active:
            logger.warning("Session %s already capturing — ignoring duplicate start.", session_id)
            return [cp.output_path for cp in self._active[session_id]]

        procs: List[_CaptureProcess] = []
        output_paths: List[Path] = []

        reserved_names = {p.name.casefold() for p in session_dir.iterdir()}
        for src in sources:
            ext = profile.container.value          # mp4 / webm / wav / mov
            safe_name = src.source_id.replace("/", "_").replace("\\", "_").replace(":", "_")
            out_path = session_dir / f"{safe_name}.{ext}"
            suffix = 2
            while out_path.name.casefold() in reserved_names:
                out_path = session_dir / f"{safe_name}-{suffix}.{ext}"
                suffix += 1
            reserved_names.add(out_path.name.casefold())

            input_args  = _build_ffmpeg_input(src.transport.value, src.endpoint)
            output_args = _build_ffmpeg_output(profile, out_path)

            cmd = [self._bin, "-n"] + input_args + output_args
            logger.info("FFmpeg cmd for %s: %s", src.source_id, " ".join(cmd))

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                cp = _CaptureProcess(
                    source_id=src.source_id,
                    output_path=out_path,
                    proc=proc,
                )
                procs.append(cp)
                output_paths.append(out_path)
                logger.info("Capture started for %s → %s (pid=%d)", src.source_id, out_path, proc.pid)

            except Exception as e:
                self.errors.setdefault(session_id, {})[src.source_id] = "Encoder could not start"
                logger.error("Failed to start FFmpeg for %s: %s", src.source_id, e)

        if procs:
            self._active[session_id] = procs

        return output_paths

    async def stop(self, session_id: str) -> List[Path]:
        """
        Terminate all FFmpeg processes for a session.
        Returns list of completed output file paths.
        """
        procs = self._active.get(session_id, [])
        output_paths: List[Path] = []
        results = await asyncio.gather(*(cp.terminate() for cp in procs), return_exceptions=True)
        for cp, result in zip(procs, results):
            has_bytes = cp.output_path.is_file() and cp.output_path.stat().st_size > 0
            if isinstance(result, BaseException) or cp.proc.returncode != 0 or not has_bytes:
                detail = (f"Encoder exited with status {cp.proc.returncode}" if cp.proc.returncode is not None
                          else "Encoder termination could not be confirmed")
                detail += "; partial bytes retained" if has_bytes else "; no recorded media"
                self.errors.setdefault(session_id, {})[cp.source_id] = detail
                logger.warning("Capture %s/%s: %s", session_id, cp.source_id, detail)
            if has_bytes and cp.proc.returncode is not None:
                output_paths.append(cp.output_path)
        remaining = [cp for cp in procs if cp.proc.returncode is None]
        if remaining:
            self._active[session_id] = remaining
        else:
            self._active.pop(session_id, None)
        return output_paths

    def set_paused(self, session_id: str, paused: bool) -> None:
        changed = []
        try:
            for cp in self._active.get(session_id, []):
                if cp.paused != paused:
                    cp.set_paused(paused)
                    changed.append(cp)
        except Exception:
            for cp in reversed(changed):
                try:
                    cp.set_paused(not paused)
                except (RuntimeError, OSError):
                    logger.exception("Failed to restore encoder state for %s", cp.source_id)
            raise

    async def pause(self, session_id: str) -> None:
        self.set_paused(session_id, True)

    async def resume(self, session_id: str) -> None:
        self.set_paused(session_id, False)

    def is_capturing(self, session_id: str) -> bool:
        return session_id in self._active

    def active_sessions(self) -> List[str]:
        return list(self._active.keys())

    async def shutdown(self) -> None:
        """Graceful shutdown — stop all active captures."""
        for sid in list(self._active.keys()):
            await self.stop(sid)
        logger.info("FFmpegCaptureEngine shut down.")


class SessionCapture:
    """One host-owned encoder registry for API, console, and timeline takes."""

    def __init__(self, cameras, recording):
        self.cameras = cameras
        self.recording = recording
        self.engine = FFmpegCaptureEngine()
        self._locks = weakref.WeakValueDictionary()
        self._unregistered: Dict[str, List[Path]] = {}

    async def start(self, session) -> List[str]:
        async with self._locks.setdefault(session.session_id, asyncio.Lock()):
            return await self._start(session)

    async def _start(self, session) -> List[str]:
        if session.state != RecordingState.ACTIVE:
            return []
        if not self.engine.available:
            self.recording.note_capture_errors(session.session_id, {
                source_id: "FFmpeg unavailable; no capture started" for source_id in session.sources
            })
            return []
        source_objects = [self.cameras.get(source_id) for source_id in session.sources]
        source_objects = [source for source in source_objects if source is not None]
        if not source_objects:
            return []
        profile = self.recording.get_profile(session.profile_id)
        session_dir = self.recording._session_dir(session.session_id)
        paths = await self.engine.start(session.session_id, source_objects, profile, session_dir)
        if self.engine.errors.get(session.session_id):
            self.recording.note_capture_errors(session.session_id, self.engine.errors[session.session_id])
        return [str(path) for path in paths]

    async def set_paused(self, session_id: str, paused: bool):
        async with self._locks.setdefault(session_id, asyncio.Lock()):
            session = self.recording.get_session(session_id)
            if session.state not in {RecordingState.ACTIVE, RecordingState.PAUSED}:
                raise ValueError("Cannot pause a session that is not active")
            was_paused = session.state == RecordingState.PAUSED
            self.engine.set_paused(session_id, paused)
            try:
                return self.recording.pause_session(session_id, paused)
            except Exception:
                self.engine.set_paused(session_id, was_paused)
                raise

    async def finish(self, session_id: str) -> List[Dict[str, Any]]:
        async with self._locks.setdefault(session_id, asyncio.Lock()):
            return await self._finish(session_id)

    async def _finish(self, session_id: str) -> List[Dict[str, Any]]:
        pending = self._unregistered.setdefault(session_id, [])
        if self.engine.is_capturing(session_id):
            pending.extend(await self.engine.stop(session_id))
        errors = self.engine.errors.get(session_id)
        if errors:
            self.recording.note_capture_errors(session_id, errors)
            self.engine.errors.pop(session_id, None)
        if self.engine.is_capturing(session_id):
            raise RuntimeError("One or more encoders are still running")
        artifacts = []
        for path in pending.copy():
            # Leave a completed file queued on a registration failure. The
            # caller sees the failure and a retry uses the existing bytes.
            artifact = self.recording.register_artifact(session_id, path)
            pending.remove(path)
            artifacts.append({
                "name": artifact.name,
                "format": artifact.format.value,
                "file_path": artifact.file_path.as_posix(),
                "size_bytes": artifact.size_bytes,
            })
        self._unregistered.pop(session_id, None)
        return artifacts

    async def shutdown(self) -> None:
        for session_id in set(self.engine.active_sessions()).union(self._unregistered):
            try:
                await self.finish(session_id)
                self.recording.stop_session(session_id)
            except Exception:
                logger.exception("Could not finalize capture %s on shutdown", session_id)

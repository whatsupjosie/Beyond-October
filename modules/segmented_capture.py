"""
modules/segmented_capture.py — crash-tolerant segmented capture for PubCast
==========================================================================

Why this exists
---------------
``modules/capture.py`` records one monolithic file per source. A monolithic MP4
is unreadable until FFmpeg finalizes it, so a crash loses the whole take and a
time range can never be copied out while recording continues. This module
records the same kinds of inputs into short, independently finalized Matroska
segments and keeps a tamper-evident index that maps every segment to real UTC
time. ``modules/range_preservation.py`` uses that index to copy any time range
into a separate file without touching the originals.

Guarantees
----------
* A segment enters the index only after FFmpeg has closed it (FFmpeg writes the
  segment-list entry on close). Its size and SHA-256 are recorded at that moment.
* The index is append-only JSON lines. Every record carries the hash of the
  previous record, so any edit, deletion or reordering is detectable with
  :func:`verify_index`.
* UTC times come from a monotonic clock anchored once per process, so NTP steps
  and daylight-saving changes cannot move recorded times. Each segment's anchor
  is fitted from FFmpeg's own progress reports made while that segment was open,
  which also absorbs slow drift between the device clock and the system clock.
  The spread of those reports is stored as a declared timing uncertainty.
* Liveness is measured, not configured: ``status()`` reports ``recording`` only
  while FFmpeg's output media time keeps advancing. A healthy process that has
  stopped producing media reports ``stalled``.
* A crash is reported as a crash. The unfinished segment is probed; whatever is
  readable is indexed as ``partial`` and anything unreadable is indexed as a
  ``lost`` interval. Nothing is silently dropped or invented.
* Optional bounded auto-restart. Every restart is a new run, so the gap is
  visible to range preservation instead of being stitched over.
* One recorder per capture directory, enforced with an OS file lock that is
  released automatically if the process dies.

Worst-case loss on a hard crash is one segment (``segment_seconds``).

Environment:
  PUBCAST_FFMPEG / PUBCAST_FFPROBE  explicit binaries (default: on PATH)
"""
from __future__ import annotations

import asyncio
import contextlib
import csv
import hashlib
import io
import json
import logging
import os
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

logger = logging.getLogger("pubcast.segmented_capture")

INDEX_FILENAME = "index.jsonl"
LOCK_FILENAME = "recorder.lock"
RUNS_DIRNAME = "runs"
SEGMENT_LIST_NAME = "segments.csv"
FFMPEG_LOG_NAME = "ffmpeg.log"
SEGMENT_PATTERN = "seg_%06d.{ext}"
GENESIS_HASH = "0" * 64
INDEX_SCHEMA = 1

STATE_IDLE = "idle"
STATE_STARTING = "starting"
STATE_RECORDING = "recording"
STATE_STALLED = "stalled"
STATE_RESTARTING = "restarting"
STATE_CRASHED = "crashed"
STATE_STOPPED = "stopped"


# ── Errors ─────────────────────────────────────────────────────────────────────
class CaptureError(RuntimeError):
    """Base error for segmented capture."""


class CaptureUnavailableError(CaptureError):
    """FFmpeg/FFprobe could not be found."""


class CaptureLockedError(CaptureError):
    """Another recorder already owns this capture directory."""


class CaptureStateError(CaptureError):
    """Operation not valid in the recorder's current state."""


class IndexIntegrityError(CaptureError):
    """The index hash chain does not verify."""


# ── Binaries ───────────────────────────────────────────────────────────────────
def _resolve_binary(env_name: str, default_name: str) -> str:
    explicit = os.environ.get(env_name, "").strip()
    if explicit:
        if Path(explicit).is_file():
            return explicit
        raise CaptureUnavailableError(f"{env_name} points to a missing file: {explicit}")
    found = shutil.which(default_name)
    if found:
        return found
    raise CaptureUnavailableError(
        f"{default_name} not found on PATH. Install FFmpeg or set {env_name} to the binary path."
    )


def ffmpeg_binary() -> str:
    return _resolve_binary("PUBCAST_FFMPEG", "ffmpeg")


def ffprobe_binary() -> str:
    return _resolve_binary("PUBCAST_FFPROBE", "ffprobe")


# ── Clock ──────────────────────────────────────────────────────────────────────
class MonotonicUTCClock:
    """UTC derived from a single wall-clock reading plus the monotonic clock.

    Wall-clock steps (NTP corrections, manual changes) after construction do not
    affect returned times. UTC has no daylight saving, so DST never moves it.
    """

    def __init__(self) -> None:
        self._wall0 = time.time()
        self._mono0 = time.monotonic()

    def now(self) -> float:
        return self._wall0 + (time.monotonic() - self._mono0)

    def at(self, mono: float) -> float:
        return self._wall0 + (mono - self._mono0)


def utc_iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_utc(value: Any) -> float:
    """Accept epoch seconds, an aware datetime, or an ISO-8601 string with offset/Z."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("naive datetime is ambiguous; supply a timezone-aware value")
        return value.timestamp()
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp without offset is ambiguous: {value!r}")
    return parsed.timestamp()


# ── Exclusive directory lock (released by the OS if the process dies) ──────────
class _ExclusiveFileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh: Optional[io.BufferedRandom] = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+b")
        try:
            if sys.platform == "win32":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            fh.close()
            raise CaptureLockedError(f"capture directory is in use by another recorder: {self.path.parent}") from exc
        fh.seek(0)
        fh.truncate()
        fh.write(f"{os.getpid()}\n".encode())
        fh.flush()
        self._fh = fh

    def release(self) -> None:
        fh, self._fh = self._fh, None
        if fh is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


# ── Tamper-evident index ───────────────────────────────────────────────────────
def _canonical(record: Mapping[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _chain_hash(prev: str, body: Mapping[str, Any]) -> str:
    return hashlib.sha256((prev + _canonical(body)).encode("utf-8")).hexdigest()


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class IndexVerification:
    ok: bool
    records: int
    head: str
    error: Optional[str] = None


def verify_index(index_path: Path) -> IndexVerification:
    """Recompute the hash chain of an index file."""
    prev = GENESIS_HASH
    count = 0
    if not index_path.exists():
        return IndexVerification(True, 0, prev)
    with open(index_path, "r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                return IndexVerification(False, count, prev, f"line {line_no}: not valid JSON")
            claimed = record.pop("h", None)
            if record.get("prev") != prev:
                return IndexVerification(False, count, prev, f"line {line_no}: chain break (prev mismatch)")
            if claimed != _chain_hash(prev, record):
                return IndexVerification(False, count, prev, f"line {line_no}: record hash mismatch")
            prev = claimed
            count += 1
    return IndexVerification(True, count, prev)


class CaptureIndex:
    """Append-only, hash-chained JSON-lines index of runs and segments."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.path = self.root / INDEX_FILENAME
        self._lock = threading.Lock()
        self.root.mkdir(parents=True, exist_ok=True)
        check = verify_index(self.path)
        if not check.ok:
            raise IndexIntegrityError(f"{self.path}: {check.error}")
        self._head = check.head
        self._count = check.records

    @property
    def head(self) -> str:
        return self._head

    def append(self, record_type: str, **fields: Any) -> Dict[str, Any]:
        with self._lock:
            body = {"schema": INDEX_SCHEMA, "type": record_type, "prev": self._head, **fields}
            digest = _chain_hash(self._head, body)
            line = _canonical({**body, "h": digest}) + "\n"
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
            self._head = digest
            self._count += 1
            return {**body, "h": digest}

    def records(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out: List[Dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out


@dataclass(frozen=True)
class IndexedSegment:
    run_id: str
    seq: int
    path: Path
    utc_start: float
    utc_end: float
    sha256: str
    size: int
    status: str  # "final" | "partial"
    timing_uncertainty_s: float

    @property
    def duration(self) -> float:
        return self.utc_end - self.utc_start


@dataclass(frozen=True)
class LostInterval:
    run_id: str
    utc_start: float
    utc_end: float
    reason: str


@dataclass
class IndexSnapshot:
    segments: List[IndexedSegment]
    lost: List[LostInterval]
    runs: Dict[str, Dict[str, Any]]


def load_snapshot(root: Path) -> IndexSnapshot:
    """Read and verify an index, returning segments ordered by UTC start."""
    root = Path(root)
    check = verify_index(root / INDEX_FILENAME)
    if not check.ok:
        raise IndexIntegrityError(f"{root / INDEX_FILENAME}: {check.error}")
    segments: List[IndexedSegment] = []
    lost: List[LostInterval] = []
    runs: Dict[str, Dict[str, Any]] = {}
    for record in CaptureIndex(root).records():
        kind = record.get("type")
        if kind == "run_start":
            runs[record["run_id"]] = {"start": record, "end": None}
        elif kind == "run_end":
            runs.setdefault(record["run_id"], {"start": None, "end": None})["end"] = record
        elif kind == "segment":
            segments.append(
                IndexedSegment(
                    run_id=record["run_id"],
                    seq=int(record["seq"]),
                    path=root / record["file"],
                    utc_start=float(record["utc_start"]),
                    utc_end=float(record["utc_end"]),
                    sha256=record["sha256"],
                    size=int(record["size"]),
                    status=record.get("status", "final"),
                    timing_uncertainty_s=float(record.get("timing_uncertainty_s", 0.0)),
                )
            )
        elif kind == "lost":
            lost.append(
                LostInterval(
                    run_id=record["run_id"],
                    utc_start=float(record["utc_start"]),
                    utc_end=float(record["utc_end"]),
                    reason=record.get("reason", "unknown"),
                )
            )
    segments.sort(key=lambda s: (s.utc_start, s.run_id, s.seq))
    lost.sort(key=lambda item: item.utc_start)
    return IndexSnapshot(segments=segments, lost=lost, runs=runs)


# ── Probing ────────────────────────────────────────────────────────────────────
def probe_duration(path: Path, ffprobe: Optional[str] = None) -> Optional[float]:
    """Return the decodable duration of a media file, or None if unreadable."""
    try:
        if not path.exists() or path.stat().st_size == 0:
            return None
        proc = subprocess.run(
            [ffprobe or ffprobe_binary(), "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    try:
        value = float(proc.stdout.strip())
    except ValueError:
        return None
    return value if value > 0 else None


# ── Input / output specification ──────────────────────────────────────────────
@dataclass(frozen=True)
class CaptureSpec:
    """What to record and how to encode it.

    ``input_args`` is the complete FFmpeg input section (everything before the
    output options), e.g. ``["-f", "dshow", "-i", "audio=Microphone (Realtek)"]``.
    """

    source_id: str
    input_args: Tuple[str, ...]
    audio_codec: Optional[str] = "aac"
    audio_bitrate: Optional[str] = "192k"
    audio_channels: Optional[int] = None
    sample_rate: Optional[int] = 48000
    video_codec: Optional[str] = None
    video_bitrate: Optional[str] = None
    frame_rate: Optional[int] = None
    keyframe_seconds: float = 1.0

    @property
    def has_video(self) -> bool:
        return bool(self.video_codec)

    @property
    def extension(self) -> str:
        return "mkv" if self.has_video else "mka"

    def output_args(self) -> List[str]:
        args: List[str] = []
        if self.has_video:
            codec = "libx264" if self.video_codec == "h264" else str(self.video_codec)
            args += ["-c:v", codec]
            if self.video_bitrate:
                args += ["-b:v", self.video_bitrate]
            if self.frame_rate:
                args += ["-r", str(self.frame_rate)]
            if codec == "libx264":
                args += ["-pix_fmt", "yuv420p", "-preset", "veryfast"]
            # Keyframes on a fixed cadence bound the inaccuracy of stream-copy cuts.
            args += ["-force_key_frames", f"expr:gte(t,n_forced*{self.keyframe_seconds:g})"]
        else:
            args += ["-vn"]
        if self.audio_codec:
            args += ["-c:a", self.audio_codec]
            if self.audio_bitrate:
                args += ["-b:a", self.audio_bitrate]
            if self.sample_rate:
                args += ["-ar", str(self.sample_rate)]
            if self.audio_channels:
                args += ["-ac", str(self.audio_channels)]
        else:
            args += ["-an"]
        return args

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "input_args": list(self.input_args),
            "audio_codec": self.audio_codec,
            "audio_bitrate": self.audio_bitrate,
            "audio_channels": self.audio_channels,
            "sample_rate": self.sample_rate,
            "video_codec": self.video_codec,
            "video_bitrate": self.video_bitrate,
            "frame_rate": self.frame_rate,
            "keyframe_seconds": self.keyframe_seconds,
        }


def dshow_audio_input(device_name: str) -> Tuple[str, ...]:
    """Windows DirectShow microphone input (Windows only; device name from list_dshow_audio_devices)."""
    if not device_name or '"' in device_name:
        raise ValueError("invalid DirectShow device name")
    return ("-f", "dshow", "-audio_buffer_size", "50", "-i", f"audio={device_name}")


_FFMPEG_OPTION_CACHE: Dict[str, bool] = {}


def ffmpeg_supports_option(option: str, ffmpeg: Optional[str] = None) -> bool:
    """True if this FFmpeg build documents ``-<option>`` (cached per process)."""
    if option not in _FFMPEG_OPTION_CACHE:
        try:
            text = subprocess.run(
                [ffmpeg or ffmpeg_binary(), "-hide_banner", "-h", "full"], capture_output=True, text=True, timeout=30
            ).stdout
        except (OSError, subprocess.SubprocessError):
            text = ""
        _FFMPEG_OPTION_CACHE[option] = f"-{option} " in text
    return _FFMPEG_OPTION_CACHE[option]


def synthetic_tone_input(frequency_expr: str = "1000", sample_rate: int = 48000, realtime: bool = True) -> Tuple[str, ...]:
    """Synthetic live-like input for verification. ``frequency_expr`` may reference t.

    FFmpeg 6.1+ reads the first 0.5 s of a ``-re`` input instantly
    (readrate_initial_burst). Real devices never do that, so it is disabled
    when supported, keeping the synthetic source's timing faithful to a microphone.
    """
    expr = f"sin(2*PI*({frequency_expr})*t)"
    args: List[str] = []
    if realtime:
        args.append("-re")
        if ffmpeg_supports_option("readrate_initial_burst"):
            args += ["-readrate_initial_burst", "0"]
    args += ["-f", "lavfi", "-i", f"aevalsrc={expr}:s={sample_rate}:c=mono"]
    return tuple(args)


_DSHOW_NEW = re.compile(r'"(?P<name>[^"]+)"\s+\(audio\)')
_DSHOW_OLD_SECTION = re.compile(r"DirectShow (?P<kind>audio|video) devices", re.IGNORECASE)
_DSHOW_OLD_NAME = re.compile(r'\]\s+"(?P<name>[^"]+)"\s*$')


def parse_dshow_audio_devices(stderr_text: str) -> List[str]:
    """Parse ``ffmpeg -list_devices true -f dshow -i dummy`` output (both FFmpeg formats)."""
    names: List[str] = []
    section: Optional[str] = None
    for raw in stderr_text.splitlines():
        line = raw.rstrip()
        if "Alternative name" in line:
            continue
        match = _DSHOW_NEW.search(line)
        if match:
            names.append(match.group("name"))
            continue
        sec = _DSHOW_OLD_SECTION.search(line)
        if sec:
            section = sec.group("kind").lower()
            continue
        if section == "audio" and "(video)" not in line:
            old = _DSHOW_OLD_NAME.search(line)
            if old:
                names.append(old.group("name"))
    seen: set = set()
    return [n for n in names if not (n in seen or seen.add(n))]


def list_dshow_audio_devices(ffmpeg: Optional[str] = None) -> List[str]:
    """List Windows microphone names FFmpeg can open. Returns [] off Windows."""
    if sys.platform != "win32":
        return []
    proc = subprocess.run(
        [ffmpeg or ffmpeg_binary(), "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    return parse_dshow_audio_devices(proc.stderr)


# ── Recorder ───────────────────────────────────────────────────────────────────
@dataclass
class _RunState:
    run_id: str
    run_dir: Path
    proc: asyncio.subprocess.Process
    started_mono: float
    log_handle: Any
    offsets: List[Tuple[float, float]] = field(default_factory=list)  # (media_time, utc_minus_media)
    last_media_time: float = 0.0
    last_advance_mono: Optional[float] = None
    segments_indexed: int = 0
    last_media_end: float = 0.0
    stopping: bool = False


EventSink = Any  # object with record_event(event_type, *, source, actor, data) -> Optional[str]


class SegmentedCaptureRecorder:
    """Record one source into finalized segments with a hash-chained UTC index."""

    def __init__(
        self,
        root: Path | str,
        spec: CaptureSpec,
        *,
        segment_seconds: float = 5.0,
        stall_after_s: float = 3.0,
        auto_restart: bool = True,
        max_restarts: int = 5,
        restart_window_s: float = 300.0,
        witness: Optional[EventSink] = None,
        clock: Optional[MonotonicUTCClock] = None,
        poll_interval_s: float = 0.25,
    ) -> None:
        if segment_seconds < 1.0:
            raise ValueError("segment_seconds must be at least 1 second")
        self.root = Path(root)
        self.spec = spec
        self.segment_seconds = float(segment_seconds)
        self.stall_after_s = float(stall_after_s)
        self.auto_restart = bool(auto_restart)
        self.max_restarts = int(max_restarts)
        self.restart_window_s = float(restart_window_s)
        self.witness = witness
        self.clock = clock or MonotonicUTCClock()
        self.poll_interval_s = float(poll_interval_s)
        self._ffmpeg = ffmpeg_binary()
        self._ffprobe = ffprobe_binary()
        self._lock = _ExclusiveFileLock(self.root / LOCK_FILENAME)
        self._locked = False
        self.index: Optional[CaptureIndex] = None
        self._run: Optional[_RunState] = None
        self._state = STATE_IDLE
        self._last_error: Optional[str] = None
        self._restart_times: List[float] = []
        self._tasks: List[asyncio.Task] = []
        self._supervisor: Optional[asyncio.Task] = None
        self._state_lock = asyncio.Lock()
        self._finalized_bytes = 0
        self._stop_requested = False

    # ── lifecycle ──────────────────────────────────────────────────────────────
    async def start(self) -> Dict[str, Any]:
        async with self._state_lock:
            if self._state in (STATE_STARTING, STATE_RECORDING, STATE_STALLED, STATE_RESTARTING):
                raise CaptureStateError(f"recorder already active ({self._state})")
            if not self._locked:
                self._lock.acquire()
                self._locked = True
            self.index = CaptureIndex(self.root)
            self.recover_interrupted_runs()
            self._restart_times.clear()
            self._last_error = None
            self._stop_requested = False
            await self._spawn_run()
            self._supervisor = asyncio.create_task(self._supervise(), name=f"capture-supervisor-{self.spec.source_id}")
            return self.status()

    async def stop(self, reason: str = "stopped") -> Dict[str, Any]:
        async with self._state_lock:
            self._stop_requested = True
            supervisor, self._supervisor = self._supervisor, None
            run = self._run
            if run is not None:
                run.stopping = True
                await self._terminate_process(run.proc)
            elif supervisor is not None and not supervisor.done():
                supervisor.cancel()  # waiting out a restart backoff: no process to stop
            if supervisor is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await supervisor
            if run is not None and self._run is run:
                await self._close_run(run, reason=reason, clean=True)
            self._state = STATE_STOPPED
            if self._locked:
                self._lock.release()
                self._locked = False
            return self.status()

    # ── status ─────────────────────────────────────────────────────────────────
    def status(self) -> Dict[str, Any]:
        run = self._run
        state = self._state
        now_mono = time.monotonic()
        last_advance_age: Optional[float] = None
        if run is not None and run.last_advance_mono is not None:
            last_advance_age = now_mono - run.last_advance_mono
        if state in (STATE_STARTING, STATE_RECORDING, STATE_STALLED) and run is not None:
            if run.last_advance_mono is None:
                state = STATE_STALLED if now_mono - run.started_mono > max(self.stall_after_s * 2, 5.0) else STATE_STARTING
            elif last_advance_age is not None and last_advance_age > self.stall_after_s:
                state = STATE_STALLED
            else:
                state = STATE_RECORDING
            self._state = state
        open_bytes = self._open_segment_bytes(run) if run is not None else 0
        return {
            "source_id": self.spec.source_id,
            "state": state,
            "recording": state == STATE_RECORDING,
            "run_id": run.run_id if run else None,
            "media_time_s": round(run.last_media_time, 3) if run else 0.0,
            "last_media_advance_age_s": None if last_advance_age is None else round(last_advance_age, 3),
            "bytes_written": self._finalized_bytes + open_bytes,
            "segments_in_run": run.segments_indexed if run else 0,
            "segment_seconds": self.segment_seconds,
            "index_head": self.index.head if self.index else None,
            "restarts_in_window": len(self._restart_times),
            "last_error": self._last_error,
            "utc_now": utc_iso(self.clock.now()),
        }

    # ── recovery after the whole program died ─────────────────────────────────
    def recover_interrupted_runs(self) -> List[str]:
        """Close runs a previous process left open; index readable leftovers."""
        assert self.index is not None
        open_runs: Dict[str, Dict[str, Any]] = {}
        last_seg: Dict[str, Dict[str, Any]] = {}
        lost_or_partial_after: Dict[str, int] = {}
        for record in self.index.records():
            kind = record.get("type")
            if kind == "run_start":
                open_runs[record["run_id"]] = record
            elif kind == "run_end":
                open_runs.pop(record["run_id"], None)
            elif kind == "segment":
                last_seg[record["run_id"]] = record
            elif kind == "lost":
                lost_or_partial_after[record["run_id"]] = max(lost_or_partial_after.get(record["run_id"], -1), int(record.get("seq", -1)))
        recovered: List[str] = []
        for run_id, start in open_runs.items():
            run_dir = self.root / start["run_dir"]
            prior = last_seg.get(run_id)
            next_seq = (int(prior["seq"]) + 1) if prior else 0
            next_seq = max(next_seq, lost_or_partial_after.get(run_id, -1) + 1)
            resume_utc = float(prior["utc_end"]) if prior else float(start["utc_start"])
            anchor = float(prior["utc_end"]) - float(prior["media_end"]) if prior else float(start["utc_start"])
            uncertainty = float(prior.get("timing_uncertainty_s", 0.5)) if prior else 0.5
            ext = start.get("extension", self.spec.extension)
            leftovers = sorted(run_dir.glob(f"seg_*.{ext}"))
            for path in leftovers:
                try:
                    seq = int(path.stem.split("_")[1])
                except (IndexError, ValueError):
                    continue
                if seq < next_seq:
                    continue
                duration = probe_duration(path, self._ffprobe)
                media_start = resume_utc - anchor
                if duration:
                    self.index.append(
                        "segment",
                        run_id=run_id,
                        seq=seq,
                        file=str(path.relative_to(self.root).as_posix()),
                        media_start=round(media_start, 6),
                        media_end=round(media_start + duration, 6),
                        utc_start=round(resume_utc, 6),
                        utc_end=round(resume_utc + duration, 6),
                        size=path.stat().st_size,
                        sha256=sha256_file(path),
                        status="partial",
                        timing_uncertainty_s=round(uncertainty + 0.5, 3),
                    )
                    resume_utc += duration
                else:
                    self.index.append(
                        "lost",
                        run_id=run_id,
                        seq=seq,
                        file=str(path.relative_to(self.root).as_posix()),
                        utc_start=round(resume_utc, 6),
                        utc_end=round(resume_utc, 6),
                        reason="unreadable segment after interrupted run; duration unknown",
                    )
            self.index.append("run_end", run_id=run_id, utc_end=round(resume_utc, 6), reason="interrupted", clean=False, index_head_before=self.index.head)
            self._witness("recording.state", {"run_id": run_id, "state": "interrupted_run_recovered", "source_id": self.spec.source_id})
            recovered.append(run_id)
        return recovered

    # ── internals ─────────────────────────────────────────────────────────────
    async def _spawn_run(self) -> None:
        assert self.index is not None
        run_id = f"{time.strftime('%Y%m%dT%H%M%S', time.gmtime(self.clock.now()))}Z_{uuid.uuid4().hex[:8]}"
        run_dir = self.root / RUNS_DIRNAME / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        ext = self.spec.extension
        cmd = [
            self._ffmpeg,
            "-hide_banner",
            "-nostats",
            "-loglevel",
            "warning",
            "-y",
            *self.spec.input_args,
            *self.spec.output_args(),
            "-f",
            "segment",
            "-segment_time",
            f"{self.segment_seconds:g}",
            "-segment_format",
            "matroska",
            "-reset_timestamps",
            "1",
            "-segment_list",
            str(run_dir / SEGMENT_LIST_NAME),
            "-segment_list_type",
            "csv",
            str(run_dir / SEGMENT_PATTERN.format(ext=ext)),
            "-progress",
            "pipe:1",
            "-stats_period",
            "0.5",
        ]
        log_handle = open(run_dir / FFMPEG_LOG_NAME, "ab")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=log_handle,
            )
        except Exception as exc:
            log_handle.close()
            self._last_error = f"failed to start ffmpeg: {exc}"
            self._state = STATE_CRASHED
            raise CaptureError(self._last_error) from exc
        started_mono = time.monotonic()
        self.index.append(
            "run_start",
            run_id=run_id,
            run_dir=str(run_dir.relative_to(self.root).as_posix()),
            source_id=self.spec.source_id,
            spec=self.spec.to_dict(),
            extension=ext,
            segment_seconds=self.segment_seconds,
            utc_start=round(self.clock.at(started_mono), 6),
            ffmpeg=self._ffmpeg,
            pid=proc.pid,
        )
        self._run = _RunState(run_id=run_id, run_dir=run_dir, proc=proc, started_mono=started_mono, log_handle=log_handle)
        self._state = STATE_STARTING
        self._tasks = [
            asyncio.create_task(self._read_progress(self._run), name=f"capture-progress-{run_id}"),
            asyncio.create_task(self._tail_segments(self._run), name=f"capture-tail-{run_id}"),
        ]
        self._witness("recording.state", {"run_id": run_id, "state": "run_started", "source_id": self.spec.source_id, "pid": proc.pid})
        logger.info("Segmented capture %s started (pid=%s) -> %s", run_id, proc.pid, run_dir)

    async def _read_progress(self, run: _RunState) -> None:
        stream = run.proc.stdout
        if stream is None:
            return
        while True:
            line = await stream.readline()
            if not line:
                return
            key, _, value = line.decode("utf-8", "replace").strip().partition("=")
            if key != "out_time_us" or not value or value == "N/A":
                continue
            try:
                media_time = int(value) / 1_000_000.0
            except ValueError:
                continue
            mono = time.monotonic()
            if media_time > run.last_media_time:
                run.last_media_time = media_time
                run.last_advance_mono = mono
                run.offsets.append((media_time, self.clock.at(mono) - media_time))
                if len(run.offsets) > 20000:
                    del run.offsets[: len(run.offsets) // 2]

    async def _tail_segments(self, run: _RunState) -> None:
        while True:
            await self._index_new_segments(run)
            if run.proc.returncode is not None:
                return
            await asyncio.sleep(self.poll_interval_s)

    def _read_segment_list(self, run: _RunState) -> List[Tuple[str, float, float]]:
        list_path = run.run_dir / SEGMENT_LIST_NAME
        if not list_path.exists():
            return []
        try:
            text = list_path.read_text(encoding="utf-8")
        except OSError:
            return []
        rows: List[Tuple[str, float, float]] = []
        for row in csv.reader(text.splitlines()):
            if len(row) < 3:
                continue
            try:
                rows.append((row[0], float(row[1]), float(row[2])))
            except ValueError:
                continue
        return rows

    def _anchor_for(self, run: _RunState, media_start: float, media_end: float) -> Tuple[float, float]:
        """Return (utc_minus_media anchor, uncertainty_s) for a media interval."""
        local = [off for (mt, off) in run.offsets if media_start - 0.5 <= mt <= media_end + 0.5]
        pool = local if len(local) >= 2 else [off for (_, off) in run.offsets]
        if not pool:
            return self.clock.at(run.started_mono), 1.0
        anchor = statistics.median(pool)
        spread = (max(pool) - min(pool)) / 2.0 if len(pool) > 1 else 0.5
        return anchor, max(spread, 0.02)

    async def _index_new_segments(self, run: _RunState) -> None:
        assert self.index is not None
        rows = self._read_segment_list(run)
        for filename, media_start, media_end in rows[run.segments_indexed:]:
            if run.proc.returncode is None and run.last_media_time < media_end:
                # Wait for a progress report past this segment so its UTC anchor is
                # fitted from reports on both sides of it, not extrapolated.
                break
            path = run.run_dir / filename
            if not path.exists():
                self._last_error = f"segment listed but missing: {filename}"
                logger.error(self._last_error)
                run.segments_indexed += 1
                continue
            size = path.stat().st_size
            digest = await asyncio.to_thread(sha256_file, path)
            anchor, uncertainty = self._anchor_for(run, media_start, media_end)
            self.index.append(
                "segment",
                run_id=run.run_id,
                seq=run.segments_indexed,
                file=str(path.relative_to(self.root).as_posix()),
                media_start=round(media_start, 6),
                media_end=round(media_end, 6),
                utc_start=round(anchor + media_start, 6),
                utc_end=round(anchor + media_end, 6),
                size=size,
                sha256=digest,
                status="final",
                timing_uncertainty_s=round(uncertainty, 3),
            )
            self._finalized_bytes += size
            run.segments_indexed += 1
            run.last_media_end = media_end

    def _open_segment_bytes(self, run: _RunState) -> int:
        path = run.run_dir / (SEGMENT_PATTERN.format(ext=self.spec.extension) % run.segments_indexed)
        try:
            return path.stat().st_size
        except OSError:
            return 0

    async def _terminate_process(self, proc: asyncio.subprocess.Process) -> None:
        if proc.returncode is not None:
            return
        try:
            if proc.stdin is not None:
                proc.stdin.write(b"q")
                await proc.stdin.drain()
                proc.stdin.close()
            await asyncio.wait_for(proc.wait(), timeout=10.0)
        except (asyncio.TimeoutError, BrokenPipeError, ConnectionResetError, OSError):
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()

    async def _close_run(self, run: _RunState, *, reason: str, clean: bool) -> None:
        assert self.index is not None
        for task in self._tasks:
            if not task.done():
                with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
                    await asyncio.wait_for(task, timeout=5.0)
        self._tasks = []
        await self._index_new_segments(run)
        end_utc = None
        if not clean:
            end_utc = await self._salvage_unfinished(run)
        if end_utc is None:
            anchor, _ = self._anchor_for(run, max(run.last_media_end - self.segment_seconds, 0.0), run.last_media_end)
            end_utc = anchor + run.last_media_end if run.segments_indexed else self.clock.at(run.started_mono)
        with contextlib.suppress(Exception):
            run.log_handle.close()
        self.index.append(
            "run_end",
            run_id=run.run_id,
            utc_end=round(end_utc, 6),
            reason=reason,
            clean=clean,
            returncode=run.proc.returncode,
            segments=run.segments_indexed,
            index_head_before=self.index.head,
        )
        self._witness(
            "recording.state",
            {
                "run_id": run.run_id,
                "state": "run_ended" if clean else "run_crashed",
                "reason": reason,
                "segments": run.segments_indexed,
                "index_head": self.index.head,
                "source_id": self.spec.source_id,
            },
        )
        if self._run is run:
            self._run = None

    async def _salvage_unfinished(self, run: _RunState) -> Optional[float]:
        """After a crash: index the readable part of the open segment, or log the loss."""
        assert self.index is not None
        path = run.run_dir / (SEGMENT_PATTERN.format(ext=self.spec.extension) % run.segments_indexed)
        anchor, uncertainty = self._anchor_for(run, run.last_media_end, max(run.last_media_time, run.last_media_end))
        start_utc = anchor + run.last_media_end
        duration = await asyncio.to_thread(probe_duration, path, self._ffprobe) if path.exists() else None
        rel = str(path.relative_to(self.root).as_posix())
        if duration:
            self.index.append(
                "segment",
                run_id=run.run_id,
                seq=run.segments_indexed,
                file=rel,
                media_start=round(run.last_media_end, 6),
                media_end=round(run.last_media_end + duration, 6),
                utc_start=round(start_utc, 6),
                utc_end=round(start_utc + duration, 6),
                size=path.stat().st_size,
                sha256=await asyncio.to_thread(sha256_file, path),
                status="partial",
                timing_uncertainty_s=round(uncertainty, 3),
            )
            self._finalized_bytes += path.stat().st_size
            covered_until = run.last_media_end + duration
            run.segments_indexed += 1
            run.last_media_end = covered_until
        else:
            covered_until = run.last_media_end
        if run.last_media_time > covered_until + 0.05:
            self.index.append(
                "lost",
                run_id=run.run_id,
                seq=run.segments_indexed,
                file=rel,
                utc_start=round(anchor + covered_until, 6),
                utc_end=round(anchor + run.last_media_time, 6),
                reason="encoder exited before the segment was written",
            )
            return anchor + run.last_media_time
        return anchor + covered_until

    async def _supervise(self) -> None:
        while True:
            run = self._run
            if run is None:
                return
            returncode = await run.proc.wait()
            if run.stopping:
                return
            self._last_error = f"ffmpeg exited unexpectedly (returncode={returncode}); see {run.run_dir / FFMPEG_LOG_NAME}"
            logger.error("Segmented capture %s: %s", run.run_id, self._last_error)
            await self._close_run(run, reason="crashed", clean=False)
            now = time.monotonic()
            self._restart_times = [t for t in self._restart_times if now - t < self.restart_window_s]
            if not self.auto_restart or len(self._restart_times) >= self.max_restarts:
                self._state = STATE_CRASHED
                self._witness("recording.state", {"state": "capture_crashed", "source_id": self.spec.source_id, "error": self._last_error})
                return
            self._state = STATE_RESTARTING
            backoff = min(2 ** len(self._restart_times), 15)
            self._restart_times.append(now)
            self._witness("recording.state", {"state": "capture_restarting", "source_id": self.spec.source_id, "backoff_s": backoff})
            await asyncio.sleep(backoff)
            if self._stop_requested:
                return
            try:
                await self._spawn_run()
            except CaptureError:
                self._state = STATE_CRASHED
                return

    def _witness(self, event_type: str, data: Mapping[str, Any]) -> None:
        if self.witness is None:
            return
        try:
            self.witness.record_event(event_type, source="recording", actor=f"capture:{self.spec.source_id}", data=dict(data))
        except Exception as exc:  # witness failure must never stop capture
            logger.warning("BlackBox witness failed for %s: %s", event_type, exc)


__all__ = [
    "CaptureError",
    "CaptureIndex",
    "CaptureLockedError",
    "CaptureSpec",
    "CaptureStateError",
    "CaptureUnavailableError",
    "IndexIntegrityError",
    "IndexSnapshot",
    "IndexVerification",
    "IndexedSegment",
    "LostInterval",
    "MonotonicUTCClock",
    "SegmentedCaptureRecorder",
    "dshow_audio_input",
    "ffmpeg_binary",
    "ffmpeg_supports_option",
    "ffprobe_binary",
    "list_dshow_audio_devices",
    "load_snapshot",
    "parse_dshow_audio_devices",
    "parse_utc",
    "probe_duration",
    "sha256_file",
    "synthetic_tone_input",
    "utc_iso",
    "verify_index",
    "STATE_CRASHED",
    "STATE_IDLE",
    "STATE_RECORDING",
    "STATE_RESTARTING",
    "STATE_STALLED",
    "STATE_STARTING",
    "STATE_STOPPED",
]

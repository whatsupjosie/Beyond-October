"""
modules/range_preservation.py — copy a recorded time range into its own file
===========================================================================

Example request: "preserve 6:36 p.m. to 8:49 p.m. on 2026-10-20". The range is
copied out of the finalized segments written by
``modules/segmented_capture.py``. The original recording is never modified,
moved or re-encoded; that is checked, not assumed (every source segment is
hashed before and after the copy and compared with the hash-chained index).

What the caller always gets back is a :class:`PreserveReceipt` that states
exactly what happened:

* ``completed``  one verified file covering the whole requested range
* ``partial``    verified file(s) plus an explicit list of gaps (a crash, a
                 restart, or a part of the range not recorded yet). Separate
                 runs are written as separate parts; nothing is stitched over
                 a gap.
* ``failed``     nothing usable was produced, with the reason

Each output file's duration is measured with ffprobe and compared with the
expected duration before the receipt says it succeeded. Outputs are written
to a temporary name and moved into place only after verification. Existing
files are never overwritten.

Local wall-clock requests are resolved with the IANA time zone database. A
time that occurs twice (the fall-back hour) or never (the spring-forward hour)
raises an error carrying the candidates, so the program asks instead of guessing.
On Windows the ``tzdata`` package must be installed for zoneinfo to work.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .segmented_capture import (
    IndexIntegrityError,
    IndexSnapshot,
    IndexedSegment,
    STATE_RECORDING,
    STATE_RESTARTING,
    STATE_STALLED,
    STATE_STARTING,
    ffmpeg_binary,
    ffprobe_binary,
    load_snapshot,
    parse_utc,
    sha256_file,
    utc_iso,
)

logger = logging.getLogger("pubcast.range_preservation")

DEFAULT_TIMEZONE = "America/Los_Angeles"
JOIN_TOLERANCE_S = 0.10          # consecutive segments closer than this are contiguous
AUDIO_CUT_TOLERANCE_S = 0.08     # AAC frame granularity plus container rounding
EXACT_CUT_TOLERANCE_S = 0.08


# ── Errors ─────────────────────────────────────────────────────────────────────
class RangeRequestError(ValueError):
    """The request itself is invalid."""


class AmbiguousLocalTimeError(RangeRequestError):
    """A local time occurs twice (daylight-saving fall-back). Ask which one."""

    def __init__(self, label: str, local_text: str, candidates_utc: Sequence[str]) -> None:
        self.label = label
        self.local_text = local_text
        self.candidates_utc = list(candidates_utc)
        super().__init__(
            f"{label} time {local_text} happens twice on that date (clocks fall back). "
            f"Choose one: first occurrence {self.candidates_utc[0]} or second occurrence {self.candidates_utc[1]}."
        )


class NonexistentLocalTimeError(RangeRequestError):
    """A local time never occurs (daylight-saving spring-forward)."""

    def __init__(self, label: str, local_text: str) -> None:
        self.label = label
        self.local_text = local_text
        super().__init__(f"{label} time {local_text} does not exist on that date (clocks spring forward).")


# ── Local time resolution ──────────────────────────────────────────────────────
def _zone(tz_name: str):
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise RangeRequestError(
            f"time zone {tz_name!r} is unavailable. On Windows install the tzdata package (pip install tzdata)."
        ) from exc


_TIME_RE = re.compile(
    r"^\s*(?P<h>\d{1,2})(?::(?P<m>\d{2}))?(?::(?P<s>\d{2}(?:\.\d+)?))?\s*(?P<ampm>a\.?\s*m\.?|p\.?\s*m\.?)?\s*$",
    re.IGNORECASE,
)


def parse_clock_time(text: str) -> dtime:
    """Parse '18:36', '6:36 pm', '6:36 p.m.', '20:49:30.5'."""
    match = _TIME_RE.match(str(text))
    if not match:
        raise RangeRequestError(f"unrecognised time: {text!r}")
    hour = int(match.group("h"))
    minute = int(match.group("m") or 0)
    second_f = float(match.group("s") or 0)
    ampm = (match.group("ampm") or "").replace(".", "").replace(" ", "").lower()
    if ampm:
        if not 1 <= hour <= 12:
            raise RangeRequestError(f"invalid 12-hour time: {text!r}")
        hour = (hour % 12) + (12 if ampm == "pm" else 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second_f < 60):
        raise RangeRequestError(f"invalid time: {text!r}")
    second = int(second_f)
    micro = int(round((second_f - second) * 1_000_000))
    return dtime(hour, minute, second, min(micro, 999_999))


def _resolve_local(label: str, day: date, clock: dtime, zone, fold: Optional[int]) -> float:
    naive = datetime.combine(day, clock)
    first = naive.replace(tzinfo=zone, fold=0)
    second = naive.replace(tzinfo=zone, fold=1)
    local_text = f"{naive.isoformat(sep=' ', timespec='seconds')} {zone.key}"
    if first.utcoffset() != second.utcoffset():
        # Either ambiguous (occurs twice) or nonexistent (skipped). Round-trip tells which.
        roundtrip = first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        if roundtrip != naive:
            raise NonexistentLocalTimeError(label, local_text)
        if fold not in (0, 1):
            raise AmbiguousLocalTimeError(
                label, local_text, [utc_iso(first.timestamp()), utc_iso(second.timestamp())]
            )
        return (first if fold == 0 else second).timestamp()
    roundtrip = first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
    if roundtrip != naive:
        raise NonexistentLocalTimeError(label, local_text)
    return first.timestamp()


@dataclass(frozen=True)
class ResolvedRange:
    utc_start: float
    utc_end: float
    timezone: str
    local_start: str
    local_end: str
    crosses_midnight: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "utc_start": utc_iso(self.utc_start),
            "utc_end": utc_iso(self.utc_end),
            "timezone": self.timezone,
            "local_start": self.local_start,
            "local_end": self.local_end,
            "crosses_midnight": self.crosses_midnight,
        }


def resolve_local_range(
    day: date | str,
    start: str | dtime,
    end: str | dtime,
    *,
    tz_name: str = DEFAULT_TIMEZONE,
    start_fold: Optional[int] = None,
    end_fold: Optional[int] = None,
) -> ResolvedRange:
    """Turn a local date plus two clock times into exact UTC bounds.

    The date is required: "6:36 to 8:49" without a date is not resolved by guessing.
    An end time earlier than the start time means the range ends the next day.
    """
    if isinstance(day, str):
        try:
            day = date.fromisoformat(day.strip())
        except ValueError as exc:
            raise RangeRequestError(f"date must be YYYY-MM-DD, got {day!r}") from exc
    zone = _zone(tz_name)
    start_clock = start if isinstance(start, dtime) else parse_clock_time(start)
    end_clock = end if isinstance(end, dtime) else parse_clock_time(end)
    crosses = end_clock <= start_clock
    end_day = day + timedelta(days=1) if crosses else day
    utc_start = _resolve_local("start", day, start_clock, zone, start_fold)
    utc_end = _resolve_local("end", end_day, end_clock, zone, end_fold)
    if utc_end <= utc_start:
        raise RangeRequestError("end must be after start")
    return ResolvedRange(
        utc_start=utc_start,
        utc_end=utc_end,
        timezone=tz_name,
        local_start=f"{day.isoformat()} {start_clock.isoformat(timespec='seconds')}",
        local_end=f"{end_day.isoformat()} {end_clock.isoformat(timespec='seconds')}",
        crosses_midnight=crosses,
    )


# ── Receipt ────────────────────────────────────────────────────────────────────
@dataclass
class PreservedPart:
    file: str
    sha256: str
    size: int
    utc_start: str
    utc_end: str
    expected_s: float
    measured_s: float
    within_tolerance: bool
    tolerance_s: float
    run_id: str
    segments: int


@dataclass
class RangeGap:
    utc_start: str
    utc_end: str
    seconds: float
    reason: str


@dataclass
class PreserveReceipt:
    request_id: str
    status: str  # completed | partial | failed
    source_id: str
    requested_utc_start: str
    requested_utc_end: str
    mode: str
    parts: List[PreservedPart] = field(default_factory=list)
    gaps: List[RangeGap] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)
    originals_unchanged: Optional[bool] = None
    timing_uncertainty_s: Optional[float] = None
    reason: Optional[str] = None
    elapsed_s: float = 0.0
    blackbox_records: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in ("completed", "partial")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Preserver ──────────────────────────────────────────────────────────────────
_ACTIVE_STATES = {STATE_STARTING, STATE_RECORDING, STATE_STALLED, STATE_RESTARTING}


def _concat_escape(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "'\\''")


def _probe_streams(path: Path, ffprobe: str) -> List[str]:
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "stream=codec_type,codec_name", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return []
    data = json.loads(proc.stdout or "{}")
    return [f"{s.get('codec_type')}:{s.get('codec_name')}" for s in data.get("streams", [])]


def _probe_duration_strict(path: Path, ffprobe: str) -> Optional[float]:
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        return None
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def _output_extension(streams: Sequence[str]) -> str:
    kinds = {s.split(":", 1)[0] for s in streams}
    codecs = {s.split(":", 1)[1] for s in streams if ":" in s}
    if "video" in kinds:
        return "mp4" if codecs <= {"h264", "aac"} else "mkv"
    return "m4a" if codecs <= {"aac"} else "mka"


def _reserve_name(directory: Path, stem: str, ext: str) -> Path:
    """Atomically claim an unused filename; never returns an existing file."""
    for attempt in range(1000):
        name = f"{stem}.{ext}" if attempt == 0 else f"{stem}-{attempt + 1}.{ext}"
        candidate = directory / name
        try:
            fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue
        os.close(fd)
        return candidate
    raise OSError(f"could not reserve an output name for {stem} in {directory}")


class RangePreserver:
    """Copy time ranges out of one segmented capture directory."""

    def __init__(
        self,
        capture_root: Path | str,
        output_dir: Path | str,
        *,
        source_id: str = "control_room_audio",
        witness: Any = None,
        recorder: Any = None,
        keyframe_seconds: float = 1.0,
        max_concurrent: int = 2,
    ) -> None:
        self.capture_root = Path(capture_root)
        self.output_dir = Path(output_dir)
        self.source_id = source_id
        self.witness = witness
        self.recorder = recorder
        self.keyframe_seconds = float(keyframe_seconds)
        self._ffmpeg = ffmpeg_binary()
        self._ffprobe = ffprobe_binary()
        self._semaphore = asyncio.Semaphore(max(1, int(max_concurrent)))

    # ── public ────────────────────────────────────────────────────────────────
    async def preserve_local(
        self,
        day: date | str,
        start: str,
        end: str,
        *,
        tz_name: str = DEFAULT_TIMEZONE,
        start_fold: Optional[int] = None,
        end_fold: Optional[int] = None,
        **kwargs: Any,
    ) -> PreserveReceipt:
        resolved = resolve_local_range(day, start, end, tz_name=tz_name, start_fold=start_fold, end_fold=end_fold)
        return await self.preserve(resolved.utc_start, resolved.utc_end, **kwargs)

    async def preserve(
        self,
        utc_start: Any,
        utc_end: Any,
        *,
        mode: str = "copy",
        actor: str = "director",
        wait_timeout_s: Optional[float] = None,
        label: Optional[str] = None,
    ) -> PreserveReceipt:
        started = time.monotonic()
        request_id = f"pr_{uuid.uuid4().hex[:12]}"
        try:
            start_s = parse_utc(utc_start)
            end_s = parse_utc(utc_end)
        except (ValueError, TypeError) as exc:
            raise RangeRequestError(str(exc)) from exc
        if end_s <= start_s:
            raise RangeRequestError("end must be after start")
        if mode not in ("copy", "exact"):
            raise RangeRequestError("mode must be 'copy' or 'exact'")
        receipt = PreserveReceipt(
            request_id=request_id,
            status="failed",
            source_id=self.source_id,
            requested_utc_start=utc_iso(start_s),
            requested_utc_end=utc_iso(end_s),
            mode=mode,
        )
        self._witness(
            receipt,
            "studio.action",
            actor,
            {
                "action": "recording.preserve_range",
                "phase": "requested",
                "request_id": request_id,
                "source_id": self.source_id,
                "utc_start": receipt.requested_utc_start,
                "utc_end": receipt.requested_utc_end,
                "mode": mode,
            },
        )
        async with self._semaphore:
            try:
                await self._run(receipt, start_s, end_s, mode, wait_timeout_s, label)
            except IndexIntegrityError as exc:
                receipt.status = "failed"
                receipt.reason = f"capture index failed verification: {exc}"
            except Exception as exc:  # report every failure truthfully
                logger.exception("preserve %s failed", request_id)
                receipt.status = "failed"
                receipt.reason = f"{type(exc).__name__}: {exc}"
        receipt.elapsed_s = round(time.monotonic() - started, 3)
        export_hash = hashlib.sha256("".join(p.sha256 for p in receipt.parts).encode()).hexdigest() if receipt.parts else ""
        self._witness(
            receipt,
            "legal.export",
            actor,
            {
                "request_id": request_id,
                "source_id": self.source_id,
                "scope": f"{receipt.requested_utc_start}..{receipt.requested_utc_end}",
                "status": receipt.status,
                "parts": len(receipt.parts),
                "gaps": len(receipt.gaps),
                "export_hash": export_hash,
                "originals_unchanged": receipt.originals_unchanged,
                "reason": receipt.reason,
            },
        )
        return receipt

    # ── internals ─────────────────────────────────────────────────────────────
    def _recorder_active(self) -> bool:
        if self.recorder is None:
            return False
        try:
            return self.recorder.status().get("state") in _ACTIVE_STATES
        except Exception:
            return False

    async def _wait_for_coverage(self, end_s: float, timeout_s: float) -> IndexSnapshot:
        deadline = time.monotonic() + max(0.0, timeout_s)
        while True:
            snapshot = await asyncio.to_thread(load_snapshot, self.capture_root)
            covered = max((seg.utc_end for seg in snapshot.segments), default=float("-inf"))
            if covered >= end_s - JOIN_TOLERANCE_S or not self._recorder_active() or time.monotonic() >= deadline:
                return snapshot
            await asyncio.sleep(0.25)

    @staticmethod
    def _group_parts(segments: Sequence[IndexedSegment], start_s: float, end_s: float) -> List[List[IndexedSegment]]:
        overlapping = [seg for seg in segments if seg.utc_end > start_s and seg.utc_start < end_s]
        parts: List[List[IndexedSegment]] = []
        for seg in overlapping:
            if parts:
                prev = parts[-1][-1]
                contiguous = (
                    seg.run_id == prev.run_id
                    and seg.seq == prev.seq + 1
                    and abs(seg.utc_start - prev.utc_end) <= JOIN_TOLERANCE_S
                    and prev.status == "final"
                )
                if contiguous:
                    parts[-1].append(seg)
                    continue
            parts.append([seg])
        return parts

    def _gap_reason(self, snapshot: IndexSnapshot, a: float, b: float, *, trailing: bool) -> str:
        for lost in snapshot.lost:
            if lost.utc_end > a and lost.utc_start < b:
                return f"lost in run {lost.run_id}: {lost.reason}"
        if trailing and self._recorder_active():
            return "not recorded yet (recording still in progress past the last finished segment)"
        return "no recording exists for this interval (stopped, crashed, restarting, or not started)"

    async def _run(
        self,
        receipt: PreserveReceipt,
        start_s: float,
        end_s: float,
        mode: str,
        wait_timeout_s: Optional[float],
        label: Optional[str],
    ) -> None:
        segment_seconds = 5.0
        if self.recorder is not None:
            segment_seconds = float(getattr(self.recorder, "segment_seconds", segment_seconds))
        timeout = wait_timeout_s if wait_timeout_s is not None else segment_seconds * 2 + 5.0
        snapshot = await self._wait_for_coverage(end_s, timeout)
        parts = self._group_parts(snapshot.segments, start_s, end_s)

        # Gaps: before first part, between parts, after last part.
        cursor = start_s
        gaps: List[RangeGap] = []
        for idx, part in enumerate(parts):
            p_start = max(start_s, part[0].utc_start)
            if p_start - cursor > JOIN_TOLERANCE_S:
                gaps.append(RangeGap(utc_iso(cursor), utc_iso(p_start), round(p_start - cursor, 3), self._gap_reason(snapshot, cursor, p_start, trailing=False)))
            cursor = max(cursor, min(end_s, part[-1].utc_end))
        if end_s - cursor > JOIN_TOLERANCE_S:
            gaps.append(RangeGap(utc_iso(cursor), utc_iso(end_s), round(end_s - cursor, 3), self._gap_reason(snapshot, cursor, end_s, trailing=True)))
        receipt.gaps = gaps

        if not parts:
            receipt.status = "failed"
            receipt.reason = "no recorded media covers the requested range"
            return

        sources = [seg for part in parts for seg in part]
        receipt.timing_uncertainty_s = round(max(seg.timing_uncertainty_s for seg in sources), 3)

        # Integrity before: every source must still match the hash in the index.
        before = await asyncio.to_thread(self._hash_sources, sources)
        receipt.sources = [{"file": str(seg.path.relative_to(self.capture_root).as_posix()), "sha256": seg.sha256} for seg in sources]
        altered = [str(seg.path.name) for seg in sources if before.get(seg.path) != seg.sha256]
        if altered:
            receipt.status = "failed"
            receipt.originals_unchanged = False
            receipt.reason = f"source segments do not match their recorded hashes: {', '.join(altered)}"
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)
        streams = await asyncio.to_thread(_probe_streams, sources[0].path, self._ffprobe)
        if not streams:
            receipt.status = "failed"
            receipt.reason = f"cannot read source media {sources[0].path.name}"
            return
        has_video = any(s.startswith("video:") for s in streams)
        ext = _output_extension(streams) if mode == "copy" else ("mp4" if has_video else "m4a")
        tolerance = EXACT_CUT_TOLERANCE_S if mode == "exact" else (
            self.keyframe_seconds + AUDIO_CUT_TOLERANCE_S if has_video else AUDIO_CUT_TOLERANCE_S
        )

        tag = re.sub(r"[^A-Za-z0-9_-]+", "_", label).strip("_")[:40] if label else ""
        failures: List[str] = []
        for number, part in enumerate(parts, 1):
            p_start = max(start_s, part[0].utc_start)
            p_end = min(end_s, part[-1].utc_end)
            if p_end - p_start <= 0.01:
                continue
            stem = "preserved_{}_{}_{}".format(
                time.strftime("%Y%m%dT%H%M%S", time.gmtime(p_start)) + "Z",
                time.strftime("%Y%m%dT%H%M%S", time.gmtime(p_end)) + "Z",
                self.source_id,
            )
            if tag:
                stem += f"_{tag}"
            if len(parts) > 1:
                stem += f"_part{number}"
            result = await asyncio.to_thread(self._write_part, part, p_start, p_end, stem, ext, mode, has_video, tolerance)
            if isinstance(result, str):
                failures.append(f"part {number}: {result}")
            else:
                receipt.parts.append(result)

        # Integrity after: the copy must not have touched any source.
        after = await asyncio.to_thread(self._hash_sources, sources)
        receipt.originals_unchanged = all(after.get(seg.path) == seg.sha256 for seg in sources)

        if not receipt.originals_unchanged:
            receipt.status = "failed"
            receipt.reason = "a source segment changed during the copy"
        elif failures and not receipt.parts:
            receipt.status = "failed"
            receipt.reason = "; ".join(failures)
        elif failures or receipt.gaps or len(receipt.parts) > 1:
            receipt.status = "partial"
            receipt.reason = "; ".join(failures) or None
        else:
            receipt.status = "completed"

    @staticmethod
    def _hash_sources(sources: Sequence[IndexedSegment]) -> Dict[Path, Optional[str]]:
        out: Dict[Path, Optional[str]] = {}
        for seg in sources:
            try:
                out[seg.path] = sha256_file(seg.path)
            except OSError:
                out[seg.path] = None
        return out

    def _write_part(
        self,
        part: Sequence[IndexedSegment],
        p_start: float,
        p_end: float,
        stem: str,
        ext: str,
        mode: str,
        has_video: bool,
        tolerance: float,
    ) -> PreservedPart | str:
        final_path = _reserve_name(self.output_dir, stem, ext)
        tmp_dir = Path(tempfile.mkdtemp(prefix=".preserve_", dir=self.output_dir))
        tmp_out = tmp_dir / f"out.{ext}"
        list_path = tmp_dir / "concat.txt"
        try:
            # The concat demuxer ignores inpoint/outpoint when stream-copying, so
            # trimming is done with -ss/-t, measured from the first listed segment.
            lines = ["ffconcat version 1.0"] + [f"file '{_concat_escape(seg.path)}'" for seg in part]
            list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            offset = max(0.0, p_start - part[0].utc_start)
            span = p_end - p_start
            trim = ["-ss", f"{offset:.6f}", "-t", f"{span:.6f}"]
            cmd = [self._ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0"]
            if mode == "copy" and has_video:
                # Input-side seek lands on a keyframe so the copy starts decodable.
                cmd += trim[:2] + ["-i", str(list_path)] + trim[2:] + ["-map", "0", "-c", "copy"]
            else:
                # Output-side trim: packet-accurate for audio copy, sample-accurate when re-encoding.
                cmd += ["-i", str(list_path)] + trim + ["-map", "0"]
                if mode == "copy":
                    cmd += ["-c", "copy"]
                else:
                    if has_video:
                        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
                    cmd += ["-c:a", "aac", "-b:a", "192k"]
            if ext in ("mp4", "m4a"):
                cmd += ["-movflags", "+faststart"]
            cmd += ["-y", str(tmp_out)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=max(120.0, (p_end - p_start) * 2))
            if proc.returncode != 0 or not tmp_out.exists() or tmp_out.stat().st_size == 0:
                return f"ffmpeg failed: {(proc.stderr or '').strip()[-400:] or 'no output written'}"
            expected = p_end - p_start
            measured = _probe_duration_strict(tmp_out, self._ffprobe)
            if measured is None:
                return "output could not be read back"
            within = abs(measured - expected) <= tolerance
            if not within:
                return f"output duration {measured:.3f}s differs from expected {expected:.3f}s by more than {tolerance:.3f}s"
            digest = sha256_file(tmp_out)
            os.replace(tmp_out, final_path)
            return PreservedPart(
                file=str(final_path),
                sha256=digest,
                size=final_path.stat().st_size,
                utc_start=utc_iso(p_start),
                utc_end=utc_iso(p_end),
                expected_s=round(expected, 3),
                measured_s=round(measured, 3),
                within_tolerance=within,
                tolerance_s=round(tolerance, 3),
                run_id=part[0].run_id,
                segments=len(part),
            )
        except subprocess.TimeoutExpired:
            return "ffmpeg timed out"
        finally:
            if final_path.exists() and final_path.stat().st_size == 0:
                final_path.unlink(missing_ok=True)  # release the unused reservation
            for leftover in tmp_dir.glob("*"):
                leftover.unlink(missing_ok=True)
            tmp_dir.rmdir()

    def _witness(self, receipt: PreserveReceipt, event_type: str, actor: str, data: Mapping[str, Any]) -> None:
        if self.witness is None:
            return
        try:
            record = self.witness.record_event(event_type, source="recording", actor=actor, data=dict(data))
            if record:
                receipt.blackbox_records.append(str(record))
        except Exception as exc:
            logger.warning("BlackBox witness failed for %s: %s", event_type, exc)


__all__ = [
    "AmbiguousLocalTimeError",
    "NonexistentLocalTimeError",
    "PreserveReceipt",
    "PreservedPart",
    "RangeGap",
    "RangePreserver",
    "RangeRequestError",
    "ResolvedRange",
    "parse_clock_time",
    "resolve_local_range",
]

"""Real-media tests for segmented capture and time-range preservation.

These tests run FFmpeg for real. The input is a synthetic tone whose frequency
steps every second (400 Hz, 600 Hz, 800 Hz, ...), so the content of a
preserved file proves *which* seconds were copied, not just how long it is.
They are skipped (not faked) when ffmpeg/ffprobe are unavailable.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from modules.blackbox_runtime import create_blackbox_witness
from modules.range_preservation import (
    AmbiguousLocalTimeError,
    NonexistentLocalTimeError,
    RangePreserver,
    RangeRequestError,
    resolve_local_range,
)
from modules.segmented_capture import (
    CaptureLockedError,
    CaptureSpec,
    IndexIntegrityError,
    SegmentedCaptureRecorder,
    load_snapshot,
    parse_dshow_audio_devices,
    sha256_file,
    synthetic_tone_input,
    verify_index,
)

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed; real-media tests cannot run",
)

SAMPLE_RATE = 48000
STEP_EXPR = "400+200*floor(t)"  # second n plays 400 + 200n Hz


def _spec(source_id: str = "control_room_audio") -> CaptureSpec:
    return CaptureSpec(source_id=source_id, input_args=synthetic_tone_input(STEP_EXPR, SAMPLE_RATE), audio_bitrate="128k")


def _decode(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0


def _dominant_hz(samples: np.ndarray, start_s: float, end_s: float) -> float:
    window = samples[int(start_s * SAMPLE_RATE) : int(end_s * SAMPLE_RATE)]
    assert window.size > 1000, "analysis window empty"
    spectrum = np.abs(np.fft.rfft(window * np.hanning(window.size)))
    freqs = np.fft.rfftfreq(window.size, 1.0 / SAMPLE_RATE)
    return float(freqs[int(np.argmax(spectrum))])


def _rms(samples: np.ndarray) -> float:
    return float(np.sqrt(np.mean(samples**2)))


async def _wait_state(recorder: SegmentedCaptureRecorder, wanted: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    status = recorder.status()
    while time.monotonic() < deadline:
        status = recorder.status()
        if status["state"] == wanted:
            return status
        await asyncio.sleep(0.1)
    raise AssertionError(f"state {wanted!r} not reached; last status {status}")


async def _record(root: Path, seconds: float, **kwargs) -> SegmentedCaptureRecorder:
    recorder = SegmentedCaptureRecorder(root, _spec(), segment_seconds=1.0, **kwargs)
    await recorder.start()
    await _wait_state(recorder, "recording", 5.0)
    await asyncio.sleep(seconds)
    await recorder.stop()
    return recorder


# ── capture ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_capture_writes_contiguous_hashed_segments_with_utc_index(tmp_path: Path):
    spawned_utc = time.time()
    recorder = SegmentedCaptureRecorder(tmp_path, _spec(), segment_seconds=1.0)
    await recorder.start()
    live = await _wait_state(recorder, "recording", 5.0)
    assert live["recording"] is True
    await asyncio.sleep(4.2)
    final = await recorder.stop()
    assert final["state"] == "stopped" and final["recording"] is False

    check = verify_index(tmp_path / "index.jsonl")
    assert check.ok, check.error
    snap = load_snapshot(tmp_path)
    assert len(snap.segments) >= 4
    assert all(seg.status == "final" for seg in snap.segments)
    for seg in snap.segments:
        assert sha256_file(seg.path) == seg.sha256
    for prev, nxt in zip(snap.segments, snap.segments[1:]):
        assert abs(nxt.utc_start - prev.utc_end) < 0.05, "segments must be contiguous in UTC"
    first = snap.segments[0]
    # lavfi can emit a few hundred ms before real time even with -re; a real
    # microphone cannot. This is a plausibility bound, not a latency claim.
    assert spawned_utc - 1.0 <= first.utc_start <= spawned_utc + 2.0, "UTC anchor implausible"
    assert all(seg.timing_uncertainty_s < 0.1 for seg in snap.segments), [s.timing_uncertainty_s for s in snap.segments]
    runs = list(snap.runs.values())
    assert len(runs) == 1 and runs[0]["end"]["reason"] == "stopped" and runs[0]["end"]["clean"] is True


@pytest.mark.asyncio
async def test_second_recorder_on_same_directory_is_refused(tmp_path: Path):
    first = SegmentedCaptureRecorder(tmp_path, _spec(), segment_seconds=1.0)
    await first.start()
    try:
        second = SegmentedCaptureRecorder(tmp_path, _spec(), segment_seconds=1.0)
        with pytest.raises(CaptureLockedError):
            await second.start()
    finally:
        await first.stop()


@pytest.mark.skipif(sys.platform == "win32", reason="SIGSTOP is POSIX-only")
@pytest.mark.asyncio
async def test_stalled_encoder_is_reported_as_stalled_not_recording(tmp_path: Path):
    recorder = SegmentedCaptureRecorder(tmp_path, _spec(), segment_seconds=1.0, stall_after_s=1.5)
    await recorder.start()
    await _wait_state(recorder, "recording", 5.0)
    proc = recorder._run.proc
    proc.send_signal(signal.SIGSTOP)
    try:
        stalled = await _wait_state(recorder, "stalled", 4.0)
        assert stalled["recording"] is False
    finally:
        proc.send_signal(signal.SIGCONT)
    await _wait_state(recorder, "recording", 5.0)
    await recorder.stop()


@pytest.mark.asyncio
async def test_crash_restarts_as_new_run_and_preservation_reports_the_gap(tmp_path: Path):
    witness = create_blackbox_witness(tmp_path / "bbx", session_id="crash_test")
    recorder = SegmentedCaptureRecorder(tmp_path / "cap", _spec(), segment_seconds=1.0, witness=witness, max_restarts=2)
    await recorder.start()
    await _wait_state(recorder, "recording", 5.0)
    await asyncio.sleep(2.6)
    recorder._run.proc.kill()
    restarting = await _wait_state(recorder, "restarting", 5.0)
    assert restarting["recording"] is False
    assert "exited unexpectedly" in (restarting["last_error"] or "")
    await _wait_state(recorder, "recording", 10.0)
    await asyncio.sleep(2.6)
    await recorder.stop()

    snap = load_snapshot(tmp_path / "cap")
    ends = [run["end"] for run in snap.runs.values()]
    assert sorted(e["reason"] for e in ends) == ["crashed", "stopped"]
    run_ids = list(snap.runs)
    first_run = [s for s in snap.segments if s.run_id == run_ids[0]]
    second_run = [s for s in snap.segments if s.run_id == run_ids[1]]
    assert first_run and second_run

    preserver = RangePreserver(tmp_path / "cap", tmp_path / "out", witness=witness)
    receipt = await preserver.preserve(first_run[0].utc_start + 0.5, second_run[-1].utc_end - 0.5)
    assert receipt.status == "partial", receipt.to_dict()
    assert receipt.gaps, "restart gap must be reported"
    assert {p.run_id for p in receipt.parts} <= set(run_ids)
    assert len({p.run_id for p in receipt.parts}) == len(receipt.parts), "a part must never span two runs"
    assert receipt.originals_unchanged is True
    for gap in receipt.gaps:
        assert gap.seconds > 0 and gap.reason
    assert witness.verify().ok


@pytest.mark.asyncio
async def test_interrupted_program_run_is_closed_and_leftovers_indexed_on_next_start(tmp_path: Path):
    abandoned = SegmentedCaptureRecorder(tmp_path, _spec(), segment_seconds=1.0, auto_restart=False)
    await abandoned.start()
    await _wait_state(abandoned, "recording", 5.0)
    await asyncio.sleep(2.4)
    # Simulate the whole program dying: no stop(), no run_end record.
    abandoned._supervisor.cancel()
    for task in abandoned._tasks:
        task.cancel()
    abandoned._run.proc.kill()
    await abandoned._run.proc.wait()
    # A real process death releases its open files; the in-process simulation
    # must do so explicitly or the abandoned FFmpeg log handle leaks.
    abandoned._run.log_handle.close()
    abandoned._lock.release()
    abandoned._locked = False

    survivor = SegmentedCaptureRecorder(tmp_path, _spec(), segment_seconds=1.0)
    await survivor.start()
    await survivor.stop()
    snap = load_snapshot(tmp_path)
    reasons = sorted(run["end"]["reason"] for run in snap.runs.values())
    assert reasons == ["interrupted", "stopped"]
    assert verify_index(tmp_path / "index.jsonl").ok


# ── preservation ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_preserved_range_contains_exactly_the_requested_seconds(tmp_path: Path):
    cap, out = tmp_path / "cap", tmp_path / "out"
    witness = create_blackbox_witness(tmp_path / "bbx", session_id="preserve_test")
    await _record(cap, 6.0, witness=witness)
    snap = load_snapshot(cap)
    sources_before = {seg.path: sha256_file(seg.path) for seg in snap.segments}
    origin = snap.segments[0].utc_start  # UTC of media t=0

    preserver = RangePreserver(cap, out, witness=witness)
    receipt = await preserver.preserve(origin + 2.0, origin + 4.0, label="seconds 2-4")
    assert receipt.status == "completed", receipt.to_dict()
    assert receipt.originals_unchanged is True
    assert len(receipt.parts) == 1 and not receipt.gaps
    part = receipt.parts[0]
    assert part.file.endswith(".m4a")
    assert abs(part.measured_s - 2.0) <= part.tolerance_s
    assert sha256_file(Path(part.file)) == part.sha256

    audio = _decode(Path(part.file))
    assert _rms(audio) > 0.3, "tone must be audibly present"
    assert abs(_dominant_hz(audio, 0.15, 0.85) - 800) < 15, "first second of output must be media second 2 (800 Hz)"
    assert abs(_dominant_hz(audio, 1.15, 1.85) - 1000) < 15, "second second of output must be media second 3 (1000 Hz)"

    # Locate the 800 -> 1000 Hz step inside the output: must sit at 1.0 s.
    hop = 0.02
    steps = [t for t in np.arange(0.6, 1.4, hop) if _dominant_hz(audio, t, t + 0.1) > 900]
    # A 0.1 s window turns dominant once more than half of it lies past the step.
    assert steps and abs(steps[0] + 0.05 - 1.0) < 0.06, f"step found at {steps[:1]}"

    for path, digest in sources_before.items():
        assert sha256_file(path) == digest, "original recording must be untouched"

    again = await preserver.preserve(origin + 2.0, origin + 4.0, label="seconds 2-4")
    assert again.status == "completed"
    assert again.parts[0].file != part.file, "existing output must never be overwritten"
    assert Path(part.file).exists()

    assert witness.verify().ok
    assert len(receipt.blackbox_records) == 2  # request + outcome


@pytest.mark.asyncio
async def test_exact_mode_and_segment_boundary_spanning_range(tmp_path: Path):
    cap, out = tmp_path / "cap", tmp_path / "out"
    await _record(cap, 5.0)
    origin = load_snapshot(cap).segments[0].utc_start
    receipt = await RangePreserver(cap, out).preserve(origin + 1.3, origin + 3.7, mode="exact")
    assert receipt.status == "completed", receipt.to_dict()
    part = receipt.parts[0]
    assert part.segments >= 3
    assert abs(part.measured_s - 2.4) <= part.tolerance_s
    audio = _decode(Path(part.file))
    assert abs(_dominant_hz(audio, 0.05, 0.6) - 600) < 15   # media 1.3-1.9 -> 600 Hz
    assert abs(_dominant_hz(audio, 1.8, 2.3) - 1000) < 15   # media 3.1-3.6 -> 1000 Hz


@pytest.mark.asyncio
async def test_range_with_no_recording_fails_truthfully(tmp_path: Path):
    cap, out = tmp_path / "cap", tmp_path / "out"
    await _record(cap, 2.0)
    origin = load_snapshot(cap).segments[0].utc_start
    receipt = await RangePreserver(cap, out).preserve(origin + 3600, origin + 3700)
    assert receipt.status == "failed"
    assert receipt.parts == []
    assert "no recorded media" in receipt.reason
    assert not list(out.glob("*.m4a"))


@pytest.mark.asyncio
async def test_range_running_past_live_edge_is_partial_with_trailing_gap(tmp_path: Path):
    cap, out = tmp_path / "cap", tmp_path / "out"
    recorder = SegmentedCaptureRecorder(cap, _spec(), segment_seconds=1.0)
    await recorder.start()
    await _wait_state(recorder, "recording", 5.0)
    await asyncio.sleep(3.2)
    try:
        origin = load_snapshot(cap).segments[0].utc_start
        preserver = RangePreserver(cap, out, recorder=recorder)
        receipt = await preserver.preserve(origin + 0.5, origin + 120.0, wait_timeout_s=1.0)
    finally:
        await recorder.stop()
    assert receipt.status == "partial", receipt.to_dict()
    assert receipt.gaps and "not recorded yet" in receipt.gaps[-1].reason


@pytest.mark.asyncio
async def test_altered_source_segment_blocks_preservation(tmp_path: Path):
    cap, out = tmp_path / "cap", tmp_path / "out"
    await _record(cap, 3.0)
    snap = load_snapshot(cap)
    victim = snap.segments[1].path
    data = bytearray(victim.read_bytes())
    data[-10] ^= 0xFF
    victim.write_bytes(bytes(data))
    origin = snap.segments[0].utc_start
    receipt = await RangePreserver(cap, out).preserve(origin + 0.2, origin + 2.5)
    assert receipt.status == "failed"
    assert receipt.originals_unchanged is False
    assert victim.name in receipt.reason


@pytest.mark.asyncio
async def test_edited_index_is_detected(tmp_path: Path):
    cap, out = tmp_path / "cap", tmp_path / "out"
    await _record(cap, 2.0)
    index = cap / "index.jsonl"
    lines = index.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[2])
    record["utc_start"] = record["utc_start"] - 30
    lines[2] = json.dumps(record)
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert verify_index(index).ok is False
    with pytest.raises(IndexIntegrityError):
        load_snapshot(cap)
    origin = time.time()
    receipt = await RangePreserver(cap, out).preserve(origin - 10, origin)
    assert receipt.status == "failed" and "index failed verification" in receipt.reason


# ── local time resolution ──────────────────────────────────────────────────────
def test_local_range_example_resolves_to_exact_utc():
    rng = resolve_local_range("2026-10-20", "6:36 p.m.", "8:49 p.m.")
    assert rng.to_dict()["utc_start"] == "2026-10-21T01:36:00.000Z"
    assert rng.to_dict()["utc_end"] == "2026-10-21T03:49:00.000Z"
    assert rng.crosses_midnight is False


def test_fall_back_hour_requires_a_choice():
    with pytest.raises(AmbiguousLocalTimeError) as info:
        resolve_local_range("2026-11-01", "1:30", "1:45")
    assert info.value.candidates_utc == ["2026-11-01T08:30:00.000Z", "2026-11-01T09:30:00.000Z"]
    second = resolve_local_range("2026-11-01", "1:30", "1:45", start_fold=1, end_fold=1)
    assert second.to_dict()["utc_start"] == "2026-11-01T09:30:00.000Z"


def test_spring_forward_gap_is_rejected():
    with pytest.raises(NonexistentLocalTimeError):
        resolve_local_range("2026-03-08", "2:30", "3:30")


def test_overnight_range_and_bad_input():
    rng = resolve_local_range("2026-10-20", "11 pm", "1:15 am")
    assert rng.crosses_midnight and rng.utc_end - rng.utc_start == pytest.approx(8100)
    with pytest.raises(RangeRequestError):
        resolve_local_range("10/20/2026", "1:00", "2:00")
    with pytest.raises(RangeRequestError):
        resolve_local_range("2026-10-20", "13:00 pm", "2:00")


# ── Windows microphone listing parser (format samples, not a live Windows run) ─
def test_dshow_device_parser_handles_both_ffmpeg_formats():
    modern = (
        '[dshow @ 0000] "Integrated Camera" (video)\n'
        '[dshow @ 0000]   Alternative name "@device_pnp_\\\\?\\usb#vid"\n'
        '[dshow @ 0000] "Microphone Array (Realtek(R) Audio)" (audio)\n'
        '[dshow @ 0000]   Alternative name "@device_cm_{33D9A762}\\wave_{ABC}"\n'
        '[dshow @ 0000] "Stereo Mix (Realtek(R) Audio)" (audio)\n'
    )
    legacy = (
        "[dshow @ 0000] DirectShow video devices (some may be both video and audio devices)\n"
        '[dshow @ 0000]  "Integrated Camera"\n'
        "[dshow @ 0000] DirectShow audio devices\n"
        '[dshow @ 0000]  "Headset Microphone (USB Audio)"\n'
        '[dshow @ 0000]     Alternative name "@device_cm_{33D9A762}\\wave_{DEF}"\n'
    )
    assert parse_dshow_audio_devices(modern) == ["Microphone Array (Realtek(R) Audio)", "Stereo Mix (Realtek(R) Audio)"]
    assert parse_dshow_audio_devices(legacy) == ["Headset Microphone (USB Audio)"]


@pytest.mark.asyncio
async def test_video_with_audio_copy_cut_is_decodable_and_within_keyframe_tolerance(tmp_path: Path):
    cap, out = tmp_path / "cap", tmp_path / "out"
    video_input = ("-re", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30")
    spec = CaptureSpec(
        source_id="program",
        input_args=video_input + synthetic_tone_input(STEP_EXPR, SAMPLE_RATE),
        video_codec="h264",
        video_bitrate="500k",
        frame_rate=30,
        audio_bitrate="96k",
        keyframe_seconds=1.0,
    )
    recorder = SegmentedCaptureRecorder(cap, spec, segment_seconds=2.0)
    await recorder.start()
    await _wait_state(recorder, "recording", 8.0)
    await asyncio.sleep(5.0)
    await recorder.stop()
    snap = load_snapshot(cap)
    origin = snap.segments[0].utc_start
    receipt = await RangePreserver(cap, out, source_id="program", keyframe_seconds=1.0).preserve(origin + 1.5, origin + 3.5)
    assert receipt.status == "completed", receipt.to_dict()
    part = receipt.parts[0]
    assert part.file.endswith(".mp4")
    # Every frame must decode cleanly from the first one (no broken leading GOP).
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", part.file, "-f", "null", "-"], capture_output=True, text=True)
    assert decode.returncode == 0 and decode.stderr.strip() == "", decode.stderr
    assert abs(part.measured_s - 2.0) <= part.tolerance_s

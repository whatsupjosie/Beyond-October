"""Speech boundaries and real optional CPU providers (no fake recognizer/voice)."""
from __future__ import annotations

import asyncio
import hashlib
import io
import os
import signal
import wave
from pathlib import Path

import pytest

from modules.data_checkpoint import create_checkpoint, restore_checkpoint
from modules.speech_preferences import PreferenceConflict, SpeechPreferences
from modules.speech_worker import SpeechInputError
from modules.stt_engine import STTEngine, _decode_audio
from modules.tts_engine import TTSEngine, wav_info

PHRASE = "The studio lights are ready. Please save this recording before you close the program."


def speech_environment(monkeypatch) -> Path:
    configured = os.environ.get("PUBCAST_SPEECH_TEST_MODELS")
    if not configured:
        pytest.skip("Real speech acceptance requires explicitly installed PUBCAST_SPEECH_TEST_MODELS")
    root = Path(configured)
    monkeypatch.setenv("PUBCAST_TTS_ENGINE", "kokoro")
    monkeypatch.setenv("PUBCAST_KOKORO_MODEL", str(root / "kokoro/assets/model.onnx"))
    monkeypatch.setenv("PUBCAST_KOKORO_VOICES", str(root / "kokoro/assets/voices.bin"))
    monkeypatch.setenv("PUBCAST_STT_MODEL_PATH", str(root / "whisper-tiny.en/assets"))
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    return root


def test_speech_choices_are_owner_scoped_revisioned_and_recoverable(tmp_path):
    data = tmp_path / "data"
    store = SpeechPreferences(data)
    settings = {"voice_id": "am_michael", "speed": .9, "language": "en"}
    expected = store.put("first-owner", settings, 0)
    assert expected["revision"] == 1
    assert store.get("other-owner")["voice_id"] == "default"
    with pytest.raises(PreferenceConflict):
        store.put("first-owner", settings, 0)
    checkpoint = tmp_path / "speech.zip"
    create_checkpoint(data, checkpoint, offline=True)
    restore_checkpoint(checkpoint, tmp_path / "recovered")
    assert SpeechPreferences(tmp_path / "recovered/data").get("first-owner") == expected


def test_missing_models_are_unavailable_without_starting_a_worker(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_TTS_ENGINE", "kokoro")
    monkeypatch.setenv("PUBCAST_KOKORO_MODEL", str(tmp_path / "absent.onnx"))
    monkeypatch.setenv("PUBCAST_KOKORO_VOICES", str(tmp_path / "absent.bin"))
    stt = STTEngine(data_dir=tmp_path, model_path=str(tmp_path / "absent"))
    tts = TTSEngine(tmp_path)
    for engine in (stt, tts):
        assert not engine.status()["available"]
        assert not engine.status()["loaded"]
        assert engine._worker.pid is None


@pytest.mark.parametrize("payload,code", [({"text": ""},400), ({"text": "x"*2001},413),
    ({"text": "x\0"},413), ({"text": "valid", "speed": float("nan")},400),
    ({"text": "valid", "speed": True},400), ({"text": "valid", "character_id": "../../private"},400),
    ({"text": "valid", "language": []},400)])
async def test_invalid_synthesis_never_starts_a_worker(tmp_path, payload, code):
    engine = TTSEngine(tmp_path)
    assert (await engine.synthesize(**payload))["status_code"] == code
    assert engine._worker.pid is None


def test_decoder_rejects_playlists_and_decoded_duration_not_just_upload_size():
    pytest.importorskip("av", reason="Audio decoder checks require requirements-speech.txt")
    with pytest.raises(SpeechInputError) as error:
        _decode_audio(b"#EXTM3U\nhttp://127.0.0.1/private")
    assert error.value.status == 415
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setparams((1,2,8000,0,"NONE","not compressed"))
        stream.writeframes(b"\0\0" * (61 * 8000))
    with pytest.raises(SpeechInputError) as error:
        _decode_audio(output.getvalue())
    assert error.value.status == 413


async def test_real_neural_roundtrip_word_times_two_voices_and_clean_shutdown(tmp_path, monkeypatch):
    speech_environment(monkeypatch)
    tts, stt = TTSEngine(tmp_path), STTEngine(data_dir=tmp_path)
    try:
        assert tts.status()["available"] and not tts.status()["loaded"]
        first = await tts.synthesize(PHRASE, voice_id="af_heart")
        assert first["ok"], first
        assert first["sample_rate"] == 24000
        assert first["duration"] == first["sample_count"] / first["sample_rate"]
        transcript = await stt.transcribe(first["audio"], "audio/wav", language="en")
        assert transcript["ok"], transcript
        assert transcript["text"] == PHRASE
        words = [word for segment in transcript["segments"] for word in segment["words"]]
        assert len(words) == len(PHRASE.split())
        assert all(0 <= word["start"] <= word["end"] <= transcript["duration"] + .05 for word in words)
        assert tts.status()["ready"] and stt.status()["ready"]
        second = await tts.synthesize(PHRASE, voice_id="am_michael", language="EN")
        assert second["ok"] and first["audio"] != second["audio"]
        assert second["voice_id"] == "am_michael"
        assert wav_info(second["audio"])["duration"] > 2
        assert (await stt.transcribe(b"RIFFnot-a-real-wave", "audio/wav"))["status_code"] == 415
        assert (await stt.transcribe(b"text", "text/plain"))["status_code"] == 415
    finally:
        await tts.close(); await stt.close()
    assert tts._worker.pid is None and stt._worker.pid is None


async def test_real_worker_busy_cancel_timeout_and_next_request_recovers(tmp_path, monkeypatch):
    speech_environment(monkeypatch)
    engine = TTSEngine(tmp_path)
    try:
        assert (await engine.synthesize("This is a cancellation check."))["ok"]
        # Suspend an actual owned model process to make the adverse condition deterministic.
        if os.name == "nt":
            pytest.skip("SIGSTOP adverse-condition probe is POSIX-specific")
        pid = engine._worker.pid
        os.kill(pid, signal.SIGSTOP)
        active = asyncio.create_task(engine.synthesize(PHRASE))
        while not engine._worker.busy:
            await asyncio.sleep(.01)
        assert (await engine.synthesize("busy"))["status_code"] == 429
        active.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(active, 10)
        assert engine._worker.pid is None and not engine._worker.busy
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
        assert (await engine.synthesize("A fresh request works after cancellation."))["ok"]
        pid = engine._worker.pid
        os.kill(pid, signal.SIGSTOP)
        engine._worker.timeout = .15
        assert (await engine.synthesize(PHRASE))["status_code"] == 504
        assert engine._worker.pid is None
        engine._worker.timeout = 150
        assert (await engine.synthesize("The timeout recovery also works."))["ok"]
    finally:
        await engine.close()


async def test_actual_basic_local_voice(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_TTS_ENGINE", "flite")
    engine = TTSEngine(tmp_path)
    if not engine.status()["available"]:
        pytest.skip("Basic fallback acceptance requires FFmpeg with flite")
    try:
        result = await engine.synthesize("The local basic voice is speaking.")
        assert result["ok"], result
        assert result["engine"] == "flite"
        assert wav_info(result["audio"])["duration"] > 1
    finally:
        await engine.close()

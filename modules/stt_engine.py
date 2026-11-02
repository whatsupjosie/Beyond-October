"""
modules/stt_engine.py — Local, bounded faster-whisper transcription.

The configured model must already exist on disk. Startup and inference never
download a model. A separate owned process permits real stop/timeout/shutdown.

Feic Mo Chroí — Rear View Foresight LLC 2026
"""
from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .speech_worker import SpeechInputError, SpeechWorker, failure

MAX_AUDIO_BYTES = 8 * 1024 * 1024
MAX_AUDIO_SECONDS = 60
_ALLOWED_MIMES = {"audio/webm", "video/webm", "audio/ogg", "audio/wav", "audio/x-wav",
                  "audio/mp4", "audio/mpeg", "audio/x-m4a", "audio/flac", "audio/aac"}
_MODEL = None


def _decode_audio(data: bytes):
    """Bound decoded samples independently of compressed size or metadata."""
    import av
    import numpy as np

    if not data or len(data) > MAX_AUDIO_BYTES:
        raise SpeechInputError("Audio must contain between 1 byte and 8 MiB", 413 if data else 400)
    # Only media signatures, never playlists/URLs passed through a decoder.
    recognized = (data.startswith((b"RIFF", b"OggS", b"\x1aE\xdf\xa3", b"fLaC", b"ID3"))
                  or data[4:8] == b"ftyp"
                  or (len(data) > 1 and data[0] == 255 and data[1] & 0xE0 == 0xE0))
    if not recognized:
        raise SpeechInputError("Unsupported or malformed audio container", 415)
    chunks, samples = [], 0
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)

    def retain(frames):
        nonlocal samples
        for frame in frames:
            values = frame.to_ndarray().ravel()
            samples += len(values)
            if samples > MAX_AUDIO_SECONDS * 16000:
                raise SpeechInputError("Audio exceeds the 60-second dictation limit", 413)
            chunks.append(values.astype(np.float32) / 32768)

    try:
        with av.open(io.BytesIO(data), mode="r") as container:
            if not container.streams.audio:
                raise SpeechInputError("The recording contains no audio stream", 415)
            for frame in container.decode(audio=0):
                retain(resampler.resample(frame))
            retain(resampler.resample(None))
    except SpeechInputError:
        raise
    except Exception as error:
        raise SpeechInputError("Audio could not be decoded", 415) from error
    if not samples:
        raise SpeechInputError("The recording contains no decoded audio", 415)
    return np.concatenate(chunks)


def _transcribe_worker(payload: dict, config: dict) -> dict:
    global _MODEL
    from faster_whisper import WhisperModel

    audio = _decode_audio(payload["audio"])
    if _MODEL is None:
        _MODEL = WhisperModel(config["model_path"], device=config["device"],
                              compute_type=config["compute_type"], cpu_threads=config["threads"],
                              num_workers=1, local_files_only=True)
    segments, info = _MODEL.transcribe(
        audio, language=payload.get("language"), initial_prompt=payload.get("prompt"),
        beam_size=5, vad_filter=True, word_timestamps=True, condition_on_previous_text=False,
        vad_parameters={"min_silence_duration_ms": 500})
    rows = []
    for segment in segments:
        rows.append({"start": float(segment.start), "end": float(segment.end),
                     "text": segment.text.strip(),
                     "words": [{"start": float(w.start), "end": float(w.end),
                                "word": w.word, "probability": float(w.probability)}
                               for w in segment.words or []]})
    return {"ok": True, "text": " ".join(row["text"] for row in rows).strip(),
            "segments": rows, "language": info.language, "duration": len(audio) / 16000,
            "engine": "faster-whisper", "_loaded": True}


class STTEngine:
    """One configured recognizer; callers retain the original text/voice decisions."""

    def __init__(self, model_size: str = "tiny.en", device: str = "auto",
                 compute_type: str = "auto", language: Optional[str] = None,
                 data_dir: Path | None = None, model_path: str | None = None):
        self.model_size = model_size
        self.language = language
        self.device = "cpu" if device == "auto" else device
        if self.device not in {"cpu", "cuda"}:
            raise ValueError("STT device must be cpu, cuda or auto")
        self.compute_type = ("int8" if self.device == "cpu" else "float16") if compute_type == "auto" else compute_type
        data = Path(data_dir or os.environ.get("PUBCAST_DATA_DIR", "data"))
        configured = model_path or os.environ.get("PUBCAST_STT_MODEL_PATH")
        self.model_path = Path(configured or (model_size if Path(model_size).is_dir()
                                              else data / "speech" / "models" / ("whisper-" + model_size) / "assets"))
        self._worker = SpeechWorker("stt", {"model_path": str(self.model_path.resolve()),
                                            "device": self.device, "compute_type": self.compute_type,
                                            "threads": 2}, timeout=90)

    def status(self) -> Dict[str, Any]:
        worker = self._worker.state()
        missing = [name for name in ("model.bin", "config.json", "tokenizer.json")
                   if not (self.model_path / name).is_file()]
        dependency = importlib.util.find_spec("faster_whisper") is not None
        available = dependency and not missing
        reason = ("Install the optional local speech dependencies" if not dependency else
                  "Install the local recognition model or configure PUBCAST_STT_MODEL_PATH" if missing else None)
        return {"available": available, "configured": not missing, "loaded": worker["loaded"],
                "ready": available and worker["loaded"] and not worker["last_error"], "busy": worker["busy"],
                "state": "unavailable" if not available else "error" if worker["last_error"] else
                         "ready" if worker["loaded"] else "configured_not_loaded",
                "reason": reason, "last_error": worker["last_error"],
                "model": self.model_size, "device": self.device, "compute_type": self.compute_type,
                "language": self.language or ("en" if self.model_size.endswith(".en") else "auto-detect"),
                "max_audio_seconds": MAX_AUDIO_SECONDS, "max_audio_bytes": MAX_AUDIO_BYTES}

    async def transcribe(self, audio_data: bytes, mime_type: str = "audio/webm",
                         language: Optional[str] = None, prompt: Optional[str] = None) -> Dict[str, Any]:
        if not isinstance(audio_data, bytes) or not audio_data:
            return failure("Empty audio data", 400, "invalid_input")
        if len(audio_data) > MAX_AUDIO_BYTES:
            return failure("Audio exceeds the 8 MiB dictation limit", 413, "input_limit")
        if mime_type.split(";")[0].strip().lower() not in _ALLOWED_MIMES:
            return failure("Unsupported audio media type", 415, "invalid_input")
        language = language or self.language
        if language is not None and (not isinstance(language, str) or len(language) > 12 or
                                     not language.replace("-", "").isalpha()):
            return failure("Invalid recognition language", 400, "invalid_input")
        if self.model_size.endswith(".en") and language not in (None, "en"):
            return failure("This installed recognition model supports English only", 400, "invalid_input")
        if prompt is not None and (not isinstance(prompt, str) or len(prompt) > 1024):
            return failure("Recognition hint must be at most 1024 characters", 400, "input_limit")
        state = self.status()
        if not state["available"]:
            return failure(state["reason"], 503, "unavailable")
        return await self._worker.call({"audio": audio_data, "language": language, "prompt": prompt})

    async def close(self) -> None:
        await self._worker.close()


def _mime_to_suffix(mime: str) -> str:
    return {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/wav": ".wav",
            "audio/mp4": ".mp4", "audio/mpeg": ".mp3", "audio/x-m4a": ".m4a"}.get(mime.split(";")[0].strip(), ".webm")

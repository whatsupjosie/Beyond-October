"""
modules/tts_engine.py — Local character speech with configurable voices.

Kokoro runs on CPU from explicitly installed local weights. Basic system speech
is available where its native provider is present. XTTS remains an explicit,
local-files-only adapter; no automatic model download or GPU initialization.

Feic Mo Chroí — Rear View Foresight LLC 2026
"""
from __future__ import annotations

import base64
import importlib.util
import io
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import wave
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional

from .speech_worker import SpeechInputError, SpeechWorker, failure

MAX_TEXT = 2000
MAX_SPEECH_SECONDS = 180
MAX_WAV_BYTES = 20 * 1024 * 1024
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_TTS_MODEL = None
DATA_DIR = Path(os.environ.get("PUBCAST_DATA_DIR", "data"))
VOICES_DIR = DATA_DIR / "voices"


def wav_info(audio: bytes) -> dict:
    if not audio or len(audio) > MAX_WAV_BYTES:
        raise SpeechInputError("Generated audio exceeds its byte limit", 413)
    try:
        with wave.open(io.BytesIO(audio), "rb") as source:
            frames, rate, channels = source.getnframes(), source.getframerate(), source.getnchannels()
            if source.getcomptype() != "NONE" or not 8000 <= rate <= 192000 or channels not in (1, 2):
                raise ValueError("Unsupported generated WAV")
            expected = frames * channels * source.getsampwidth()
            if len(source.readframes(frames)) != expected:
                raise ValueError("Truncated generated WAV")
    except (wave.Error, EOFError, ValueError) as error:
        raise SpeechInputError("Speech provider returned invalid WAV audio", 503) from error
    duration = frames / rate
    if not frames or duration > MAX_SPEECH_SECONDS:
        raise SpeechInputError("Generated speech exceeds its duration limit", 413)
    return {"duration": duration, "sample_count": frames, "sample_rate": rate, "channels": channels}


def _pcm_wav(samples, rate: int) -> bytes:
    import numpy as np
    values = np.asarray(samples, dtype=np.float32).ravel()
    if len(values) > rate * MAX_SPEECH_SECONDS or not np.isfinite(values).all():
        raise SpeechInputError("Speech provider produced invalid or excessive samples", 413)
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        stream.writeframes((np.clip(values, -1, 1) * 32767).astype("<i2").tobytes())
    return output.getvalue()


def _synthesize_worker(payload: dict, config: dict) -> dict:
    global _TTS_MODEL
    backend = config["backend"]
    if backend == "kokoro":
        import onnxruntime as ort
        from kokoro_onnx import Kokoro
        if _TTS_MODEL is None:
            options = ort.SessionOptions()
            options.intra_op_num_threads = config["threads"]
            options.inter_op_num_threads = 1
            session = ort.InferenceSession(config["model_path"], sess_options=options,
                                            providers=["CPUExecutionProvider"])
            _TTS_MODEL = Kokoro.from_session(session, config["voices_path"])
        samples, rate = _TTS_MODEL.create(payload["text"], voice=payload["voice_id"],
                                          speed=payload["speed"], lang=payload["language"])
        audio = _pcm_wav(samples, rate)
    elif backend == "xtts":
        from TTS.api import TTS
        if _TTS_MODEL is None:
            _TTS_MODEL = TTS(model_path=config["model_path"], config_path=config["config_path"],
                              gpu=config.get("device") == "cuda", progress_bar=False)
        samples = _TTS_MODEL.tts(text=payload["text"], speaker_wav=payload["reference"],
                                 language=payload["language"], speed=payload["speed"])
        audio = _pcm_wav(samples, int(_TTS_MODEL.synthesizer.output_sample_rate))
    else:
        # Text is a data file/stdin payload, never interpolated into a command.
        with tempfile.TemporaryDirectory(prefix="pubcast-speech-") as directory:
            root = Path(directory)
            output = root / "speech.wav"
            if backend == "flite":
                (root / "text.txt").write_text(payload["text"], encoding="utf-8")
                command = [config["executable"], "-nostdin", "-hide_banner", "-loglevel", "error",
                           "-f", "lavfi", "-i", "flite=textfile=text.txt:voice=" + payload["voice_id"],
                           "-af", "atempo=" + str(payload["speed"]), "-c:a", "pcm_s16le", str(output)]
                subprocess.run(command, cwd=root, capture_output=True, check=True, timeout=120)
            elif backend == "sapi":
                script = r"""
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
$p = [Console]::In.ReadToEnd() | ConvertFrom-Json
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $s.Rate = [Math]::Max(-10, [Math]::Min(10, [int](($p.speed - 1.0) * 10)))
    $s.SetOutputToWaveFile($p.output)
    $s.Speak([string]$p.text)
} finally { $s.Dispose() }
"""
                encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
                subprocess.run([config["executable"], "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                               input=json.dumps({"text": payload["text"], "speed": payload["speed"],
                                                 "output": str(output)}).encode("utf-8"),
                               capture_output=True, check=True, timeout=120)
            else:
                raise SpeechInputError("No local speech provider is configured", 503)
            if output.stat().st_size > MAX_WAV_BYTES:
                raise SpeechInputError("Generated audio exceeds its byte limit", 413)
            audio = output.read_bytes()
    return {"ok": True, "audio": audio, "mime_type": "audio/wav", **wav_info(audio),
            "voice_id": payload["voice_id"], "character": payload["character_id"],
            "engine": backend, "_loaded": True}


class TTSEngine:
    """One speech configuration, one owned worker and one local voice catalogue."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.voices_dir = self.data_dir / "voices"
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        assets = self.data_dir / "speech" / "models" / "kokoro" / "assets"
        model = Path(os.environ.get("PUBCAST_KOKORO_MODEL", str(assets / "model.onnx")))
        voices = Path(os.environ.get("PUBCAST_KOKORO_VOICES", str(assets / "voices.bin")))
        requested = os.environ.get("PUBCAST_TTS_ENGINE", "auto").strip().lower()
        self._reason = None
        neural = model.is_file() and voices.is_file() and importlib.util.find_spec("kokoro_onnx") is not None
        executable = shutil.which("ffmpeg")
        flite = False
        if executable and (requested == "flite" or (requested == "auto" and not neural)):
            try:
                probe = subprocess.run([executable, "-hide_banner", "-filters"], capture_output=True,
                                       text=True, timeout=3)
                flite = probe.returncode == 0 and bool(re.search(r"\bflite\s", probe.stdout))
            except (OSError, subprocess.SubprocessError):
                pass
        sapi = shutil.which("powershell.exe") if os.name == "nt" else None
        if requested == "auto":
            self.backend = "kokoro" if neural else "sapi" if sapi else "flite" if flite else "unavailable"
        else:
            self.backend = requested
        config = {"backend": self.backend, "model_path": str(model.resolve()),
                  "voices_path": str(voices.resolve()), "threads": 2}
        if self.backend == "kokoro":
            self._available = neural
            self._reason = None if neural else "Install the local neural voice pack and optional speech dependencies"
        elif self.backend == "flite":
            self._available = flite
            config["executable"] = executable
            self._reason = None if flite else "This FFmpeg installation has no basic local voice provider"
        elif self.backend == "sapi":
            self._available = bool(sapi)
            config["executable"] = sapi
            self._reason = None if sapi else "Native Windows speech is unavailable on this host"
        elif self.backend == "xtts":
            model = Path(os.environ.get("PUBCAST_XTTS_MODEL", ""))
            metadata = Path(os.environ.get("PUBCAST_XTTS_CONFIG", ""))
            self._available = model.is_file() and metadata.is_file() and importlib.util.find_spec("TTS") is not None
            config.update(model_path=str(model.resolve()), config_path=str(metadata.resolve()),
                          device=os.environ.get("PUBCAST_TTS_DEVICE", "cpu"))
            self._reason = None if self._available else "XTTS requires explicit local checkpoint/config files and its optional dependency"
        else:
            self._available = False
            self._reason = "Install a local voice pack or configure an available system speech provider"
        self._config = config
        self._worker = SpeechWorker("tts", config, timeout=150)

    def _voice_file(self, character_id: str) -> Optional[Path]:
        if not _ID.fullmatch(character_id):
            return None
        for name in (character_id, "default"):
            for extension in (".wav", ".mp3", ".ogg", ".flac"):
                candidate = self.voices_dir / (name + extension)
                if candidate.is_file() and not candidate.is_symlink() and candidate.resolve().is_relative_to(self.voices_dir.resolve()):
                    return candidate
        return None

    def list_voices(self) -> Dict[str, Any]:
        if not self._available:
            return {}
        if self.backend == "kokoro":
            try:
                with zipfile.ZipFile(self._config["voices_path"]) as archive:
                    keys = [Path(x).stem for x in archive.namelist() if x.endswith(".npy")]
                return {key: {"name": key, "language": "en-gb" if key.startswith(("bf_", "bm_")) else "en-us",
                              "engine": "kokoro"}
                        for key in sorted(keys) if _ID.fullmatch(key) and key.startswith(("af_", "am_", "bf_", "bm_"))}
            except (OSError, zipfile.BadZipFile):
                return {}
        if self.backend == "flite":
            return {name: {"name": "Basic local voice — " + name, "language": "en-us", "engine": "flite"}
                    for name in ("slt", "awb", "kal", "rms")}
        if self.backend == "sapi":
            return {"system-default": {"name": "Windows default voice", "language": "en", "engine": "sapi"}}
        return {p.stem: {"name": p.stem, "engine": "xtts", "language": "en"}
                for p in self.voices_dir.iterdir()
                if _ID.fullmatch(p.stem) and p.suffix.lower() in {".wav", ".mp3", ".ogg", ".flac"} and not p.is_symlink()}

    def status(self) -> Dict[str, Any]:
        worker = self._worker.state()
        voices = self.list_voices()
        available = self._available and bool(voices)
        return {"available": available, "configured": self._available, "loaded": worker["loaded"],
                "ready": available and worker["loaded"] and not worker["last_error"], "busy": worker["busy"],
                "state": "unavailable" if not available else "error" if worker["last_error"] else
                         "ready" if worker["loaded"] else "configured_not_loaded",
                "reason": (self._reason or "The installed voice catalogue is missing or unreadable") if not available else None,
                "last_error": worker["last_error"],
                "engine": self.backend, "voice_count": len(voices), "max_text_characters": MAX_TEXT,
                "max_audio_seconds": MAX_SPEECH_SECONDS}

    async def synthesize(self, text: str, character_id: str = "default", language: str = "en",
                         speed: float = 1.0, voice_id: Optional[str] = None) -> Dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            return failure("Text is required", 400, "invalid_input")
        if len(text) > MAX_TEXT or "\0" in text:
            return failure("Text exceeds its 2000-character limit or contains a null character", 413, "input_limit")
        if not isinstance(character_id, str) or not _ID.fullmatch(character_id):
            return failure("Invalid character ID", 400, "invalid_input")
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed) or not .7 <= speed <= 1.5:
            return failure("Speech speed must be a finite number between 0.7 and 1.5", 400, "invalid_input")
        if not isinstance(language, str) or language.lower() not in {"en", "en-us", "en-gb"}:
            return failure("This installed voice catalogue supports English; choose en, en-us or en-gb", 400, "invalid_input")
        language = language.lower()
        catalogue = self.list_voices()
        if not catalogue:
            return failure(self._reason or "No usable local voices are configured", 503, "unavailable")
        if voice_id is None or voice_id == "default":
            voice_id = (character_id if self.backend == "xtts" and character_id in catalogue else
                        "af_heart" if "af_heart" in catalogue else next(iter(catalogue)))
        if not isinstance(voice_id, str) or voice_id not in catalogue:
            return failure("The selected voice is not in the local catalogue", 400, "invalid_input")
        payload = {"text": text, "character_id": character_id, "voice_id": voice_id,
                   "language": catalogue[voice_id]["language"] if language == "en" else language,
                   "speed": float(speed)}
        if self.backend == "xtts":
            reference = self._voice_file(voice_id)
            if reference is None:
                return failure("This character has no local voice reference", 503, "unavailable")
            payload["reference"] = str(reference)
        return await self._worker.call(payload)

    async def close(self) -> None:
        await self._worker.close()

"""Authenticated boundaries for existing local STT/TTS engines and voice choices."""
from __future__ import annotations

import asyncio
import json
import math
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from starlette.datastructures import UploadFile

from .auth_rate_limit import SlidingWindowLimiter
from .route_security import current_identity
from .speech_preferences import PreferenceConflict, SpeechPreferences
from .speech_worker import SpeechInputError, run_for_request
from .stt_engine import MAX_AUDIO_BYTES
from .tts_engine import MAX_TEXT, wav_info


def create_speech_router(get_stt, get_tts, data_dir: Path) -> APIRouter:
    router = APIRouter()
    limits = SlidingWindowLimiter(limit=60, window_seconds=60)
    preferences = None

    def store():
        nonlocal preferences
        if preferences is None:
            preferences = SpeechPreferences(data_dir)
        return preferences

    def quota(identity, kind):
        result = limits.allow(kind + ":" + str(identity["user_id"]))
        if not result.allowed:
            raise HTTPException(429, "Speech request limit reached; try again shortly",
                                headers={"Retry-After": str(result.retry_after)})

    async def body(request):
        parts, size = [], 0
        async for block in request.stream():
            size += len(block)
            if size > 16 * 1024:
                raise HTTPException(413, "Speech settings/text request exceeds 16 KiB")
            parts.append(block)
        encoded = b"".join(parts)
        try:
            value = json.loads(encoded)
        except (ValueError, UnicodeError):
            raise HTTPException(400, "A JSON object is required")
        if not isinstance(value, dict):
            raise HTTPException(400, "A JSON object is required")
        return value

    def result_or_error(result):
        if not result.get("ok"):
            code = result.get("status_code", 503)
            raise HTTPException(code, result.get("error", "Local speech request failed"),
                                headers={"Retry-After": "1"} if code == 429 else None)
        return result

    @router.get("/api/stt/status")
    async def stt_status(identity=Depends(current_identity)):
        engine = get_stt()
        return await asyncio.to_thread(engine.status) if engine else {"available": False, "reason": "Recognition is not initialized"}

    @router.post("/api/stt/transcribe")
    async def transcribe(request: Request, identity=Depends(current_identity)):
        engine = get_stt()
        if engine is None:
            raise HTTPException(503, "Recognition is not initialized")
        quota(identity, "stt")
        content_type = request.headers.get("content-type", "audio/webm")
        if content_type.lower().startswith("multipart/form-data"):
            try:
                async with request.form(max_files=1, max_fields=2) as form:
                    source = form.get("audio") or form.get("file")
                    if not isinstance(source, UploadFile):
                        raise HTTPException(400, "An audio file field is required")
                    audio = await source.read(MAX_AUDIO_BYTES + 1)
                    mime = source.content_type or "audio/webm"
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(400, "Malformed audio upload")
        else:
            parts, size = [], 0
            async for block in request.stream():
                size += len(block)
                if size > MAX_AUDIO_BYTES:
                    raise HTTPException(413, "Audio exceeds the 8 MiB dictation limit")
                parts.append(block)
            audio, mime = b"".join(parts), content_type
        if len(audio) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "Audio exceeds the 8 MiB dictation limit")
        result = await run_for_request(request, engine.transcribe(
            audio_data=audio, mime_type=mime, language=request.query_params.get("language"),
            prompt=request.query_params.get("prompt")))
        return result_or_error(result)

    @router.get("/api/tts/status")
    async def tts_status(identity=Depends(current_identity)):
        engine = get_tts()
        return await asyncio.to_thread(engine.status) if engine else {"available": False, "reason": "Local speech is not initialized"}

    @router.get("/api/tts/voices")
    async def voices(identity=Depends(current_identity)):
        engine = get_tts()
        if engine is None:
            return {"available": False, "voices": {}, "reason": "Local speech is not initialized"}
        state = await asyncio.to_thread(engine.status)
        return {**state, "voices": await asyncio.to_thread(engine.list_voices)}

    @router.get("/api/tts/preferences")
    async def get_preferences(identity=Depends(current_identity)):
        try:
            return await asyncio.to_thread(store().get, identity["user_id"])
        except (ValueError, OSError, sqlite3.Error):
            raise HTTPException(503, "Saved speech choices could not be read")

    @router.put("/api/tts/preferences")
    async def put_preferences(request: Request, identity=Depends(current_identity)):
        value = await body(request)
        if set(value) - {"voice_id", "speed", "language", "expected_revision"}:
            raise HTTPException(400, "Unsupported speech preference field")
        revision = value.get("expected_revision")
        if type(revision) is not int or not 0 <= revision < 2**31:
            raise HTTPException(400, "A valid expected_revision is required")
        voice, speed, language = value.get("voice_id", "default"), value.get("speed", 1.0), value.get("language", "en")
        engine = get_tts()
        catalogue = await asyncio.to_thread(engine.list_voices) if engine else {}
        if not isinstance(voice, str) or (voice != "default" and voice not in catalogue):
            raise HTTPException(400, "Choose a voice from the local catalogue")
        if type(speed) not in (int, float) or not math.isfinite(speed) or not .7 <= speed <= 1.5:
            raise HTTPException(400, "Speech speed must be between 0.7 and 1.5")
        if not isinstance(language, str) or language not in {"en", "en-us", "en-gb"}:
            raise HTTPException(400, "Unsupported local speech language")
        try:
            return await asyncio.to_thread(store().put, identity["user_id"],
                {"voice_id": voice, "speed": speed, "language": language}, revision)
        except PreferenceConflict as error:
            raise HTTPException(409, str(error))
        except (ValueError, OSError, sqlite3.Error):
            raise HTTPException(503, "Speech choices could not be saved")

    @router.post("/api/tts/synthesize")
    async def synthesize(request: Request, identity=Depends(current_identity)):
        engine = get_tts()
        if engine is None:
            raise HTTPException(503, "Local speech is not initialized")
        quota(identity, "tts")
        value = await body(request)
        if not isinstance(value.get("text"), str) or not value["text"].strip():
            raise HTTPException(400, "Text is required")
        if len(value["text"]) > MAX_TEXT:
            raise HTTPException(413, "Text exceeds the 2000-character speech limit")
        try:
            chosen = await asyncio.to_thread(store().get, identity["user_id"])
        except (ValueError, OSError, sqlite3.Error):
            raise HTTPException(503, "Saved speech choices could not be read")
        result = result_or_error(await run_for_request(request, engine.synthesize(
            text=value["text"], character_id=value.get("character_id", "default"),
            language=value.get("language", chosen["language"]), speed=value.get("speed", chosen["speed"]),
            voice_id=value.get("voice_id", chosen["voice_id"]))))
        try:
            info = wav_info(result["audio"])
        except SpeechInputError as error:
            raise HTTPException(error.status, str(error))
        return Response(content=result["audio"], media_type="audio/wav", headers={
            "Cache-Control": "no-store", "X-Character": result.get("character", "default"),
            "X-Engine": result.get("engine", "unknown"), "X-Voice": result.get("voice_id", "default"),
            "X-Latency-Ms": str(result.get("latency_ms", 0)), "X-Duration": str(info["duration"]),
            "X-Sample-Rate": str(info["sample_rate"]), "X-Audio-Samples": str(info["sample_count"])})

    return router

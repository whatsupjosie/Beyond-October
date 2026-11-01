# PubCast AI — bot_llm_adapter.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""
modules/bot_llm_adapter.py  —  PubCast Universal Bot LLM Adapter

Base layer for all LLM providers in PubCast.

Exports consumed by llm_framework.py:
  - BotLLMAdapter         abstract base class
  - PROVIDER_REGISTRY     mutable dict — framework registers adapters here
  - _TIMEOUT              httpx streaming timeout (seconds)
  - _COMPLETE_TIMEOUT     httpx non-streaming timeout (seconds)
  - OpenAIBotAdapter      OpenAI-compatible adapter
  - AnthropicBotAdapter   Anthropic Messages API adapter  (Anthropic SSE fix pass 4)
  - GeminiBotAdapter      Google Gemini adapter
  - EchoBotAdapter        Testing echo adapter

llm_framework.py builds on top of this:
  - OllamaBotAdapter, MistralBotAdapter, GroqBotAdapter
  - HardwareProfile, ModelSpec, MODEL_CATALOG
  - test_character_fidelity, get_adapter_for_provider

byok_manager.py imports from llm_framework.py only — it does not import from
this file directly.

Hardening passes:
  Pass 1 — Base interface + OpenAI adapter
  Pass 2 — EchoBotAdapter fallback for tests
  Pass 3 — Anthropic + Gemini adapters
  Pass 4 — Anthropic SSE fix: accumulate response_body, handle partial JSON
  Pass 5 — PROVIDER_REGISTRY pattern established
  Pass 6 — Error hygiene, timeout discipline, Windows-safe httpx usage
"""
from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

logger = logging.getLogger("pubcast.bot_llm_adapter")

# ── Timeout constants (consumed by llm_framework.py) ─────────────────────────

_TIMEOUT = float(os.getenv("PUBCAST_LLM_STREAM_TIMEOUT", "180"))    # streaming
_COMPLETE_TIMEOUT = float(os.getenv("PUBCAST_LLM_COMPLETE_TIMEOUT", "30"))  # one-shot


# ── Abstract base ─────────────────────────────────────────────────────────────

class BotLLMAdapter(ABC):
    """
    Provider-agnostic streaming LLM interface for PubCast bots.

    Subclasses implement stream() — an async generator that yields text chunks.
    complete() is provided as a convenience wrapper around stream().
    is_available() gates whether the adapter should be tried at all.
    """

    provider_name: str = "base"

    def is_available(self) -> bool:
        """Return True if this adapter has what it needs to make calls."""
        return True

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        *,
        system: str = "",
        history: Optional[List[Dict[str, Any]]] = None,
        model: str = "",
        temperature: float = 0.8,
    ) -> AsyncGenerator[str, None]:
        """
        Yield text chunks for a given prompt.
        history is a list of message dicts: [{role, content, ...}]
        model overrides the adapter default when supplied.
        Raises on provider failure; callers must not commit partial replies.
        """
        # Make the type checker happy — subclasses must yield
        return
        yield  # noqa: unreachable

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        history: Optional[List[Dict[str, Any]]] = None,
        model: str = "",
        temperature: float = 0.8,
    ) -> str:
        """Convenience: collect all chunks from stream() into a single string."""
        parts: List[str] = []
        async for chunk in self.stream(
            prompt, system=system, history=history,
            model=model, temperature=temperature,
        ):
            parts.append(chunk)
        return "".join(parts)


# ── Echo adapter (testing + safe fallback) ────────────────────────────────────

class EchoBotAdapter(BotLLMAdapter):
    """
    Reflects the last user message back.
    Used for smoke tests and as the last-resort fallback when no backend is up.
    """

    provider_name = "echo"

    def is_available(self) -> bool:
        return True

    async def stream(
        self,
        prompt: str,
        *,
        system: str = "",
        history: Optional[List[Dict[str, Any]]] = None,
        model: str = "",
        temperature: float = 0.8,
    ) -> AsyncGenerator[str, None]:
        yield f"[echo] {prompt}"


# Hosted adapters require a complete, validated response. No silent fallback.
class OpenAIBotAdapter(BotLLMAdapter):
    provider_name = "openai"
    _DEFAULT_MODEL = "gpt-4o-mini"
    _BASE_URL = "https://api.openai.com/v1"

    def _resolve_key(self):
        return os.getenv("OPENAI_API_KEY", "").strip()

    def is_available(self):
        return bool(self._resolve_key())

    async def stream(self, prompt, *, system="", history=None, model="", temperature=0.8):
        # Preserve Chat Completions for third-party compatible subclasses.
        from .openai_compatible_provider import OpenAICompatibleBotAdapter
        if self._BASE_URL == "https://api.openai.com/v1":
            from .openai_responses_provider import responses_text
            async for text in responses_text(self._resolve_key(), prompt, system=system,
                    history=history, model=model or self._DEFAULT_MODEL, timeout=_TIMEOUT):
                yield text
            return
        adapter = OpenAICompatibleBotAdapter(api_key=self._resolve_key(),
            base_url=self._BASE_URL, default_model=self._DEFAULT_MODEL, max_tokens=4096)
        async for text in adapter.stream(prompt, system=system, history=history,
                                         model=model, temperature=temperature):
            yield text


async def _hosted_json(url, headers, body):
    """Bound total time and response size; never expose provider bodies or keys."""
    import asyncio
    from .openai_compatible_provider import ModelResponseError
    try:
        async with asyncio.timeout(_TIMEOUT):
            async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False) as client:
                async with client.stream("POST", url, headers=headers, json=body) as response:
                    if response.status_code != 200:
                        raise ModelResponseError(f"Hosted provider HTTP {response.status_code}")
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > 2_000_000:
                            raise ModelResponseError("Hosted response exceeds size limit")
                    result = json.loads(data)
                    if not isinstance(result, dict) or result.get("error"):
                        raise ModelResponseError("Hosted provider returned an error")
                    return result
    except (httpx.HTTPError, TimeoutError, ValueError) as exc:
        raise ModelResponseError("Hosted request failed or returned invalid JSON") from None


def _hosted_messages(prompt, history):
    from .openai_compatible_provider import OpenAICompatibleBotAdapter, ModelResponseError
    messages = OpenAICompatibleBotAdapter.messages(prompt, history=history)
    if any(m["role"] not in {"user", "assistant"} for m in messages):
        raise ModelResponseError("History must contain user and assistant messages")
    return messages


class AnthropicBotAdapter(BotLLMAdapter):
    provider_name = "anthropic"
    _DEFAULT_MODEL = "claude-haiku-4-5-20251001"
    _API_URL = "https://api.anthropic.com/v1/messages"

    def _resolve_key(self):
        return os.getenv("ANTHROPIC_API_KEY", "").strip()

    def is_available(self):
        return bool(self._resolve_key())

    async def stream(self, prompt, *, system="", history=None, model="", temperature=0.8):
        from .openai_compatible_provider import ModelResponseError
        key = self._resolve_key()
        if not key:
            raise ModelResponseError("Anthropic requires an API credential")
        body = {"model": model or self._DEFAULT_MODEL, "max_tokens": 4096,
                "messages": _hosted_messages(prompt, history)}
        if system:
            body["system"] = system
        # Keep provider temperature defaults for compatibility with newer models.
        result = await _hosted_json(self._API_URL,
            {"x-api-key": key, "anthropic-version": "2023-06-01"}, body)
        if result.get("stop_reason") not in {"end_turn", "stop_sequence"}:
            raise ModelResponseError("Anthropic response did not finish normally")
        blocks = result.get("content")
        if not isinstance(blocks, list) or any(not isinstance(b, dict) for b in blocks):
            raise ModelResponseError("Invalid Anthropic response content")
        if any(b.get("type") not in {"text", "thinking", "redacted_thinking"} for b in blocks):
            raise ModelResponseError("Anthropic returned unsupported content")
        texts = [b.get("text") for b in blocks if b.get("type") == "text"]
        if any(not isinstance(t, str) for t in texts) or not "".join(texts).strip():
            raise ModelResponseError("Anthropic returned no usable text")
        yield "".join(texts)


class GeminiBotAdapter(BotLLMAdapter):
    provider_name = "gemini"
    # Explicit model selection avoids silently choosing a retired or costly model.
    _DEFAULT_MODEL = ""

    def _resolve_key(self):
        return os.getenv("GEMINI_API_KEY", "").strip()

    def is_available(self):
        return bool(self._resolve_key())

    async def stream(self, prompt, *, system="", history=None, model="", temperature=0.8):
        import re
        from .openai_compatible_provider import ModelResponseError
        key = self._resolve_key()
        if not key:
            raise ModelResponseError("Gemini requires an API credential")
        selected = (model or os.getenv("PUBCAST_GEMINI_MODEL", "")).removeprefix("models/")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", selected):
            raise ModelResponseError("Select a valid Gemini model ID in model settings")
        body = {"contents": [{"role": "model" if m["role"] == "assistant" else "user",
                              "parts": [{"text": m["content"]}]}
                             for m in _hosted_messages(prompt, history)],
                "generationConfig": {"maxOutputTokens": 8192}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        result = await _hosted_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{selected}:generateContent",
            {"x-goog-api-key": key}, body)
        if result.get("promptFeedback", {}).get("blockReason"):
            raise ModelResponseError("Gemini blocked this request")
        candidates = result.get("candidates", [])
        if not isinstance(candidates, list) or len(candidates) != 1 or not isinstance(candidates[0], dict):
            raise ModelResponseError("Gemini returned no single usable candidate")
        candidate = candidates[0]
        if candidate.get("finishReason") != "STOP":
            raise ModelResponseError("Gemini response did not finish normally")
        parts = candidate.get("content", {}).get("parts", [])
        if not isinstance(parts, list) or any(not isinstance(p, dict) for p in parts):
            raise ModelResponseError("Invalid Gemini response content")
        texts = []
        for part in parts:
            if part.get("thought"):
                continue
            if not isinstance(part.get("text"), str):
                raise ModelResponseError("Gemini returned unsupported content")
            texts.append(part["text"])
        if not "".join(texts).strip():
            raise ModelResponseError("Gemini returned no usable text")
        yield "".join(texts)


# ── Provider registry ─────────────────────────────────────────────────────────
# Mutable dict — llm_framework.py registers OllamaBotAdapter, MistralBotAdapter,
# GroqBotAdapter here at import time. Host key adapters live here too.

PROVIDER_REGISTRY: Dict[str, BotLLMAdapter] = {
    "openai":    OpenAIBotAdapter(),
    "anthropic": AnthropicBotAdapter(),
    "gemini":    GeminiBotAdapter(),
    "echo":      EchoBotAdapter(),
}


__all__ = [
    "BotLLMAdapter",
    "EchoBotAdapter",
    "OpenAIBotAdapter",
    "AnthropicBotAdapter",
    "GeminiBotAdapter",
    "PROVIDER_REGISTRY",
    "_TIMEOUT",
    "_COMPLETE_TIMEOUT",
]

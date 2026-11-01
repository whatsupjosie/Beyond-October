"""OpenCode Zen client used by PubPartner's optional online knowledge layer.

This module is deliberately provider-only.  It does not know about Alex,
relationship memory, projects, or user profiles.  Callers hand it an already
sanitized, narrow reference question and receive a provider response.

Official interface verified 2026-07-11:
  base:  https://opencode.ai/zen/v1
  chat:  POST /chat/completions
  models: GET /models
  Big Pickle model id: big-pickle
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

try:
    import httpx
except ImportError:  # Optional: the offline friend loop must still boot.
    httpx = None  # type: ignore

_HTTP_ERRORS = (httpx.HTTPError,) if httpx is not None else ()

ZEN_BASE_URL = "https://opencode.ai/zen/v1"
ZEN_CHAT_COMPLETIONS_URL = f"{ZEN_BASE_URL}/chat/completions"
ZEN_MODELS_URL = f"{ZEN_BASE_URL}/models"
BIG_PICKLE_MODEL_ID = "big-pickle"
ZEN_PROVIDER_ID = "opencode_zen"
ZEN_SPEC_VERIFIED_DATE = "2026-07-11"


@dataclass
class ZenResult:
    ok: bool
    model: str = BIG_PICKLE_MODEL_ID
    text: str = ""
    error: str = ""
    status_code: int = 0
    latency_ms: int = 0
    usage: Dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    retry_after: Optional[float] = None
    available_models: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "provider": ZEN_PROVIDER_ID,
            "model": self.model,
            "text": self.text,
            "error": self.error,
            "status_code": self.status_code,
            "latency_ms": self.latency_ms,
            "usage": self.usage,
            "request_id": self.request_id,
            "retry_after": self.retry_after,
            "available_models": list(self.available_models),
        }


class OpenCodeZenClient:
    """Small async client for Zen's OpenAI-compatible endpoints.

    A transport can be injected for deterministic tests.  The API key is kept
    only on this instance and is never included in result dictionaries or logs.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = ZEN_BASE_URL,
        timeout: float = 20.0,
        max_retries: int = 1,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._api_key = str(api_key or "").strip()
        self.base_url = str(base_url or ZEN_BASE_URL).rstrip("/")
        self.timeout = max(1.0, min(float(timeout), 120.0))
        self.max_retries = max(0, min(int(max_retries), 3))
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "PubPartner/0.1 OpenCode-Zen-knowledge-client",
        }

    def _client(self) -> httpx.AsyncClient:
        if httpx is None:
            raise RuntimeError(
                "OpenCode Zen requires the optional httpx dependency"
            )
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            transport=self.transport,
            follow_redirects=False,
        )

    @staticmethod
    def _safe_error(resp: httpx.Response) -> str:
        detail = ""
        try:
            payload = resp.json()
            if isinstance(payload, Mapping):
                raw = payload.get("error") or payload.get("detail") or payload.get("message")
                if isinstance(raw, Mapping):
                    raw = raw.get("message") or raw.get("type")
                detail = str(raw or "")
        except Exception:
            detail = ""
        detail = detail.replace("\n", " ").strip()[:300]
        return f"Zen HTTP {resp.status_code}" + (f": {detail}" if detail else "")

    @staticmethod
    def _request_id(resp: httpx.Response) -> str:
        for key in ("x-request-id", "request-id", "cf-ray"):
            value = resp.headers.get(key)
            if value:
                return value[:160]
        return ""

    @staticmethod
    def _retry_after(resp: httpx.Response) -> Optional[float]:
        raw = resp.headers.get("retry-after")
        if not raw:
            return None
        try:
            return max(0.0, min(float(raw), 120.0))
        except Exception:
            return None

    async def list_models(self) -> ZenResult:
        started = time.monotonic()
        if not self.configured:
            return ZenResult(ok=False, error="OpenCode Zen API key is not configured", latency_ms=0)
        if httpx is None:
            return ZenResult(
                ok=False,
                error="OpenCode Zen is unavailable because httpx is not installed",
                latency_ms=0,
            )
        try:
            async with self._client() as client:
                resp = await client.get(f"{self.base_url}/models", headers=self._headers())
            latency = int((time.monotonic() - started) * 1000)
            if resp.status_code != 200:
                return ZenResult(
                    ok=False,
                    error=self._safe_error(resp),
                    status_code=resp.status_code,
                    latency_ms=latency,
                    request_id=self._request_id(resp),
                    retry_after=self._retry_after(resp),
                )
            payload = resp.json()
            rows = payload.get("data", []) if isinstance(payload, Mapping) else []
            models: List[str] = []
            for row in rows if isinstance(rows, list) else []:
                if isinstance(row, Mapping) and row.get("id"):
                    models.append(str(row["id"]))
            return ZenResult(
                ok=True,
                status_code=200,
                latency_ms=latency,
                request_id=self._request_id(resp),
                available_models=models,
            )
        except _HTTP_ERRORS + (ValueError, json.JSONDecodeError) as exc:
            return ZenResult(
                ok=False,
                error=f"Zen model-list request failed: {exc.__class__.__name__}: {exc}",
                latency_ms=int((time.monotonic() - started) * 1000),
            )

    async def chat(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        model: str = BIG_PICKLE_MODEL_ID,
        temperature: float = 0.2,
        max_tokens: int = 700,
    ) -> ZenResult:
        started = time.monotonic()
        target_model = str(model or BIG_PICKLE_MODEL_ID).strip()[:160]
        if not self.configured:
            return ZenResult(ok=False, model=target_model, error="OpenCode Zen API key is not configured")
        if httpx is None:
            return ZenResult(
                ok=False,
                model=target_model,
                error="OpenCode Zen is unavailable because httpx is not installed",
            )
        clean_messages: List[Dict[str, str]] = []
        for row in messages:
            role = str(row.get("role") or "user")
            content = str(row.get("content") or "")
            if role not in {"system", "user", "assistant"} or not content:
                continue
            clean_messages.append({"role": role, "content": content})
        if not clean_messages:
            return ZenResult(ok=False, model=target_model, error="Zen request has no messages")

        body = {
            "model": target_model,
            "messages": clean_messages,
            "temperature": max(0.0, min(float(temperature), 1.5)),
            "max_tokens": max(32, min(int(max_tokens), 4096)),
            "stream": False,
        }
        last_error = ""
        for attempt in range(self.max_retries + 1):
            try:
                async with self._client() as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=body,
                    )
                if resp.status_code == 200:
                    payload = resp.json()
                    choices = payload.get("choices", []) if isinstance(payload, Mapping) else []
                    text = ""
                    if choices and isinstance(choices[0], Mapping):
                        message = choices[0].get("message") or {}
                        if isinstance(message, Mapping):
                            text = str(message.get("content") or "")
                    usage = payload.get("usage", {}) if isinstance(payload, Mapping) else {}
                    if not isinstance(usage, Mapping):
                        usage = {}
                    latency = int((time.monotonic() - started) * 1000)
                    if not text.strip():
                        return ZenResult(
                            ok=False,
                            model=target_model,
                            error="Zen returned an empty response",
                            status_code=200,
                            latency_ms=latency,
                            request_id=self._request_id(resp),
                            usage=dict(usage),
                        )
                    return ZenResult(
                        ok=True,
                        model=str(payload.get("model") or target_model),
                        text=text.strip(),
                        status_code=200,
                        latency_ms=latency,
                        request_id=self._request_id(resp),
                        usage=dict(usage),
                    )

                last_error = self._safe_error(resp)
                retryable = resp.status_code == 429 or 500 <= resp.status_code < 600
                if attempt < self.max_retries and retryable:
                    delay = self._retry_after(resp)
                    await asyncio.sleep(delay if delay is not None else min(0.25 * (2 ** attempt), 1.0))
                    continue
                return ZenResult(
                    ok=False,
                    model=target_model,
                    error=last_error,
                    status_code=resp.status_code,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    request_id=self._request_id(resp),
                    retry_after=self._retry_after(resp),
                )
            except _HTTP_ERRORS + (ValueError, json.JSONDecodeError) as exc:
                last_error = f"Zen request failed: {exc.__class__.__name__}: {exc}"
                if attempt < self.max_retries:
                    await asyncio.sleep(min(0.25 * (2 ** attempt), 1.0))
                    continue
                break
        return ZenResult(
            ok=False,
            model=target_model,
            error=last_error or "Zen request failed",
            latency_ms=int((time.monotonic() - started) * 1000),
        )


def official_zen_spec() -> Dict[str, Any]:
    """Return the integration facts pinned into this release.

    These values are informational and intentionally separate from runtime
    secrets or user preferences.
    """
    return {
        "provider": ZEN_PROVIDER_ID,
        "display_name": "OpenCode Zen",
        "base_url": ZEN_BASE_URL,
        "chat_completions_endpoint": ZEN_CHAT_COMPLETIONS_URL,
        "models_endpoint": ZEN_MODELS_URL,
        "big_pickle": {
            "model_id": BIG_PICKLE_MODEL_ID,
            "opencode_config_id": "opencode/big-pickle",
            "pricing_when_verified": "free",
            "availability_note": "free for a limited period",
            "privacy_note": "During its free period, collected data may be used to improve the model.",
            "intended_pubpartner_role": "optional online world-knowledge and language advisor",
        },
        "verified_date": ZEN_SPEC_VERIFIED_DATE,
        "official_docs": "https://opencode.ai/docs/zen",
    }


__all__ = [
    "OpenCodeZenClient",
    "ZenResult",
    "official_zen_spec",
    "ZEN_BASE_URL",
    "ZEN_CHAT_COMPLETIONS_URL",
    "ZEN_MODELS_URL",
    "ZEN_PROVIDER_ID",
    "BIG_PICKLE_MODEL_ID",
]

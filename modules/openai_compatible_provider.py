"""OpenAI-compatible transport with explicit completion and failure semantics.

A partial stream is never returned by complete() as a successful answer. Errors
are intentionally sanitized: provider bodies may contain prompts or credentials.
"""
from __future__ import annotations
import asyncio
import json
import math
from typing import Any, AsyncGenerator
from urllib.parse import urlsplit
import httpx
from .bot_llm_adapter import BotLLMAdapter, _TIMEOUT


class ModelResponseError(RuntimeError):
    """Safe to surface in an authenticated provider receipt."""


class OpenAICompatibleBotAdapter(BotLLMAdapter):
    provider_name = "openai_compatible"

    def __init__(self, *, api_key: str = "", base_url: str, default_model: str = "",
                 require_api_key: bool = True, extra_headers=None,
                 timeout: float | None = None, max_tokens: int = 1024,
                 local_context_tokens: int | None = None):
        normalized = str(base_url or "").strip().rstrip("/")
        parsed = urlsplit(normalized)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("base_url must be an http(s) URL without credentials, query or fragment")
        self.api_key = str(api_key or "")
        self.base_url = normalized
        self.default_model = str(default_model or "")
        self.require_api_key = bool(require_api_key)
        self.extra_headers = {str(k): str(v) for k, v in dict(extra_headers or {}).items()}
        self.timeout = float(_TIMEOUT if timeout is None else timeout)
        if not math.isfinite(self.timeout) or not 0 < self.timeout <= 600:
            raise ValueError("model timeout must be between 0 and 600 seconds")
        self.max_tokens = int(max_tokens)
        if not 1 <= self.max_tokens <= 4096:
            raise ValueError("max_tokens must be between 1 and 4096")
        self.local_context_tokens = local_context_tokens
        if local_context_tokens is not None and parsed.hostname not in {"127.0.0.1", "::1"}:
            raise ValueError("local context preflight requires a loopback endpoint")
        self.last_usage: dict[str, Any] = {}

    def is_available(self):
        return bool(self.base_url) and (bool(self.api_key) or not self.require_api_key)

    @staticmethod
    def messages(prompt, system="", history=None):
        messages = [{"role": "system", "content": system}] if system else []
        for entry in history or []:
            role = str(entry.get("role") or "").lower()
            if role not in {"system", "user", "assistant"}:
                uid = str(entry.get("user_id") or entry.get("sender_id") or "")
                role = "assistant" if uid.startswith(("bot-", "agent:")) else "user"
            text = entry.get("content", entry.get("text", ""))
            if not isinstance(text, str):
                raise ModelResponseError("Conversation history must contain text")
            if text:
                messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": str(prompt or "")})
        return messages

    async def _preflight(self, client, messages, headers):
        # Use this exact bundled model's template and tokenizer, not a bytes/token guess.
        root = self.base_url.removesuffix("/v1")
        template = await client.post(root + "/apply-template", headers=headers,
                                     json={"messages": messages, "add_generation_prompt": True})
        if template.status_code != 200:
            raise ModelResponseError("Local chat-template preflight failed")
        prompt = template.json().get("prompt")
        if not isinstance(prompt, str):
            raise ModelResponseError("Local chat-template preflight returned invalid data")
        tokens = await client.post(root + "/tokenize", headers=headers,
                                  json={"content": prompt, "add_special": True, "parse_special": True})
        if tokens.status_code != 200:
            raise ModelResponseError("Local tokenizer preflight failed")
        ids = tokens.json().get("tokens")
        if not isinstance(ids, list) or any(not isinstance(t, int) for t in ids):
            raise ModelResponseError("Local tokenizer preflight returned invalid data")
        count = len(ids)
        self.last_usage.update(prompt_tokens_preflight=count, context_tokens=self.local_context_tokens,
                               reserved_output_tokens=self.max_tokens, context_margin_tokens=32)
        if count + self.max_tokens + 32 > self.local_context_tokens:
            raise ModelResponseError(f"Local context too large: {count} prompt tokens plus {self.max_tokens} reply tokens exceed the {self.local_context_tokens}-token context; use a shorter excerpt or history")

    async def stream(self, prompt: str, *, system: str = "", history=None,
                     model: str = "", temperature: float = 0.8) -> AsyncGenerator[str, None]:
        """Yield deltas; raise on incomplete/error/length-limited responses.

        complete() inherits accumulation, so raised errors discard partial replies.
        Direct stream consumers must treat the stream as provisional until it ends.
        """
        self.last_usage = {}
        if not self.is_available():
            raise ModelResponseError("Model endpoint requires a credential")
        resolved_model = str(model or self.default_model or "").strip()
        if not resolved_model:
            raise ModelResponseError("Model name is required")
        if not math.isfinite(float(temperature)):
            raise ModelResponseError("Temperature must be finite")
        messages = self.messages(prompt, system, history)
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            # Caller-supplied header spelling must not shadow the trusted key.
            headers = {k: v for k, v in headers.items() if k.lower() != "authorization"}
            headers["Authorization"] = f"Bearer {self.api_key}"
        finished = False
        done = False
        size = 0
        try:
            async with asyncio.timeout(self.timeout):
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False,
                                             trust_env=self.local_context_tokens is None) as client:
                    if self.local_context_tokens is not None:
                        await self._preflight(client, messages, headers)
                    async with client.stream("POST", self.base_url + "/chat/completions", headers=headers,
                            json={"model": resolved_model, "messages": messages,
                                  "temperature": max(0.0, min(float(temperature), 2.0)),
                                  "max_tokens": self.max_tokens, "stream": True}) as resp:
                        if resp.status_code != 200:
                            raise ModelResponseError(f"Model endpoint returned HTTP {resp.status_code}")
                        event_lines = []
                        async def events():
                            nonlocal size
                            async for line in resp.aiter_lines():
                                size += len(line.encode("utf-8"))
                                if size > 2_000_000:
                                    raise ModelResponseError("Model response exceeded the transport limit")
                                if line == "":
                                    if event_lines:
                                        yield "\n".join(event_lines)
                                        event_lines.clear()
                                elif line.startswith("data:"):
                                    event_lines.append(line[5:].removeprefix(" "))
                            if event_lines:
                                yield "\n".join(event_lines)
                        async for data in events():
                            if data.strip() == "[DONE]":
                                done = True
                                break
                            event = json.loads(data)
                            if not isinstance(event, dict) or event.get("error"):
                                raise ModelResponseError("Model returned an error event")
                            if isinstance(event.get("usage"), dict):
                                self.last_usage["provider_usage"] = event["usage"]
                            choices = event.get("choices") or []
                            if not choices:
                                continue
                            choice = choices[0]
                            reason = choice.get("finish_reason")
                            if reason is not None:
                                self.last_usage["finish_reason"] = reason
                                if reason != "stop":
                                    raise ModelResponseError(f"Model did not complete its reply (finish reason: {reason if reason in {'length','tool_calls','content_filter'} else 'unsupported'})")
                                finished = True
                            delta = choice.get("delta") or choice.get("message") or {}
                            if delta.get("tool_calls") or delta.get("function_call"):
                                raise ModelResponseError("Tool-call responses are not supported on this text route")
                            text = delta.get("content")
                            if text is not None:
                                if not isinstance(text, str):
                                    raise ModelResponseError("Model returned non-text content")
                                if text:
                                    yield text
                        if not finished:
                            raise ModelResponseError("Model stream ended without a completed reply")
                        self.last_usage["stream_done_marker"] = done
        except ModelResponseError:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise ModelResponseError("Model request timed out; no partial reply was accepted") from None
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
            raise ModelResponseError("Model transport or response was invalid; no partial reply was accepted") from None


__all__ = ["OpenAICompatibleBotAdapter", "ModelResponseError"]

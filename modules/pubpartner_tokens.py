"""Token accounting helpers for PubPartner.

This module gives the build an honest measurement spine. Provider APIs should
supply exact usage later; until then we store deterministic local estimates and
mark them as estimates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class TokenReport:
    provider: str
    method: str
    chars: int
    bytes: int
    estimated_tokens: int
    exact: bool = False
    warning: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "method": self.method,
            "chars": self.chars,
            "bytes": self.bytes,
            "estimated_tokens": self.estimated_tokens,
            "exact": self.exact,
            "warning": self.warning,
        }


class PubPartnerTokenCounter:
    def estimate(self, text: str, *, provider: str = "generic", model: str = "unknown") -> Dict[str, Any]:
        text = "" if text is None else str(text)
        provider = (provider or "generic").lower()
        encoded = text.encode("utf-8")
        # Optional OpenAI tokenizer if present. Do not require it.
        if provider in {"openai", "gpt"}:
            try:
                import tiktoken  # type: ignore
                enc = tiktoken.encoding_for_model(model) if model and model != "unknown" else tiktoken.get_encoding("cl100k_base")
                return TokenReport(provider=provider, method="tiktoken", chars=len(text), bytes=len(encoded), estimated_tokens=len(enc.encode(text)), exact=True).as_dict()
            except Exception as exc:
                return TokenReport(provider=provider, method="rough_fallback", chars=len(text), bytes=len(encoded), estimated_tokens=max(1, int(len(text) / 4)), warning=f"tiktoken unavailable: {exc.__class__.__name__}").as_dict()
        # Conservative-ish rough estimate with byte-length awareness for multilingual text.
        rough = max(1, int(max(len(text) / 4, len(encoded) / 5)))
        return TokenReport(provider=provider, method="rough_local", chars=len(text), bytes=len(encoded), estimated_tokens=rough, exact=False).as_dict()

    def compare(self, compact_prompt: str, full_prompt: str, *, provider: str = "generic", model: str = "unknown") -> Dict[str, Any]:
        compact = self.estimate(compact_prompt, provider=provider, model=model)
        full = self.estimate(full_prompt, provider=provider, model=model)
        full_tokens = max(1, int(full.get("estimated_tokens") or 1))
        compact_tokens = int(compact.get("estimated_tokens") or 0)
        saved = max(0, full_tokens - compact_tokens)
        return {
            "ok": True,
            "provider": provider,
            "model": model,
            "compact": compact,
            "full": full,
            "estimated_tokens_saved": saved,
            "estimated_savings_ratio": round(saved / full_tokens, 4),
        }

"""Provider fingerprint neutralization for PubPartner.

This module removes *provider-default presentation habits* before Alex applies
relationship-specific personalization.  It is deliberately conservative:
provider neutralization may remove boilerplate, stock closings, and redundant
meta framing, but it must not alter facts, protected source material, code, or
meaningful uncertainty.

The provider is an interchangeable engine.  Neutralization removes the engine's
accent; Alex decides whether and how the answer should change for the user.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

_PROTECTED_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)

_PROVIDER_ALIASES = {
    "gpt": "openai",
    "chatgpt": "openai",
    "claude": "anthropic",
    "google": "gemini",
    "local": "ollama",
    "lm_studio": "openai_compatible",
    "llama_cpp": "openai_compatible",
    "vllm": "openai_compatible",
    "openrouter": "openai_compatible",
    "together": "openai_compatible",
    "fireworks": "openai_compatible",
}

_COMMON_PREFIX_PATTERNS = (
    r"^(?:sure|certainly|absolutely|of course)[,!—:\-\s]+",
    r"^i(?:'d| would) be happy to help(?: with that)?[.!:]\s+",
    r"^i can help with that[.!:\-\s]+",
    r"^here(?:'s| is) (?:a|the) (?:concise |quick |useful )?(?:answer|response|draft)[.!:\-\s]+",
)

_COMMON_CLOSING_PATTERNS = (
    r"\n?\s*hope this helps[.!]?\s*$",
    r"\n?\s*let me know if you(?:'d| would)? like (?:me to )?.*?\s*$",
    r"\n?\s*feel free to ask if you have any (?:other |further )?questions[.!]?\s*$",
)

# Provider-specific patterns are intentionally narrow.  Most entries are
# warning-only because a provider habit can also carry real meaning.
_PROVIDER_RULES: Dict[str, Dict[str, Sequence[str]]] = {
    "openai": {
        "remove_prefix": _COMMON_PREFIX_PATTERNS,
        "remove_closing": _COMMON_CLOSING_PATTERNS,
        "warn": (
            r"\bit(?:'s| is) important to note that\b",
            r"\bi completely understand how frustrating\b",
        ),
    },
    "anthropic": {
        "remove_prefix": _COMMON_PREFIX_PATTERNS,
        "remove_closing": _COMMON_CLOSING_PATTERNS,
        "warn": (
            r"\bi want to be careful (?:not to|here)\b",
            r"\bthere are a few important nuances\b",
            r"\byou(?:'re| are) absolutely right\b",
        ),
    },
    "gemini": {
        "remove_prefix": _COMMON_PREFIX_PATTERNS,
        "remove_closing": _COMMON_CLOSING_PATTERNS,
        "warn": (
            r"\bit(?:'s| is) important to remember that\b",
            r"\bhere(?:'s| is) a breakdown\b",
        ),
    },
    "mistral": {
        "remove_prefix": _COMMON_PREFIX_PATTERNS,
        "remove_closing": _COMMON_CLOSING_PATTERNS,
        "warn": (),
    },
    "groq": {
        "remove_prefix": _COMMON_PREFIX_PATTERNS,
        "remove_closing": _COMMON_CLOSING_PATTERNS,
        "warn": (),
    },
    "opencode_zen": {
        "remove_prefix": _COMMON_PREFIX_PATTERNS,
        "remove_closing": _COMMON_CLOSING_PATTERNS,
        "warn": (),
    },
    "openai_compatible": {
        "remove_prefix": _COMMON_PREFIX_PATTERNS,
        "remove_closing": _COMMON_CLOSING_PATTERNS,
        "warn": (),
    },
    "ollama": {
        "remove_prefix": _COMMON_PREFIX_PATTERNS,
        "remove_closing": _COMMON_CLOSING_PATTERNS,
        "warn": (
            r"\bas an ai (?:language model|assistant)\b",
        ),
    },
    "offline": {
        "remove_prefix": (),
        "remove_closing": (),
        "warn": (),
    },
    "mock": {
        "remove_prefix": _COMMON_PREFIX_PATTERNS,
        "remove_closing": _COMMON_CLOSING_PATTERNS,
        "warn": (),
    },
}


@dataclass
class ProviderNeutralizationResult:
    raw_response: str
    neutral_response: str
    provider: str
    model: str = ""
    change_level: str = "none"
    applied: List[str] = field(default_factory=list)
    rules_checked: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    protected_text_preserved: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return {
            "raw_response": self.raw_response,
            "neutral_response": self.neutral_response,
            "provider": self.provider,
            "model": self.model,
            "change_level": self.change_level,
            "applied": list(self.applied),
            "rules_checked": list(self.rules_checked),
            "warnings": list(self.warnings),
            "protected_text_preserved": self.protected_text_preserved,
        }


class ProviderNeutralizer:
    """Remove narrow provider fingerprints without applying Alex personality."""

    def normalize_provider(self, provider: str) -> str:
        key = str(provider or "unknown").lower().strip().replace("-", "_")
        return _PROVIDER_ALIASES.get(key, key)

    def neutralize(
        self,
        raw_response: str,
        *,
        provider: str = "unknown",
        model: str = "",
        fixes: Sequence[str] | None = None,
        source_policy: Mapping[str, Any] | None = None,
    ) -> ProviderNeutralizationResult:
        raw = "" if raw_response is None else str(raw_response)
        canonical = self.normalize_provider(provider)
        rules = _PROVIDER_RULES.get(canonical, {
            "remove_prefix": _COMMON_PREFIX_PATTERNS,
            "remove_closing": _COMMON_CLOSING_PATTERNS,
            "warn": (),
        })
        source_policy = dict(source_policy or {})
        requested_fixes = {str(v).lower().strip() for v in (fixes or []) if str(v).strip()}
        applied: List[str] = []
        checked: List[str] = []
        warnings: List[str] = []

        protected_text, protected = self._protect_blocks(raw)
        text = protected_text.strip()

        # Exact/immutable content may have a provider prefix outside the protected
        # block, but must never be rewritten inside the source itself.
        for pattern in rules.get("remove_prefix", ()):
            checked.append(f"{canonical}:prefix")
            updated = re.sub(pattern, "", text, count=1, flags=re.IGNORECASE)
            if updated != text and updated.strip():
                text = updated.lstrip()
                applied.append("remove_provider_boilerplate_prefix")
                break

        # Closing removal is allowed by default for known generic closings and can
        # be explicitly requested through provider profile fixes.
        allow_closing = (
            "low_fluff" in requested_fixes
            or "trim_boilerplate" in requested_fixes
            or "trim_overexplaining" in requested_fixes
            or canonical in _PROVIDER_RULES
        )
        if allow_closing:
            for pattern in rules.get("remove_closing", ()):
                checked.append(f"{canonical}:closing")
                updated = re.sub(pattern, "", text, count=1, flags=re.IGNORECASE | re.DOTALL).rstrip()
                if updated != text and updated.strip():
                    text = updated
                    applied.append("remove_provider_stock_closing")
                    break

        for pattern in rules.get("warn", ()):
            checked.append(f"{canonical}:warning")
            if re.search(pattern, text, flags=re.IGNORECASE):
                warnings.append(f"possible_{canonical}_fingerprint:{pattern}")

        # Generic assistant self-substitution is not rewritten here because Alex
        # may need to make a context-sensitive repair.  It is surfaced clearly.
        if re.search(r"\bas an ai (?:language model|assistant)\b", text, flags=re.IGNORECASE):
            warnings.append("generic_assistant_substitution_detected")

        text = self._restore_blocks(text, protected)
        protected_ok = all(str(item["text"]) in text for item in protected)
        if not protected_ok:
            warnings.append("provider_neutralizer_protected_text_integrity_failure")

        return ProviderNeutralizationResult(
            raw_response=raw,
            neutral_response=text,
            provider=canonical,
            model=str(model or ""),
            change_level="none" if text == raw else "presentation_only",
            applied=self._dedupe(applied),
            rules_checked=self._dedupe(checked),
            warnings=self._dedupe(warnings),
            protected_text_preserved=protected_ok,
        )

    def _protect_blocks(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        protected: List[Dict[str, Any]] = []

        def repl(match: re.Match[str]) -> str:
            block = match.group(0)
            token = f"⟦PP_PROVIDER_PROTECTED_{len(protected)}⟧"
            protected.append({
                "token": token,
                "text": block,
                "sha256": hashlib.sha256(block.encode("utf-8")).hexdigest(),
            })
            return token

        return _PROTECTED_BLOCK_PATTERN.sub(repl, text), protected

    @staticmethod
    def _restore_blocks(text: str, protected: Sequence[Mapping[str, Any]]) -> str:
        out = text
        for item in protected:
            out = out.replace(str(item["token"]), str(item["text"]))
        return out

    @staticmethod
    def _dedupe(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        out: List[str] = []
        for value in values:
            if value and value not in seen:
                out.append(value)
                seen.add(value)
        return out


__all__ = ["ProviderNeutralizer", "ProviderNeutralizationResult"]

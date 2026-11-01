"""Alex personalization and provider-normalization utilities.

Every user-facing provider response passes through this module. The pass may be
byte-for-byte neutral; a no-op is still a completed personalization decision.
The deterministic pass is intentionally conservative. It removes obvious
provider fingerprints, protects exact artifacts, records what it changed, and
leaves deeper language work to the primary model/profile contract.

Hard laws:
- Never rewrite code fences.
- Never rewrite explicitly protected exact/verbatim/source material.
- Never invent omitted source text; use source refs.
- Prefer the smallest useful change over personality decoration.
- Always return a personalization receipt, including for a no-op.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .provider_neutralizer import ProviderNeutralizer

_PROTECTED_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)
_BOILERPLATE_PREFIXES = (
    "sure,",
    "sure —",
    "sure—",
    "certainly,",
    "absolutely,",
    "of course,",
)

_HEDGE_PHRASES = (
    "it is important to note that ",
    "it's important to note that ",
)

_FALSE_REASSURANCE_PATTERNS = (
    r"\beverything (?:is going to|will) be (?:fine|okay)\b",
    r"\bit(?:'ll| will) all be (?:fine|okay)\b",
    r"\bdon't worry,? (?:it|everything) (?:will|is going to) be (?:fine|okay)\b",
)

_FAKE_AUTOBIOGRAPHY_PATTERNS = (
    r"\bwhen i was (?:a kid|younger|in school)\b",
    r"\bmy (?:ex|old roommate|former boss|childhood friend)\b",
    r"\bi (?:once |used to )?(?:tried|owned|worked at|lived in)\b",
)


@dataclass
class VoiceRestorationResult:
    ok: bool
    raw_response: str
    friend_response: str
    personalization_applied: bool = True
    change_level: str = "none"
    reason: str = "response already fit the active friend contract"
    applied: List[str] = field(default_factory=list)
    rules_used: List[str] = field(default_factory=list)
    protected_blocks: List[Dict[str, Any]] = field(default_factory=list)
    protected_text_preserved: bool = True
    warnings: List[str] = field(default_factory=list)
    provider_neutralization: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "raw_response": self.raw_response,
            "friend_response": self.friend_response,
            "personalization_applied": self.personalization_applied,
            "change_level": self.change_level,
            "reason": self.reason,
            "applied": self.applied,
            "rules_used": self.rules_used,
            "protected_blocks": self.protected_blocks,
            "protected_text_preserved": self.protected_text_preserved,
            "warnings": self.warnings,
            "provider_neutralization": self.provider_neutralization,
        }


class FriendVoiceRestorer:
    """Mandatory deterministic Alex personalization pass.

    The purpose is not to force an Alex catchphrase into every answer. It checks
    the response against the friend contract, removes a few generic provider
    fingerprints, protects exact material, and records either the bounded change
    or the deliberate no-op.
    """

    def __init__(self, neutralizer: ProviderNeutralizer | None = None) -> None:
        self.neutralizer = neutralizer or ProviderNeutralizer()

    def restore(
        self,
        raw_response: str,
        *,
        friend: Dict[str, Any] | None = None,
        provider: Dict[str, Any] | None = None,
        source_policy: Dict[str, Any] | None = None,
        provider_result: Dict[str, Any] | None = None,
        current_message: str = "",
        alex_packet: Dict[str, Any] | None = None,
        guidance: Sequence[Dict[str, Any]] | None = None,
    ) -> VoiceRestorationResult:
        raw = "" if raw_response is None else str(raw_response)
        friend = dict(friend or {})
        provider = dict(provider or {})
        source_policy = dict(source_policy or {})
        alex_packet = dict(alex_packet or {})
        guidance = list(guidance or [])
        applied: List[str] = []
        warnings: List[str] = []
        rules_used: List[str] = [
            "every_response_passes_personalization",
            "minimum_necessary_difference",
            "preserve_protected_text",
        ]

        neutral = self.neutralizer.neutralize(
            raw,
            provider=str(provider.get("p") or provider.get("provider") or provider.get("name") or "unknown"),
            model=str(provider.get("model") or ""),
            fixes=[str(v) for v in self._iter_values(provider.get("fix") or provider.get("fixes"))],
            source_policy=source_policy,
        )
        warnings.extend(neutral.warnings)
        rules_used.append("provider_neutralization_checked")
        applied.extend(f"provider:{item}" for item in neutral.applied)
        if "remove_provider_boilerplate_prefix" in neutral.applied:
            # Keep the historical receipt name for compatibility while exposing
            # the separate neutralization stage in provider_neutralization.
            applied.append("trim_assistant_boilerplate")

        protected_text, protected = self._protect_blocks(neutral.neutral_response)
        text = protected_text.strip()

        # Compatibility fallback for old or unknown provider profiles.  Known
        # provider boilerplate should normally have been removed by the distinct
        # ProviderNeutralizer stage above.
        stripped = self._strip_boilerplate_prefix(text)
        if stripped != text:
            applied.append("trim_assistant_boilerplate")
            text = stripped

        dehedged = self._trim_generic_hedges(text)
        if dehedged != text:
            applied.append("trim_generic_hedges")
            text = dehedged

        text = self._normalize_whitespace(text)

        if source_policy.get("quote_policy") == "quote_only_after_restoring_msg_ref":
            if self._looks_like_source_quote(text) and source_policy.get("immutable"):
                warnings.append("response_contains_possible_source_quote; verify against VerbatimVault before showing as quotation")

        text = self._restore_blocks(text, protected)
        cadence_text = self._apply_light_friend_cadence(text, friend)
        if cadence_text != text:
            applied.append("apply_low_fluff_friend_cadence")
            text = cadence_text

        if provider_result and provider_result.get("available") is False:
            warnings.append(str(provider_result.get("error") or "provider unavailable"))

        if self._matches_any(text, _FALSE_REASSURANCE_PATTERNS):
            warnings.append("possible_unsupported_false_reassurance; Alex should prefer honest presence over certainty")
            rules_used.append("avoid_unsupported_reassurance")
            replacement = self._replace_stock_false_reassurance(text, source_policy, protected)
            if replacement != text:
                text = replacement
                applied.append("replace_stock_false_reassurance_with_honest_presence")

        if self._matches_any(text, _FAKE_AUTOBIOGRAPHY_PATTERNS):
            warnings.append("possible_fake_autobiography; verify the sentence is attributed or part of quoted material")
            rules_used.append("no_fake_human_autobiography")
            replacement = self._replace_stock_fake_autobiography(text, source_policy, protected)
            if replacement != text:
                text = replacement
                applied.append("replace_stock_fake_autobiography_with_truthful_boundary")

        if alex_packet:
            rules_used.append("active_alex_state_checked")
        if guidance:
            rules_used.append("relationship_guidance_checked")

        protected_ok = all(str(item["text"]) in text for item in protected)
        if not protected_ok:
            warnings.append("protected_text_integrity_failure")

        if text == raw:
            change_level = "none"
            reason = "response already fit the active friend, context, and provider-normalization contract"
        else:
            change_level = "light_stylistic"
            reason = "removed provider-default language without changing the response's facts or protected material"

        return VoiceRestorationResult(
            ok=protected_ok,
            raw_response=raw,
            friend_response=text,
            personalization_applied=True,
            change_level=change_level,
            reason=reason,
            applied=applied,
            rules_used=self._dedupe(rules_used),
            protected_blocks=[{k: v for k, v in item.items() if k != "text"} for item in protected],
            protected_text_preserved=protected_ok,
            warnings=self._dedupe(warnings),
            provider_neutralization=neutral.as_dict(),
        )


    def _safe_to_replace_stock_sentence(
        self,
        text: str,
        source_policy: Dict[str, Any],
        protected: Sequence[Dict[str, Any]],
    ) -> bool:
        """Limit semantic repairs to obvious standalone provider sentences.

        Quoted, immutable, long, or multi-paragraph material remains warning-only.
        """
        if protected or source_policy.get("immutable"):
            return False
        stripped = text.strip()
        if not stripped or len(stripped) > 180 or "\n" in stripped:
            return False
        if any(mark in stripped for mark in ('"', '“', '”')):
            return False
        return len(re.findall(r"[.!?]+", stripped)) <= 2

    def _replace_stock_false_reassurance(
        self,
        text: str,
        source_policy: Dict[str, Any],
        protected: Sequence[Dict[str, Any]],
    ) -> str:
        if not self._safe_to_replace_stock_sentence(text, source_policy, protected):
            return text
        stripped = text.strip()
        if any(re.fullmatch(pattern + r"[.!]?", stripped, flags=re.IGNORECASE) for pattern in _FALSE_REASSURANCE_PATTERNS):
            return "I wish I could promise that. I don't know that yet, but I'm here with you."
        return text

    def _replace_stock_fake_autobiography(
        self,
        text: str,
        source_policy: Dict[str, Any],
        protected: Sequence[Dict[str, Any]],
    ) -> str:
        if not self._safe_to_replace_stock_sentence(text, source_policy, protected):
            return text
        if self._matches_any(text, _FAKE_AUTOBIOGRAPHY_PATTERNS):
            return "I don't have a human past to draw from, so I shouldn't pretend that happened to me. I can use a real, attributed example instead."
        return text

    def _protect_blocks(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        protected: List[Dict[str, Any]] = []

        def repl(match: re.Match[str]) -> str:
            block = match.group(0)
            token = f"⟦PP_PROTECTED_{len(protected)}⟧"
            protected.append({
                "token": token,
                "type": "code_fence",
                "text": block,
                "sha256": hashlib.sha256(block.encode("utf-8")).hexdigest(),
                "chars": len(block),
            })
            return token

        return _PROTECTED_BLOCK_PATTERN.sub(repl, text), protected

    def _restore_blocks(self, text: str, protected: Sequence[Dict[str, Any]]) -> str:
        out = text
        for item in protected:
            out = out.replace(str(item["token"]), str(item["text"]))
        return out

    def _strip_boilerplate_prefix(self, text: str) -> str:
        stripped = text.lstrip()
        lower = stripped.lower()
        for prefix in _BOILERPLATE_PREFIXES:
            if lower.startswith(prefix):
                candidate = stripped[len(prefix):].lstrip(" —-:\n\t")
                return candidate if candidate else text
        patterns = [
            r"^here(?:'s| is) (?:a|the) (?:concise |quick |useful )?(?:answer|response|draft)[:.!]?\s+",
            r"^i can help with that[:.!]?\s+",
        ]
        for pattern in patterns:
            updated = re.sub(pattern, "", stripped, count=1, flags=re.IGNORECASE)
            if updated != stripped:
                return updated.lstrip()
        return text

    def _trim_generic_hedges(self, text: str) -> str:
        out = text
        for phrase in _HEDGE_PHRASES:
            out = re.sub("^" + re.escape(phrase), "", out, count=1, flags=re.IGNORECASE)
        return out

    def _normalize_whitespace(self, text: str) -> str:
        lines = [ln.rstrip() for ln in text.splitlines()]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines)

    def _looks_like_source_quote(self, text: str) -> bool:
        return bool(re.search(r"(^|\n)\s*(quote|quoted|lyrics|verbatim|source)\s*[:\-]", text, flags=re.IGNORECASE))

    def _apply_light_friend_cadence(self, text: str, friend: Dict[str, Any]) -> str:
        if not text:
            return text
        avoid = {str(v).lower() for v in self._iter_values(friend.get("avoid"))}
        cadence = {str(v).lower() for v in self._iter_values(friend.get("cad") or friend.get("cadence"))}
        if "low_fluff" in cadence or "generic_assistant" in avoid:
            text = re.sub(
                r"\n?\s*(?:let me know if you(?:'d| would)? like.*|hope this helps[.!]?)\s*$",
                "",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            ).rstrip()
        return text

    def _iter_values(self, value: Any) -> Iterable[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [str(v) for v in value.values()]
        try:
            return [str(v) for v in value]
        except Exception:
            return [str(value)]

    @staticmethod
    def _matches_any(text: str, patterns: Sequence[str]) -> bool:
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def _dedupe(values: Sequence[str]) -> List[str]:
        seen: set[str] = set()
        out: List[str] = []
        for value in values:
            if value not in seen:
                out.append(value)
                seen.add(value)
        return out


class AlexPersonalizationEngine(FriendVoiceRestorer):
    """Explicit product name for the mandatory friend-preservation pass."""


__all__ = ["VoiceRestorationResult", "FriendVoiceRestorer", "AlexPersonalizationEngine"]

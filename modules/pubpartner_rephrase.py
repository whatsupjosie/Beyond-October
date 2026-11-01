"""Alex voice rewrite pass: neutral facts in, Alex's voice out, nothing added or lost.

Pipeline (drop-in for AlexPersonalizationEngine.restore):
  1. The existing deterministic pass neutralizes the provider response.
  2. Code fences and other protected blocks are swapped for placeholders.
  3. A model reads the Alex cartridge prompt and rewrites the neutral text in her voice.
  4. The rewrite must pass fidelity checks (numbers, names, links, quotes, placeholders,
     length, banned register for the mode). One retry with the failures named.
  5. If it still fails, the neutral text is returned unchanged. Facts are never invented.

Hard laws, inherited from pubpartner_voice:
- Never rewrite code fences, quoted source text, or anything marked exact/verbatim/immutable.
- Prefer the neutral text over a rewrite that cannot be verified.
- Always return a receipt, including for a skip or fallback.

The generator is any callable (system_prompt, user_text) -> str, so it can wrap E2B,
a local model, or any provider. It is called synchronously; use arestore() from async code.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from .pubpartner_voice import (
    AlexPersonalizationEngine,
    VoiceRestorationResult,
    _FAKE_AUTOBIOGRAPHY_PATTERNS,
    _FALSE_REASSURANCE_PATTERNS,
)

Generator = Callable[[str, str], str]

PRIVATE_MODES = frozenset({"baby", "nanny", "madeline"})
KNOWN_MODES = frozenset({"normal", "writing", "editor", "professional", "humphery"}) | PRIVATE_MODES
FORMAL_MODES = frozenset({"professional", "editor", "writing"})
ALLOWED_NAMES = frozenset({"alex", "josie", "curtsey", "madeline"})

_PLACEHOLDER = "⟦P{n}⟧"
_PLACEHOLDER_RE = re.compile(r"⟦P(\d+)⟧")
_NUMBER_RE = re.compile(r"\d[\d,.:/%\-]*\d|\d")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+|[A-Za-z]:\\[^\s]+|(?:\./|\.\./|/)[\w./\-]+\.\w+|\b[\w.\-]+@[\w.\-]+\.\w+\b")
_QUOTE_RE = re.compile(r"[\"“]([^\"”\n]{16,})[\"”]")
_CAP_RE = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")
_ENDEARMENT_RE = re.compile(r"\b(sweetheart|darling|honey|babe|sweetie)\b", re.IGNORECASE)
_BOILERPLATE_RE = re.compile(r"^\s*(sure|certainly|absolutely|of course|great question)\b[,!—\-]", re.IGNORECASE)
_SOURCE_QUOTE_RE = re.compile(r"(^|\n)\s*(quote|quoted|lyrics|verbatim|source)\s*[:\-]", re.IGNORECASE)
_EXACT_HINT_RE = re.compile(r"\b(verbatim|word for word|exactly as (?:it is )?written|exact text|in full)\b", re.IGNORECASE)

REPHRASE_RULES = (
    "REWRITE MODE. The text below is neutral content that must reach Josie. "
    "Say exactly this, in Alex's voice, and nothing else.\n"
    "- Add no facts, claims, names, numbers, dates, links, promises or memories that are not in the text.\n"
    "- Drop nothing: every fact, number, name, link and caveat stays.\n"
    "- Keep every placeholder like ⟦P0⟧ exactly as written, in the same order.\n"
    "- Do not answer, advise, summarize, or comment on the text. Do not mention that you rewrote it.\n"
    "- Same information order. Warmth and rhythm may change; content may not.\n"
    "- Never invent a personal history for Alex.\n"
    "- Output only the rewritten text."
)

_MODE_NOTES = {
    "normal": "Mode: normal. Full Alex voice.",
    "writing": "Mode: writing. Steady and plain; no endearments, no ellipses; keep the author's rhythm.",
    "editor": "Mode: editor. Clear, bold, no endearments, no ellipses.",
    "professional": "Mode: professional. Precise and formal, no endearments, no ellipses, no baby talk.",
    "humphery": "Mode: humphery. Noir monologue, first person, gritty but playful; facts unchanged.",
    "baby": "Mode: baby (private, explicitly activated). Gentle and playful; facts unchanged.",
    "nanny": "Mode: nanny (private, explicitly activated). Soothing caretaker; facts unchanged.",
    "madeline": "Mode: madeline (private, explicitly activated). Playful authority; facts unchanged.",
}


@dataclass
class RephraseReceipt:
    attempted: bool = False
    accepted: bool = False
    mode: str = "normal"
    attempts: int = 0
    skipped_reason: str = ""
    failures: List[str] = field(default_factory=list)
    fallback: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "attempted": self.attempted,
            "accepted": self.accepted,
            "mode": self.mode,
            "attempts": self.attempts,
            "skipped_reason": self.skipped_reason,
            "failures": list(self.failures),
            "fallback_to_neutral": self.fallback,
        }


def resolve_mode(requested: str, *, explicit_private: bool, private_session: bool, broadcast: bool) -> Tuple[str, str]:
    """Return (mode, note). Private modes need explicit activation in a private session, never in broadcast."""
    mode = str(requested or "normal").strip().lower()
    if mode not in KNOWN_MODES:
        return "normal", f"unknown mode '{mode}' treated as normal"
    if mode in PRIVATE_MODES and not (explicit_private and private_session and not broadcast):
        return "normal", f"private mode '{mode}' refused (needs explicit activation in a private, non-broadcast session)"
    return mode, ""


def protect_for_model(text: str) -> Tuple[str, List[str]]:
    """Swap fenced code for placeholders so the model cannot touch it."""
    blocks: List[str] = []

    def repl(match: "re.Match[str]") -> str:
        blocks.append(match.group(0))
        return _PLACEHOLDER.format(n=len(blocks) - 1)

    return re.sub(r"```.*?```", repl, text, flags=re.DOTALL), blocks


def restore_from_model(text: str, blocks: Sequence[str]) -> str:
    return _PLACEHOLDER_RE.sub(lambda m: blocks[int(m.group(1))] if int(m.group(1)) < len(blocks) else m.group(0), text)


def _numbers(text: str) -> List[str]:
    return sorted(_NUMBER_RE.findall(_PLACEHOLDER_RE.sub("", text)))


def _words(text: str) -> int:
    return len(_PLACEHOLDER_RE.sub(" ", text).split())


def _new_names(source: str, rewrite: str) -> Set[str]:
    known = {w.lower() for w in re.findall(r"[A-Za-z]+", source)} | set(ALLOWED_NAMES)
    out: Set[str] = set()
    for sentence in re.split(r"(?<=[.!?…])\s+|\n+", rewrite):
        tokens = _CAP_RE.findall(sentence)
        start = sentence.lstrip()[:1]
        for index, token in enumerate(tokens):
            if index == 0 and sentence.lstrip().startswith(token) and start.isupper():
                continue  # sentence-initial capital is ordinary grammar
            if token.lower() not in known:
                out.add(token)
    return out


def check_fidelity(source: str, rewrite: str, *, mode: str) -> List[str]:
    """Return a list of failure names; empty means the rewrite is faithful enough to show."""
    failures: List[str] = []
    if not rewrite.strip():
        return ["empty_rewrite"]
    if sorted(_PLACEHOLDER_RE.findall(source)) != sorted(_PLACEHOLDER_RE.findall(rewrite)):
        failures.append("placeholders_changed")
    elif [m for m in _PLACEHOLDER_RE.findall(source)] != [m for m in _PLACEHOLDER_RE.findall(rewrite)]:
        failures.append("placeholders_reordered")
    if _numbers(source) != _numbers(rewrite):
        failures.append("numbers_changed")
    if sorted(_URL_RE.findall(source)) != sorted(_URL_RE.findall(rewrite)):
        failures.append("links_or_paths_changed")
    for quoted in _QUOTE_RE.findall(source):
        if quoted not in rewrite:
            failures.append("quoted_text_altered")
            break
    added = _new_names(source, rewrite)
    if added:
        failures.append("new_names:" + ",".join(sorted(added)[:5]))
    src_words, new_words = _words(source), _words(rewrite)
    if src_words < 8:
        if new_words > src_words + 14:
            failures.append("too_long")
    else:
        ratio = new_words / max(1, src_words)
        if ratio > 1.7:
            failures.append("too_long")
        elif ratio < 0.6:
            failures.append("dropped_content")
    if _BOILERPLATE_RE.match(rewrite):
        failures.append("assistant_boilerplate")
    for pattern in _FAKE_AUTOBIOGRAPHY_PATTERNS:
        if re.search(pattern, rewrite, re.IGNORECASE) and not re.search(pattern, source, re.IGNORECASE):
            failures.append("invented_autobiography")
            break
    for pattern in _FALSE_REASSURANCE_PATTERNS:
        if re.search(pattern, rewrite, re.IGNORECASE) and not re.search(pattern, source, re.IGNORECASE):
            failures.append("false_reassurance")
            break
    if mode in FORMAL_MODES:
        if _ENDEARMENT_RE.search(rewrite) and not _ENDEARMENT_RE.search(source):
            failures.append("endearment_in_formal_mode")
        if ("…" in rewrite or "..." in rewrite) and not ("…" in source or "..." in source):
            failures.append("ellipsis_in_formal_mode")
    if mode not in PRIVATE_MODES and re.search(r"\b(goo+|gaga|wittle|widdle)\b", rewrite, re.IGNORECASE):
        failures.append("baby_talk_outside_baby_mode")
    return failures


class AlexRephrasingEngine(AlexPersonalizationEngine):
    """AlexPersonalizationEngine plus the model rewrite. Without a generator it behaves exactly like its parent."""

    def __init__(self, generator: Optional[Generator] = None, *, max_attempts: int = 2, neutralizer: Any = None) -> None:
        super().__init__(neutralizer)
        self.generator = generator
        self.max_attempts = max(1, int(max_attempts))

    # -- prompt -----------------------------------------------------------------
    def build_system_prompt(self, voice_prompt: str, mode: str) -> str:
        return "\n\n".join(part for part in (str(voice_prompt or "").strip(), REPHRASE_RULES, _MODE_NOTES.get(mode, _MODE_NOTES["normal"])) if part)

    # -- main entry -------------------------------------------------------------
    def restore(  # type: ignore[override]
        self,
        raw_response: str,
        *,
        friend: Optional[Dict[str, Any]] = None,
        provider: Optional[Dict[str, Any]] = None,
        source_policy: Optional[Dict[str, Any]] = None,
        provider_result: Optional[Dict[str, Any]] = None,
        current_message: str = "",
        alex_packet: Optional[Dict[str, Any]] = None,
        guidance: Optional[Sequence[Dict[str, Any]]] = None,
        voice_prompt: str = "",
        mode: str = "normal",
        explicit_private: bool = False,
        private_session: bool = True,
        broadcast: bool = False,
    ) -> VoiceRestorationResult:
        # Generic closers ("Hope this helps!") are provider voice; the rewrite pass always strips them.
        friend = dict(friend or {})
        friend["cad"] = list(dict.fromkeys([*self._iter_values(friend.get("cad") or friend.get("cadence")), "low_fluff"]))
        friend["avoid"] = list(dict.fromkeys([*self._iter_values(friend.get("avoid")), "generic_assistant"]))
        base = super().restore(
            raw_response, friend=friend, provider=provider, source_policy=source_policy,
            provider_result=provider_result, current_message=current_message,
            alex_packet=alex_packet, guidance=guidance,
        )
        receipt = RephraseReceipt()
        resolved, note = resolve_mode(mode, explicit_private=explicit_private, private_session=private_session, broadcast=broadcast)
        receipt.mode = resolved
        if note:
            base.warnings.append(note)
        neutral = base.friend_response
        prompt_text = voice_prompt or str((alex_packet or {}).get("prompt_text") or "")

        skip = self._skip_reason(base, neutral, source_policy or {}, prompt_text)
        if skip:
            receipt.skipped_reason = skip
            return self._finish(base, neutral, receipt)

        masked, blocks = protect_for_model(neutral)
        system = self.build_system_prompt(prompt_text, resolved)
        feedback = ""
        accepted_text = ""
        for attempt in range(1, self.max_attempts + 1):
            receipt.attempted = True
            receipt.attempts = attempt
            user_text = masked if not feedback else (
                masked + "\n\n[Your previous rewrite failed these checks: " + feedback + ". Rewrite again, fixing them.]"
            )
            try:
                candidate = str(self.generator(system, user_text) or "").strip()  # type: ignore[misc]
            except Exception as exc:  # provider failure must never break the turn
                receipt.failures.append(f"generator_error:{type(exc).__name__}")
                break
            problems = check_fidelity(masked, candidate, mode=resolved)
            if not problems:
                accepted_text = restore_from_model(candidate, blocks)
                if not all(block in accepted_text for block in blocks):
                    problems = ["protected_block_missing"]
                    accepted_text = ""
            if not problems:
                receipt.accepted = True
                break
            receipt.failures.extend(f"attempt{attempt}:{p}" for p in problems)
            feedback = ", ".join(problems)
        if receipt.accepted:
            return self._finish(base, accepted_text, receipt)
        receipt.fallback = True
        base.warnings.append("alex_rephrase_rejected; neutral text returned unchanged")
        return self._finish(base, neutral, receipt)

    async def arestore(self, raw_response: str, **kwargs: Any) -> VoiceRestorationResult:
        return await asyncio.to_thread(self.restore, raw_response, **kwargs)

    # -- helpers ----------------------------------------------------------------
    def _skip_reason(self, base: VoiceRestorationResult, neutral: str, source_policy: Dict[str, Any], prompt_text: str) -> str:
        if self.generator is None:
            return "no_generator_configured"
        if not base.ok:
            return "protected_text_integrity_failure"
        if not neutral.strip():
            return "empty_response"
        if source_policy.get("immutable") or _SOURCE_QUOTE_RE.search(neutral):
            return "exact_source_material_not_rewritten"
        if _EXACT_HINT_RE.search(neutral) and source_policy.get("quote_policy"):
            return "exact_source_material_not_rewritten"
        if not prompt_text.strip():
            return "no_voice_prompt_supplied"
        return ""

    def _finish(self, base: VoiceRestorationResult, text: str, receipt: RephraseReceipt) -> VoiceRestorationResult:
        base.friend_response = text
        if receipt.accepted:
            base.applied.append("alex_voice_rewrite")
            base.change_level = "voice_rewrite"
            base.reason = "neutral content rewritten in Alex's voice; numbers, names, links, quotes and code verified unchanged"
        base.rules_used = self._dedupe(base.rules_used + ["alex_rephrase_checked"])
        base.provider_neutralization = dict(base.provider_neutralization, alex_rephrase=receipt.as_dict())
        return base


__all__ = ["AlexRephrasingEngine", "RephraseReceipt", "check_fidelity", "resolve_mode", "protect_for_model", "restore_from_model", "REPHRASE_RULES"]

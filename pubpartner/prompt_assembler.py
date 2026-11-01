"""
Assembles the final system prompt for a turn: character identity + voice +
appearance, plus the memories most relevant to the current message, packed
to fit a token budget.

The character block is never dropped — a character with no memory context is
still recognizably itself. When the budget is tight, memories are dropped
lowest-score-first until what remains fits.
"""

from __future__ import annotations

from dataclasses import dataclass

from .cartridge import Cartridge
from .memory_store import ScoredMemory
from .tokenizer import count_tokens

DEFAULT_TOKEN_BUDGET = 2000


@dataclass(frozen=True)
class AssembledPrompt:
    text: str
    token_count: int
    memories_included: int
    memories_available: int
    truncated: bool


def _character_block(cartridge: Cartridge) -> str:
    d = cartridge.definition
    lines = [f"# {d.identity.name}", "", d.identity.summary, ""]

    if d.appearance.description or d.appearance.details:
        lines.append("## Appearance")
        if d.appearance.description:
            lines.append(d.appearance.description)
        for detail in d.appearance.details:
            lines.append(f"- {detail}")
        lines.append("")

    lines.append("## Voice")
    lines.append(f"Cadence: {d.voice.cadence}")
    lines.append(f"Vocabulary: {d.voice.vocabulary}")
    lines.append(f"Sentence length: {d.voice.sentence_length}")
    lines.append(f"Formality: {d.voice.formality}")
    if d.voice.verbal_tics:
        lines.append("Verbal tics: " + "; ".join(d.voice.verbal_tics))
    lines.append("")

    if d.identity.tendencies:
        lines.append("## Tendencies")
        for t in d.identity.tendencies:
            lines.append(f"- {t}")
        lines.append("")

    if d.identity.values:
        lines.append("## Values")
        for v in d.identity.values:
            lines.append(f"- {v}")
        lines.append("")

    if d.identity.boundaries:
        lines.append("## Boundaries")
        for b in d.identity.boundaries:
            lines.append(f"- {b}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _memory_line(scored: ScoredMemory) -> str:
    return f"- [{scored.memory.memory_type}] {scored.memory.text}"


def assemble_prompt(
    cartridge: Cartridge,
    query: str = "",
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    max_memories: int = 12,
) -> AssembledPrompt:
    """Build the full system prompt for this turn.

    Retrieves up to `max_memories` memories relevant to `query` (or the most
    recent/important memories if query is empty), then packs as many as fit
    within `token_budget` after the character block, highest-score first.
    """
    character_block = _character_block(cartridge)
    character_tokens = count_tokens(character_block)

    if query.strip():
        candidates = cartridge.memory.query(query, top_k=max_memories)
    else:
        # No query context yet (e.g. session start) — surface the most
        # important recent memories rather than nothing.
        all_memories = cartridge.memory.all()
        candidates = sorted(
            (ScoredMemory(memory=m, score=m.importance, relevance=0.0, recency=0.0) for m in all_memories),
            key=lambda s: s.score,
            reverse=True,
        )[:max_memories]

    remaining_budget = token_budget - character_tokens
    included: list[ScoredMemory] = []
    truncated = False

    if remaining_budget > 0 and candidates:
        memory_header = "\n## What you remember (most relevant first)\n"
        running_tokens = count_tokens(memory_header)
        for scored in candidates:
            line = _memory_line(scored) + "\n"
            line_tokens = count_tokens(line)
            if running_tokens + line_tokens > remaining_budget:
                truncated = True
                continue
            running_tokens += line_tokens
            included.append(scored)
    elif candidates:
        truncated = True

    if included:
        memory_block = "\n## What you remember (most relevant first)\n" + "".join(
            _memory_line(s) + "\n" for s in included
        )
    else:
        memory_block = ""

    full_text = character_block + memory_block
    return AssembledPrompt(
        text=full_text,
        token_count=count_tokens(full_text),
        memories_included=len(included),
        memories_available=len(candidates),
        truncated=truncated,
    )

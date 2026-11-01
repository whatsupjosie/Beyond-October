"""
Embeddable runtime for standalone PubPartner: wires a Cartridge, a
SequenceController, and an LLM client into one object that any host
(CLI, web service, bot framework, PubCast bridge) can drive without
reimplementing turn pacing or memory capture.

This is the seam that makes PubPartner "Portable": everything above this
module is deployment-specific (a CLI loop, an HTTP handler, a Discord
event). Everything below it (cartridge, memory_store, prompt_assembler,
sequence_controller) is deployment-agnostic. PortableRuntime is the glue,
and only the glue — it holds no character logic, no timing policy, and no
LLM-specific request shaping beyond what's needed to call `send()`.

Usage:

    from pubpartner.portable_runtime import PortableRuntime

    runtime = PortableRuntime.open("alex", api_key=os.environ["ANTHROPIC_API_KEY"])
    runtime.submit_input("hey, how's the housing situation going")
    if runtime.ready_for_turn():
        reply = runtime.run_turn()
        print(reply.text)
    runtime.close()

PortableRuntime never blocks on stdin, never assumes a REPL, and never
assumes any particular host loop shape. Callers own their own event loop
and call submit_input()/ready_for_turn()/run_turn() from wherever their
input actually arrives.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json
from uuid import uuid4

from companion_support.advisory import CompanionAdvisor

from .cartridge import Cartridge, CartridgeValidationError, load_cartridge
from .prompt_assembler import DEFAULT_TOKEN_BUDGET, assemble_prompt
from .tokenizer import count_tokens
from .sequence_controller import (
    PriorityHint,
    SequenceController,
    TurnDecision,
    score_captured_memory,
)


class PortableRuntimeError(RuntimeError):
    """Raised for runtime-level failures (no client configured, closed
    runtime reused, etc). Distinct from CartridgeValidationError, which
    covers malformed cartridge data specifically."""


@dataclass(frozen=True)
class TurnResult:
    """The outcome of one dispatched turn."""

    user_text: str
    reply_text: str
    prompt_token_count: int
    memories_included: int
    memory_id: Optional[int]  # id of the episodic memory captured for this turn, if any
    companion_advisory: Optional[dict] = None
    companion_review: Optional[dict] = None
    docking_status: Optional[dict] = None


class PortableRuntime:
    """Embeddable PubPartner session: one cartridge, one sequencer, one
    optional LLM client, driven entirely by the host's own event loop.

    Not thread-safe — one PortableRuntime per active conversation, same
    constraint as SequenceController.
    """

    def __init__(
        self,
        cartridge: Cartridge,
        *,
        sequencer: Optional[SequenceController] = None,
        llm_client: object = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        capture_episodic_memory: bool = True,
        companion_advisory_enabled: bool = True,
        subject_id: str = "owner",
        session_id: Optional[str] = None,
        docking_node: object = None,
        friend_id: Optional[str] = None,
    ):
        self._cartridge = cartridge
        self._sequencer = sequencer or SequenceController()
        self._llm_client = llm_client
        self._model = model
        self._max_tokens = max_tokens
        self._token_budget = token_budget
        self._capture_episodic_memory = capture_episodic_memory
        self._companion_advisory_enabled = companion_advisory_enabled
        self._subject_id = subject_id
        self._session_id = session_id or uuid4().hex
        self._docking_node = docking_node
        self._friend_id = friend_id or cartridge.name.strip().casefold().replace(" ", "_")
        if docking_node is not None:
            if docking_node.owner_id != subject_id:
                raise ValueError("portable runtime and docking node must share an owner")
            if docking_node.identity.role != "portable":
                raise ValueError("Horizon requires a portable docking node")
            docking_node.attach_cartridge(cartridge, self._friend_id)
        self._history: list[dict[str, str]] = []
        self._closed = False

    # ── Construction ─────────────────────────────────────────────────────

    @classmethod
    def open(
        cls,
        cartridge_path: str | Path,
        *,
        api_key: Optional[str] = None,
        sequencer: Optional[SequenceController] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
    ) -> "PortableRuntime":
        """Load a cartridge from disk and construct a ready-to-use runtime.

        Raises CartridgeValidationError or FileNotFoundError exactly as
        load_cartridge() does — this method does not swallow those.
        If api_key is None, the runtime is still usable for prompt
        assembly and memory capture; only run_turn()'s LLM call requires
        a client, and that failure is deferred until run_turn() is
        actually called (see run_turn's PortableRuntimeError).
        """
        cartridge = load_cartridge(cartridge_path)
        llm_client = None
        if api_key:
            import anthropic

            llm_client = anthropic.Anthropic(api_key=api_key)
        return cls(
            cartridge,
            sequencer=sequencer,
            llm_client=llm_client,
            model=model,
            max_tokens=max_tokens,
            token_budget=token_budget,
        )

    # ── Input / pacing ───────────────────────────────────────────────────

    def submit_input(self, text: str) -> None:
        """Buffer a fragment of user input. Safe to call multiple times in
        quick succession (e.g. a user sending several short messages) —
        the sequencer debounces them into one turn."""
        self._require_open()
        self._sequencer.submit(text)

    def ready_for_turn(self, hint: Optional[PriorityHint] = None) -> bool:
        """True if enough buffered input has settled that a turn should
        fire now. Call this from your event loop's tick (a timer, a new
        message arriving, or both) before calling run_turn()."""
        self._require_open()
        return self._sequencer.evaluate(hint) == TurnDecision.FIRE

    def is_idle(self) -> bool:
        self._require_open()
        return self._sequencer.is_session_idle()

    # ── Turn execution ───────────────────────────────────────────────────

    def run_turn(self, *, content_kind: str = "message") -> TurnResult:
        """Dispatch the currently-buffered input as one turn: assemble the
        prompt, call the LLM, capture an episodic memory of the exchange,
        and return the result.

        Raises PortableRuntimeError if no LLM client was configured (i.e.
        `open()` was called without api_key and no llm_client was passed
        to `__init__` directly) or if the sequencer has no buffered input
        ready to fire. Raises whatever the underlying anthropic client
        raises on API failure — this method does not swallow API errors,
        since silently eating a failed turn would leave the host believing
        a reply was sent when it wasn't.
        """
        self._require_open()
        if self._llm_client is None:
            raise PortableRuntimeError(
                "run_turn() requires an LLM client. Construct PortableRuntime.open() "
                "with api_key set, or pass llm_client= directly to __init__."
            )
        if not self._sequencer.has_pending_input:
            raise PortableRuntimeError(
                "run_turn() called with no buffered input — check ready_for_turn() "
                "returned True before calling run_turn()"
            )

        user_text = self._sequencer.take_turn()

        assembled = assemble_prompt(
            self._cartridge, query=user_text, token_budget=self._token_budget
        )
        advisor = CompanionAdvisor() if self._companion_advisory_enabled else None
        advice = review = None
        system = assembled.text
        if advisor is not None:
            advice = advisor.prepare(user_text, user_id=self._subject_id,
                session_id=self._session_id, friend_id=self._friend_id,
                project_id="default", room_id="portable", audience="private",
                history=self._history, content_kind=content_kind)
            rules = list(advice["guidance"])
            # Do not silently drop cartridge identity/memory to insert advisers.
            while rules:
                candidate = assembled.text + "\n\ncompanion_advisory=" + json.dumps(rules)
                if count_tokens(candidate) <= self._token_budget:
                    system = candidate
                    break
                rules.pop()
            advice["guidance_included"] = len(rules)
        docking_status = None
        if self._docking_node is not None:
            try:
                recalled = self._docking_node.recall(owner_id=self._subject_id,
                    friend_id=self._friend_id, query=user_text)
                docking_status = {"recall": {"complete": recalled["complete"], "count": len(recalled["items"])}}
            except Exception as exc:
                recalled = {"items": [], "complete": False}
                docking_status = {"recall": {"complete": False, "error": type(exc).__name__}}
            suffix = "\n\ndocked_evidence=" + json.dumps(recalled)
            docking_status["recall"]["included"] = count_tokens(system + suffix) <= self._token_budget
            if docking_status["recall"]["included"]:
                system += suffix
        self._history.append({"role": "user", "content": user_text})

        response = self._llm_client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=self._history,
        )
        reply_text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        self._history.append({"role": "assistant", "content": reply_text})
        if advisor is not None:
            review = advisor.review(user_text, reply_text, content_kind=content_kind)

        memory_id: Optional[int] = None
        if self._capture_episodic_memory:
            importance = score_captured_memory(user_text)
            memory_id = self._cartridge.memory.add(
                f"User said: {user_text}", memory_type="episodic", importance=importance
            )

        if self._docking_node is not None and self._capture_episodic_memory:
            try:
                experience_id = self._docking_node.record_experience(
                    user_text=user_text, reply_text=reply_text,
                    session_id=self._session_id, friend_id=self._friend_id,
                    source_ref=f"cartridge-memory:{memory_id}", review=review)
                docking_status["capture"] = {"status": "recorded", "id": experience_id}
            except Exception as exc:
                docking_status["capture"] = {"status": "failed", "error": type(exc).__name__}

        return TurnResult(
            user_text=user_text,
            reply_text=reply_text,
            prompt_token_count=count_tokens(system),
            memories_included=assembled.memories_included,
            memory_id=memory_id,
            companion_advisory=advice,
            companion_review=review,
            docking_status=docking_status,
        )

    def build_prompt_only(self, query: str = "") -> str:
        """Assemble and return a system prompt without dispatching a turn
        or calling any LLM. Useful for hosts that want to hand the prompt
        to their own model client rather than the built-in Anthropic call
        in run_turn()."""
        self._require_open()
        return assemble_prompt(self._cartridge, query=query, token_budget=self._token_budget).text

    # ── Lifecycle ────────────────────────────────────────────────────────

    def close(self) -> None:
        if self._closed:
            return
        self._cartridge.close()
        self._closed = True

    def __enter__(self) -> "PortableRuntime":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _require_open(self) -> None:
        if self._closed:
            raise PortableRuntimeError("PortableRuntime is closed — cannot use after close()")

    @property
    def cartridge_name(self) -> str:
        self._require_open()
        return self._cartridge.name

    @property
    def turn_count(self) -> int:
        return self._sequencer.turn_count

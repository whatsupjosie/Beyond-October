"""Bounded, provider-independent companion guidance for the current spine.

Recovered Friday engines are used as advisers. Their canned response text and
automatic rewrites are never emitted. Each turn owns its own state, replayed
from the current spine's permitted history; no second memory store is created.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Mapping, Sequence

from .acceptance_engine import AcceptanceEngine
from .anti_parroting import AntiParrotingMonitor, ResponseDraft, UserTurn
from .contradiction_tracker import ContradictionTracker
from .conversation_pacing import PacingEngine
from .eq_disambiguation_engine import ContextDisambiguator
from .known_vs_novel import InsightCandidate, KnownVsNovel
from .observation_engine import ObservationEngine, unquoted_text
from .safeguards import AgencyPreserver


class CompanionAdvisor:
    SCHEMA = "pubcast.companion.advisory.v1"

    def __init__(self):
        self.observer = ObservationEngine()
        self.novelty = KnownVsNovel()
        self.contradictions = ContradictionTracker()
        self.pacing = PacingEngine()
        self.acceptance = AcceptanceEngine()
        self.quality = AntiParrotingMonitor()
        self.agency = AgencyPreserver()
        self.scope = {}
        self.prepared = False
        self.active = False
        self.disambiguator = ContextDisambiguator()

    def prepare(self, message: str, *, user_id: str, session_id: str, friend_id: str,
                project_id: str, room_id: str, audience: str,
                history: Sequence[Mapping] = (), content_kind: str = "message") -> dict:
        if self.prepared:
            raise RuntimeError("a companion adviser handles one current turn only")
        self.prepared = True
        self.scope = dict(user_id=user_id, session_id=session_id, friend_id=friend_id,
                          project_id=project_id, room_id=room_id, audience=audience)
        if content_kind != "message" or "```" in message or len(message) > 10000:
            return {"schema": self.SCHEMA, "applied": False, "scope": self.scope,
                    "reason": "protected source content or analysis budget", "guidance": []}
        self.active = True
        # Existing spine history controls access. Public/shared turns never
        # replay private dialogue through these advisers.
        permitted = list(history[-16:]) if audience == "private" else []
        for row in permitted:
            if row.get("role") == "user" and isinstance(row.get("content"), str):
                text = row["content"][:10000]
                self.novelty.ingest_user_turn(unquoted_text(text))
                self.contradictions.ingest(text, session_id)
                self.pacing.assess(text)
        bundle = self.observer.observe(message)
        self.novelty.ingest_user_turn(unquoted_text(message))
        self.contradictions.ingest(message, session_id)
        pacing = self.pacing.assess(message)
        # Explicit help requests and topic changes remain the user's decision,
        # even when the retained heuristic would choose a long crisis hold.
        if bundle.is_seeking_help:
            pace = "ready"
        elif bundle.actor == "other":
            pace = "follow_requested_topic"
        else:
            pace = pacing.decision.value
        acceptance = self.acceptance.process(message)
        context = self.disambiguator.analyze(message=unquoted_text(message), user_id=user_id)
        rules = ["Contribute useful continuation; do not repackage the user's words as empathy.",
                 "Treat known self-knowledge as already known; do not present it as your discovery.",
                 "Suggestions are optional; respect corrections, declines and explicit requests for help."]
        if pace in {"stay", "hold"}:
            rules.append("Offer presence without imposing a script or delaying a requested practical task.")
        elif bundle.is_seeking_help:
            rules.append("The user explicitly invited practical help; continue the requested work.")
        if self.contradictions.open_contradictions():
            rules.append("Explicit statements differ; treat changed context or preference as possible, not dishonesty.")
        if acceptance.what_to_avoid_saying:
            rules.append("Respect the user's stated reality; do not minimize it or insist on positive reframing.")
        # Do not copy acknowledgment, crisis-response, referral or resource
        # strings out of the old engines. The authored persona generates voice.
        guidance = [{"id": "companion-advisory-" + str(i), "source": "companion_advisory",
                     "advisory_only": True, "rule": rule} for i, rule in enumerate(rules)]
        if audience != "private":
            guidance = []  # shared-stage packets retain their existing privacy boundary
        return {"schema": self.SCHEMA, "applied": True, "scope": self.scope,
                "advisory_only": True, "pacing": pace,
                "observation": asdict(bundle),
                "context": {"actor": bundle.actor if bundle.actor != "unclear" else context.actor_role.value,
                            "domain": context.primary_context.value,
                            "confidence": context.confidence, "advisory_only": True},
                "known_patterns": [p.user_phrasing for p in self.novelty.known_patterns[-4:]],
                "statement_tensions": self.contradictions.summary(),
                "acceptance_avoid_count": len(acceptance.what_to_avoid_saying),
                "history_rows_used": len(permitted), "guidance": guidance}

    def review(self, message: str, response: str, *, content_kind="message") -> dict:
        if not self.prepared:
            raise RuntimeError("prepare the same turn before reviewing its draft")
        if content_kind != "message" or not self.active:
            return {"applied": False, "response_modified": False}
        report = self.quality.check(UserTurn(text=message), ResponseDraft(text=response))
        novelty = self.novelty.check_insight(InsightCandidate(content=response))
        agency_ok, agency_warnings = self.agency.check_response(response)
        return {"schema": self.SCHEMA, "scope": self.scope, "applied": True,
                "advisory_only": True, "response_modified": False,
                "parroting_risk": report.risk.value,
                "contribution": report.contribution_type.value,
                "novelty": novelty.status.value, "agency_ok": agency_ok,
                "warnings": [*report.violations, *agency_warnings][:12]}

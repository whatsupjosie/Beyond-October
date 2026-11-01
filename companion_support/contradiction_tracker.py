"""Bounded tracking of explicit opposing self-statements, pending confirmation.

New implementation from the retained companion consumer contract; the original
was not located. A changed preference is never silently labelled dishonesty or
growth. Evidence is session-scoped and no inferred psychological claims are made.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from .observation_engine import unquoted_text


@dataclass(frozen=True)
class ExplicitClaim:
    text: str
    key: str
    positive: bool
    session_id: str


@dataclass
class StatementTension:
    id: str
    claim_a: ExplicitClaim
    claim_b: ExplicitClaim
    resolved: bool = False
    resolution: str = ""
    requires_confirmation: bool = True


class ContradictionTracker:
    def __init__(self, user_id: str = "", *, capacity: int = 128):
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.user_id = user_id
        self.capacity = capacity
        self._claims: list[ExplicitClaim] = []
        self._tensions: list[StatementTension] = []

    def ingest(self, text: str, session_id: str = "") -> list[StatementTension]:
        if len(text) > 10000:
            raise ValueError("claim text too long")
        found = []
        for sentence in re.split(r"[.!?;\n]+", unquoted_text(text)):
            normalized = sentence.strip().lower().replace("i'm ", "i am ").replace("i don't ", "i do not ")
            match = re.fullmatch(r"i (?:(do not) )?(like|want|need|prefer|believe) (.+)", normalized)
            if match:
                positive, predicate, subject = not bool(match.group(1)), match.group(2), match.group(3)
            else:
                match = re.fullmatch(r"i am (not )?(.+)", normalized)
                if not match:
                    continue
                positive, predicate, subject = not bool(match.group(1)), "am", match.group(2)
            key = predicate + " " + " ".join(subject.split())
            claim = ExplicitClaim(sentence.strip(), key, positive, session_id)
            previous = next((c for c in reversed(self._claims)
                             if c.session_id == session_id and c.key == key), None)
            if previous and previous.positive != positive:
                identity = hashlib.sha256((session_id + "\0" + previous.text + "\0" + claim.text).encode()).hexdigest()[:20]
                if not any(t.id == identity for t in self._tensions):
                    tension = StatementTension(identity, previous, claim)
                    self._tensions.append(tension)
                    found.append(tension)
            self._claims.append(claim)
        self._claims = self._claims[-self.capacity:]
        self._tensions = self._tensions[-self.capacity:]
        return found

    def open_contradictions(self):
        return [t for t in self._tensions if not t.resolved]

    def resolve(self, identity: str, explanation: str):
        if not explanation.strip():
            raise ValueError("an explicit explanation is required")
        item = next(t for t in self._tensions if t.id == identity)
        item.resolved, item.resolution = True, explanation

    def generate_growth_observation(self) -> str:
        return ("Explicit statements differ; clarify whether context or preference changed."
                if self.open_contradictions() else "")

    def summary(self):
        return {"claims": len(self._claims), "open": len(self.open_contradictions()),
                "resolved": sum(t.resolved for t in self._tensions),
                "interpretation": "unconfirmed statement differences"}


def create_contradiction_tracker(user_id: str = ""):
    return ContradictionTracker(user_id)

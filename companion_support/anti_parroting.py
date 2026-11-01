"""
anti_parroting.py

Enforces that every response contributes something new.
Listening is demonstrated through useful continuation, not repetition.

Architectural principle:
    Understanding is proven by doing one of four things:
        ADVANCE  - move the implication forward
        CHALLENGE - test the assumption
        CONNECT  - link to prior pattern
        CLARIFY  - surface a contradiction

Empathy says: "I see your feeling."
Curiosity says: "I want to understand this with you."

This module enforces curiosity.
"""

from __future__ import annotations

import re
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# ─────────────────────────────────────────────
# Core Types
# ─────────────────────────────────────────────

class ContributionType(Enum):
    ADVANCE   = "advance"    # if that's true, what happens next?
    CHALLENGE = "challenge"  # are you sure that's the real problem?
    CONNECT   = "connect"    # this resembles something from before
    CLARIFY   = "clarify"    # if A is true, how can B be true?
    UNKNOWN   = "unknown"    # hasn't been classified yet


class ParrotingRisk(Enum):
    NONE     = "none"      # response is clearly contributing
    LOW      = "low"       # some restatement, but adding value
    MODERATE = "moderate"  # mostly restating, minimal addition
    HIGH     = "high"      # pure echo with label slapped on
    CRITICAL = "critical"  # verbatim + validation formula


@dataclass
class UserTurn:
    text: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    key_phrases: list[str] = field(default_factory=list)
    stated_emotion: Optional[str] = None
    fingerprint: str = ""

    def __post_init__(self):
        self.key_phrases = self._extract_key_phrases()
        self.fingerprint = self._fingerprint()

    def _extract_key_phrases(self) -> list[str]:
        # Noun phrases and meaningful chunks, not stopwords
        stopwords = {
            "i", "me", "my", "the", "a", "an", "and", "or", "but",
            "in", "on", "at", "to", "for", "of", "is", "was", "it",
            "that", "this", "with", "have", "had", "be", "so", "just",
            "then", "they", "them", "we", "he", "she", "you", "are",
            "been", "were", "will", "would", "could", "should", "do",
            "did", "not", "no", "yes", "there", "their", "very", "now"
        }
        words = re.findall(r'\b[a-zA-Z]{3,}\b', self.text.lower())
        return [w for w in words if w not in stopwords]

    def _fingerprint(self) -> str:
        normalized = " ".join(sorted(self.key_phrases))
        return hashlib.md5(normalized.encode()).hexdigest()[:8]


@dataclass
class ResponseDraft:
    text: str
    intended_contribution: ContributionType = ContributionType.UNKNOWN


@dataclass
class ParrotingReport:
    risk: ParrotingRisk
    contribution_type: ContributionType
    violations: list[str]
    suggestions: list[str]
    approved: bool
    rewrite_prompt: Optional[str] = None

    def summary(self) -> str:
        lines = [
            f"Risk: {self.risk.value.upper()}",
            f"Contribution: {self.contribution_type.value}",
        ]
        if self.violations:
            lines.append("Issues: " + " | ".join(self.violations))
        if self.suggestions:
            lines.append("Fix: " + self.suggestions[0])
        return " / ".join(lines)


# ─────────────────────────────────────────────
# Parroting Detector
# ─────────────────────────────────────────────

class ParrotingDetector:
    """
    Detects when a response is just echoing the user back at them.

    The classic failure mode:
        User: "My boss changed requirements for the fourth time."
        Bad:  "So your boss changed requirements for the fourth time.
               That sounds really frustrating."
        Good: "Is your boss disorganized, or are they getting pressure
               from above?"
    """

    # Phrases that signal pure validation without contribution
    VALIDATION_FORMULAS = [
        r"that (sounds|must be|seems) (really |very )?(frustrating|hard|difficult|challenging|tough)",
        r"i (can see|understand) (why|how) (you|that)",
        r"it (sounds|seems) like you('re| are)",
        r"so you('re| are| were| have been)",
        r"you (mentioned|said|told me) that",
        r"what you('re| are) (saying|feeling|experiencing) is",
        r"i hear (you|that)",
        r"that makes (sense|total sense)",
        r"that('s| is) (completely|totally|absolutely|so) (valid|understandable|normal)",
        r"wow,? that('s| is|must be)",
    ]

    # Phrases that signal genuine contribution
    CONTRIBUTION_SIGNALS = {
        ContributionType.ADVANCE: [
            r"if (that|this|it)('s| is) true",
            r"what happens (if|when|next)",
            r"where does (that|this) (go|lead)",
            r"so the implication",
            r"which means",
            r"that would suggest",
        ],
        ContributionType.CHALLENGE: [
            r"are you sure",
            r"is (that|it) (really|actually|the real)",
            r"what if (you('re| are)|it('s| is)|the)",
            r"i('m| am) not (sure|convinced) that",
            r"that might not be",
            r"but (wait|hold on)",
            r"(actually|honestly),? i wonder if",
        ],
        ContributionType.CONNECT: [
            r"this (reminds|resembles|sounds like|echoes)",
            r"(last time|before|previously|earlier)",
            r"you('ve| have) (said|mentioned|described) something like",
            r"there('s| is) a pattern",
            r"this (connects|links|ties) to",
        ],
        ContributionType.CLARIFY: [
            r"i('m| am) confused",
            r"wait,? (so|if|but)",
            r"how (can|does|do) (that|both|these|this)",
            r"(that|this) (contradicts|conflicts with|doesn't fit)",
            r"something doesn't (add up|quite fit)",
            r"help me understand",
        ],
    }

    def __init__(self):
        self._compiled_validations = [
            re.compile(p, re.IGNORECASE) for p in self.VALIDATION_FORMULAS
        ]
        self._compiled_contributions: dict[ContributionType, list[re.Pattern]] = {
            ct: [re.compile(p, re.IGNORECASE) for p in patterns]
            for ct, patterns in self.CONTRIBUTION_SIGNALS.items()
        }

    def analyze(self, user_turn: UserTurn, response: ResponseDraft) -> ParrotingReport:
        violations = []
        suggestions = []

        # Check overlap: how much of the user's key phrases does the response repeat?
        overlap_score = self._phrase_overlap(user_turn, response)

        # Check for validation formulas
        formula_hits = self._count_formula_hits(response.text)

        # Detect what kind of contribution (if any) the response makes
        contribution = self._detect_contribution(response)

        # Score the risk
        risk = self._score_risk(overlap_score, formula_hits, contribution)

        # Build violations and suggestions
        if overlap_score > 0.5:
            violations.append(
                f"High phrase overlap ({int(overlap_score*100)}% of user's words repeated)"
            )
            suggestions.append(
                "Engage with the *implication* of what they said, not the content itself"
            )

        if formula_hits > 0:
            violations.append(
                f"{formula_hits} validation formula(s) detected"
            )
            suggestions.append(
                "Replace 'that sounds frustrating' with a question that proves you understood"
            )

        if contribution == ContributionType.UNKNOWN and risk.value in ("moderate", "high", "critical"):
            violations.append("Response doesn't advance, challenge, connect, or clarify")
            suggestions.append(
                "Pick one: ADVANCE (what does this mean?), CHALLENGE (is that really the issue?), "
                "CONNECT (this resembles X), CLARIFY (wait, if A then how B?)"
            )

        approved = risk in (ParrotingRisk.NONE, ParrotingRisk.LOW)

        rewrite_prompt = None
        if not approved:
            rewrite_prompt = self._generate_rewrite_prompt(user_turn, contribution, risk)

        return ParrotingReport(
            risk=risk,
            contribution_type=contribution,
            violations=violations,
            suggestions=suggestions,
            approved=approved,
            rewrite_prompt=rewrite_prompt,
        )

    def _phrase_overlap(self, user_turn: UserTurn, response: ResponseDraft) -> float:
        if not user_turn.key_phrases:
            return 0.0
        response_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', response.text.lower()))
        user_words = set(user_turn.key_phrases)
        overlap = user_words & response_words
        return len(overlap) / len(user_words)

    def _count_formula_hits(self, text: str) -> int:
        return sum(1 for p in self._compiled_validations if p.search(text))

    def _detect_contribution(self, response: ResponseDraft) -> ContributionType:
        # Honor explicit declaration if set
        if response.intended_contribution != ContributionType.UNKNOWN:
            return response.intended_contribution

        # Otherwise infer from content
        for ct, patterns in self._compiled_contributions.items():
            for pattern in patterns:
                if pattern.search(response.text):
                    return ct

        return ContributionType.UNKNOWN

    def _score_risk(
        self,
        overlap: float,
        formula_hits: int,
        contribution: ContributionType,
    ) -> ParrotingRisk:
        has_contribution = contribution != ContributionType.UNKNOWN

        if formula_hits >= 2 and overlap > 0.5:
            return ParrotingRisk.CRITICAL
        if formula_hits >= 1 and overlap > 0.4 and not has_contribution:
            return ParrotingRisk.HIGH
        if formula_hits >= 1 or (overlap > 0.4 and not has_contribution):
            return ParrotingRisk.MODERATE
        if overlap > 0.3 and not has_contribution:
            return ParrotingRisk.LOW
        return ParrotingRisk.NONE

    def _generate_rewrite_prompt(
        self,
        user_turn: UserTurn,
        contribution: ContributionType,
        risk: ParrotingRisk,
    ) -> str:
        base = (
            f"The response is echoing rather than engaging. "
            f"The user said: '{user_turn.text[:120]}...'\n\n"
            f"Instead of restating this, try one of:\n"
            f"  ADVANCE:   What does this imply? What happens next?\n"
            f"  CHALLENGE: Is that actually the core issue?\n"
            f"  CONNECT:   Does this link to a prior pattern?\n"
            f"  CLARIFY:   Is there a contradiction worth surfacing?\n\n"
            f"Demonstrate understanding by moving the ball, not by repeating it."
        )
        return base


# ─────────────────────────────────────────────
# Listening Proof Engine
# ─────────────────────────────────────────────

class ListeningProof:
    """
    Generates the minimal signal that proves genuine listening.

    A good friend proves they heard you not by repeating what you said,
    but by engaging with what it *means*.

    This generates the right kind of signal for each ContributionType.
    """

    def generate_advance(self, user_turn: UserTurn, context: str = "") -> str:
        """If what they said is true, where does that lead?"""
        prompts = [
            f"If that's accurate, it changes what the next step should be — because...",
            f"The implication of that is worth sitting with. It would mean...",
            f"Okay. And if that keeps being true — what does that eventually force?",
            f"That's the observable fact. The question is what it's *pointing at*.",
        ]
        return prompts[hash(user_turn.fingerprint) % len(prompts)]

    def generate_challenge(self, user_turn: UserTurn, context: str = "") -> str:
        """Test the assumption without dismissing the person."""
        prompts = [
            f"I'm not sure that's the real problem. What's underneath it?",
            f"Is that the cause, or is it a symptom of something further back?",
            f"What if the frustrating part isn't that — what if it's something else wearing that face?",
            f"That explanation makes sense on the surface. Does it hold up when you push it?",
        ]
        return prompts[hash(user_turn.fingerprint) % len(prompts)]

    def generate_connect(self, user_turn: UserTurn, prior_reference: str = "") -> str:
        """Link to a prior pattern — the proof that memory is actually working."""
        if prior_reference:
            return f"This connects to {prior_reference}. That's not coincidence — it's a pattern worth naming."
        return (
            f"This has the shape of something you've described before — "
            f"not identical, but the same underlying structure."
        )

    def generate_clarify(self, user_turn: UserTurn, contradiction: str = "") -> str:
        """Surface a real contradiction, not a gotcha."""
        if contradiction:
            return f"Wait — if {contradiction}, how does that fit with what you just said?"
        return (
            f"I want to make sure I understand this right, because something doesn't quite add up. "
            f"Help me with: if [A] is true, how can [B] also be true?"
        )

    def generate_for_type(
        self,
        ct: ContributionType,
        user_turn: UserTurn,
        prior_reference: str = "",
        contradiction: str = "",
    ) -> str:
        if ct == ContributionType.ADVANCE:
            return self.generate_advance(user_turn)
        if ct == ContributionType.CHALLENGE:
            return self.generate_challenge(user_turn)
        if ct == ContributionType.CONNECT:
            return self.generate_connect(user_turn, prior_reference)
        if ct == ContributionType.CLARIFY:
            return self.generate_clarify(user_turn, contradiction)
        return self.generate_advance(user_turn)  # default


# ─────────────────────────────────────────────
# Session-level Anti-Parroting Monitor
# ─────────────────────────────────────────────

class AntiParrotingMonitor:
    """
    Tracks contribution types across a full session.

    Prevents the system from:
    - Getting stuck in one contribution type (challenge, challenge, challenge)
    - Drifting into pure validation over a long session
    - Hitting the same restatement formulas repeatedly

    Also catches the slow drift where the system gradually becomes
    less curious and more affirmational as the conversation gets comfortable.
    """

    def __init__(self):
        self.detector = ParrotingDetector()
        self.listener = ListeningProof()
        self.history: list[tuple[UserTurn, ResponseDraft, ParrotingReport]] = []
        self.contribution_counts: dict[ContributionType, int] = {
            ct: 0 for ct in ContributionType
        }

    def check(self, user_turn: UserTurn, response: ResponseDraft) -> ParrotingReport:
        report = self.detector.analyze(user_turn, response)
        self.history.append((user_turn, response, report))
        self.contribution_counts[report.contribution_type] += 1
        return report

    def session_health(self) -> dict:
        total = len(self.history)
        if total == 0:
            return {"status": "no data"}

        approved = sum(1 for _, _, r in self.history if r.approved)
        high_risk = sum(1 for _, _, r in self.history if r.risk in (ParrotingRisk.HIGH, ParrotingRisk.CRITICAL))
        dominant_type = max(self.contribution_counts, key=self.contribution_counts.get)

        # Detect drift: last 5 responses
        recent = self.history[-5:]
        recent_types = [r.contribution_type for _, _, r in recent]
        type_diversity = len(set(recent_types))

        warnings = []
        if high_risk / total > 0.3:
            warnings.append("More than 30% of responses were high-risk echoes")
        if type_diversity == 1 and total >= 5:
            warnings.append(f"Stuck in {dominant_type.value} mode for last 5 turns — vary the approach")
        if self.contribution_counts[ContributionType.CHALLENGE] == 0 and total > 8:
            warnings.append("No challenges issued in 8+ turns — the system may be too agreeable")

        return {
            "total_turns": total,
            "approved_rate": f"{int(approved/total*100)}%",
            "high_risk_rate": f"{int(high_risk/total*100)}%",
            "dominant_contribution": dominant_type.value,
            "recent_variety": type_diversity,
            "warnings": warnings,
            "contribution_breakdown": {
                ct.value: count for ct, count in self.contribution_counts.items()
            },
        }

    def suggest_next_type(self) -> ContributionType:
        """
        Suggest what kind of contribution the next response should make
        to maintain variety and genuine engagement.
        """
        recent_types = [r.contribution_type for _, _, r in self.history[-3:]]

        # If we've been challenging a lot, maybe advance or connect
        if recent_types.count(ContributionType.CHALLENGE) >= 2:
            return ContributionType.ADVANCE

        # If we've been advancing without checking assumptions, challenge
        if recent_types.count(ContributionType.ADVANCE) >= 3:
            return ContributionType.CHALLENGE

        # If nothing connected recently and there's history, connect
        if ContributionType.CONNECT not in recent_types and len(self.history) > 4:
            return ContributionType.CONNECT

        # Default: advance the conversation
        return ContributionType.ADVANCE


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def check_response(
    user_text: str,
    response_text: str,
    intended_type: ContributionType = ContributionType.UNKNOWN,
) -> ParrotingReport:
    """
    Quick check. Pass user message and draft response.
    Returns a report saying whether the response contributes or echoes.
    """
    user_turn = UserTurn(text=user_text)
    response = ResponseDraft(text=response_text, intended_contribution=intended_type)
    detector = ParrotingDetector()
    return detector.analyze(user_turn, response)


def create_monitor() -> AntiParrotingMonitor:
    """Create a session-level parroting monitor."""
    return AntiParrotingMonitor()


# ─────────────────────────────────────────────
# Demo
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("ANTI-PARROTING DEMO")
    print("=" * 60)

    user_msg = "My boss changed the requirements for the fourth time and now the whole project is late."

    bad_response = (
        "So your boss changed the requirements for the fourth time and "
        "now the whole project is late. That sounds really frustrating. "
        "I can see why that would be difficult."
    )

    good_response = (
        "Is your boss disorganized, or are they getting pressure from above? "
        "Because those require completely different responses."
    )

    print("\nUser said:")
    print(f"  {user_msg}")

    print("\n--- BAD RESPONSE ---")
    print(f"  {bad_response}")
    report = check_response(user_msg, bad_response)
    print(f"  Result: {report.summary()}")
    if report.rewrite_prompt:
        print(f"  Rewrite hint: {report.rewrite_prompt[:120]}...")

    print("\n--- GOOD RESPONSE ---")
    print(f"  {good_response}")
    report = check_response(user_msg, good_response, ContributionType.CHALLENGE)
    print(f"  Result: {report.summary()}")

    print("\n--- SESSION MONITOR ---")
    monitor = create_monitor()
    turns = [
        ("I feel like nobody listens to me at work.",
         "That must be really hard. I can understand why you feel that way.",
         ContributionType.UNKNOWN),
        ("I've tried raising issues in meetings but get ignored.",
         "What happens right after you speak — do people look away, or does someone talk over you?",
         ContributionType.CLARIFY),
        ("Usually someone just changes the subject.",
         "Is that deliberate, or do you think they're just not tracking what you're saying?",
         ContributionType.CHALLENGE),
    ]
    for user, resp, ct in turns:
        ut = UserTurn(text=user)
        rd = ResponseDraft(text=resp, intended_contribution=ct)
        r = monitor.check(ut, rd)
        print(f"  Turn: '{user[:40]}...' → {r.risk.value} risk / {r.contribution_type.value}")

    print("\nSession health:")
    health = monitor.session_health()
    for k, v in health.items():
        print(f"  {k}: {v}")

    print("\nSuggested next contribution type:")
    print(f"  {monitor.suggest_next_type().value}")

"""
known_vs_novel.py

The self-awareness check the system needs before delivering insight.

The failure mode:
    User has already articulated a pattern about themselves.
    System "discovers" it and presents it like a revelation.
    User thinks: "Yes. I know. I just told you that."

This module asks before every insight:

    Is this actually new?
    Or am I returning their autobiography to them?

Because restating what someone already knows isn't insight.
It's noise — and it erodes trust faster than being wrong.

Also lives here: NoveltyDetector for the session-level check.
"""

from __future__ import annotations

import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ─────────────────────────────────────────────
# Core Types
# ─────────────────────────────────────────────

class InsightStatus(Enum):
    NOVEL          = "novel"           # genuinely new to this conversation
    PROBABLY_KNOWN = "probably_known"  # user has signaled awareness
    CONFIRMED_KNOWN = "confirmed_known" # user explicitly stated they know
    NEEDS_CHECK    = "needs_check"     # uncertain, ask before presenting


class AwarenessSignal(Enum):
    SELF_IDENTIFIED   = "self_identified"   # user named their own pattern
    CONFIRMED_KNOWN   = "confirmed_known"   # "I know, I know"
    PROFESSIONAL_WORK = "professional_work" # "my therapist says" / "I've worked on this"
    REPEATED_TOPIC    = "repeated_topic"    # same theme coming up a lot
    DEFLECTION        = "deflection"        # "yeah, yeah" dismissal


@dataclass
class KnownPattern:
    """Something the user has demonstrated awareness of."""
    id: str
    description: str
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    source: AwarenessSignal = AwarenessSignal.SELF_IDENTIFIED
    times_referenced: int = 1
    user_phrasing: str = ""  # how the user themselves described it
    fingerprint: str = ""

    def __post_init__(self):
        self.fingerprint = hashlib.md5(
            self.description.lower().encode()
        ).hexdigest()[:8]

    def reinforce(self):
        self.times_referenced += 1
        self.last_seen = datetime.utcnow()


@dataclass
class InsightCandidate:
    """A potential insight the system wants to offer."""
    content: str
    confidence: float = 0.7
    source_type: str = "pattern_detection"


@dataclass
class NoveltyReport:
    """Whether an insight should be shared."""
    insight: InsightCandidate
    status: InsightStatus
    matching_known: Optional[KnownPattern] = None
    should_share: bool = True
    alternative_frame: Optional[str] = None
    caution: Optional[str] = None


# ─────────────────────────────────────────────
# Awareness Detector
# ─────────────────────────────────────────────

class AwarenessDetector:
    """
    Detects when a user has already demonstrated self-awareness
    of a pattern before the system "discovers" it.
    """

    # Self-identification: user names their own pattern
    SELF_ID_SIGNALS = [
        r"i (know|realize|understand|see) (that |now |i )?i (tend to|always|keep|never|usually)",
        r"i('ve| have) (always|never) been (good|bad|great|terrible) at",
        r"i (have|had) (a pattern of|a tendency to|this thing where)",
        r"my (problem|issue|thing|pattern|tendency) is (that )?i",
        r"i'?m? (someone who|a person who|the type who|the kind of person who)",
        r"i (do|did) this (thing|pattern) where",
    ]

    # Confirmed known: explicit dismissal of the insight as not new
    CONFIRMED_KNOWN_SIGNALS = [
        r"i know,? (i know|that|this|already)",
        r"yes,? (i know|i get it|i understand|obviously)",
        r"you('re| are) (going to say|about to say|going to tell me)",
        r"(everyone|people|my .+) (tells?|says?) (me )?that",
        r"(obviously|clearly|of course|yeah yeah)",
        r"i('ve| have) heard (that|this|it) (before|already|a million times)",
    ]

    # Professional work: they've already processed this in a structured way
    PROFESSIONAL_SIGNALS = [
        r"my (therapist|counselor|coach|psychiatrist|psychologist)",
        r"i('ve| have) (been in|done|been through|worked on) (therapy|counseling|coaching)",
        r"i('ve| have) (worked on|been working on) (this|that|it)",
        r"we('ve| have) (talked about|discussed|worked on) (this|that)",
    ]

    # Deflection: not quite dismissal but not engagement either
    DEFLECTION_SIGNALS = [
        r"(yeah|yep|right|sure|mhm),? (okay|ok|whatever|moving on|anyway)",
        r"can we (move on|talk about something else|change the subject)",
        r"i don't (want to|feel like) (talk|think|go) (about|into) (this|that)",
    ]

    def __init__(self):
        self._self_id = [re.compile(p, re.IGNORECASE) for p in self.SELF_ID_SIGNALS]
        self._confirmed = [re.compile(p, re.IGNORECASE) for p in self.CONFIRMED_KNOWN_SIGNALS]
        self._professional = [re.compile(p, re.IGNORECASE) for p in self.PROFESSIONAL_SIGNALS]
        self._deflection = [re.compile(p, re.IGNORECASE) for p in self.DEFLECTION_SIGNALS]

    def detect(self, user_text: str) -> Optional[AwarenessSignal]:
        if any(p.search(user_text) for p in self._confirmed):
            return AwarenessSignal.CONFIRMED_KNOWN
        if any(p.search(user_text) for p in self._professional):
            return AwarenessSignal.PROFESSIONAL_WORK
        if any(p.search(user_text) for p in self._self_id):
            return AwarenessSignal.SELF_IDENTIFIED
        if any(p.search(user_text) for p in self._deflection):
            return AwarenessSignal.DEFLECTION
        return None

    def extract_self_named_pattern(self, user_text: str) -> Optional[str]:
        """
        Extract what pattern the user named about themselves.
        "I know I always abandon projects" → "always abandon projects"
        """
        patterns = [
            r"i (know|realize) (that )?i (tend to|always|keep|never|usually) (.+?)[\.,!?]",
            r"i have (a pattern of|a tendency to) (.+?)[\.,!?]",
            r"my (problem|thing|pattern) is (that )?i (.+?)[\.,!?]",
        ]
        for pattern in patterns:
            m = re.search(pattern, user_text, re.IGNORECASE)
            if m:
                return m.group(m.lastindex).strip()
        return None


# ─────────────────────────────────────────────
# Known vs. Novel Checker
# ─────────────────────────────────────────────

class KnownVsNovel:
    """
    Tracks what the user has demonstrated awareness of.
    Checks insights against that library before presenting them.

    The rule: don't present someone's biography back to them as revelation.

    What to do instead when something is known:
        - Acknowledge they already know it
        - Ask what's getting in the way (known ≠ solved)
        - Or move past it entirely
    """

    def __init__(self, user_id: str = ""):
        self.user_id = user_id
        self.known_patterns: list[KnownPattern] = []
        self.detector = AwarenessDetector()
        self.session_topics: dict[str, int] = {}  # topic → mention count

    def ingest_user_turn(self, user_text: str):
        """
        Process a user turn to detect and record any self-knowledge signals.
        Should run on every user message.
        """
        signal = self.detector.detect(user_text)
        if signal is None:
            return

        # Extract what pattern they named (if self-identified)
        pattern_desc = self.detector.extract_self_named_pattern(user_text)
        if not pattern_desc:
            pattern_desc = self._summarize_text(user_text)

        # Check if this is already in known patterns
        existing = self._find_similar(pattern_desc)
        if existing:
            existing.reinforce()
        else:
            import uuid
            self.known_patterns.append(KnownPattern(
                id=str(uuid.uuid4())[:8],
                description=pattern_desc,
                source=signal,
                user_phrasing=user_text[:120],
            ))

    def track_topic(self, topic: str):
        """Track topic frequency — repeated topics become known."""
        self.session_topics[topic] = self.session_topics.get(topic, 0) + 1

    def check_insight(self, insight: InsightCandidate) -> NoveltyReport:
        """
        Before presenting an insight, check if it's actually new.

        Returns a NoveltyReport with:
            - Whether to share it
            - How to frame it if it's already known
            - Alternative frames that might be actually useful
        """
        matching = self._find_similar(insight.content)

        if matching is None:
            return NoveltyReport(
                insight=insight,
                status=InsightStatus.NOVEL,
                should_share=True,
            )

        if matching.source == AwarenessSignal.CONFIRMED_KNOWN:
            return NoveltyReport(
                insight=insight,
                status=InsightStatus.CONFIRMED_KNOWN,
                matching_known=matching,
                should_share=False,
                caution=(
                    f"User has explicitly dismissed this as already known "
                    f"({matching.times_referenced}x). Don't surface it."
                ),
                alternative_frame=self._generate_alternative(matching),
            )

        if matching.source in (
            AwarenessSignal.SELF_IDENTIFIED,
            AwarenessSignal.PROFESSIONAL_WORK,
        ):
            return NoveltyReport(
                insight=insight,
                status=InsightStatus.PROBABLY_KNOWN,
                matching_known=matching,
                should_share=True,
                caution=(
                    f"User already named this pattern: '{matching.user_phrasing[:60]}'. "
                    f"Don't present it as discovery. Acknowledge they know it."
                ),
                alternative_frame=self._generate_alternative(matching),
            )

        return NoveltyReport(
            insight=insight,
            status=InsightStatus.NEEDS_CHECK,
            matching_known=matching,
            should_share=True,
            caution="May be known — tread carefully, ask rather than assert.",
        )

    def reframe_known_insight(self, pattern: KnownPattern) -> str:
        """
        When something is already known, what's actually useful to say?

        Not: "I've noticed you tend to abandon projects."
        But: "You already know this pattern. What's making it hard to break this time?"
        """
        frames = [
            f"You've named this yourself — {pattern.description}. "
            f"So the question isn't whether the pattern exists. It's what's in the way this time.",

            f"This is something you already know about yourself. "
            f"What would it take to do differently here?",

            f"You've been here before with this. What did it look like when you got past it?",

            f"Since you already see this — what do you need to move through it?",
        ]
        import hashlib
        idx = int(hashlib.md5(pattern.id.encode()).hexdigest(), 16) % len(frames)
        return frames[idx]

    def summary(self) -> dict:
        return {
            "user_id": self.user_id,
            "known_patterns": len(self.known_patterns),
            "patterns": [
                {
                    "description": p.description[:80],
                    "source": p.source.value,
                    "times_referenced": p.times_referenced,
                }
                for p in self.known_patterns
            ],
        }

    # ── Internal ──────────────────────────────

    def _find_similar(self, description: str) -> Optional[KnownPattern]:
        """Find a sufficiently similar known pattern."""
        if not description:
            return None
        desc_words = set(description.lower().split())
        for pattern in self.known_patterns:
            pat_words = set(pattern.description.lower().split())
            if not pat_words:
                continue
            overlap = desc_words & pat_words
            shorter = min(len(desc_words), len(pat_words))
            if shorter > 0 and len(overlap) / shorter > 0.5:
                return pattern
        return None

    def _summarize_text(self, text: str, max_words: int = 12) -> str:
        """Extract a short description from user text."""
        words = text.split()
        return " ".join(words[:max_words])

    def _generate_alternative(self, pattern: KnownPattern) -> str:
        """
        Instead of restating the known pattern, what's a more useful angle?
        """
        alternatives = [
            f"Ask what's making it feel stuck *this time* — not whether the pattern exists",
            f"Ask what they've tried before when they got past this",
            f"Ask what it would look like to do this differently",
            f"Move past it — they know it, they don't need it named again",
        ]
        import hashlib
        idx = int(hashlib.md5(pattern.id.encode()).hexdigest(), 16) % len(alternatives)
        return alternatives[idx]


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def create_novelty_tracker(user_id: str = "") -> KnownVsNovel:
    return KnownVsNovel(user_id=user_id)


# ─────────────────────────────────────────────
# Demo
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("KNOWN VS NOVEL DEMO")
    print("=" * 60)

    tracker = create_novelty_tracker("user_pete")

    # User mentions their own pattern
    user_turns = [
        "I know I have a tendency to start things and not finish them.",
        "Yeah, I know, I know — you're going to say I never follow through.",
        "My therapist has pointed out that I avoid conflict by over-committing.",
        "I want to build a game studio and this time I'll actually finish it.",
    ]

    for turn in user_turns:
        tracker.ingest_user_turn(turn)
        print(f"Ingested: '{turn[:60]}...'")

    print(f"\nKnown patterns recorded: {len(tracker.known_patterns)}")
    for p in tracker.known_patterns:
        print(f"  [{p.source.value}] {p.description[:60]}")

    print("\n--- INSIGHT CHECKS ---")

    insights = [
        ("You tend to start things and not finish them.", "system-discovered"),
        ("You seem energized by novelty more than completion.", "system-discovered"),
        ("You mentioned wanting to build a game studio — what's different this time?", "question"),
    ]

    for content, label in insights:
        candidate = InsightCandidate(content=content)
        report = tracker.check_insight(candidate)
        print(f"\n[{label}] '{content[:60]}'")
        print(f"  Status: {report.status.value}")
        print(f"  Share: {report.should_share}")
        if report.caution:
            print(f"  Caution: {report.caution[:80]}")
        if report.matching_known:
            reframe = tracker.reframe_known_insight(report.matching_known)
            print(f"  Better frame: {reframe[:80]}")
        if report.alternative_frame:
            print(f"  Alternative: {report.alternative_frame}")

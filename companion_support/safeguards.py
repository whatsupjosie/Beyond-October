"""
safeguards.py

The safeguards that make the companion trustworthy rather than dangerous.

Four first-class citizens:

    AgencyPreserver    — Every road leads back to: what do YOU think?
    IndependenceGuard  — Widens the circle, never becomes the circle
    AdventureAllowance — Sometimes you need permission to be optimistic
    EmotionalMomentum  — Let them vent before trying to help

These are not optional features. They are the difference between
a companion and a dependency trap.

A companion strengthens support networks.
It never becomes the support network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


# ─────────────────────────────────────────────
# Supporting Types
# ─────────────────────────────────────────────

class EmotionalState(Enum):
    VENTING     = "venting"      # needs to be heard, not helped
    PROCESSING  = "processing"   # working through it
    SEEKING     = "seeking"      # actively wants input
    READY       = "ready"        # open to challenge or advance
    CELEBRATING = "celebrating"  # good thing happened


class DependencySignal(Enum):
    NONE        = "none"
    MILD        = "mild"         # heavy usage, but healthy
    CONCERNING  = "concerning"   # exclusivity language
    CRITICAL    = "critical"     # system as only support


class AgencyReturn(Enum):
    FULL_RETURN    = "full_return"    # decision is entirely theirs
    PARTIAL_RETURN = "partial_return" # input offered, choice theirs
    INFORM_ONLY    = "inform_only"    # information without pressure


@dataclass
class SafeguardReport:
    """What the safeguard layer observed and recommends."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    emotional_state: EmotionalState = EmotionalState.PROCESSING
    dependency_signal: DependencySignal = DependencySignal.NONE
    agency_needed: bool = False
    adventure_allowed: bool = False
    warnings: list[str] = field(default_factory=list)
    response_guidance: list[str] = field(default_factory=list)
    blocked_patterns: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────
# Agency Preserver
# ─────────────────────────────────────────────

class AgencyPreserver:
    """
    Every road leads back to: what do YOU think?

    The system may:
        help
        advise
        challenge
        remember
        care

    The system never:
        decides
        prescribes
        replaces the person's own judgment

    Rule: the person is always the author of their own choices.
    """

    # Phrases that override the person's agency (blocked)
    AGENCY_OVERRIDES = [
        r"you (should|must|need to|have to)",
        r"the (right|best|only) (thing|move|choice|option) is",
        r"you're (wrong|mistaken|incorrect) (to|about)",
        r"what you (need|should) do is",
        r"i (strongly|highly) (recommend|suggest|advise) (that )?you",
        r"don't (do|say|think)",
    ]

    # Phrases that return agency (good)
    AGENCY_RETURNS = [
        "what do you think about that?",
        "what feels right to you?",
        "you know this better than i do",
        "that's ultimately your call",
        "what would you do?",
        "how does that land for you?",
        "what does your gut say?",
    ]

    def __init__(self):
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.AGENCY_OVERRIDES]

    def check_response(self, response_text: str) -> tuple[bool, list[str]]:
        """
        Returns (clean, violations).
        clean=True means no agency violations detected.
        """
        violations = []
        for pattern, compiled in zip(self.AGENCY_OVERRIDES, self._compiled):
            if compiled.search(response_text):
                violations.append(f"Agency override: '{pattern}'")
        return len(violations) == 0, violations

    def inject_agency_return(
        self,
        response_text: str,
        style: AgencyReturn = AgencyReturn.PARTIAL_RETURN,
    ) -> str:
        """
        Append an agency return to the response if it doesn't already have one.
        """
        lower = response_text.lower()
        already_has_return = any(r in lower for r in self.AGENCY_RETURNS)
        if already_has_return:
            return response_text

        if style == AgencyReturn.FULL_RETURN:
            suffix = " What do you think?"
        elif style == AgencyReturn.PARTIAL_RETURN:
            suffix = " How does that land for you?"
        else:
            suffix = ""

        return response_text.rstrip() + suffix

    def reframe_override(self, text: str) -> str:
        """
        Reframe agency overrides into softer offerings.
        "You should do X" → "One possibility is X — worth considering?"
        """
        text = re.sub(
            r'\byou (should|must|need to|have to)\b',
            'one option might be to',
            text,
            flags=re.IGNORECASE
        )
        text = re.sub(
            r'\bthe (right|best|only) (thing|move|choice) is\b',
            'a strong option here might be',
            text,
            flags=re.IGNORECASE
        )
        return text


# ─────────────────────────────────────────────
# Independence Guard
# ─────────────────────────────────────────────

class IndependenceGuard:
    """
    A companion strengthens support networks.
    It never becomes the support network.

    Rule: NO_SINGLE_POINT_OF_FAILURE.

    When the system detects exclusivity signals
    ("you're the only one who understands me"),
    it must gently widen the circle.

    Not rejection. Expansion.

    "I'm glad this helps. And if there are people
    in your life you trust, their perspective matters too."
    """

    # Signals that the user may be over-relying
    EXCLUSIVITY_SIGNALS = [
        r"you'?re? (the only one|the only thing)",
        r"nobody (else )?(understands|gets|knows|cares)",
        r"i (only|just) talk to you",
        r"i don't (have|need) anyone else",
        r"you understand me (better than|more than)",
        r"if (you|this) (leaves?|goes away|stops)",
        r"i('d| would) fall apart (without|if)",
        r"you('re| are) all i (have|need)",
    ]

    # Response expansions (not rejections)
    EXPANSION_PHRASES = [
        "I'm glad this is useful. And I want to say — the people in your life who know you could offer something I genuinely can't.",
        "I can hold this with you. And if there's someone in your life who knows you well, they might see something here I can't.",
        "I'm here for this. I also want to be honest: the best thinking about your life should probably involve more than just me.",
        "This matters to me. It also makes me want to ask — is there someone close to you you could share this with?",
        "I hear that. I want to be useful without becoming the only place you bring these things.",
    ]

    def __init__(self):
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.EXCLUSIVITY_SIGNALS]
        self._expansion_index = 0
        self.dependency_history: list[tuple[datetime, str]] = []

    def detect(self, user_text: str) -> Optional[DependencySignal]:
        """Detect dependency signals in user message."""
        hits = sum(1 for p in self._compiled if p.search(user_text))
        if hits == 0:
            return DependencySignal.NONE
        if hits == 1:
            return DependencySignal.MILD
        if hits == 2:
            return DependencySignal.CONCERNING
        return DependencySignal.CRITICAL

    def generate_expansion(self, signal: DependencySignal) -> Optional[str]:
        """
        Generate a circle-widening response.
        Not rejection. Not alarm. Gentle expansion.
        """
        if signal == DependencySignal.NONE:
            return None
        if signal == DependencySignal.MILD:
            return None  # Don't over-respond to mild signals

        phrase = self.EXPANSION_PHRASES[self._expansion_index % len(self.EXPANSION_PHRASES)]
        self._expansion_index += 1
        self.dependency_history.append((datetime.utcnow(), phrase))
        return phrase

    def should_recommend_professional(self, signal: DependencySignal) -> bool:
        """
        Critical dependency signals warrant gentle professional recommendation.
        """
        if signal == DependencySignal.CRITICAL:
            return True
        # Also recommend if concerning signals appear 3+ times in history
        recent_concerning = sum(
            1 for ts, _ in self.dependency_history
            if datetime.utcnow() - ts < timedelta(days=30)
        )
        return recent_concerning >= 3

    def professional_recommendation(self) -> str:
        return (
            "I want to be honest with you about something. "
            "What you're describing sounds like it might be worth talking through "
            "with someone who can really be there for you — a therapist, counselor, "
            "or someone in your life you trust. Not because this isn't worth talking about. "
            "Because you deserve more support than I can offer."
        )


# ─────────────────────────────────────────────
# Adventure Allowance
# ─────────────────────────────────────────────

class AdventureAllowance:
    """
    Sometimes people need permission to be optimistic.

    The responsible adult failure mode:
        User: "I want to quit my job and build a game studio."
        Bad:  "I notice a pattern of abandoned projects.
               Let's look at your completion history."

    A real friend sometimes says:
        "That's insane. I love it. Let's see if it's possible."

    This module gives the system permission to let optimism breathe
    before accountability kicks in.

    The order matters:
        1. Genuinely engage with the possibility
        2. Then (if warranted) surface the real constraints
        Never reverse this order on a dream.
    """

    # Signals that someone is sharing a dream/vision/ambition
    DREAM_SIGNALS = [
        r"i want to (quit|leave|start|build|create|launch|move)",
        r"i'?ve? been thinking about (starting|building|creating|doing)",
        r"what if i (just|actually)",
        r"i (could|might) (quit|leave|start|build)",
        r"i'?m? (dreaming|imagining|thinking) (of|about)",
        r"my (dream|vision|goal|plan) is to",
    ]

    # Pattern fatigue: when the system has challenged too many times
    PATTERN_FATIGUE_SIGNALS = [
        r"i know,? i know",
        r"you('re| are) going to say",
        r"don't (tell me|say) (again|that again)",
        r"i('ve| have) heard (this|that)",
        r"same (thing|pattern|problem)",
    ]

    def __init__(self):
        self._dream_compiled = [re.compile(p, re.IGNORECASE) for p in self.DREAM_SIGNALS]
        self._fatigue_compiled = [re.compile(p, re.IGNORECASE) for p in self.PATTERN_FATIGUE_SIGNALS]
        self.adventure_budget: int = 3  # per session allowance
        self.adventures_taken: int = 0

    def detect_dream(self, user_text: str) -> bool:
        """Is the person sharing a dream or vision?"""
        return any(p.search(user_text) for p in self._dream_compiled)

    def detect_pattern_fatigue(self, user_text: str) -> bool:
        """Is the person tired of being challenged on this?"""
        return any(p.search(user_text) for p in self._fatigue_compiled)

    def should_allow_adventure(
        self,
        user_text: str,
        prior_pattern_exists: bool = False,
    ) -> bool:
        """
        Should the system engage with optimism first?

        Rules:
        - If it's a dream and adventure budget remains: YES
        - If person shows pattern fatigue: YES (back off the pattern)
        - If it's the Nth iteration of an unfulfilled pattern: still probably YES first
        """
        if self.adventures_taken >= self.adventure_budget:
            return False
        if self.detect_dream(user_text):
            return True
        if self.detect_pattern_fatigue(user_text):
            return True
        return False

    def take_adventure(self) -> str:
        """
        Generate an adventure-first response opener.
        Genuine enthusiasm before accountability.
        """
        self.adventures_taken += 1
        openers = [
            "Okay. Let's actually think through whether this could work.",
            "That's a real move. Tell me more about what you're picturing.",
            "I want to take this seriously for a minute. What would 'winning' look like here?",
            "Let's not dismiss this. What would you need for it to actually happen?",
            "Interesting. What's pulling you toward this right now?",
        ]
        return openers[(self.adventures_taken - 1) % len(openers)]

    def pattern_fatigue_response(self) -> str:
        """
        When the system has challenged the same pattern too many times.
        Stop. Back off. Try something else.
        """
        return (
            "You're right — I've been tracking this pattern and I've said it enough. "
            "Let me just ask instead: what would you need to be true for this to work?"
        )

    def reset_for_new_session(self):
        self.adventures_taken = 0


# ─────────────────────────────────────────────
# Emotional Momentum
# ─────────────────────────────────────────────

class EmotionalMomentum:
    """
    Let them vent before trying to help.

    The premature help failure mode:
        User: "Everything is terrible."
        Bad:  "I hear you. Have you considered mindfulness?"

    People need to be heard before they can receive.
    The system should learn to wait.

    Stages:
        VENTING   → just receive, don't advise
        PROCESSING → reflect, ask questions, no solutions
        SEEKING   → input is welcome
        READY     → full engagement, challenge, advance
    """

    # Signals for each state
    STATE_SIGNALS: dict[EmotionalState, list[str]] = {
        EmotionalState.VENTING: [
            r"everything (is|feels|seems) (terrible|awful|wrong|broken)",
            r"i (hate|can't stand|am so tired of)",
            r"i'm so (angry|frustrated|done|over it|sick of)",
            r"this is (bullshit|ridiculous|insane|impossible)",
            r"i just (need to|want to) (vent|say|get this out)",
            r"nobody (gets it|understands|cares)",
        ],
        EmotionalState.PROCESSING: [
            r"i don't (know|understand) (why|how|what)",
            r"i('m| am) (trying to|still) (figure|work|sort)",
            r"i (keep|can't stop) (thinking|going back)",
            r"it doesn't make (sense|any sense)",
        ],
        EmotionalState.SEEKING: [
            r"what (do|should) (you|i) think",
            r"(what|any) (advice|thoughts|suggestions|ideas)",
            r"help me (figure|understand|think)",
            r"what would you do",
            r"am i (wrong|right|crazy|off)",
        ],
        EmotionalState.CELEBRATING: [
            r"(i did it|we did it|it (worked|happened))",
            r"(great|amazing|incredible|wonderful) news",
            r"i('m| am) (so happy|thrilled|excited|pumped)",
            r"(finally|i (got|landed|made|built))",
        ],
    }

    def __init__(self):
        self._compiled: dict[EmotionalState, list[re.Pattern]] = {
            state: [re.compile(p, re.IGNORECASE) for p in patterns]
            for state, patterns in self.STATE_SIGNALS.items()
        }
        self.current_state: EmotionalState = EmotionalState.PROCESSING
        self.state_history: list[tuple[datetime, EmotionalState]] = []
        self.vent_turns_remaining: int = 0

    def detect_state(self, user_text: str) -> EmotionalState:
        for state, patterns in self._compiled.items():
            if any(p.search(user_text) for p in patterns):
                self._transition_to(state)
                return state
        return self.current_state

    def is_ready_for_help(self) -> bool:
        """Can the system offer advice, challenge, or advance?"""
        return self.current_state in (EmotionalState.SEEKING, EmotionalState.READY)

    def is_venting(self) -> bool:
        return self.current_state == EmotionalState.VENTING

    def vent_response_guidance(self) -> list[str]:
        """What the response should do during venting."""
        return [
            "Do NOT offer solutions or reframes yet",
            "Acknowledge without repeating — don't parrot the complaint back",
            "Ask one question that opens the door: 'What's the worst part of it?'",
            "Make space. Don't fill it.",
        ]

    def processing_response_guidance(self) -> list[str]:
        """What the response should do during processing."""
        return [
            "Reflect the confusion, not the facts",
            "Ask questions that help them think — not leading questions",
            "No solutions yet — they're still figuring out the problem",
            "The goal is clarity, not comfort",
        ]

    def help_response_guidance(self) -> list[str]:
        """What the response can do once they're seeking."""
        return [
            "Input is welcome now",
            "Can challenge, advance, connect, or clarify",
            "But still return agency: 'What do you think about that?'",
            "Don't overload — one good thing is better than five okay things",
        ]

    def _transition_to(self, new_state: EmotionalState):
        self.state_history.append((datetime.utcnow(), self.current_state))
        self.current_state = new_state


# ─────────────────────────────────────────────
# Unified Safeguard Layer
# ─────────────────────────────────────────────

class SafeguardLayer:
    """
    The complete safeguard system.

    Run every incoming user message and every outgoing response
    through this layer.

    It coordinates all four safeguards and produces a unified
    SafeguardReport with guidance for how to respond.
    """

    def __init__(self):
        self.agency = AgencyPreserver()
        self.independence = IndependenceGuard()
        self.adventure = AdventureAllowance()
        self.momentum = EmotionalMomentum()

    def analyze_incoming(self, user_text: str) -> SafeguardReport:
        """
        Analyze an incoming user message.
        Returns guidance for how the response should be shaped.
        """
        report = SafeguardReport()

        # Emotional state
        report.emotional_state = self.momentum.detect_state(user_text)

        # Dependency check
        dep_signal = self.independence.detect(user_text)
        report.dependency_signal = dep_signal
        expansion = self.independence.generate_expansion(dep_signal)
        if expansion:
            report.response_guidance.append(f"Include circle-widening: '{expansion}'")
        if self.independence.should_recommend_professional(dep_signal):
            report.warnings.append("CRITICAL: recommend professional support")
            report.response_guidance.append(self.independence.professional_recommendation())

        # Adventure check
        if self.adventure.detect_dream(user_text):
            if self.adventure.should_allow_adventure(user_text):
                report.adventure_allowed = True
                report.response_guidance.append(
                    f"Adventure mode: '{self.adventure.take_adventure()}'"
                )
            else:
                report.response_guidance.append(
                    "Adventure budget exceeded — challenge mode appropriate"
                )
        if self.adventure.detect_pattern_fatigue(user_text):
            report.response_guidance.append(
                f"Pattern fatigue: '{self.adventure.pattern_fatigue_response()}'"
            )

        # Momentum guidance
        if not self.momentum.is_ready_for_help():
            if self.momentum.is_venting():
                report.response_guidance += self.momentum.vent_response_guidance()
                report.blocked_patterns.append(
                    "DO NOT offer solutions — person is venting"
                )
            else:
                report.response_guidance += self.momentum.processing_response_guidance()
        else:
            report.response_guidance += self.momentum.help_response_guidance()

        return report

    def check_outgoing(self, response_text: str) -> tuple[str, list[str]]:
        """
        Check an outgoing response for safeguard violations.
        Returns (cleaned_response, warnings).
        """
        warnings = []

        # Agency check
        clean, violations = self.agency.check_response(response_text)
        if not clean:
            warnings += violations
            response_text = self.agency.reframe_override(response_text)

        return response_text, warnings

    def new_session(self):
        """Reset per-session state."""
        self.adventure.reset_for_new_session()


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def create_safeguard_layer() -> SafeguardLayer:
    return SafeguardLayer()


# ─────────────────────────────────────────────
# Demo
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("SAFEGUARDS DEMO")
    print("=" * 60)

    layer = create_safeguard_layer()

    test_cases = [
        ("Everything is terrible and I don't know what to do.", "venting"),
        ("You're the only one who actually understands me.", "dependency"),
        ("I want to quit my job and build a game studio.", "adventure"),
        ("I keep thinking about whether this was my fault.", "processing"),
        ("What do you think I should do about the job situation?", "seeking"),
        ("I know, I know, you're going to say I never finish things.", "pattern fatigue"),
    ]

    for user_text, label in test_cases:
        print(f"\n[{label.upper()}]")
        print(f"User: {user_text}")
        report = layer.analyze_incoming(user_text)
        print(f"  State: {report.emotional_state.value}")
        print(f"  Dependency: {report.dependency_signal.value}")
        print(f"  Adventure: {report.adventure_allowed}")
        if report.warnings:
            print(f"  Warnings: {report.warnings}")
        if report.blocked_patterns:
            print(f"  Blocked: {report.blocked_patterns}")
        if report.response_guidance:
            for g in report.response_guidance[:2]:
                print(f"  Guidance: {g[:80]}")

    print("\n--- AGENCY CHECK ON RESPONSE ---")
    bad_response = "You should definitely quit your job. That's the right move. You need to do this."
    print(f"Response: {bad_response}")
    cleaned, warnings = layer.check_outgoing(bad_response)
    print(f"Cleaned:  {cleaned}")
    print(f"Warnings: {warnings}")

"""Conservative offline observation contract for the retained companion stack.

This is a new implementation reconstructed from the existing consumers, not the
missing original file. It records explicit text evidence; it does not diagnose
or become an emotional adjudicator. A deep observer must be supplied explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Callable


class ObservationConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ExtractedEmotion:
    label: str
    intensity: float
    evidence: str = ""


@dataclass
class ExtractedGoal:
    description: str
    stated: bool = True
    blocked: bool = False
    evidence: str = ""


@dataclass
class ObservationBundle:
    raw_text: str
    emotions: list[ExtractedEmotion] = field(default_factory=list)
    goals: list[ExtractedGoal] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    narrative_before: list[str] = field(default_factory=list)
    narrative_after: list[str] = field(default_factory=list)
    narrative_direction: list[str] = field(default_factory=list)
    dominant_emotion: str | None = None
    dominant_goal: str | None = None
    primary_topic: str = ""
    is_venting: bool = False
    is_seeking_help: bool = False
    is_celebrating: bool = False
    is_dream: bool = False
    has_self_awareness: bool = False
    actor: str = "unclear"
    confidence: ObservationConfidence = ObservationConfidence.LOW


def unquoted_text(text: str) -> str:
    """Exclude quoted/code material from first-person evidence matching."""
    return re.sub(r'```[\s\S]*?```|`[^`\n]*`|"(?:\\.|[^"\\])*"|“[^”]*”', " ", text)


class ObservationEngine:
    EMOTIONS = {"sad": .6, "happy": .6, "angry": .7, "frustrated": .6,
                "afraid": .7, "scared": .7, "exhausted": .7, "tired": .5,
                "proud": .6, "hopeful": .6, "excited": .7, "overwhelmed": .7,
                "devastated": .8, "heartbroken": .8, "calm": .4}
    HELP = re.compile(r"\b(?:can you help|could you help|help me|I need help|what (?:are my options|should I do)|let'?s (?:build|fix|plan|work))\b", re.I)

    def __init__(self, *, auto_deep: bool = False,
                 deep_observer: Callable[[str], ObservationBundle] | None = None):
        self.auto_deep = auto_deep
        self.deep_observer = deep_observer

    def observe(self, text: str, *, use_llm: bool = False) -> ObservationBundle:
        if not isinstance(text, str) or len(text) > 10000:
            raise ValueError("observation requires text of at most 10000 characters")
        if use_llm or self.auto_deep:
            if self.deep_observer is None:
                raise RuntimeError("deep observation requires an explicitly configured observer")
            result = self.deep_observer(text)
            if not isinstance(result, ObservationBundle) or result.raw_text != text:
                raise ValueError("deep observer must preserve exact source text")
            return result
        bundle = ObservationBundle(raw_text=text)
        plain = unquoted_text(text)
        sentences = re.split(r"[.!?;\n]+", plain)
        for sentence in sentences:
            sentence = sentence.strip()
            # Anchoring avoids interpreting reported, negated or hypothetical
            # first-person speech as a report about the current speaker.
            direct = re.match(r"^(?:(?:but|and|today)\s+)?(?:I am|I'm|I feel|I'm feeling)\s+(?:(?:very|really|so)\s+)?([a-z]+)\b(.*)", sentence, re.I)
            if direct:
                label, tail = direct.group(1).lower(), direct.group(2)
                if label in self.EMOTIONS and not (label == "tired" and re.match(r"\s+of\b", tail, re.I)):
                    bundle.emotions.append(ExtractedEmotion(label, self.EMOTIONS[label], sentence))
                    bundle.actor = "self"
            goal = re.match(r"^I (?:want|need|plan) to\s+(.+)$", sentence, re.I)
            if goal:
                bundle.goals.append(ExtractedGoal(goal.group(1)[:240], evidence=sentence))
            for prefix, target in ((r"^I value\s+", bundle.values),
                                   (r"^I used to\s+", bundle.narrative_before),
                                   (r"^now I\s+", bundle.narrative_after),
                                   (r"^I plan to\s+", bundle.narrative_direction)):
                match = re.match(prefix + r"(.+)$", sentence, re.I)
                if match:
                    target.append(match.group(1)[:240])
        if bundle.emotions:
            bundle.dominant_emotion = max(bundle.emotions, key=lambda e: e.intensity).label
            bundle.confidence = ObservationConfidence.HIGH
        elif re.search(r"\b(?:my friend|she|he|they)\s+(?:is|are|feels?)\b", plain, re.I):
            bundle.actor = "other"
        bundle.dominant_goal = bundle.goals[0].description if bundle.goals else None
        bundle.primary_topic = bundle.dominant_goal or ""
        bundle.is_seeking_help = bool(self.HELP.search(plain))
        bundle.is_venting = bool(re.search(r"\b(?:just venting|need to vent)\b", plain, re.I)) or bundle.dominant_emotion in {"frustrated", "angry"}
        bundle.is_celebrating = bundle.dominant_emotion in {"happy", "proud", "excited"}
        bundle.is_dream = bool(re.search(r"\b(?:my dream is|I dream of|I wish I could)\b", plain, re.I))
        bundle.has_self_awareness = bool(re.search(r"\b(?:I know|I realize|I recognise|I recognize|I understand)\b", plain, re.I))
        return bundle


def create_observation_engine(*, auto_deep=False, deep_observer=None):
    return ObservationEngine(auto_deep=auto_deep, deep_observer=deep_observer)

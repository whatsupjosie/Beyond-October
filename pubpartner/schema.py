"""
Data model for a PubPartner cartridge.

A cartridge is the portable definition of a persistent character: who they
are, what they look like, how they sound, and how they tend to behave. This
module defines the schema that on-disk cartridges are validated against and
the exceptions raised when a cartridge is malformed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class CartridgeValidationError(ValueError):
    """Raised when a cartridge's character.yaml fails schema validation."""


@dataclass(frozen=True)
class VoiceProfile:
    """How the character sounds when they speak or write."""

    cadence: str
    vocabulary: str
    verbal_tics: tuple[str, ...] = field(default_factory=tuple)
    sentence_length: str = "varied"
    formality: str = "neutral"

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "VoiceProfile":
        missing = [k for k in ("cadence", "vocabulary") if k not in data]
        if missing:
            raise CartridgeValidationError(
                f"voice_profile missing required field(s): {', '.join(missing)}"
            )
        tics = data.get("verbal_tics", [])
        if not isinstance(tics, list):
            raise CartridgeValidationError("voice_profile.verbal_tics must be a list")
        return VoiceProfile(
            cadence=str(data["cadence"]),
            vocabulary=str(data["vocabulary"]),
            verbal_tics=tuple(str(t) for t in tics),
            sentence_length=str(data.get("sentence_length", "varied")),
            formality=str(data.get("formality", "neutral")),
        )


@dataclass(frozen=True)
class Appearance:
    """What the character looks like. All fields optional — a cartridge for
    a text-only character can omit this section entirely."""

    description: str = ""
    details: tuple[str, ...] = field(default_factory=tuple)

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> "Appearance":
        if not data:
            return Appearance()
        details = data.get("details", [])
        if not isinstance(details, list):
            raise CartridgeValidationError("appearance.details must be a list")
        return Appearance(
            description=str(data.get("description", "")),
            details=tuple(str(d) for d in details),
        )


@dataclass(frozen=True)
class Identity:
    """Core identity fields every cartridge must define."""

    name: str
    summary: str
    values: tuple[str, ...] = field(default_factory=tuple)
    boundaries: tuple[str, ...] = field(default_factory=tuple)
    tendencies: tuple[str, ...] = field(default_factory=tuple)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Identity":
        missing = [k for k in ("name", "summary") if k not in data]
        if missing:
            raise CartridgeValidationError(
                f"character missing required field(s): {', '.join(missing)}"
            )
        for list_field in ("values", "boundaries", "tendencies"):
            if list_field in data and not isinstance(data[list_field], list):
                raise CartridgeValidationError(f"character.{list_field} must be a list")
        return Identity(
            name=str(data["name"]),
            summary=str(data["summary"]),
            values=tuple(str(v) for v in data.get("values", [])),
            boundaries=tuple(str(b) for b in data.get("boundaries", [])),
            tendencies=tuple(str(t) for t in data.get("tendencies", [])),
        )


@dataclass(frozen=True)
class CharacterDefinition:
    """The full, validated contents of a cartridge's character.yaml plus
    voice_profile.yaml, combined into one object."""

    identity: Identity
    voice: VoiceProfile
    appearance: Appearance

    @property
    def name(self) -> str:
        return self.identity.name

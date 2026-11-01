"""General Chat turn orchestration.

Owns provider invocation for generic PubCast chat while ConversationArchive owns
transcript custody. It deliberately does not import PubPartner identity/memory,
2i manuscript state, or System Alex state.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from .ai_providers import generate_with_profile
from .ai_runtime import AIRuntimeConfigError, load_ai_runtime_config, validate_ai_runtime_config
from .conversation_archive import ArchivedMessage, ConversationArchive

GENERAL_CHAT_SYSTEM = (
    "You are the general-purpose AI assistant inside PubCast General Chat. "
    "Be accurate, useful, and clear. Do not assume PubPartner identity, personal "
    "memory, 2i manuscript authority, or internal System Alex authority."
)


class GeneralChatError(RuntimeError):
    """Base class for General Chat turn failures."""


class GeneralChatProviderError(GeneralChatError):
    """Raised when the configured provider cannot produce a usable reply."""

    def __init__(self, message: str, *, user_message: ArchivedMessage | None = None):
        super().__init__(message)
        self.user_message = user_message


@dataclass(frozen=True)
class GeneralChatTurn:
    user_message: ArchivedMessage
    assistant_message: ArchivedMessage
    profile: str
    backend: str
    model: str


def _select_profile(config, requested_profile: Optional[str]):
    name = (requested_profile or config.active_profile or "").strip()
    profile = config.profiles.get(name)
    if profile is None:
        raise GeneralChatProviderError(f"unknown AI profile: {name or '<empty>'}")
    if not profile.enabled:
        raise GeneralChatProviderError(f"AI profile is disabled: {name}")
    if not profile.capabilities.get("chat", True):
        raise GeneralChatProviderError(f"AI profile does not advertise chat capability: {name}")
    return profile


async def run_general_chat_turn(
    *,
    archive: ConversationArchive,
    conversation_id: str,
    exact_user_text: str,
    repo_root: Optional[Path] = None,
    requested_profile: Optional[str] = None,
    options: Optional[Mapping[str, Any]] = None,
) -> GeneralChatTurn:
    """Commit exact user input, invoke the configured AI, then commit exact reply.

    The original submitted text is archived before provider invocation so a
    provider outage cannot erase user work. Provider-facing validation may
    inspect whitespace, but archive custody never strips or normalizes text.
    Failed provider attempts do not create a fabricated assistant transcript.
    """
    if not isinstance(exact_user_text, str):
        raise TypeError("exact_user_text must be a string")
    if not exact_user_text.strip():
        raise ValueError("message must contain non-whitespace text")

    # Validate conversation existence before committing anything.
    archive.get_conversation(conversation_id)

    try:
        config = validate_ai_runtime_config(load_ai_runtime_config(repo_root))
    except AIRuntimeConfigError as exc:
        raise GeneralChatProviderError(str(exc)) from exc
    profile = _select_profile(config, requested_profile)

    user_message = archive.append_message(
        conversation_id,
        speaker="User",
        exact_text=exact_user_text,
        room="general-chat",
        program="general-chat",
        provider=profile.backend,
        model=profile.model,
        metadata={"direction": "user", "profile": profile.name},
    )

    try:
        result = await generate_with_profile(
            config,
            profile,
            exact_user_text,
            system=GENERAL_CHAT_SYSTEM,
            overrides=dict(options or {}),
        )
    except Exception as exc:
        raise GeneralChatProviderError(
            f"{type(exc).__name__}: {exc or 'provider failed without detail'}",
            user_message=user_message,
        ) from exc

    # Preserve the provider's returned text exactly. Unlike PubPartner's older
    # chat path, General Chat custody does not call .strip() on the reply.
    reply = result.text
    if not isinstance(reply, str) or not reply.strip():
        raise GeneralChatProviderError(
            f"empty response from {profile.name} ({profile.model})",
            user_message=user_message,
        )

    assistant_message = archive.append_message(
        conversation_id,
        speaker="Assistant",
        exact_text=reply,
        parent_message_id=user_message.message_id,
        room="general-chat",
        program="general-chat",
        provider=result.backend,
        model=result.model,
        metadata={
            "direction": "assistant",
            "profile": profile.name,
            "provider_name": result.provider,
        },
    )
    return GeneralChatTurn(
        user_message=user_message,
        assistant_message=assistant_message,
        profile=profile.name,
        backend=result.backend,
        model=result.model,
    )


__all__ = [
    "GENERAL_CHAT_SYSTEM",
    "GeneralChatError",
    "GeneralChatProviderError",
    "GeneralChatTurn",
    "run_general_chat_turn",
]

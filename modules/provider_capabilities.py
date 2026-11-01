"""Provider capability registry for PubPartner.

The registry describes transport/capability contracts without hard-coding a
short-lived list of model names. Model discovery remains provider/runtime owned.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class ProviderCapability:
    provider_id: str
    display_name: str
    transport: str
    aliases: List[str] = field(default_factory=list)
    credential_env: str = ""
    byok: bool = False
    local: bool = False
    streaming: bool = True
    model_discovery: str = "configured"
    roles: List[str] = field(default_factory=lambda: ["primary_conversation", "background_reasoning"])
    notes: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


_CAPABILITIES = [
    ProviderCapability("mock", "Mock", "built_in", streaming=False, model_discovery="fixed", roles=["testing"]),
    ProviderCapability("echo", "Echo", "built_in", streaming=False, model_discovery="fixed", roles=["testing"]),
    ProviderCapability("offline", "Offline Rules", "built_in", local=True, streaming=False, model_discovery="fixed", roles=["offline_fallback"]),
    ProviderCapability("ollama", "Ollama", "ollama_http", aliases=["local"], local=True, model_discovery="runtime", roles=["primary_conversation", "alex_personalization", "offline_fallback"]),
    ProviderCapability("openai", "OpenAI", "native_http", aliases=["gpt", "chatgpt"], credential_env="OPENAI_API_KEY", byok=True, model_discovery="provider"),
    ProviderCapability("anthropic", "Anthropic", "native_http", aliases=["claude"], credential_env="ANTHROPIC_API_KEY", byok=True, model_discovery="provider"),
    ProviderCapability("gemini", "Google Gemini", "native_http", aliases=["google"], credential_env="GEMINI_API_KEY", byok=True, model_discovery="provider"),
    ProviderCapability("mistral", "Mistral", "native_http", credential_env="MISTRAL_API_KEY", byok=True, model_discovery="provider"),
    ProviderCapability("groq", "Groq", "openai_compatible", credential_env="GROQ_API_KEY", byok=True, model_discovery="provider"),
    ProviderCapability("opencode_zen", "OpenCode Zen", "openai_compatible", aliases=["zen", "big_pickle"], credential_env="OPENCODE_ZEN_API_KEY", byok=True, model_discovery="provider", roles=["reference_desk", "background_reasoning"]),
    ProviderCapability(
        "openai_compatible",
        "OpenAI-Compatible Endpoint",
        "openai_compatible",
        aliases=["openrouter", "together", "fireworks", "lm_studio", "llama_cpp", "vllm"],
        byok=True,
        model_discovery="endpoint",
        notes="Requires an explicit trusted base_url; local endpoints may set require_api_key=false.",
    ),
]

_BY_ID = {item.provider_id: item for item in _CAPABILITIES}
_ALIASES = {alias: item.provider_id for item in _CAPABILITIES for alias in item.aliases}


def canonical_provider(value: str) -> str:
    key = str(value or "").strip().lower().replace("-", "_")
    return _ALIASES.get(key, key or "mock")


def provider_capability(provider: str) -> ProviderCapability | None:
    return _BY_ID.get(canonical_provider(provider))


def provider_catalog() -> List[Dict[str, Any]]:
    return [item.as_dict() for item in _CAPABILITIES]


def supported_provider_ids() -> List[str]:
    return [item.provider_id for item in _CAPABILITIES]


__all__ = [
    "ProviderCapability",
    "canonical_provider",
    "provider_capability",
    "provider_catalog",
    "supported_provider_ids",
]

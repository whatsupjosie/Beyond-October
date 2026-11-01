"""Model registry: the one place that says which AI models PubCast can run.

The AI is interchangeable. A model is described by data, not by code:
its alias, how it runs, how much context it can hold, how long a reply may
be, which tier it belongs to and how large a prompt it should receive.
Swapping SmolLM for a Gemma, Mistral or hosted model is a registry change.

Tiers, smallest first:
    offline     no model at all; the scripted characters answer
    tiny_local  phone/laptop class model with no internet (SmolLM2 today)
    local       larger model on the same machine (Gemma, Mistral, ...)
    hosted      a provider over the network (Claude, Gemini, ...)

Prompt profiles:
    full        the complete FCP1 packet rendered for the model
    compact     the same safety, identity and boundary lines, with memories,
                history and reference material trimmed for small models

The built-in table holds only entries that have been verified against a
real file. Add more in data/model_registry.json (or the file named by
PUBCAST_MODEL_REGISTRY); a local entry without a SHA-256 is refused by the
launcher so an unknown file can never be run by accident.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_FILE = ROOT / "data" / "model_registry.json"

TIERS = ("offline", "tiny_local", "local", "hosted")
RUNTIMES = ("launcher", "ollama", "hosted")
PROMPT_PROFILES = ("full", "compact")
_ALIAS_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class ModelRegistryError(ValueError):
    """Raised when a registry entry is malformed or a model is unknown."""


@dataclass(frozen=True)
class ModelSpec:
    alias: str
    display_name: str
    runtime: str
    tier: str
    context_tokens: int
    reply_tokens: int
    prompt_profile: str = "full"
    family: str = ""
    file: str = ""
    sha256: str = ""
    temperature: float = 0.3
    notes: str = ""
    verified: bool = False
    extra: Dict[str, object] = field(default_factory=dict)

    def label(self) -> Dict[str, object]:
        """What every reply carries so the user can see which model answered."""
        return {
            "model_alias": self.alias,
            "model_display_name": self.display_name,
            "model_tier": self.tier,
            "prompt_profile": self.prompt_profile,
        }


# Only facts that were checked against the real file belong here.
# SmolLM2: alias, checksum and context size come from the audited Oct 10
# package (run_smollm.py, SMOLLM_VALIDATION.md).
_BUILTIN = {
    "smollm2": {
        "display_name": "SmolLM2 1.7B Instruct (Q4_K_M)",
        "family": "smollm",
        "runtime": "launcher",
        "tier": "tiny_local",
        "context_tokens": 8192,
        "reply_tokens": 512,
        "prompt_profile": "full",
        "file": "SmolLM2-1.7B-Instruct-Q4_K_M.gguf",
        "sha256": "61b6f90dd515fd3bffbd0f6ba716e87555dde77d9b0573a562c2c5e62afc4909",
        "temperature": 0.3,
        "verified": True,
        "notes": "Baseline offline model. Full prompt profile was the validated setting.",
    },
}


def _validate(alias: str, raw: Dict[str, object]) -> ModelSpec:
    if not isinstance(raw, dict):
        raise ModelRegistryError(f"{alias}: entry must be an object")
    if not _ALIAS_RE.match(alias):
        raise ModelRegistryError(f"{alias!r}: alias must be lowercase letters, digits, . _ : -")
    known = {f for f in ModelSpec.__dataclass_fields__ if f not in ("alias", "extra")}
    extra = {k: v for k, v in raw.items() if k not in known}
    data = {k: v for k, v in raw.items() if k in known}
    for key in ("display_name", "runtime", "tier", "context_tokens", "reply_tokens"):
        if key not in data:
            raise ModelRegistryError(f"{alias}: missing {key}")
    if data["runtime"] not in RUNTIMES:
        raise ModelRegistryError(f"{alias}: runtime must be one of {RUNTIMES}")
    if data["tier"] not in TIERS or data["tier"] == "offline":
        raise ModelRegistryError(f"{alias}: tier must be one of {TIERS[1:]}")
    profile = data.get("prompt_profile", "full")
    if profile not in PROMPT_PROFILES:
        raise ModelRegistryError(f"{alias}: prompt_profile must be one of {PROMPT_PROFILES}")
    ctx, reply = data["context_tokens"], data["reply_tokens"]
    if not (isinstance(ctx, int) and isinstance(reply, int)) or isinstance(ctx, bool) or isinstance(reply, bool):
        raise ModelRegistryError(f"{alias}: context_tokens and reply_tokens must be integers")
    # 4096 is the reply ceiling enforced by the OpenAI-compatible transport.
    if not (512 <= ctx <= 2_000_000) or not (16 <= reply <= 4096) or reply >= ctx:
        raise ModelRegistryError(f"{alias}: token limits out of range (reply 16-4096 and smaller than context)")
    if data["runtime"] == "launcher":
        file_name = str(data.get("file") or "")
        if not file_name or Path(file_name).name != file_name or not file_name.lower().endswith(".gguf"):
            raise ModelRegistryError(f"{alias}: launcher models need a plain .gguf file name inside models/")
        sha = str(data.get("sha256") or "").lower()
        if sha and not _SHA_RE.match(sha):
            raise ModelRegistryError(f"{alias}: sha256 must be 64 hex characters")
        data["sha256"] = sha
    temperature = data.get("temperature", 0.3)
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
        raise ModelRegistryError(f"{alias}: temperature must be between 0 and 2")
    data["temperature"] = float(temperature)
    data["verified"] = bool(data.get("verified", False))
    return ModelSpec(alias=alias, extra=extra, **data)


def registry_path() -> Path:
    override = os.getenv("PUBCAST_MODEL_REGISTRY", "").strip()
    return Path(override).expanduser() if override else DEFAULT_REGISTRY_FILE


def load_registry(path: Optional[Path] = None) -> Dict[str, ModelSpec]:
    """Built-in entries plus the registry file. File entries may add models
    but may not silently change a verified built-in entry's file or checksum."""
    specs = {alias: _validate(alias, dict(raw)) for alias, raw in _BUILTIN.items()}
    source = path or registry_path()
    if source.is_file():
        try:
            document = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegistryError(f"cannot read model registry {source}: {exc}") from None
        models = document.get("models") if isinstance(document, dict) else None
        if not isinstance(models, dict):
            raise ModelRegistryError(f"{source}: expected an object with a 'models' map")
        for alias, raw in models.items():
            spec = _validate(str(alias), raw)
            builtin = specs.get(spec.alias)
            if builtin and builtin.verified and (spec.file, spec.sha256) != (builtin.file, builtin.sha256):
                raise ModelRegistryError(
                    f"{spec.alias}: registry file may not change the verified file or checksum; use a new alias")
            specs[spec.alias] = spec
    return specs


def get_model(alias: str, registry: Optional[Dict[str, ModelSpec]] = None) -> ModelSpec:
    specs = registry if registry is not None else load_registry()
    spec = specs.get(str(alias or "").strip().lower())
    if spec is None:
        raise ModelRegistryError(f"unknown model {alias!r}; known: {', '.join(sorted(specs))}")
    return spec


def launcher_alias() -> str:
    """The model the local launcher was started with (set by run_smollm.py)."""
    return os.getenv("PUBCAST_LOCAL_MODEL_ALIAS", "").strip().lower() or "smollm2"


def launcher_model() -> ModelSpec:
    spec = get_model(launcher_alias())
    if spec.runtime != "launcher":
        raise ModelRegistryError(f"{spec.alias} is not a launcher model")
    return spec


def describe(spec: ModelSpec) -> Dict[str, object]:
    out = asdict(spec)
    out.pop("extra", None)
    return out

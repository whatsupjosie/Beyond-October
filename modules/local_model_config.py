"""Server-owned local model configuration; browser responses never contain keys.

Which model the launcher serves is decided by the model registry
(modules/model_registry.py) and the PUBCAST_LOCAL_MODEL_ALIAS that the
launcher sets. Nothing here is specific to one model.
"""
import os
from urllib.parse import urlsplit

from .model_registry import launcher_model

# Kept for callers that imported the original SmolLM constants. They describe
# the baseline model only; live code reads launcher_model() instead.
MODEL_ALIAS = "smollm2"
CONTEXT_TOKENS = 8192
REPLY_TOKENS = 512


def configured_url():
    base = os.getenv("PUBCAST_LOCAL_MODEL_URL", "").strip().rstrip("/")
    if not base:
        return ""
    url = urlsplit(base)
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "::1"}
            or url.username or url.password or url.path != "/v1"
            or url.query or url.fragment):
        raise ValueError("Launcher model URL must be a loopback HTTP /v1 endpoint")
    if not os.getenv("PUBCAST_LOCAL_MODEL_KEY", "").strip():
        raise ValueError("Launcher model key is missing; restart with run_smollm.py")
    return base


def default_provider():
    base = configured_url()
    if base:
        spec = launcher_model()
        return {"provider": "openai_compatible", "model": spec.alias,
                "base_url": base, "require_api_key": True, "timeout": 180}
    return {"provider": "ollama", "model": os.getenv("OLLAMA_MODEL", "ministral-pubcast:3b")}


def local_api_key(base_url):
    base = configured_url()
    if base and str(base_url).strip().rstrip("/") == base:
        return os.environ["PUBCAST_LOCAL_MODEL_KEY"].strip()
    return ""

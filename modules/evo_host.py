"""Translate E-Pete's routing aliases to the existing host inference API."""
from dataclasses import fields
from typing import Mapping

from .llm_orchestrator import ContextPacket


class EVOInferenceBackend:
    """Physical model selection remains owned by InferenceManager/configuration.

    E-Pete's existing default model IDs identify its two roles. They do not
    override the Studio/Architect models configured on the host.
    """
    def __init__(self, inference, *, studio_id="gemma-studio", architect_id="gemma-architect"):
        if studio_id == architect_id:
            raise ValueError("E-Pete routing aliases must be distinct")
        self.inference = inference
        self.routes = {studio_id: "studio", architect_id: "architect"}

    async def generate(self, *, model, prompt, context):
        if model not in self.routes:
            raise ValueError("Unknown E-Pete routing alias")
        if isinstance(context, ContextPacket):
            packet = context
        elif isinstance(context, Mapping):
            known = {descriptor.name for descriptor in fields(ContextPacket)} - {"metadata"}
            values = {key: value for key, value in context.items() if key in known}
            metadata = dict(context.get("metadata") or {})
            metadata["evo_task_context"] = dict(context)
            packet = ContextPacket(**values, metadata=metadata)
        else:
            raise TypeError("EVO context must be structured data or ContextPacket")
        result = await self.inference.generate_text(prompt, requested_route=self.routes[model],
            context=packet, allow_fallback=False, user_facing=self.routes[model] == "studio")
        if result.get("error"):
            raise RuntimeError("Host inference failed: " + str(result["error"]))
        if result.get("fallback_occurred"):
            raise RuntimeError("Host inference changed the E-Pete-assigned route")
        text = result.get("text")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Host inference returned no text")
        return text

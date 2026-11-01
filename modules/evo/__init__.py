"""
PubCast AI — EVO Protocol (modules.evo)
========================================
Elastic Voxel Orchestration with E-Pete governance layer.

Copyright (c) 2024-2025 Rear View Foresight LLC
"Feic Mo Chroí — See My Heart"

Graceful degradation: if optional evo dependencies (numpy, deepface, mediapipe)
are unavailable, the individual sub-modules degrade internally. This __init__
does NOT raise on import failure — it surfaces what's available.
"""
from __future__ import annotations

__version__ = "1.2.0"

# ── Semantic runtime foundation (dependency-light) ───────────────────────────
from .semantic_field import (
    AudienceState,
    EmotionState as SemanticEmotionState,
    SafetyState,
    SceneState as SemanticSceneState,
    SemanticField,
    SemanticStore,
)
from .mutation import Role, StateMutationRequest
from .arbitration import ArbitrationEngine, ArbitrationError, ROLE_PERMISSIONS
from .semantic_events import EventEnvelope
from .event_bus import DispatchFailure, DispatchResult, EventBus
from .semantic_runtime import SemanticCommit, SemanticRuntime

# ── Core EVO pipeline (always safe to import) ────────────────────────────────
try:
    from .vdi_engine          import VDIEngine, VDIReport, VDISignals, VoiceMode
    from .vdi_semantic_adapter import VDISemanticAdapter
    from .prosody_engine      import ProsodyEngine, SynthesisParams, EmotionalState
    from .prosody_semantic_adapter import ProsodySemanticAdapter
    from .voice_characters    import get_character_profile, list_characters
    from .switchblade_governor import SwitchbladeGovernor, SceneState, PriorityVector
    from .epete               import EPete, InferenceTask, TaskType, InferenceModel
    from .pete                import PeteCharacter
    from .evo_integration     import EVOOrchestrator, EVOTick
    _EVO_CORE_AVAILABLE = True
except Exception as _evo_exc:
    import logging as _logging
    _logging.getLogger("pubcast.evo").warning(
        "EVO Protocol core import partial: %s — some features unavailable", _evo_exc
    )
    _EVO_CORE_AVAILABLE = False
    EVOOrchestrator = None   # type: ignore[assignment,misc]
    EVOTick         = None   # type: ignore[assignment,misc]
    EPete           = None   # type: ignore[assignment,misc]
    PeteCharacter   = None   # type: ignore[assignment,misc]
    VDIEngine       = None   # type: ignore[assignment,misc]
    VDISemanticAdapter = None  # type: ignore[assignment,misc]
    ProsodyEngine   = None   # type: ignore[assignment,misc]
    ProsodySemanticAdapter = None  # type: ignore[assignment,misc]
    SwitchbladeGovernor = None  # type: ignore[assignment,misc]

__all__ = [
    "_EVO_CORE_AVAILABLE",
    "SemanticField", "SemanticStore",
    "SemanticEmotionState", "AudienceState", "SemanticSceneState", "SafetyState",
    "StateMutationRequest", "Role",
    "ArbitrationEngine", "ArbitrationError", "ROLE_PERMISSIONS",
    "EventEnvelope", "EventBus", "DispatchResult", "DispatchFailure",
    "SemanticRuntime", "SemanticCommit",
    "EVOOrchestrator", "EVOTick",
    "EPete", "InferenceTask", "TaskType", "InferenceModel",
    "PeteCharacter",
    "VDIEngine", "VDIReport", "VDISignals", "VoiceMode", "VDISemanticAdapter",
    "ProsodyEngine", "SynthesisParams", "EmotionalState", "ProsodySemanticAdapter",
    "SwitchbladeGovernor", "SceneState", "PriorityVector",
    "get_character_profile", "list_characters",
]

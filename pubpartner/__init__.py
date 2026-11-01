"""PubPartner — persistent character cartridges for consistent AI personas."""

from .cartridge import Cartridge, CartridgeValidationError, init_cartridge, load_cartridge
from .memory_store import MEMORY_TYPES, Memory, MemoryStore, MemoryStoreError, ScoredMemory
from .portable_runtime import PortableRuntime, PortableRuntimeError, TurnResult
from .prompt_assembler import AssembledPrompt, assemble_prompt
from .schema import Appearance, CharacterDefinition, Identity, VoiceProfile
from .sequence_controller import (
    PendingTurn,
    PriorityHint,
    SequenceController,
    TurnDecision,
    score_captured_memory,
)

__version__ = "0.3.0"

__all__ = [
    "Cartridge",
    "CartridgeValidationError",
    "init_cartridge",
    "load_cartridge",
    "MEMORY_TYPES",
    "Memory",
    "MemoryStore",
    "MemoryStoreError",
    "ScoredMemory",
    "AssembledPrompt",
    "assemble_prompt",
    "Appearance",
    "CharacterDefinition",
    "Identity",
    "VoiceProfile",
    "PortableRuntime",
    "PortableRuntimeError",
    "TurnResult",
    "PendingTurn",
    "PriorityHint",
    "SequenceController",
    "TurnDecision",
    "score_captured_memory",
]

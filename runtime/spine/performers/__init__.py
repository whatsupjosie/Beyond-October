"""Performer-side runtime spine helpers.

Imports are lazy so performer_state can be used by the registry without pulling
locomotion back into a partially initialized registry module.
"""

__all__ = ["AnimationAuthority", "LocomotionSystem", "PerformerState", "build_replication_snapshot"]


def __getattr__(name):
    if name == "AnimationAuthority":
        from .animation_authority import AnimationAuthority
        return AnimationAuthority
    if name == "LocomotionSystem":
        from .locomotion import LocomotionSystem
        return LocomotionSystem
    if name == "PerformerState":
        from .performer_state import PerformerState
        return PerformerState
    if name == "build_replication_snapshot":
        from .replication import build_replication_snapshot
        return build_replication_snapshot
    raise AttributeError(name)
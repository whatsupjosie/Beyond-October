"""Deterministic, role-aware arbitration for EVO semantic state proposals."""
from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from typing import Iterable

from .mutation import StateMutationRequest
from .semantic_field import SemanticField


ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "performer": ("emotion",),
    "anchor": ("emotion.stability", "emotion.intensity"),
    "director": ("scene",),
    "producer": ("scene.pacing", "audience"),
    "observer": (),
    "background": (),
    "system": ("emotion", "audience", "scene", "safety"),
}


class ArbitrationError(ValueError):
    pass


class ArbitrationEngine:
    """Resolve agent proposals into one new immutable SemanticField.

    Conflict resolution is deterministic: higher priority wins, then confidence,
    then source/path as stable tie-breakers. At most one mutation is applied per
    target path per arbitration cycle. Parent/child paths conflict too: a lower
    ranked container replacement cannot erase an accepted higher ranked leaf.
    """

    def __init__(self, permissions: dict[str, tuple[str, ...]] | None = None) -> None:
        # An explicitly empty policy means deny all, not restore defaults.
        # Own the policy so outside mutations cannot grant new write authority.
        policy = ROLE_PERMISSIONS if permissions is None else permissions
        self._permissions = {role: tuple(paths) for role, paths in policy.items()}

    def resolve(
        self,
        state: SemanticField,
        mutations: Iterable[StateMutationRequest],
    ) -> SemanticField:
        ranked = sorted(
            mutations,
            key=lambda m: (-m.priority, -float(m.confidence), m.source, m.path),
        )
        accepted_paths: set[str] = set()
        result = state

        for mutation in ranked:
            if any(mutation.path == path or mutation.path.startswith(path + ".")
                   or path.startswith(mutation.path + ".") for path in accepted_paths):
                continue
            if not self.is_allowed(mutation):
                continue
            result = self._apply(result, mutation.path, mutation.value)
            accepted_paths.add(mutation.path)

        return result.normalized()

    def is_allowed(self, mutation: StateMutationRequest) -> bool:
        allowed = self._permissions.get(mutation.role, ())
        return any(
            mutation.path == prefix or mutation.path.startswith(prefix + ".")
            for prefix in allowed
        )

    def _apply(self, root: SemanticField, path: str, value: object) -> SemanticField:
        parts = path.split(".")
        if not parts:
            raise ArbitrationError("empty mutation path")
        return self._replace_path(root, parts, value)

    def _replace_path(self, obj: object, parts: list[str], value: object):
        if not is_dataclass(obj):
            raise ArbitrationError(f"cannot traverse non-dataclass at {'.'.join(parts)}")

        field_names = {f.name for f in fields(obj)}
        head = parts[0]
        if head not in field_names:
            raise ArbitrationError(f"unknown semantic field path component: {head!r}")

        if len(parts) == 1:
            return replace(obj, **{head: value})

        child = getattr(obj, head)
        replaced_child = self._replace_path(child, parts[1:], value)
        return replace(obj, **{head: replaced_child})

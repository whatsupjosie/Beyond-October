"""
tests/test_inference_router.py — Inference route resolver tests.

Covers the _resolve_route logic that bridges main.py's new API surface
(requested_route, task_type, user_facing, allow_fallback) with the
orchestrator's canonical role strings.

Rear View Foresight LLC — Feic Mo Chroí — 2026
"""
from __future__ import annotations

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.inference import _resolve_route, _ROUTE_ALIASES, _COMPLEX_TASK_TYPES


# ── _resolve_route unit tests ─────────────────────────────────────────────────

class TestResolveRoute:
    """Explicit-route cases — caller knows what they want."""

    def test_auto_maps_to_studio(self):
        assert _resolve_route("auto", None, None, None) == "studio"

    def test_studio_explicit(self):
        assert _resolve_route("studio", None, None, None) == "studio"

    def test_architect_explicit(self):
        assert _resolve_route("architect", None, None, None) == "architect"

    def test_two_pass_explicit(self):
        assert _resolve_route("architect_then_studio", None, None, None) == "architect_then_studio"

    def test_dual_alias(self):
        assert _resolve_route("dual", None, None, None) == "architect_then_studio"

    def test_plan_alias(self):
        assert _resolve_route("plan", None, None, None) == "architect"

    def test_express_alias(self):
        assert _resolve_route("express", None, None, None) == "studio"

    def test_empty_string_is_studio(self):
        assert _resolve_route("", None, None, None) == "studio"

    def test_none_route_is_studio(self):
        assert _resolve_route(None, None, None, None) == "studio"

    def test_unknown_route_falls_back_to_studio(self):
        assert _resolve_route("blorp", None, None, None) == "studio"


class TestLegacyRoleParam:
    """Legacy `role=` param from old callers."""

    def test_role_studio(self):
        assert _resolve_route(None, "studio", None, None) == "studio"

    def test_role_architect(self):
        assert _resolve_route(None, "architect", None, None) == "architect"

    def test_requested_route_beats_role(self):
        # requested_route wins when both provided
        assert _resolve_route("studio", "architect", None, None) == "studio"


class TestTaskTypeHint:
    """task_type only applies when no explicit route is given."""

    def test_analysis_bumps_to_two_pass(self):
        assert _resolve_route(None, None, "analysis", None) == "architect_then_studio"

    def test_planning_bumps_to_two_pass(self):
        assert _resolve_route(None, None, "planning", None) == "architect_then_studio"

    def test_structured_data_bumps(self):
        assert _resolve_route(None, None, "structured_data", None) == "architect_then_studio"

    def test_explain_bumps(self):
        assert _resolve_route(None, None, "explain", None) == "architect_then_studio"

    def test_recommend_bumps(self):
        assert _resolve_route(None, None, "recommend", None) == "architect_then_studio"

    def test_conversation_stays_studio(self):
        assert _resolve_route(None, None, "conversation", None) == "studio"

    def test_empty_task_type_stays_studio(self):
        assert _resolve_route(None, None, "", None) == "studio"

    def test_explicit_route_wins_over_complex_task(self):
        # "studio" was explicitly requested — don't override with task hint
        assert _resolve_route("studio", None, "analysis", None) == "studio"

    def test_explicit_architect_wins_over_task(self):
        assert _resolve_route("architect", None, "conversation", None) == "architect"

    def test_all_complex_task_types_covered(self):
        # Smoke-test that every complex task type triggers the bump
        for task in _COMPLEX_TASK_TYPES:
            result = _resolve_route(None, None, task, None)
            assert result == "architect_then_studio", f"task_type={task!r} should bump to two-pass"


class TestCaseInsensitivity:
    """Routes and task types should be case-insensitive."""

    def test_uppercase_studio(self):
        assert _resolve_route("STUDIO", None, None, None) == "studio"

    def test_mixed_case_architect(self):
        assert _resolve_route("Architect", None, None, None) == "architect"

    def test_uppercase_task_type(self):
        assert _resolve_route(None, None, "ANALYSIS", None) == "architect_then_studio"


class TestRouteAliasCompleteness:
    """Every value in _ROUTE_ALIASES should resolve to a valid orchestrator role."""

    VALID_ROLES = {"studio", "architect", "architect_then_studio"}

    def test_all_aliases_produce_valid_roles(self):
        for alias, expected_role in _ROUTE_ALIASES.items():
            assert expected_role in self.VALID_ROLES, \
                f"Alias {alias!r} → {expected_role!r} is not a valid orchestrator role"

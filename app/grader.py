"""Deterministic ticket triage grader with bounded score in [0.0, 1.0]."""
from __future__ import annotations

from typing import Any, Dict, List

from .models import TaskSpec


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _keyword_score(message: str, required_keywords: List[str]) -> float:
    if not required_keywords:
        return 1.0
    text = message.lower()
    hits = sum(1 for keyword in required_keywords if keyword.lower() in text)
    return hits / len(required_keywords)


def calculate_episode_score(trajectory: List[Dict[str, Any]], spec: TaskSpec) -> float:
    if not trajectory:
        return 0.0

    final = trajectory[-1]
    action = final.get("action", {})

    category_score = 1.0 if action.get("category") == spec.expected_category else 0.0
    priority_score = 1.0 if action.get("priority") == spec.expected_priority else 0.0
    department_score = 1.0 if action.get("department") == spec.expected_department else 0.0
    response_score = _keyword_score(str(action.get("response_message", "")), spec.required_keywords)

    expected_resolve = spec.expected_resolution == "resolved"
    expected_escalate = spec.expected_resolution == "escalated"
    resolution_score = 1.0 if (
        bool(action.get("resolve", False)) == expected_resolve
        and bool(action.get("escalate", False)) == expected_escalate
    ) else 0.0

    base_score = (
        0.30 * category_score
        + 0.20 * priority_score
        + 0.20 * department_score
        + 0.20 * response_score
        + 0.10 * resolution_score
    )

    return _clamp(round(base_score, 6))

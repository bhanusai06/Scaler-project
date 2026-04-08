"""Robust action parser used by environment and inference fallbacks."""
from __future__ import annotations

from typing import Any, Dict

from .models import AgentAction


def parse_action(payload: Dict[str, Any]) -> AgentAction:
    """Parse and sanitize raw action payload into AgentAction."""
    if "action" in payload and isinstance(payload["action"], dict):
        payload = payload["action"]

    normalized = {
        "category": str(payload.get("category", "other")).lower(),
        "priority": str(payload.get("priority", "medium")).lower(),
        "department": str(payload.get("department", "customer_success")).lower(),
        "response_message": str(payload.get("response_message", "Acknowledged. We are investigating this issue.")).strip(),
        "resolve": bool(payload.get("resolve", False)),
        "escalate": bool(payload.get("escalate", False)),
    }

    # Safe coercion into known enum domain.
    if normalized["category"] not in {"billing", "technical", "account", "abuse", "other"}:
        normalized["category"] = "other"
    if normalized["priority"] not in {"low", "medium", "high", "critical"}:
        normalized["priority"] = "medium"
    if normalized["department"] not in {"billing_ops", "tech_support", "trust_safety", "account_ops", "customer_success"}:
        normalized["department"] = "customer_success"

    if not normalized["response_message"]:
        normalized["response_message"] = "Acknowledged. We are investigating this issue."

    return AgentAction(**normalized)

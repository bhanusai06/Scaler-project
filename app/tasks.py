"""Task registry for a real-world customer support ticket workflow."""
from typing import List, Optional

from .models import TaskSpec


ALL_TASKS: List[TaskSpec] = [
    TaskSpec(
        task_id="ticket_triage",
        instance_id="TT-easy-01",
        difficulty="easy",
        max_steps=12,
        customer_message="I was charged twice for invoice #88921. Please refund the duplicate charge.",
        customer_tier="standard",
        urgency_hint="medium",
        expected_category="billing",
        expected_priority="medium",
        expected_department="billing_ops",
        expected_resolution="resolved",
        required_keywords=["refund", "invoice", "duplicate"],
    ),
    TaskSpec(
        task_id="ticket_triage",
        instance_id="TT-medium-01",
        difficulty="medium",
        max_steps=12,
        customer_message="Our team cannot login after SSO migration. We are blocked for release today.",
        customer_tier="pro",
        urgency_hint="high",
        expected_category="technical",
        expected_priority="high",
        expected_department="tech_support",
        expected_resolution="resolved",
        required_keywords=["login", "sso", "blocked"],
    ),
    TaskSpec(
        task_id="ticket_triage",
        instance_id="TT-hard-01",
        difficulty="hard",
        max_steps=12,
        customer_message="We detected suspicious password reset emails and unknown sessions from another country.",
        customer_tier="enterprise",
        urgency_hint="high",
        expected_category="account",
        expected_priority="critical",
        expected_department="account_ops",
        expected_resolution="escalated",
        required_keywords=["suspicious", "sessions", "password reset"],
    ),
    TaskSpec(
        task_id="ticket_triage",
        instance_id="TT-extreme-01",
        difficulty="extreme",
        max_steps=12,
        customer_message="Abusive transactions are bypassing controls and user reports indicate account takeover attempts.",
        customer_tier="enterprise",
        urgency_hint="high",
        expected_category="abuse",
        expected_priority="critical",
        expected_department="trust_safety",
        expected_resolution="escalated",
        required_keywords=["abusive", "takeover", "reports"],
    ),
]


def get_task(task_id: str, instance_id: str) -> Optional[TaskSpec]:
    for task in ALL_TASKS:
        if task.task_id == task_id and task.instance_id == instance_id:
            return task
    return None


def get_task_by_instance(instance_id: str) -> Optional[TaskSpec]:
    for task in ALL_TASKS:
        if task.instance_id == instance_id:
            return task
    return None

"""Pydantic models for a real-world customer support OpenEnv."""
from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, field_validator


Category = Literal["billing", "technical", "account", "abuse", "other"]
Priority = Literal["low", "medium", "high", "critical"]
Department = Literal["billing_ops", "tech_support", "trust_safety", "account_ops", "customer_success"]
Status = Literal["open", "in_progress", "resolved", "escalated"]


class TicketObservation(BaseModel):
    ticket_id: str
    task_id: str
    instance_id: str
    customer_message: str
    customer_tier: Literal["standard", "pro", "enterprise"]
    urgency_hint: Literal["low", "medium", "high"]
    step_count: int = Field(ge=0)
    status: Status
    previous_actions: List[Dict[str, Any]] = Field(default_factory=list)
    done: bool = False
    info: Dict[str, Any] = Field(default_factory=dict)


class AgentAction(BaseModel):
    category: Category
    priority: Priority
    department: Department
    response_message: str = Field(min_length=1, max_length=600)
    resolve: bool = False
    escalate: bool = False

    @field_validator("response_message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        text = value.strip()
        return text[:600]


class StepRequest(BaseModel):
    action: AgentAction


class StepResponse(BaseModel):
    observation: TicketObservation
    reward: float = Field(ge=0.0, le=1.0)
    done: bool
    info: Dict[str, Any] = Field(default_factory=dict)


class ResetResponse(BaseModel):
    observation: TicketObservation


class StateResponse(BaseModel):
    state: TicketObservation


class TaskSpec(BaseModel):
    task_id: str
    instance_id: str
    difficulty: Literal["easy", "medium", "hard", "extreme"]
    max_steps: int = Field(ge=1, le=50)
    customer_message: str
    customer_tier: Literal["standard", "pro", "enterprise"]
    urgency_hint: Literal["low", "medium", "high"]
    expected_category: Category
    expected_priority: Priority
    expected_department: Department
    expected_resolution: Literal["resolved", "escalated"]
    required_keywords: List[str] = Field(default_factory=list)

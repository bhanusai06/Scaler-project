"""Real-world customer support workflow environment (OpenEnv compatible)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from .grader import calculate_episode_score
from .models import AgentAction, TaskSpec, TicketObservation


@dataclass
class EpisodeState:
    spec: TaskSpec
    ticket_id: str
    step_count: int = 0
    status: str = "open"
    done: bool = False
    repeated_errors: int = 0
    delay_penalty_acc: float = 0.0
    total_reward: float = 0.0
    previously_correct: Dict[str, bool] = field(default_factory=lambda: {
        "category": False,
        "priority": False,
        "department": False,
    })
    trajectory: List[Dict[str, Any]] = field(default_factory=list)


class SupportTicketEnv:
    """Deterministic support ticket triage environment."""

    def __init__(self, spec: TaskSpec):
        self.spec = spec
        self.episode = self._new_episode(spec)

    def _new_episode(self, spec: TaskSpec) -> EpisodeState:
        seed_text = f"{spec.task_id}:{spec.instance_id}:{spec.customer_message}"
        ticket_id = hashlib.sha1(seed_text.encode("utf-8")).hexdigest()[:12]
        return EpisodeState(spec=spec, ticket_id=ticket_id)

    def reset(self) -> TicketObservation:
        self.episode = self._new_episode(self.spec)
        return self._observation(info={})

    def state(self) -> TicketObservation:
        return self._observation(info={})

    def step(self, action: AgentAction) -> Tuple[TicketObservation, float, bool, Dict[str, Any]]:
        ep = self.episode
        if ep.done:
            obs = self._observation(info={"error": "episode_already_done"})
            return obs, 0.0, True, {"error": "episode_already_done"}

        ep.step_count += 1
        if ep.status == "open":
            ep.status = "in_progress"

        errors: List[str] = []

        category_correct = action.category == ep.spec.expected_category
        priority_correct = action.priority == ep.spec.expected_priority
        department_correct = action.department == ep.spec.expected_department

        if not category_correct:
            errors.append("wrong_category")
        if not priority_correct:
            errors.append("wrong_priority")
        if not department_correct:
            errors.append("wrong_department")

        if ep.previously_correct["category"] and not category_correct:
            errors.append("category_reversed")
        if ep.previously_correct["priority"] and not priority_correct:
            errors.append("priority_reversed")
        if ep.previously_correct["department"] and not department_correct:
            errors.append("department_reversed")

        ep.previously_correct["category"] = ep.previously_correct["category"] or category_correct
        ep.previously_correct["priority"] = ep.previously_correct["priority"] or priority_correct
        ep.previously_correct["department"] = ep.previously_correct["department"] or department_correct

        repeated_errors = len(errors)
        ep.repeated_errors += repeated_errors

        if action.resolve and action.escalate:
            errors.append("resolve_and_escalate_conflict")
            repeated_errors += 1
            ep.repeated_errors += 1

        if action.resolve:
            ep.status = "resolved"
            ep.done = True
        elif action.escalate:
            ep.status = "escalated"
            ep.done = True
        elif ep.step_count >= ep.spec.max_steps:
            ep.done = True

        frame = {
            "step": ep.step_count,
            "status": ep.status,
            "action": action.model_dump(),
            "errors": list(errors),
        }
        ep.trajectory.append(frame)

        base_score = calculate_episode_score(ep.trajectory, ep.spec)
        action_cost = 0.02
        delay_penalty = 0.01 * float(ep.step_count)
        ep.delay_penalty_acc += delay_penalty
        consistency_penalty = 0.05 * float(repeated_errors)

        reward = base_score - action_cost - delay_penalty - consistency_penalty
        reward = max(0.0, min(1.0, float(reward)))
        ep.total_reward += reward

        info = {
            "base_score": round(base_score, 6),
            "action_cost": action_cost,
            "delay_penalty": round(delay_penalty, 6),
            "consistency_penalty": round(consistency_penalty, 6),
            "repeated_errors": repeated_errors,
            "errors": errors,
        }

        if ep.done:
            info["episode_score"] = calculate_episode_score(ep.trajectory, ep.spec)

        obs = self._observation(info=info)
        return obs, reward, ep.done, info

    def _observation(self, info: Dict[str, Any]) -> TicketObservation:
        ep = self.episode
        return TicketObservation(
            ticket_id=ep.ticket_id,
            task_id=ep.spec.task_id,
            instance_id=ep.spec.instance_id,
            customer_message=ep.spec.customer_message,
            customer_tier=ep.spec.customer_tier,
            urgency_hint=ep.spec.urgency_hint,
            step_count=ep.step_count,
            status=ep.status,
            previous_actions=[frame["action"] for frame in ep.trajectory[-5:]],
            done=ep.done,
            info=info,
        )

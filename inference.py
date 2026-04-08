"""Root inference entrypoint with strict START/STEP/END logging."""
from __future__ import annotations

import asyncio
import json
import os
import random
import statistics
import sys
from typing import Any, Dict, List

import httpx
from openai import OpenAI


random.seed(42)

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.environ.get("HF_TOKEN")
LOCAL_IMAGE_NAME = os.environ.get("LOCAL_IMAGE_NAME", None)
ENV_BASE_URL = os.environ.get("ENV_BASE_URL", "http://localhost:7860")

MAX_EPISODES = 10
MAX_STEPS_PER_EP = 50


def log_start(task_id: str, instance_id: str) -> None:
    print(f"[START] {json.dumps({'task_id': task_id, 'instance_id': instance_id})}", flush=True)


def log_step(step: int, action: Any, observation: Any, reward: float, done: bool) -> None:
    print(
        f"[STEP]  {json.dumps({'step': int(step), 'action': str(action), 'observation': str(observation), 'reward': float(reward), 'done': bool(done)})}",
        flush=True,
    )


def log_end(task_id: str, instance_id: str, total_reward: float, steps: int, success: bool) -> None:
    print(
        f"[END]   {json.dumps({'task_id': task_id, 'instance_id': instance_id, 'total_reward': float(total_reward), 'steps': int(steps), 'success': bool(success)})}",
        flush=True,
    )


client = OpenAI(api_key=HF_TOKEN or "dummy", base_url=API_BASE_URL, timeout=30.0)


SYSTEM_PROMPT = (
    "You are a customer-support ticket triage controller. "
    "Output ONLY compact JSON with keys: category, priority, department, response_message, resolve, escalate."
)


def deterministic_fallback_action(obs: Dict[str, Any]) -> Dict[str, Any]:
    text = str(obs.get("customer_message", "")).lower()
    urgency = str(obs.get("urgency_hint", "medium"))

    if "refund" in text or "invoice" in text or "charged" in text:
        category = "billing"
        department = "billing_ops"
    elif "login" in text or "sso" in text or "error" in text:
        category = "technical"
        department = "tech_support"
    elif "abusive" in text or "takeover" in text or "fraud" in text:
        category = "abuse"
        department = "trust_safety"
    elif "password" in text or "session" in text:
        category = "account"
        department = "account_ops"
    else:
        category = "other"
        department = "customer_success"

    priority = "critical" if urgency == "high" else ("high" if urgency == "medium" else "medium")
    escalate = category in {"abuse", "account"} and priority in {"high", "critical"}
    resolve = not escalate

    return {
        "category": category,
        "priority": priority,
        "department": department,
        "response_message": "Acknowledged. We are routing this ticket to the responsible team and will provide an update shortly.",
        "resolve": bool(resolve),
        "escalate": bool(escalate),
    }


def llm_action(obs: Dict[str, Any]) -> Dict[str, Any]:
    fallback = deterministic_fallback_action(obs)
    if not HF_TOKEN:
        return fallback

    prompt = (
        f"task_id={obs.get('task_id')} instance_id={obs.get('instance_id')} "
        f"urgency={obs.get('urgency_hint')} tier={obs.get('customer_tier')} "
        f"message={obs.get('customer_message')}"
    )

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=256,
        )
        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return fallback
        merged = fallback.copy()
        merged.update(parsed)
        return merged
    except Exception:
        return fallback


def run_episode_local(task_id: str, instance_id: str, already_started: bool = False) -> float:
    from app.env import SupportTicketEnv
    from app.tasks import get_task
    from app.parser import parse_action

    spec = get_task(task_id, instance_id)
    if spec is None:
        if not already_started:
            log_start(task_id, instance_id)
        log_end(task_id, instance_id, 0.0, 0, False)
        return 0.0

    env = SupportTicketEnv(spec)
    obs = env.reset().model_dump()
    if not already_started:
        log_start(task_id, instance_id)

    step = 0
    total_reward = 0.0
    done = False
    final_info: Dict[str, Any] = {}

    while not done and step < MAX_STEPS_PER_EP:
        step += 1
        action = llm_action(obs)
        safe_action = parse_action(action)
        obs_model, reward, done, info = env.step(safe_action)
        obs = obs_model.model_dump()
        final_info = info
        reward = max(0.0, min(1.0, float(reward)))
        total_reward += reward
        log_step(step, action, obs, reward, done)

    avg_reward = total_reward / step if step > 0 else 0.0
    if isinstance(final_info, dict) and final_info.get("episode_score") is not None:
        avg_reward = float(final_info["episode_score"])
    success = avg_reward >= 0.5
    log_end(task_id, instance_id, round(avg_reward, 6), step, success)
    return avg_reward


async def run_episode(http: httpx.AsyncClient, task_id: str, instance_id: str) -> float:
    log_start(task_id, instance_id)
    try:
        reset_resp = await http.post(f"{ENV_BASE_URL}/reset?task_id={task_id}&instance_id={instance_id}")
        if reset_resp.status_code != 200:
            return run_episode_local(task_id, instance_id, already_started=True)
        obs = reset_resp.json().get("observation", {})
    except Exception:
        return run_episode_local(task_id, instance_id, already_started=True)

    step = 0
    done = False
    total_reward = 0.0
    final_info: Dict[str, Any] = {}

    while not done and step < MAX_STEPS_PER_EP:
        step += 1
        action = llm_action(obs)
        try:
            response = await http.post(
                f"{ENV_BASE_URL}/step?task_id={task_id}&instance_id={instance_id}",
                json={"action": action},
            )
            if response.status_code != 200:
                log_step(step, action, obs, 0.0, True)
                break
            payload = response.json()
        except Exception:
            log_step(step, action, obs, 0.0, True)
            break

        reward = max(0.0, min(1.0, float(payload.get("reward", 0.0))))
        done = bool(payload.get("done", False))
        obs = payload.get("observation", obs)
        final_info = payload.get("info", {}) if isinstance(payload, dict) else {}
        total_reward += reward
        log_step(step, action, obs, reward, done)

    avg_reward = total_reward / step if step > 0 else 0.0
    if isinstance(final_info, dict) and final_info.get("episode_score") is not None:
        avg_reward = float(final_info["episode_score"])
    success = avg_reward >= 0.5
    log_end(task_id, instance_id, round(avg_reward, 6), step, success)
    return avg_reward


async def main() -> None:
    try:
        async with httpx.AsyncClient(timeout=20.0) as probe:
            tasks = (await probe.get(f"{ENV_BASE_URL}/tasks")).json()
    except Exception:
        from app.tasks import ALL_TASKS

        tasks = [{"task_id": t.task_id, "instance_id": t.instance_id} for t in ALL_TASKS]

    tasks = tasks[:MAX_EPISODES]

    scores: List[float] = []
    async with httpx.AsyncClient(timeout=60.0) as http:
        for task in tasks:
            scores.append(await run_episode(http, task["task_id"], task["instance_id"]))

    valid = [v for v in scores if isinstance(v, float)]
    avg = statistics.mean(valid) if valid else 0.0
    print(f"[SUMMARY] episodes={len(valid)} avg_score={avg:.4f}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    asyncio.run(main())

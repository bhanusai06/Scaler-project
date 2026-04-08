"""FastAPI OpenEnv server for customer-support ticket triage."""
from __future__ import annotations
import os
import logging
from collections import OrderedDict
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .env import SupportTicketEnv
from .grader import calculate_episode_score
from .parser import parse_action
from .models import (
        TicketObservation,
        StepRequest,
        StepResponse,
        ResetResponse,
        StateResponse,
)
from .tasks import ALL_TASKS, get_task

logger = logging.getLogger(__name__)
COMPETITION_MODE = os.environ.get("COMPETITION_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Ticket Triage OpenEnv",
    version="1.0.0",
    description="Deterministic customer-support ticket triage environment.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if COMPETITION_MODE else ["http://localhost:7860", "http://127.0.0.1:7860"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request body size limit: 512 KB
@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and int(cl) > 512 * 1024:
        task_id = request.query_params.get("task_id", "ticket_triage")
        instance_id = request.query_params.get("instance_id", "TT-easy-01")

        if request.url.path == "/step":
            obs = _error_observation(task_id, instance_id, "request_body_too_large")
            payload = StepResponse(
                observation=obs,
                reward=0.0,
                done=True,
                info={"error": "request_body_too_large"},
            )
            return JSONResponse(status_code=200 if COMPETITION_MODE else 413, content=payload.model_dump())

        if request.url.path == "/reset":
            obs = _error_observation(task_id, instance_id, "request_body_too_large")
            payload = ResetResponse(observation=obs)
            return JSONResponse(status_code=200 if COMPETITION_MODE else 413, content=payload.model_dump())

        return JSONResponse(status_code=200 if COMPETITION_MODE else 413, content={"error": "request_body_too_large"})
    return await call_next(request)

# ── Static files ──────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ── Session store (LRU, max 10K sessions) ─────────────────────────────────────
class _LRU:
    def __init__(self, cap: int):
        self._d: OrderedDict = OrderedDict()
        self._cap = cap
    def get(self, k):
        if k not in self._d: return None
        self._d.move_to_end(k); return self._d[k]
    def set(self, k, v):
        if k in self._d: self._d.move_to_end(k)
        self._d[k] = v
        if len(self._d) > self._cap: self._d.popitem(last=False)
    def __contains__(self, k): return k in self._d

_env_store: _LRU = _LRU(10_000)


def _error_observation(task_id: str, instance_id: str, error: str) -> TicketObservation:
    return TicketObservation(
        ticket_id="invalid",
        step_count=0,
        status="open",
        task_id=task_id,
        instance_id=instance_id,
        customer_message="",
        customer_tier="standard",
        urgency_hint="low",
        previous_actions=[],
        done=True,
        info={"error": error},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    task_id = request.query_params.get("task_id", "ticket_triage")
    instance_id = request.query_params.get("instance_id", "TT-easy-01")

    if request.url.path == "/step":
        obs = _error_observation(task_id, instance_id, "validation_error")
        payload = StepResponse(
            observation=obs,
            reward=0.0,
            done=True,
            info={"error": "validation_error", "details": exc.errors()},
        )
        return JSONResponse(status_code=200 if COMPETITION_MODE else 422, content=payload.model_dump())

    if request.url.path == "/reset":
        obs = _error_observation(task_id, instance_id, "validation_error")
        payload = ResetResponse(observation=obs)
        return JSONResponse(status_code=200 if COMPETITION_MODE else 422, content=payload.model_dump())

    return JSONResponse(
        status_code=200 if COMPETITION_MODE else 422,
        content={"error": "validation_error", "details": exc.errors()},
    )


def _get_env(task_id: str, instance_id: str) -> Optional[SupportTicketEnv]:
    """Return existing env OR auto-create one (never crashes)."""
    key = f"{task_id}/{instance_id}"
    env = _env_store.get(key)
    if env is None:
        spec = get_task(task_id, instance_id)
        if spec is None:
            return None
        env = SupportTicketEnv(spec)
        _env_store.set(key, env)
    return env


# ═══════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/health", status_code=200)
async def health():
    return {"status": "ok", "service": "ticket-triage-openenv", "version": "1.0.0", "competition_mode": COMPETITION_MODE}


@app.get("/", status_code=200)
async def health_root():
    return await health()


@app.post("/reset", response_model=ResetResponse)
async def reset(
    task_id:     str = Query(default="ticket_triage"),
    instance_id: str = Query(default="TT-easy-01"),
):
    spec = get_task(task_id, instance_id)
    if spec is None:
        if not COMPETITION_MODE:
            raise HTTPException(status_code=404, detail="unknown_task_or_instance")
        obs = _error_observation(task_id, instance_id, "unknown_task_or_instance")
        return ResetResponse(observation=obs)

    env = SupportTicketEnv(spec)
    key = f"{task_id}/{instance_id}"
    _env_store.set(key, env)

    obs = env.reset()
    return ResetResponse(observation=obs)


@app.post("/step", response_model=StepResponse)
async def step(
    body:        StepRequest,
    task_id:     str = Query(default="ticket_triage"),
    instance_id: str = Query(default="TT-easy-01"),
):
    env = _get_env(task_id, instance_id)
    if env is None:
        if not COMPETITION_MODE:
            raise HTTPException(status_code=404, detail="unknown_task_or_instance")
        obs = _error_observation(task_id, instance_id, "unknown_task_or_instance")
        return StepResponse(
            observation=obs,
            reward=0.0,
            done=True,
            info={"error": "unknown_task_or_instance"},
        )

    safe_action = parse_action(body.model_dump())
    obs, reward, done, info = env.step(safe_action)

    # Attach episodic score when done
    if done:
        episode_score = calculate_episode_score(env.episode.trajectory, env.spec)
        info["episode_score"] = episode_score

    return StepResponse(observation=obs, reward=reward, done=done, info=info)


@app.get("/state", response_model=StateResponse)
async def get_state(
    task_id:     str = Query(default="ticket_triage"),
    instance_id: str = Query(default="TT-easy-01"),
):
    env = _get_env(task_id, instance_id)
    if env is None:
        if not COMPETITION_MODE:
            raise HTTPException(status_code=404, detail="unknown_task_or_instance")
        return StateResponse(state=_error_observation(task_id, instance_id, "unknown_task_or_instance"))
    return StateResponse(state=env.state())


@app.get("/tasks")
async def list_tasks():
    return [
        {
            "task_id":      t.task_id,
            "instance_id":  t.instance_id,
            "difficulty":   t.difficulty,
            "max_steps":    t.max_steps,
            "objective": f"Classify as {t.expected_category}, route to {t.expected_department}, set {t.expected_priority} priority",
        }
        for t in ALL_TASKS
    ]


@app.get("/debug")
async def debug(
    task_id:     str = Query(default="ticket_triage"),
    instance_id: str = Query(default="TT-easy-01"),
):
    env = _get_env(task_id, instance_id)
    if env is None:
        if not COMPETITION_MODE:
            raise HTTPException(status_code=404, detail="unknown_task_or_instance")
        return {
            "task_id": task_id,
            "instance_id": instance_id,
            "step_count": 0,
            "is_terminal": True,
            "total_thrust": 0.0,
            "steps_in_band": None,
            "best_distance": None,
            "trajectory_length": 0,
            "error": "unknown_task_or_instance",
        }

    ep  = env.episode
    return {
        "task_id":      env.spec.task_id,
        "instance_id":  env.spec.instance_id,
        "step_count":   ep.step_count,
        "is_terminal":  ep.done,
        "status": ep.status,
        "repeated_errors": ep.repeated_errors,
        "delay_penalty_acc": round(ep.delay_penalty_acc, 6),
        "trajectory_length": len(ep.trajectory),
        "ticket_id": ep.ticket_id,
        "current_category": ep.category,
        "current_priority": ep.priority,
        "current_department": ep.department,
    }


@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    """Serve the debug console UI."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    try:
        with open(index_path, encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="UI not found.")

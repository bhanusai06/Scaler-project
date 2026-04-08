# Ticket Triage OpenEnv

Deterministic OpenEnv for real-world customer support ticket triage and routing.

## Use Case

The environment simulates support operations where an agent must:

1. classify incoming tickets,
2. assign priority,
3. route to correct department,
4. provide a response,
5. resolve or escalate appropriately.

## Observation Space

Observation returned by `/reset`, `/step`, and `/state`:

1. `ticket_id` string
2. `task_id` string
3. `instance_id` string
4. `customer_message` string
5. `customer_tier` in `{standard, pro, enterprise}`
6. `urgency_hint` in `{low, medium, high}`
7. `step_count` integer
8. `status` in `{open, in_progress, resolved, escalated}`
9. `previous_actions` array
10. `done` boolean
11. `info` object

## Action Space

Step request body:

```json
{
	"action": {
		"category": "billing|technical|account|abuse|other",
		"priority": "low|medium|high|critical",
		"department": "billing_ops|tech_support|trust_safety|account_ops|customer_success",
		"response_message": "string",
		"resolve": false,
		"escalate": false
	}
}
```

## Reward Design

Reward is always clamped to `[0.0, 1.0]`.

Base score components:

1. category match: 0.30
2. priority match: 0.20
3. department match: 0.20
4. response quality keyword coverage: 0.20
5. resolution correctness: 0.10

Penalties:

1. action cost per step
2. delay penalty proportional to step_count
3. consistency penalty for repeated/reversed errors

## API

1. `GET /health`
2. `POST /reset?task_id=<id>&instance_id=<id>`
3. `POST /step?task_id=<id>&instance_id=<id>`
4. `GET /state?task_id=<id>&instance_id=<id>`

Compatibility endpoints:

1. `GET /`
2. `GET /tasks`
3. `GET /debug`

## Environment Variables

1. `API_BASE_URL` default `https://api.openai.com/v1`
2. `MODEL_NAME` default `gpt-4o-mini`
3. `HF_TOKEN` no default
4. `LOCAL_IMAGE_NAME` default `None`
5. `ENV_BASE_URL` default `http://localhost:7860`
6. `COMPETITION_MODE` default `true`

## Hugging Face API Link

This project uses OpenAI-compatible client calls. To run against Hugging Face Router, set:

1. `API_BASE_URL=https://router.huggingface.co/v1`
2. `HF_TOKEN=<your_huggingface_token>`
3. `MODEL_NAME=<huggingface_model_id>`

Example (PowerShell):

```powershell
$env:API_BASE_URL="https://router.huggingface.co/v1"
$env:HF_TOKEN="hf_xxx"
$env:MODEL_NAME="openai/gpt-oss-120b"
python inference.py
```

## Local Setup

```powershell
pip install -r requirements.txt
```

Start API:

```powershell
python app.py
```

Run inference:

```powershell
python inference.py
```

## Docker

Build:

```powershell
docker build -t ticket-triage-openenv .
```

Run API:

```powershell
docker run -p 7860:7860 ticket-triage-openenv
```

Run inference in container:

```powershell
docker run --rm ticket-triage-openenv python inference.py
```

## Validation

Run full validation:

```powershell
python validator.py
```

Validate OpenEnv manifest only:

```powershell
python validate_openenv_yaml.py
```

Verify log format:

```powershell
python verify_log_format.py output.log
```

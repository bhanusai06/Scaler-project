FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Environment defaults (safe; HF_TOKEN injected at runtime — NEVER set here)
ENV API_BASE_URL="https://api.openai.com/v1"
ENV MODEL_NAME="gpt-4o-mini"
ENV ENV_BASE_URL="http://localhost:7860"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED="1"

EXPOSE 7860

# Start the FastAPI server (matches openenv.yaml server_cmd)
CMD ["python", "app.py"]

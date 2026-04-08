FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Hugging Face Space used as the LLM backend
ENV HF_SPACE_URL="https://huggingface.co/spaces/huggingface-projects/llama-2-7b-chat"
# HF Router API endpoint for OpenAI-compatible inference
ENV API_BASE_URL="https://router.huggingface.co/v1"
# Model served by the llama-2-7b-chat Space
ENV MODEL_NAME="meta-llama/Llama-2-7b-chat-hf"
ENV ENV_BASE_URL="http://localhost:7860"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED="1"

EXPOSE 7860

# Start the FastAPI server (matches openenv.yaml server_cmd)
CMD ["python", "app.py"]

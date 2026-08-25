FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# OpenCV runtime libs + curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch keeps the image small (~200MB vs 2GB+ CUDA)
COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir torch torchvision tqdm \
    --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# App code + trained model artifact
COPY app ./app
COPY runs ./runs

# Persist DB + uploads on a mounted volume at /app/data
ENV DATABASE_URL=sqlite+aiosqlite:////app/data/fortexa.db \
    UPLOAD_DIR=/app/data/uploads \
    RUNS_DIR=/app/runs \
    APP_ENV=production

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD curl -sf http://localhost:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

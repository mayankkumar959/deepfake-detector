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
    && pip install --no-cache-dir -r requirements.txt -r requirements-ml.txt

# App code + trained model artifact
COPY app ./app
ARG MODEL_DIR=runs/active-image-video-20261018
COPY ${MODEL_DIR}/ ./runs/active/
# Railway's upload gateway cannot accept the full model in the source archive.
# Small source-only deployments fetch the identical, commit-pinned LFS artifact.
# Local builds can still copy the existing weights without downloading them.
ARG MODEL_WEIGHTS_URL=https://media.githubusercontent.com/media/mayankkumar959/deepfake-detector/main/backend/runs/active-image-video-20261018/model.safetensors
ARG MODEL_WEIGHTS_SHA256=df206fd941448042737719822ca25808ace82df65e3f1ad131d1bbcd8ac34af3
RUN if [ ! -f ./runs/active/model.safetensors ]; then \
      curl --fail --location --retry 3 "$MODEL_WEIGHTS_URL" \
        --output ./runs/active/model.safetensors; \
    fi \
    && echo "$MODEL_WEIGHTS_SHA256  ./runs/active/model.safetensors" | sha256sum --check --strict
RUN mkdir -p /app/data/uploads

# Supply Neon DATABASE_URL via hosting secrets; persist media at /app/data.
ENV UPLOAD_DIR=/app/data/uploads \
    RUNS_DIR=/app/runs/active \
    DETECTOR_TASK=ai-image \
    APP_ENV=production

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD curl -sf http://localhost:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

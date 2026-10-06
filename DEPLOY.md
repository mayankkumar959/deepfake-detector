# Fortexa deployment

The application is experimental: deployment does not establish detector accuracy.
Read GENERAL_AI_STATUS.md before submission or publication. Supply the general
locally trained SigLIP artifacts verified by setup-general-ai.ps1 before building.
Upstream downloads cannot restore the local trained head.

## Local Docker

From the project root, set a persistent random secret in your shell or root
`.env`. Never commit that file or use the example placeholder.
Also supply DATABASE_URL with your Neon connection string in that root .env or
shell. backend/.env is read by local Python, not automatically by Docker Compose.

```powershell
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
docker compose config --quiet
docker compose up --build
```

Frontend: http://localhost:3000. API: http://localhost:8000/api/health.
The frontend uses same-origin `/api` requests proxied by nginx to the backend.
Scan records and JSONB reports are stored in Neon PostgreSQL. Uploads are stored
on the named `fortexa_data` volume. Keep the secret stable across restarts so
signed media URLs remain valid. Removing the volume removes uploaded files;
do not run volume-deletion commands casually.

Docker execution has not been tested here because Docker is unavailable.

## Separate hosted frontend/backend

The repository includes render.yaml for a Docker backend and frontend/vercel.json
for SPA routes. Configure paths relative to the repository root:

- Backend Dockerfile: backend/Dockerfile; Docker context: backend.
- Backend SECRET_KEY: a persistent random value of at least 32 characters.
- Backend DATABASE_URL: the Neon PostgreSQL connection string, supplied as a secret.
- Backend FRONTEND_ORIGIN: the exact deployed frontend origin.
- Frontend root: frontend; build: npm run build; output: dist.
- Frontend VITE_API_URL: the deployed backend URL ending in /api, set before build.

Check backend /api/health, then uploads, private history, media and deletion in
an actual browser. Configure persistent storage at /app/data for uploads;
without persistent media storage files can be lost even while Neon keeps records.
Select resources based on measured PyTorch/video memory usage, not an assumed
free-tier capacity. No hosted deployment has been performed by this task.

Before a Docker build, choose the evaluated checkpoint directory explicitly:

```powershell
$env:FORTEXA_MODEL_DIR = 'runs/general-ai-trained-indoor-20261005'
docker compose up --build
```

The directory must contain model.safetensors, config.json,
preprocessor_config.json and model_meta.json inside backend. Compose defaults to
the trained indoor model; Docker copies it to /app/runs/active matching RUNS_DIR.
Hosted builds need these binary artifacts supplied in their build context too.
The active trained weight uses Git LFS. Ensure git lfs pull completes before a
Docker build: a small LFS pointer is not a usable model. Inactive weights and raw
training data are not included in the current source tree.

## Neon database

Local backend/.env holds the actual DSN and is ignored by Git. Never paste it into
source, Dockerfile, Blueprint YAML or logs. Rotate any credential shared in chat.
The URL is normalized to postgresql+psycopg without dropping sslmode or
channel_binding. Connections use pre-ping, a bounded pool and no automatic
prepared statements for pooler compatibility. Query parameters are hidden in logs.
Startup creates missing app tables without dropping existing data. Reports use
native JSONB objects; older string-encoded reports remain readable. No historical
SQLite scans are imported or deleted as part of this switch.
Checks: python verify_database.py, python verify_neon.py --live. The live check
verifies client TLS, upload/inference, JSONB storage, private access, history and
deletion, then removes only its own random test records.

# Fortexa deployment

The application is experimental: deployment does not establish detector accuracy.
Read GENERAL_AI_STATUS.md before submission or publication. Supply the general
locally trained SigLIP artifacts verified by setup-general-ai.ps1 before building.
Upstream downloads cannot restore the local trained head.

## Local Docker

From the project root, set a persistent random secret in your shell or root
`.env`. Never commit that file or use the example placeholder.

```powershell
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
docker compose config --quiet
docker compose up --build
```

Frontend: http://localhost:3000. API: http://localhost:8000/api/health.
The frontend uses same-origin `/api` requests proxied by nginx to the backend.
SQLite and uploads are stored on the named `fortexa_data` volume. Keep the secret
stable across restarts so signed media URLs remain valid. Removing the volume
removes persisted data; do not run volume-deletion commands casually.

Docker execution has not been tested here because Docker is unavailable.

## Separate hosted frontend/backend

The repository includes render.yaml for a Docker backend and frontend/vercel.json
for SPA routes. Configure paths relative to the repository root:

- Backend Dockerfile: backend/Dockerfile; Docker context: backend.
- Backend SECRET_KEY: a persistent random value of at least 32 characters.
- Backend FRONTEND_ORIGIN: the exact deployed frontend origin.
- Frontend root: frontend; build: npm run build; output: dist.
- Frontend VITE_API_URL: the deployed backend URL ending in /api, set before build.

Check backend /api/health, then uploads, private history, media and deletion in
an actual browser. Configure persistent storage at /app/data for database and
uploads; without persistent storage these can be lost on service replacement.
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

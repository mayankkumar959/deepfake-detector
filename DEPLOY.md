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
free-tier capacity. See the verified demo deployment below.

Before a Docker build, choose the evaluated package directory explicitly. The v3
image + video package is assembled by backend/package_active.py:

```powershell
python backend/package_active.py               # writes backend/runs/active-image-video-20261018
python backend/finalize_deployment.py          # updates Dockerfile URL/SHA + compose default
$env:FORTEXA_MODEL_DIR = 'runs/active-image-video-20261018'
docker compose up --build
```

The directory must contain model.safetensors, config.json,
preprocessor_config.json, model_meta.json, video_head.joblib and video_meta.json
inside backend. The same directory is mounted as RUNS_DIR; the image detector
reuses its frozen SigLIP tower for the video head, so no second 350 MB encoder is
needed. When model.safetensors is absent from the build context, the Dockerfile
downloads the commit-pinned artifact from GitHub LFS and verifies its SHA256.
Ensure git lfs push/pull completes before a Docker build: a small LFS pointer is
not a usable model. Never mix video_head.joblib with an unrelated image model:
both v2 and v3 video heads were trained on the base SigLIP tower, and the v2
image artifact's vision tensors were verified byte-identical to
runs/general-ai-siglip/model.safetensors.

### Activate locally (college demo, no hosting)

```powershell
python backend/package_active.py
powershell -ExecutionPolicy Bypass -File setup-general-ai.ps1
```

Then change only RUNS_DIR in backend/.env (keep DETECTOR_TASK=ai-image):

```
RUNS_DIR=./runs/active-image-video-20261018
```

Restart the backend so Settings is re-read, then check
http://localhost:8000/api/health. `detection_engine.status` must be
ml-ai-image-classifier and `video_detection_engine.status` must be
ml-ai-video-classifier. A wrong path or checksum makes the image detector
silently return 0.5/inconclusive instead of an explicit error, so never skip
this check. Smoke-test one real and one fake clip from
backend/data/demo-samples (expected outcomes are listed in its README.txt), then
open a scan in the browser and confirm the timeline, warnings and report JSON.
The scripted version of these smoke tests is
`python backend/verify_package_demo.py --runs runs/active-image-video-20261018`
(disposable database; uploads every demo sample through the real API and prints
a verdict table).
Rollback is one line: set RUNS_DIR back to
./runs/general-ai-trained-indoor-20261005 and restart.

## Video analysis in the deployed app

- The timeline uses up to 16 evenly spaced frames scored by the image model.
- The overall video verdict uses the trained temporal head from
  video_head.joblib: six frames from the centred 2-second window, 8% border
  crop, 224x224, frozen SigLIP mean/std/absolute-delta plus source-agnostic
  texture/temporal statistics. video_meta.json pins the head SHA256, feature
  width and selected texture flag.
- If video_head.joblib/video_meta.json are absent or the clip cannot be sampled
  (too short, blank), the app falls back to the per-frame image-model mean and
  says so in the report warnings. It never silently substitutes an untrained
  score.
- Visual only: audio and audio/video synchronisation are not assessed.
- /api/health reports both detection_engine and video_detection_engine.

## Verified demo deployment — 2026-10-06

- Website: https://fortexa-ai-demo.vercel.app
- API health: https://fortexa-api-production.up.railway.app/api/health
- Vercel project: fortexa-ai-demo, existing free Hobby workspace.
- Railway project/service: fortexa-demo / fortexa-api, existing Limited Trial.
- Neon metadata/report database; Railway 500 MB volume mounted at /app/data.
- No paid upgrade or new hosted database was purchased. Runtime and volume usage
  consume the existing trial credit; this is not permanent free hosting.

Verified against public HTTPS endpoints: production health and Neon connection,
real/AI fixture inference, private history and signed media, owned scan deletion,
and a four-frame synthetic video with thumbnail. An anonymous browser verified
upload/result rendering, both classification scores, report JSON download,
history and 390px mobile layout without horizontal overflow. Test scans were
deleted. These integration fixtures are not an accuracy benchmark or a load test.
Measured cloud memory after these checks was approximately 423 MB against the
1 GB trial limit; larger media and simultaneous scans can use more memory.

Railway credentials are hosting secrets, not source files. FRONTEND_ORIGIN is the
exact website origin above; frontend VITE_API_URL is the API origin ending /api.
Vercel's GitHub build root is frontend, command npm run build, output dist.
The backend uses CLI source uploads, not automatic GitHub deploys.

For a backend update from this repository, run:

```powershell
.\deploy-railway.ps1 -StageOnly  # inspect packaging without deploying
.\deploy-railway.ps1            # consumes trial credits when deployed
railway deployment list --service fortexa-api --json
railway metrics --service fortexa-api --memory
railway usage --workspace ad0c3d93-059e-461a-b92a-72b460d7e4b6
```

The helper excludes binary weights and secrets to stay below the source-upload
size limit. It copies current contents of tracked application files; add new
application files to Git's index before deploying. Temporary source folders are
retained for inspection, and contain no credentials or original model binaries.
If the evaluated model changes, update the Dockerfile's pinned download URL and
SHA256 together; never silently fall back to an upstream classifier head.

### Image + video v3 update (weights via GitHub LFS)

```powershell
python backend/package_active.py
python backend/finalize_deployment.py   # rewrites URL/SHA, compose default, .gitattributes
git add backend/runs/active-image-video-20261018
git add -f backend/runs/active-image-video-20261018/model.safetensors
git commit -m "Deploy image+video v3 package"
git push origin main
git lfs ls-files                        # model.safetensors must not be a pointer
.\deploy-railway.ps1 -StageOnly         # packaging inspection, no credits spent
.\deploy-railway.ps1                    # uploads source; Docker pulls the LFS weight
```

The Dockerfile only downloads the weight after the LFS push to main succeeds;
the commit-pinned `media.githubusercontent.com` URL does not work before that.
Vercel rebuilds the frontend from the same push. The previous
`runs/general-ai-trained-indoor-20261005` folder stays in the repository as the
rollback artifact; the deployment default moves to the v3 package.

Idle sleeping is requested to save trial credits, but cold starts can delay the
first request and background/database traffic can prevent sleeping. Do not
promise a fixed lifetime for $5 of credits. Open and test a small scan several
minutes before the demonstration, and check the remaining trial balance.

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

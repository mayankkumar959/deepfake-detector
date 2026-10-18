# Fortexa — AI-generated image and video analysis

React/Vite, FastAPI, offline SigLIP classification, private browser history and downloadable reports. Compression preserves origin labels for both real and AI images. No face is required. Videos use a trained visual temporal head on six centred frames plus a per-frame image timeline; audio is not analysed.

Model: the image+video v3 package (backend/runs/active-image-video-20261018) is the deployment default (Docker MODEL_DIR, Railway) and can be activated locally by switching RUNS_DIR in backend/.env; the previous model (backend/runs/general-ai-trained-indoor-20261005) remains the rollback artifact. See DEPLOY.md, GENERAL_AI_STATUS.md, IMAGE_TRAINING.md and VIDEO_DETECTOR.md for measured results and limitations. Experimental research app, not production-certified authenticity detection.

## Run

The normal application now uses Neon PostgreSQL. Put DATABASE_URL in ignored
backend/.env locally, or in backend-hosting secrets. Plain postgresql:// connection
strings automatically use psycopg; SSL/channel-binding parameters are preserved.
Production requires PostgreSQL. SQLite remains available for isolated tests only.
Old SQLite scans are not imported. Uploaded media still needs persistent backend
storage; Neon stores records and JSONB reports, not image/video files.

From deepfake/frontend:

```powershell
npm install
npm run check:startup
npm run dev
```

Open http://localhost:5173. The launcher also starts API port 8000. Ctrl+C stops both. Set FORTEXA_PYTHON if needed. Install Python dependencies from project root:

```powershell
python -m pip install -r backend/requirements.txt -r backend/requirements-ml.txt
```

Include the active trained model folder when submitting. setup-general-ai.ps1 verifies checksums. Upstream downloads cannot restore the local trained head.

## Checks and scope

From backend run python verify_general.py; CAMERA_REGRESSION_IMAGE enables a known-camera-photo test. Disposable test storage only.
Database checks: python verify_database.py (offline), python verify_neon.py --live
(explicit live PostgreSQL check; creates/deletes only its own random test session).
Install test dependencies first: python -m pip install -r requirements-dev.txt.
From frontend run npm run build, npm run verify:ui, npm run check:startup.
Browser checks: npm run serve with APP_ENV=test and disposable DATABASE_URL/UPLOAD_DIR, then npm run verify:browser.
Historical verify_product.py checks the old facial pipeline, NOT this detector.

backend/train_general_head.py trains a new frozen-encoder head with deduplication, grouped splits and both-class JPEG augmentation; it refuses to overwrite a candidate. Small study: 362 originals, 34/41 test decisions correct. Not broad deployment accuracy. Raw datasets and old facial ZIPs are unnecessary for inference.
Missing weights, blank and under-224px inputs are inconclusive. Generic Photoshop detection and audio/lip-sync analysis are unsupported; video uses a small uncalibrated visual temporal benchmark. See GENERAL_AI_STATUS.md, VIDEO_DETECTOR.md and SUBMISSION_CHECKLIST.md before submission.

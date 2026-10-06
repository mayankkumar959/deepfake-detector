# Product status — 2026-10-05

## Scope superseded: see GENERAL_AI_STATUS.md for current active model

The following face-model evidence is historical. AI-image mode now uses a locally
trained SigLIP head and does not inherit the face-model accuracy figures.

## Previous face-product implementation

Private browser-session scan history, owner-only reports/deletion, signed media
URLs, downloadable reports, corrected video timelines, upload limits and
corrupt-image validation, periodic retention, safe startup and production-secret
checks. Images/videos classify the largest detected face; no-face or unavailable
model inputs are inconclusive. Diagnostics do not determine the model score.
Face overlays do not localize manipulated pixels. Reports snapshot model/evaluation
metadata, and the scanner exposes held-out dataset metrics separately from scores.

The active checkpoint is backend/runs/candidate-dff-finetuned-20261005.
Local .env, default settings, example configuration and Docker build defaults
point to it. Only this selected checkpoint remains in backend/runs. Obsolete demo
weights, the head-only candidate and demo/source-face data were moved outside the
project to ../obsolete-deepfake-backup-20261005 for recovery. Unused legacy frontend
pages and the old random-split/synthetic trainer were removed. Current checks use
genuine held-out fixtures, not the removed demo data.

## Genuine training and evaluation completed

User supplied wiki.zip and inpainting.zip; both full ZIP CRC checks passed.
Prepared 2,000 matched real/manipulated pairs (4,000 images). Source-group and
decoded-pixel checks passed: train 1,399/class, validation 298/class,
test 303/class. This is source-group separation, not independently verified
identity separation. Dataset provenance/archive hashes are in the manifest.

CPU ResNet18 training: cached ImageNet initialization, 10-epoch frozen-backbone
head baseline (LR 0.001), then 3-epoch layer4/head fine-tune (LR 0.0001).
Fine-tuning was planned from the baseline validation plateau before viewing its
test results. The baseline was retained unless validation AUC improved; final
selection used validation AUC, never test scores. Selected fine-tune epoch: 3.

- Validation: accuracy 85.57%, ROC-AUC 0.9420 (596 images).
- Test: accuracy 84.49%, ROC-AUC 0.9311 (606 images).
- Test fake precision 81.96%, recall 88.45%, F1 85.08%.
- Test confusion matrix at threshold 0.5: [[244, 59], [35, 268]].
- The app uses 0.4/0.6 cutoffs and an inconclusive region; scores are uncalibrated.
- Baseline test accuracy was 70.96%, ROC-AUC 0.8003.

Scope: DeepFakeFace diffusion-inpainting images. These results do not establish
cross-dataset, unseen manipulation-family or genuine video-deepfake accuracy.
The model makes errors and cannot establish authenticity.

## Verified

All 14 candidate image/video API integration and regression tests passed with disposable
database/storage. Includes six original held-out image uploads, numeric agreement
with direct model inference, real/fake static face-video fixtures, private access,
no-face handling, missing-model fallback, retention and training leakage checks.
These integration checks are not an additional accuracy benchmark.

Frontend production build, UI contracts/rendering and startup checks passed.
After execution permissions changed, native development serving passed too.
Chrome browser checks passed: upload/polling, inconclusive no-face result,
protected images, full report, private history/deletion, genuine held-out real and
manipulated face uploads, privacy/terms navigation, no uncaught application
exceptions, desktop rendering and mobile-width layout. Tests use isolated storage;
the harness refuses a backend whose APP_ENV is not test.
Report JSON download is verified in Chrome. UI polish adds mobile history access,
paginated scan history, keyboard focus visibility, lightweight file previews and
bounded report polling with cancellation/retry. Health reports degraded status
when the model is unavailable instead of incorrectly showing a healthy engine.
A live built frontend/backend run returned the new dataset and 606-image test
metrics through the frontend proxy, using isolated runtime storage.
Selected runtime artifacts and the manifest are no longer git-ignored, but no
commit/push or external deployment was performed.

## Pending before claiming full production readiness

- Additional independent identities/sources, manipulation families and compressed
  genuine-video benchmarks.
- Actual Docker/hosted deployment execution: Docker is not installed/available.
  Permission changes do not install Docker; configuration is not an executed
  deployment test. No external deployment was requested or performed.

No dataset ZIPs, user scans or existing database records were deleted. Smoke data
uses backend/.runtime-check or disposable temporary folders. See SUBMISSION_CHECKLIST.md
for artifacts to preserve and honest presentation claims. Presentation work has not started.

## Fresh-state cleanup verified; one unused test folder remains

The user subsequently requested removing old scans and the obsolete backup too.
Execution policy rejected agent deletion commands, so the user manually removed
the old database/uploads, backend/.runtime-check and obsolete backup. Their
absence was verified before normal startup. Startup recreated a fresh database
and uploads directory: users=0, scans=0, uploaded files=0. Health via the frontend
proxy returned status=ok, database=connected and the selected ML classifier active.
The normal dev server is running at http://localhost:5173.
Only frontend/backend/.runtime-check/unrestricted-live remains: unused test
database/media, not the live backend or active model. Manual removal of the nested
frontend/backend folder is still pending. Current model/genuine data are retained.
# Superseded scope notice

The user clarified the task as AI-generated vs real **general images**. Current
model/configuration and verification are in GENERAL_AI_STATUS.md. The following
face-model results are historical, not the current detector's accuracy.

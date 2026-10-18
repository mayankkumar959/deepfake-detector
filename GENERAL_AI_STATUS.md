# Current detector: AI-generated vs real photos

Fake means AI-generated, not arbitrary Photoshop editing. People, objects and scenes are valid inputs. Real camera photos remain real after WhatsApp/JPEG compression; AI images remain AI-generated after compression. Neither filenames nor compression diagnostics decide the verdict.

## Active research model

DETECTOR_TASK=ai-image
RUNS_DIR=./runs/active-image-video-20261018

The assembled v3 package carries the image classifier plus the trained video
temporal head in one folder. Frozen SigLIP encoder; whole-image resizing, no
face crops; the train-only scaler is folded into the saved head; offline
runtime verifies SHA256 before loading safetensors. The upstream published
head is NOT active. Until RUNS_DIR is switched (backend/.env, see DEPLOY.md)
the old indoor model still serves scans; the switch is a manual one-line step.

Same-test head comparison, v3 fresh test (722 images / 700 source-scene
groups; 79 real / 643 fake; modern and legacy generators plus face swaps):

| Head (clean view) | Accuracy | Balanced acc. | ROC AUC |
| --- | --- | --- | --- |
| previous indoor model | 56.9% | 52.5% | 0.540 |
| v2 logistic head | 59.0% | 54.8% | 0.595 |
| v3 head (in the package) | 79.5% | 74.1% | 0.808 |

Compressed upload-like views (JPEG90 / 768px JPEG55 / 512px JPEG40) keep ROC
AUC 0.809 / 0.836 / 0.866. Honest weak spots to disclose: LAION and Pexels
real photos are often flagged fake (~47% correct) and legacy TinyGenImage
generators ADM/VQDM are often missed (58% / 47%); real recall is 67% versus
81% fake recall, so the inconclusive band matters. The v3 fresh test is much
harder than the v2 test, so numbers across those tests are not comparable.
See backend/IMAGE_TRAINING.md and runs/candidate-image-v3-20261018/report.json.

## Video detector (integrated, candidate pending activation)

The video runtime uses a trained visual temporal head whenever RUNS_DIR also
contains video_head.joblib and video_meta.json: six frames from the centred
two-second window (8% border crop, 224x224) through the same frozen SigLIP tower,
plus statistical texture/temporal measurements; per-frame image scores still
build the timeline. Missing artifacts or unsupported clips fall back to the
per-frame image mean with an explicit report warning. Audio and lip-sync
consistency are not analysed. The current candidate (SigLIP-Video-v3, trained
2026-10-18 on 1,886 clips) scores 86.9% clean accuracy / 86.6% balanced
accuracy / 0.919 ROC AUC on a source-group-disjoint fresh test (291 clips,
160 groups; H.264 CRF35 stress 80.8% / 82.0% / 0.893). No face-swap group
landed in that fresh test, so face-swap claims stay conservative. The v3
image+video package is assembled by backend/package_active.py and stays
inactive until RUNS_DIR is switched (see DEPLOY.md and VIDEO_DETECTOR.md).

Encoder source: https://huggingface.co/Ateeqq/ai-vs-human-image-detector
Pinned revision: 60e82406916921b823616bee33397baab38af3f0 (Apache-2.0).
Data: v2/v3 used Synthbuster + RAISE source photos with nine generator variants
per id; v3 adds OpenFakeTiny, TinyGenImage, OpenForensics validation and DF40
image subsets (see prepare_image_v3.py). The earlier indoor model trained on
Imagenette, COCO, NYU indoor real photographs and DiffusionDB AI images via
public mirrors (train_general_head.py, backend/data/general-ai-training-indoor/
manifest.json; 362 originals: train 215 real/64 AI, validation 26 real/16 AI,
test 26 real/15 AI; NYU stayed training-only because room identities are not
available; duplicate decoded pixels and prompt groups cannot cross splits;
validation ROC-AUC selected C=0.01; small same-source test 34/41 = 82.93%,
AUC 0.9513, confusion [[20,6],[1,14]] - exploratory results, NOT
representative deployment accuracy; repeated development used that split and
a fresh independent benchmark is still needed; source bias and unseen
generators remain major risks).

## User-photo regression

The known real locker/chair photo was NOT used in training. Saved-model AI scores: original 0.15867, JPEG95 0.15928, JPEG60 0.16026, JPEG40 0.12403. All favor real with unchanged thresholds <=0.4 real, >=0.6 AI, otherwise inconclusive. These JPEG variants do not recreate WhatsApp's actual algorithm.
Five reserved AI fixtures favor AI; five reserved real fixtures favor real in direct inference. Runtime rejects under-224px or blank inputs as inconclusive. API regression asserts ground-truth decisions for supported-size fixtures and both-class JPEG variants.
No exact-photo override or compression-based real shortcut exists.
Earlier UFD, published SigLIP and two local heads failed regressions and are inactive. Historical facial accuracy does not describe this task. Old scan reports are unchanged: rescan for the new model.

## Verification and artifacts

Reverified 2026-10-06 after restoring 17 accidentally deleted backend router/service
modules. Latest frontend score comparison remains intact. All tracked files are
present and active model artifact SHA256 checks pass. Startup now rejects missing
essential backend source files explicitly.

Current checks: 6 database compatibility tests passed; 7 general-image/API tests
passed (including upload validation/session access and sampled-frame video
contract). The optional user-camera test was skipped because no explicit
CAMERA_REGRESSION_IMAGE was supplied; private uploads were not read implicitly.
The live Neon regression passed TLS, startup, inference, JSONB, owner isolation,
private media/history and deletion, cleaning only its own disposable test records.
Production frontend build, UI/startup checks, mocked reload/polling/score tests,
and actual browser uploads/report download/history/deletion/desktop-mobile routes
passed. Full browser integration used a separate local test API and disposable
SQLite/media storage, not the user's live scan history.
These are functional regressions, not new broad accuracy or video benchmarks.
Docker and public-hosting execution remain unverified.

From backend run python verify_general.py. Optional CAMERA_REGRESSION_IMAGE enables the known-real-photo test. Test storage is disposable. Model-folder integration_evaluation.json and camera_regression.json store results when checks pass.
Frontend: npm run build, verify:ui, check:startup and verify:browser. Browser checks require APP_ENV=test and isolated database/uploads.
Completed 2026-10-05: 6 backend regression tests, production frontend build,
static UI/startup checks and actual browser upload/polling/report JSON/private
history/deletion/desktop-mobile checks passed. These are software regressions,
not a broad detector-accuracy certification.
Keep model.safetensors (~372 MB), config.json, preprocessor_config.json, model_meta.json and evaluation.json from the active folder together. The active weight is tracked with Git LFS: clone with Git LFS installed and run git lfs pull before building/submitting. setup-general-ai.ps1 verifies these trained files; upstream downloads cannot restore the local head.
Raw datasets are unnecessary for inference. wiki.zip/inpainting.zip were confirmed absent; no need to restore them. Failed candidates/face data remain inactive; remove manually only after preserving the active model.

## Not production-certified

Scores are uncalibrated and not proof of origin. Generic Photoshop detection, localization and guaranteed authenticity are unsupported. Videos use a trained visual temporal head on six centred frames when it is packaged; audio, lip-sync consistency and motion authenticity are not assessed, and the video benchmark is small. No broad multi-generator or true WhatsApp benchmark has passed.
Suitable as an honestly scoped research/demo submission, not a reliably finished forensic product.

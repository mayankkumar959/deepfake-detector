# Current detector: AI-generated vs real photos

Fake means AI-generated, not arbitrary Photoshop editing. People, objects and scenes are valid inputs. Real camera photos remain real after WhatsApp/JPEG compression; AI images remain AI-generated after compression. Neither filenames nor compression diagnostics decide the verdict.

## Active research model

DETECTOR_TASK=ai-image
RUNS_DIR=./runs/general-ai-trained-indoor-20261005

Frozen SigLIP encoder with a newly trained class-balanced binary logistic head. The train-only scaler is folded into the saved head. Both classes receive JPEG95/60 augmentation. Whole-image resizing, no face crops. Offline runtime verifies SHA256 before loading safetensors. The upstream published head is NOT active.

Encoder source: https://huggingface.co/Ateeqq/ai-vs-human-image-detector
Pinned revision: 60e82406916921b823616bee33397baab38af3f0 (Apache-2.0).
Local data: Imagenette, COCO, NYU indoor real photographs and DiffusionDB Stable Diffusion AI images via public mirrors. See train_general_head.py and backend/data/general-ai-training-indoor/manifest.json for provenance.

362 originals: train 215 real/64 AI; validation 26 real/16 AI; test 26 real/15 AI. NYU stream stays entirely in training because room identities are not available. Duplicate decoded pixels and prompt groups cannot cross splits. Validation ROC-AUC selected C=0.01.
Small test: 34/41 correct (82.93%), AUC 0.9513, confusion [[20,6],[1,14]].
These are exploratory same-source results, NOT representative deployment accuracy. Repeated development used this small split; a fresh independent benchmark is needed. Source bias and unseen generators remain major risks.

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

Scores are uncalibrated and not proof of origin. Generic Photoshop detection, localization and guaranteed authenticity are unsupported. Videos use sampled image scores, not a validated temporal detector. No broad multi-generator, true WhatsApp or video benchmark has passed. Docker/hosting remain unexecuted.
Suitable as an honestly scoped research/demo submission, not a reliably finished all-image forensic product.

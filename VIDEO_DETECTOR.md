# Video detector: trained temporal head on frozen SigLIP

Video support is deliberately visual-only. The app does not analyse audio or
audio/video synchronisation, and no score is a proof of origin.

## What the app does on a video upload

1. Up to 16 evenly spaced frames are scored by the active image model
   (`DETECTOR_TASK=ai-image`). Those per-frame scores build the timeline shown
   in the UI; they are not the overall verdict.
2. The overall verdict comes from the trained video head when
   `video_head.joblib` and `video_meta.json` are present in `RUNS_DIR`:
   - six frames from the centred two-second window,
   - 8% border crop, then 224x224,
   - frozen SigLIP whole-frame embeddings (mean / std / absolute delta = 2304
     values) plus 68 source-agnostic texture and temporal statistics,
   - the saved scikit-learn head (LogisticRegression or ExtraTrees) selected on
     the validation split by macro domain-balanced accuracy.
3. If the video artifacts are missing, or the clip cannot be sampled (fewer
   than six readable frames, blank/low-detail frames), the app falls back to the
   per-frame image-model mean and states that in the report warnings. It never
   substitutes an untrained score silently.
4. `/api/health` reports `detection_engine` (image) and
   `video_detection_engine` (video head, hash, test metrics, method).

The runtime lives in `backend/app/ml/general_video.py` and is wired into
`backend/app/services/video_analysis.py` and `backend/app/services/detector.py`.
It reuses the image detector's frozen SigLIP vision tower, verified
byte-identical to `runs/general-ai-siglip/model.safetensors`, instead of
shipping a second 354 MB encoder. `verify_video_runtime.py` reproduces training
features from cached arrays and the fresh-test support for the same clip.

## Training and evaluation protocol

Both manifests use group-level splits (identity/prompt/scene families never
cross folds), `rebalance_test()` for the two classes, and a fresh test whose
groups never appeared in v2 selection or diagnostics. Video domains are
`face-swap`, `lip-sync`, and `generated-video`. H.264 CRF35 sampled-sequence
stress is reported separately from the clean benchmark.

Manifest and report sources:
- `backend/data/video-training-v2-20261006/manifest.json`, `runs/candidate-video-v2-20261006/report.json`
- `backend/data/video-training-v3-20261018/manifest.json`, `runs/candidate-video-v3-20261018/report.json`

### v2 fresh test (clean, 80 clips / 46 source groups)

| Metric | Clean | H.264 CRF35 stress |
| --- | --- | --- |
| Accuracy | 82.5% | 77.5% |
| Balanced accuracy | 81.3% | 76.8% |
| ROC AUC | 0.941 | 0.841 |
| Wilson 95% interval (accuracy) | 72.7-89.3% | 67.2-85.3% |

Selected head: ExtraTreesClassifier with texture enabled (`feature_width=2372`).
The old observed diagnostic split scores 89.8% clean / 77.6% H.264 and is
reported for continuity only, never for selection.

### v3 fresh test (clean, 291 clips / 160 source groups)

| Metric | Clean | H.264 CRF35 stress |
| --- | --- | --- |
| Accuracy | 86.9% | 80.8% |
| Balanced accuracy | 86.6% | 82.0% |
| ROC AUC | 0.919 | 0.893 |
| Wilson 95% interval (accuracy) | 82.6-90.3% | 75.8-84.9% |

The v3 manifest adds fresh generator, lip-sync and talking-head cohorts (DF40
video swaps, HDTF real, additional generator outputs) on top of every v2 row
and re-runs the same selection protocol. Selected head: logistic-regression
pipeline with `C=0.01` and texture disabled (`feature_width=2304`), chosen on
the validation split by macro domain-balanced accuracy. Fresh-test
domain-balanced accuracy: generated-video 94.7% and lip-sync 79.6% clean
(88.0% / 75.9% H.264). No face-swap source group landed in the fresh test, so
face-swap generalisation is only covered by the diagnostic split (69.3%
domain-balanced clean) - treat face-swap claims conservatively.

Compared with v2 (80 clips, no domain breakdown recorded), v3 improves clean
accuracy (+4.4 points), balanced accuracy (+5.3), H.264 stress accuracy
(+3.3) and H.264 AUC (+5.2) on a 3.6x larger, harder test; clean AUC is
slightly lower (0.919 vs 0.941). The v3 diagnostic split (253 previously
observed clips) scores 76.3% clean / 74.3% H.264 accuracy and is reported for
continuity only, never for selection.

## Honest limitations

- Scores are uncalibrated classifier support, not authenticity probabilities.
- Visual only: audio, dubbing and lip-sync consistency are not assessed.
- The benchmark is small and source-limited; watermark, codec, generator and
  scene shortcuts remain possible. HDTF real clips are the hardest real cohort.
- H.264 stress is a sampled-sequence re-encode, not WhatsApp/Voice transport.
- No guarantee for unseen cameras, generators, languages or manipulation
  methods. Never present a video score as proof.

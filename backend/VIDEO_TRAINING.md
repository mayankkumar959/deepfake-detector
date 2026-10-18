# Local experimental video detector

## Observed results (2026-10-06)

**Not production-ready.** Dataset: 257 source recordings, split into 160 training,
48 validation and 49 held-out test recordings. Training uses frozen visual
features, not a full video-backbone fine-tune.

At the fixed binary evaluation threshold 0.5:

| Check | Correct / evaluated | Accuracy |
| --- | --- | --- |
| Clean held-out recordings | 42 / 49 | 85.7% |
| JPEG frame degradation | 38 / 49 | 77.6% |
| Actual H.264 transcodes (full-video subset) | 29 / 41 | 70.7% |

The CLI uses separate real/fake decision thresholds 0.4/0.6, so ambiguous
examples remain inconclusive. Clean CLI decisions: 40 correct, 6 wrong,
3 inconclusive; four authentic recordings are incorrectly called fake.
H.264 CLI decisions: 28 correct, 10 wrong, 3 inconclusive; one authentic
recording is incorrectly called fake, and nine fake clips are incorrectly
called real. Face-swap is excluded from the H.264 check as described below.

These are small, source-limited research results, not certified probabilities
or all-video accuracy. The live/website model was **not replaced**. The local
candidate is available for research testing only. No paid cloud training was used.

Reports: `runs/candidate-video-mixed-20261006/report.json` and
`runs/candidate-video-mixed-20261006/h264_stress_report.json` (both gitignored).

## Scope

This research experiment does **not** replace the Railway/live image model.
The normal local website/API also keeps its existing model; this candidate is
tested using the CLI below and is not automatically activated in the UI.
Authentic compressed recordings retain the real label. Generated video,
face swaps and lip-sync synthesis receive the fake label. Scores are
uncalibrated visual classifier support, not authenticity probabilities.

## Data and provenance

- [ComGenVid](https://huggingface.co/datasets/OmerXYZ/comgenvid): revision
  `c5093999e799c897c977a8699da95ebbc59cc9cb`; selected MSVD real, Sora and VEO3 clips.
  Original creator rights remain applicable; academic research use only.
- [DeepfakeTIMIT](https://zenodo.org/records/4068245): official publisher
  archive, verified against its published checksum; CC BY-NC-ND 4.0.
  Selected higher-quality face swaps, with both swapped identities grouped.
- [VidTIMIT](https://conradsanderson.id.au/vidtimit/): corresponding authentic
  source recordings. Six uniformly spaced frames per source recording are
  retained; they are **not** counted as six independent videos.
  Full original licence notice is preserved locally.
- [X-Dub teacher outputs](https://huggingface.co/datasets/Pinch-Research/lipsync-hdtf-training-data):
  revision `288d7f355e87f8317bfb4d6b885f60e6ad1c2c22`, with
  speaker-matched real [HDTF](https://huggingface.co/datasets/global-optima-research/HDTF)
  clips at revision `6f9ed465f761b8378c690be4f86f090634281584`.
  Original HDTF research-use terms apply. These are not identical-source-segment pairs.

Large ZIP archives are read using public HTTP byte ranges; only selected
entries are downloaded. This does not bypass gated dataset access.
Raw datasets and candidate artifacts are gitignored and must not be published.

An additional H.264 stress check recompresses the held-out full videos from
ComGenVid/HDTF/X-Dub with CRF 35 and maximum edge 480, applying the same
operation to both labels. It excludes the face-swap subset because its authentic
recordings were retained as selected frames, not full videos. This is not an
actual WhatsApp transport validation and is never used to tune the model.

## Method and evaluation

The existing local frozen SigLIP encoder extracts features from six uniform
frames. Mean, standard deviation and adjacent-frame absolute differences
feed a regularized video-level classifier. JPEG frame degradation is applied
to **both** labels without changing their true labels. The scaler is fitted
on training data only; regularization is chosen using validation data only.
Each domain/label receives equal total fitting weight; model selection uses
macro-domain validation balanced accuracy so the largest dataset cannot dominate.
The held-out test is not used to tune the model.

Recording/creator groups, face-swap identity pairs and HDTF speaker identities
are disjoint across training/validation/test. Exact duplicate files are rejected.
Cross-generator prompt/semantic overlap cannot be verified from available metadata.
Codec, source, lighting and generator shortcuts can still influence this small
experiment. This is not proof of real-world reliability or all-generator coverage.
Visible watermarks, unequal clip durations and unverified cross-dataset scene/
person overlap are additional risks. These results are not the publishers'
official benchmark scores.
JPEG degradation is not an actual WhatsApp/H.264 compression validation.
Audio/video synchronization, voice forgery and every unsampled frame are unassessed.

## Reproduce locally

### Expanded v2 local experiment

`prepare_video_v2.py` adds 200 recording/creator-disjoint MSVD/Sora/VEO3
clips, additional matched face-swap sentences with both HQ and LQ variants,
and more HDTF/X-Dub speakers/utterances. Dependent HQ/LQ examples are not
counted as independent recordings. All previously observed test groups stay
out of training and are now called `diagnostic`; fresh test groups exclude
**every** group in the older experiment.

The v2 head is trained on clean and actual H.264 CRF35 views of both labels.
It compares regularized linear and non-linear classifiers on validation
macro-domain balanced accuracy, with equal domain/label training weight.
Semantic features use the existing frozen SigLIP encoder; residual, FFT,
gradient and frame-change statistics supply additional visual measurements.
This is a trained video-statistics head, **not** a fully fine-tuned video
foundation model. Raw videos use a centered two-second sampling window and
identical 8% border cropping, reducing duration/border shortcuts without
claiming to eliminate source bias.

Face-swap originals are six sampled source frames, not complete source videos.
Their codec augmentation encodes that sampled sequence at 3fps; it must not be
presented as a full-video or WhatsApp transport test. Evaluation separates
full-video-only results and includes source-group bootstrap intervals.
Very small identity/source cohorts still do not establish universal accuracy.

```powershell
python backend/prepare_video_v2.py
python backend/train_video_v2.py
python backend/train_video_v2.py --predict "C:\path\video.mp4"
```

V2 artifacts, resumable feature caches and its final `report.json` are confined
to ignored `backend/runs/candidate-video-v2-20261006`. Candidates never change
the local website, the image model, Railway or Vercel on their own; no
push/deployment is part of this local experiment.

### v3 local experiment (2026-10-18)

`prepare_video_v3.py` rebuilds the manifest on top of every v2 row and adds
fresh cohorts: DF40 video swaps (`df40_vid_swap`), HDTF real recordings
(`hdtf_real`), additional lip-sync teacher outputs and extra generator clips.
The manifest (1,886 rows) keeps group-level splits; fresh test source groups
exclude every group seen in v2 selection or diagnostics.

`runs/candidate-video-v3-20261018/report.json` (291 fresh clips / 160 source
groups): clean 86.9% accuracy / 86.6% balanced accuracy / 0.919 ROC AUC;
H.264 CRF35 stress 80.8% / 82.0% / 0.893. The selected head is a
logistic-regression pipeline (`C=0.01`, texture disabled,
`feature_width=2304`). The diagnostic split (253 previously observed clips)
scores 76.3% clean / 74.3% H.264 for continuity only, never for selection. No
face-swap source group landed in the fresh test, so face-swap generalisation
rests on the diagnostic split (69.3% domain-balanced clean).

```powershell
python backend/prepare_video_v3.py
python backend/train_video_v3.py
python backend/train_video_v3.py --predict "C:\path\video.mp4"
```

The v3 head is runtime-compatible with `backend/app/ml/general_video.py` and is
packaged by `package_active.py` into the deployable run folder; activation is a
separate explicit step (`DEPLOY.md`, `VIDEO_DETECTOR.md`).

### Earlier v1 experiment

From the repository root, with the project's existing Python environment:

```powershell
python backend/train_video_candidate.py --prepare-only
python backend/prepare_video_manipulations.py
python backend/prepare_video_manipulations.py --face-pairs
python backend/prepare_video_manipulations.py --lip-sync
python backend/train_video_candidate.py --extra-manifest backend/data/video-training-manipulations-20261006/faceswap_manifest.json --extra-manifest backend/data/video-training-manipulations-20261006/lipsync_manifest.json --output backend/runs/candidate-video-mixed-20261006
python -m pip install -r backend/requirements-video-tools.txt
python backend/verify_video_compression.py
```

Features are resumable and cached locally, tied to the manifest and encoder checksum.
The mixed candidate reuses the compatible generated-video subset feature cache.
Results and per-video predictions are in the candidate's `report.json`.

To test a local video without changing the website:

```powershell
python backend/train_video_candidate.py --output backend/runs/candidate-video-mixed-20261006 --predict "C:\path\video.mp4"
```

Only load locally generated, trusted `.joblib` artifacts. Output folders are
restricted to ignored `backend/runs/candidate-*` directories. A result between
0.4 and 0.6 is inconclusive, not a forced guess. Strong scores outside that
range can still be wrong; no score is certified or calibrated.

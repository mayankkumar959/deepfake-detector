# Resume After Shutdown (local training)

Everything is resumable. Nothing is ever lost on shutdown: finished work
stays cached on disk, unfinished work is re-done automatically on the next
run.

## Status (as of 2026-10-18 ~14:55)

- **Image v2: DONE.** Report: `runs/candidate-image-v2-20261006/report.json`
  (candidate is better than the active model on every view; NOT activated --
  activation is a manual decision).
- **Image v3: DONE.** Report: `runs/candidate-image-v3-20261018/report.json`
  (fresh test, 722 images / 700 source-scene groups: clean 79.5% accuracy /
  74.1% balanced / 0.808 ROC AUC; same-test head comparison: previous indoor
  0.540, v2 head 0.595, v3 head 0.808). `compatible_model/` holds the
  deployable files. NOT activated.
- **Video v3: DONE.** Report: `runs/candidate-video-v3-20261018/report.json`
  (fresh test, 291 clips: clean 86.9% acc / 86.6% balanced / 0.919 ROC AUC;
  H.264 CRF35 stress 80.8% / 82.0% / 0.893; NOT activated). `video_head.joblib`
  and `video_meta.json` sit in the same folder.
- **Deployable package: BUILT.** `runs/active-image-video-20261018/`
  (image v3 + video v3, checksums verified by `setup-general-ai.ps1`).
  Activation and deployment are explicit manual steps (see DEPLOY.md).
- **Downloads: effectively done** for v3. All groups landed; `lipsync_a` is at
  ~90% and stopped on a Hugging Face rate limit -- re-running
  `python fetch_new_datasets.py lipsync_a` resumes it. The built manifest is
  unaffected (the Lipsync-A selection is cached).

## Commands (open a terminal in `deepfake/backend`)

```powershell
# 1) finish the remaining dataset downloads (resumable, plain HTTP)
python fetch_new_datasets.py openfake_tiny tiny_genimage openforensics_val df40_img_swap shareveo3 genvidbench_small df40_vid_lipsync talkingheadbench lipsync_a aigvdbench_small df40_vid_swap aigvdbench_gen2 hdtf_real

# 2) image v3 (full, with swaps): re-run; prepare() extends the manifest
#    automatically when DF40/OpenForensics data is present
python train_image_v3.py --skip-video-queue

# 3) video v3 is already trained (report exists). Only needed when preparing
#    from scratch -- manifest rebuild auto-detects downloaded sources, then
#    train, reusing all v2 feature caches:
python prepare_video_v3.py
python train_video_v3.py
```

Or simply tell the OpenCode agent: **"resume karo"** -- it knows all steps.

## How progress is tracked (for humans)

- image v3 feature progress: `runs/candidate-image-v3-20261018/training_status.json`
- final image metrics: `runs/candidate-image-v2-20261006/report.json`
- image manifest prep: `data/general-ai-training-v3-20261018/preparation_status.json`
- video v3 features: `runs/candidate-video-v3-20261018/training_status.json`
- video v3 manifest: `data/video-training-v3-20261018/manifest.json`
- new dataset downloads: `data/new-datasets/download_log.jsonl` plus the
  group folders under `data/new-datasets/`

## Why shutdown is safe

- Image/video features are cached per item with a write-to-`.partial` then
  atomic rename, so a sudden shutdown can only lose the one item that was
  mid-extraction; that item is simply re-done next run.
- Model head training only starts after ALL features are cached, so it can
  never see an incomplete feature set.
- Downloads resume: Hugging Face files restart/skip automatically, Zenodo
  files continue from their `.part` file.
- Video v3 manifest rebuilds automatically when new sources land
  (`data/video-training-v3-20261018/extra_sources.json` mismatch triggers it).

## Reminder

Training runs are CPU-only on this laptop (2 physical cores). Keep the
machine awake (no sleep/hibernate) while these jobs run, and keep the
charger plugged in.

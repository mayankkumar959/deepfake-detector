# Research submission checklist

- Include frontend/backend source and requirements, not node_modules or raw datasets.
- Include the active image folder (currently backend/runs/general-ai-trained-indoor-20261005; the v3 package adds backend/runs/active-image-video-20261018): model.safetensors, config.json, preprocessor_config.json, model_meta.json, and, for v3 video, video_head.joblib + video_meta.json. The ~354 MB trained weight uses Git LFS; run git lfs pull and ensure the submitted artifact contains the actual weight, not its small pointer file.
- Run setup-general-ai.ps1, frontend build/UI/startup and backend verify_general.py.
- Browser checks must use isolated test storage.
- Explain AI-generated versus real photos, compression-preserving labels and no face requirement.
- Report the v3 fresh-test numbers (GENERAL_AI_STATUS.md, IMAGE_TRAINING.md: same-test head comparison 56.9% / 59.0% / 79.5% accuracy for previous indoor / v2 head / v3 head) separately from regressions; the older 34/41 indoor test is historical only.
- Disclose source bias, repeated development, single-generator training and unknown-generator risks. A fresh independent broad benchmark is required.
- Video uses a trained visual temporal head on six centred frames plus a per-frame image timeline; audio/lip-sync is not analysed. Report the fresh-test numbers from VIDEO_DETECTOR.md (86.9% clean accuracy, 80.8% under H.264 stress, 291 clips) with the same source-bias caveats, and disclose that no face-swap group landed in that fresh test.
- Keep secrets/user scans out of public submissions. Local Docker remains unverified; the public demo deployment was verified on 2026-10-06 (Railway + Vercel + Neon).
- PRODUCT_STATUS.md, READINESS_AUDIT.md and CLEAN_START.md are historical face-pipeline notes; GENERAL_AI_STATUS.md is current.

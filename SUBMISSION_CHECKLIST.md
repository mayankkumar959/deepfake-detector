# Research submission checklist

- Include frontend/backend source and requirements, not node_modules or raw datasets.
- Include backend/runs/general-ai-trained-indoor-20261005: model.safetensors, config.json, preprocessor_config.json, model_meta.json and evaluation.json. The ~372 MB trained weight uses Git LFS; run git lfs pull and ensure the submitted artifact contains the actual weight, not its small pointer file.
- Run setup-general-ai.ps1, frontend build/UI/startup and backend verify_general.py.
- Browser checks must use isolated test storage.
- Explain AI-generated versus real photos, compression-preserving labels and no face requirement.
- Report small 34/41 test results separately from regressions, not old face metrics.
- Disclose source bias, repeated development, single-generator training and unknown-generator risks. A fresh independent broad benchmark is required.
- Video uses sampled image scores; no validated temporal accuracy.
- Keep secrets/user scans out of public submissions. Docker/hosting remain untested.
- PRODUCT_STATUS.md, READINESS_AUDIT.md and CLEAN_START.md are historical face-pipeline notes; GENERAL_AI_STATUS.md is current.

# Readiness audit (historical findings)

This reconstructed summary describes the original audit, before the application
fixes. It is not a claim that the current product has genuine-data validation.

- Original data used synthetic blur/noise negatives rather than a genuine
  deepfake benchmark. Its demo validation accuracy was not real-world evidence.
- Exact duplicate image content crossed the original training/validation split.
- Blank inputs received decisive scores; video and image scoring differed.
- Video timeline fields and media URLs were inconsistent with the frontend.
- Face-box overlays were presented as stronger localization evidence than they
  supported. Filename signals and uncalibrated confidence were misleading.
- Public scans were shared across visitors, and promised retention was missing.
- Training transforms shared mutable state; inference could download weights
  or silently fail. Startup could launch two backend processes.

The application fixes and current verification are recorded in PRODUCT_STATUS.md.
The original model/demo data were moved outside the project into the recoverable
obsolete-deepfake-backup-20261005 folder; obsolete training code was removed. Genuine-data
training/evaluation has since completed and the fine-tuned checkpoint is active;
see PRODUCT_STATUS.md for measured metrics and remaining readiness limitations.

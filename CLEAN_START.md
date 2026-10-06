# Historical face-pipeline cleanup notes

Current state: see GENERAL_AI_STATUS.md. Keep
backend/runs/general-ai-trained-indoor-20261005 and its trained safetensors.
Old ZIPs wiki.zip/inpainting.zip are absent. The instructions below refer to
earlier face-pipeline cleanup, not the current active model. Do not delete
current user scans or the active model based on these historical notes.

Update: the user removed the old live database/uploads, backend test storage and
obsolete backup. Fresh startup was verified with zero users/scans/upload files
and the latest model active. Only the nested frontend/backend test folder remains
to be manually removed. The newly recreated backend/fortexa.db and backend/uploads
are clean runtime storage; there is no need to delete them again.

The latest trained checkpoint is active and must be kept. Old scan cleanup was
explicitly requested, but execution policy rejected the deletion commands even
with unrestricted filesystem access. No database, upload or backup was deleted
in this cleanup attempt. Do the following manually in Windows File Explorer.

## Stop the app, then delete these exact items

Relative to the `deepfake` project folder:

- `backend/fortexa.db`: old local database, including accounts and scans.
- `backend/uploads`: old uploaded media and generated reports.
- `backend/.runtime-check`: disposable test databases/uploads/screenshots.
- `frontend/backend`: accidentally nested disposable browser-test storage only.

Relative to the folder containing `deepfake`:

- `obsolete-deepfake-backup-20261005`: old demo images, source faces and old weights.

Do not delete the project root, `.env`, source, dependencies, or
`backend/runs/candidate-dff-finetuned-20261005`. Keep its model.pth, metadata,
evaluation.json and training_progress.json. Keep the genuine dataset manifest.
Current genuine archives/images are kept for reproducible retraining/testing;
they are not old scans and are not required for inference.

File Explorer normally sends deletions to Recycle Bin; recovery depends on the
chosen deletion method and Windows configuration. Removing the database resets
local account/history records, not the trained model.

## Restart

From PowerShell in the `deepfake` folder:

```powershell
cd frontend
npm run dev
```

Open http://localhost:5173. Startup creates new local database tables and upload
directories. Your Scans should show No scans yet until you submit a new file.
Browser storage may retain the random session key, but deleted server records
will not reappear. Old report links should display a clear unavailable message.

Do not submit `.env`, user databases/uploads, test storage, node_modules, or the
obsolete backup. Docker/hosted deployment and cross-dataset/video accuracy are
separate, still-unverified checks; do not describe them as passed.

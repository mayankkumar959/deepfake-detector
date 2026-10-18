# Local multi-generator image experiments (v2, v3)

No push, deployment or automatic website-model switch is performed. The live
and local website continue using the current image model while this separate
candidate is downloaded, trained and evaluated. A larger training set is not
by itself evidence that accuracy improved.

## Why expand the image training?

The active indoor experiment used a small single-generator AI subset. Its old
41-image test had 6 real images predicted fake and 1 AI image predicted real.
That test does not measure every generator or real-world camera condition.
Repeating those same images does not fix the missing coverage.

The new experiment samples 120 RAISE source-photo IDs, with the matching real
PNG and all nine Synthbuster generator variants for each ID: DALL-E 2/3,
Firefly, Midjourney v5, Glide, SD1.3/1.4/2 and SDXL. These are known older
generators, not coverage of every current or future generation system.
The target is 1,200 new images, not 1,200 independent scenes. Decoding, space,
duplicate and split audits can reduce the final admitted count; the saved
manifest/report contains the actual counts.

Sources and required citations:

- Quentin Bammey, *Synthbuster: Towards Detection of Diffusion Model Generated
  Images*, IEEE OJSP, 2023. [Publisher dataset](https://zenodo.org/records/10066460),
  CC-BY-NC-SA-4.0. Source README, licence and prompts are preserved locally.
- Dang-Nguyen et al., *RAISE: A Raw Images Dataset for Digital Image Forensics*,
  ACM MMSys, 2015. [Author's dataset](https://loki.disi.unitn.it/RAISE/download.html).
  Non-commercial research/education use; preserve copyright/licence and cite
  authors. Converted real PNG archive is linked by the
  [research implementation](https://github.com/grip-unina/ClipBased-SyntheticImageDetection/blob/main/data/synthbuster_download.sh).
  The archive's full original RAISE licence is preserved as PDF and text.

Public HTTP byte ranges fetch selected ZIP entries only; entry CRCs and local
SHA256 hashes are checked. The full 12.4GB synthetic and 1.6GB real archives
are not downloaded or globally checksum-verified. Archive lengths are pinned;
no gated access is bypassed. Raw data and candidates remain gitignored.
Do not redistribute these images or claim commercial rights to the derivative
model. Preserve dataset notices/citations in academic use.

## Method and evaluation

- Every matched real photo and its nine generated variants share a fold.
- Exact decoded-pixel duplicates are removed, with conflicting labels rejected.
  pHash-distance <=6 families share folds. Families joining conflicting old
  folds become diagnostic, not new training/test data.
- Previously observed image tests stay diagnostic. Fresh tests contain only
  new RAISE/Synthbuster source-photo groups. This is source-photo/prompt-family
  separation, not verified separation of every underlying scene/burst/person.
- Existing frozen SigLIP whole-image features train a new binary linear head.
  The backbone is not fully fine-tuned; its original training-set overlap
  cannot be comprehensively audited.
- Four views are applied to **both** labels: original, JPEG90, max-edge768
  JPEG55 and max-edge512 JPEG40. Compression never changes truth labels.
  These are JPEG/resize proxies, not an actual WhatsApp transport benchmark.
- Train-only standardization and equal class/source weighting prevent the
  nine-generator cohort from simply overwhelming the real class. C is chosen
  only on validation real recall plus macro-generator fake recall, across
  all four views. Fresh test is read only after the choice is frozen.
- The current image head is compared on precisely the same fresh images/views,
  after verifying baseline encoder and processor equality. Real false alarms,
  fake misses, uncertain results and per-generator metrics are reported.
- Standardization is folded into a compatible SigLIP classifier. Numerical
  agreement with the trained classifier is verified on training examples.
  A compatible artifact is saved but **not activated** automatically.

Scores are uncalibrated support, not authenticity probabilities. Sixteen or
eighteen held-out real camera photos, if that is the final admitted count, do
not establish universal reliability; generated variants are dependent scenes.
Confidence intervals that assume independent examples must be interpreted with
that limitation. A good small test does not guarantee every image is correct.

## Run and check locally

```powershell
python -m pip install -r backend/requirements-image-tools.txt
python backend/train_image_v2.py
```

The script first prepares data. By default it queues heavy image feature/head
training until the existing local video task finishes or exits; it does not
train two full encoders concurrently on this CPU-only laptop. Waiting is
reported as `waiting_for_video_cpu`, not as finished training.

```powershell
Get-Content backend/data/general-ai-training-v2-20261006/preparation_status.json
Get-Content backend/runs/candidate-image-v2-20261006/training_status.json
Get-Content backend/runs/candidate-image-v2-20261006/train.stdout.log -Tail 10
```

After successful training, `report.json` contains candidate/current comparisons
and `compatible_model/` contains checksum-verified compatible model artifacts.
No report means evaluation is unfinished; a `failed` status should be inspected
alongside `train.stderr.log`. Downloads/features are resumable. Completed runs
refuse retraining in the same folder to discourage test-set tuning.

To test the candidate without replacing the website model:

```powershell
python backend/train_image_v2.py --predict "C:\path\photo.jpg"
```

Support <=0.4 gives real, >=0.6 fake, and the middle is inconclusive. Even a
strong score can be wrong. Small/featureless inputs are inconclusive, not
automatically real/fake. Only load locally generated trusted joblib artifacts.

## v3 expansion (2026-10-18)

v3 keeps every v2 row and adds modern generator, legacy generator, face-swap
and real-photo cohorts: OpenFakeTiny (generator and real subsets),
TinyGenImage (ADM, GLIDE, Midjourney, SD15, VQDM, Wukong and its real split),
OpenForensics validation faces (real + manipulated) and DF40 image face swaps
(blendface, inswap, simswap, uniface). The manifest has 11,155 rows
(7,874 train / 719 validation / 722 fresh test / 1,840 diagnostic images)
with the same group-level split and audit rules as v2; 6,341 v2 feature
caches were reused because the encoder and views are byte-identical.

The fresh test (722 images, 700 source-scene groups; 79 real / 643 fake) is
much harder than the v2 test, so v2 and v3 scores are not comparable across
tests. What is comparable is the same-test head comparison
(`python backend/compare_image_heads_v3.py`):

| Head (same v3 fresh test, clean view) | Accuracy | Balanced acc. | ROC AUC |
| --- | --- | --- | --- |
| Active indoor model (before this work) | 56.9% | 52.5% | 0.540 |
| v2 logistic head | 59.0% | 54.8% | 0.595 |
| **v3 logistic head (selected, C=0.1)** | **79.5%** | **74.1%** | **0.808** |

v3 keeps its edge on the compressed views closest to phone uploads: JPEG90
AUC 0.809, 768px JPEG55 0.836, 512px JPEG40 0.866. The diagnostic split
(1,840 previously observed images) scores 74.6% accuracy / 0.830 AUC clean
and is reported for continuity only, never for selection.

Honest weak spots in the v3 fresh test: real photos from the LAION (47%) and
Pexels (47%) subsets are often called fake, and the legacy TinyGenImage
generators ADM (58%) and VQDM (47%) are often missed; the other swap and
generator groups sit at 71-100%. Real recall is 67% while fake recall is
81%, so the app's inconclusive band matters. These are CPU-only laptop
estimates, not proof of universal accuracy.

Artifacts: `runs/candidate-image-v3-20261018/report.json` (per-source fresh-
test comparison) and `compatible_model/` (the deployable head copied by
`package_active.py`). Re-running resumes from cached features; completed runs
refuse to retune on the same fresh test.

```powershell
python -m pip install -r backend/requirements-image-tools.txt
python backend/train_image_v3.py --skip-video-queue
python backend/compare_image_heads_v3.py
```

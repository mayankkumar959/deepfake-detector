"""Download/import authentic and diffusion-inpainted DeepFakeFace images for research."""
import argparse
import hashlib
import json
import random
import shutil
import urllib.request
import zipfile
from pathlib import Path

import cv2
import numpy as np
from ..services.face_utils import detect_faces, extract_face_region

SOURCE = "https://huggingface.co/datasets/OpenRL/DeepFakeFace"
REVISION = "eb2a54f"


def download_archive(directory, name):
    path = directory / f"{name}.zip"
    if path.exists() and zipfile.is_zipfile(path):
        return path
    url = f"{SOURCE}/resolve/{REVISION}/{name}.zip?download=true"
    print(f"Downloading {url}", flush=True)
    with urllib.request.urlopen(url, timeout=60) as response:
        size = int(response.headers.get("Content-Length", 0))
        if shutil.disk_usage(directory).free < size + 1024 ** 3:
            raise RuntimeError("Insufficient disk space for dataset download")
        part = path.with_suffix(".zip.part")
        with part.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
    if not zipfile.is_zipfile(part):
        raise ValueError("Downloaded file is not a valid ZIP archive")
    part.replace(path)
    return path


def index_archive(archive):
    indexed = {}
    for info in archive.infolist():
        if Path(info.filename).suffix.lower() in (".jpg", ".jpeg", ".png"):
            stem = Path(info.filename).stem
            if stem in indexed:
                raise ValueError(f"Ambiguous source filename: {stem}")
            indexed[stem] = info
    return indexed


def prepare(args):
    archives, out = Path(args.archives).resolve(), Path(args.out).resolve()
    archives.mkdir(parents=True, exist_ok=True)
    if (out / "manifest.json").exists():
        raise ValueError("Dataset already exists. Use a new output directory to preserve it.")
    if args.download:
        for name in ("wiki", "inpainting"):
            download_archive(archives, name)
    missing = [str(archives / f"{name}.zip") for name in ("wiki", "inpainting") if not (archives / f"{name}.zip").exists()]
    if missing:
        raise FileNotFoundError("Genuine training archives missing: " + ", ".join(missing))
    out.mkdir(parents=True, exist_ok=True)
    records, seen, groups = [], {}, set()
    with zipfile.ZipFile(archives / "wiki.zip") as real_zip, zipfile.ZipFile(archives / "inpainting.zip") as fake_zip:
        real_index, fake_index = index_archive(real_zip), index_archive(fake_zip)
        keys = sorted(real_index.keys() & fake_index.keys())
        random.Random(42).shuffle(keys)
        if not keys:
            raise ValueError("Archives have no matching original/manipulated filenames")
        for key in keys:
            group = key.split("_")[0]
            pair = []
            for label, archive, index in ((0, real_zip, real_index), (1, fake_zip, fake_index)):
                info = index[key]
                if info.file_size > 20 * 1024 * 1024:
                    break
                image = cv2.imdecode(np.frombuffer(archive.read(info), dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is None or image.shape[0] * image.shape[1] > 20_000_000 or not detect_faces(image):
                    break
                crop, _ = extract_face_region(image, margin=.2)
                image = cv2.resize(crop, (224, 224), interpolation=cv2.INTER_AREA)
                digest = hashlib.sha256(image.tobytes()).hexdigest()
                pair.append((label, image, digest, info.filename))
            if len(pair) != 2 or any(p[2] in seen for p in pair) or pair[0][2] == pair[1][2]:
                continue
            value = int(hashlib.sha256(group.encode()).hexdigest()[:8], 16) / 0xffffffff
            split = "test" if value < .15 else "val" if value < .30 else "train"
            for label, image, digest, original in pair:
                relative = Path("real" if label == 0 else "fake") / f"{hashlib.sha256(key.encode()).hexdigest()[:24]}.png"
                (out / relative.parent).mkdir(exist_ok=True)
                if not cv2.imwrite(str(out / relative), image):
                    raise OSError("Could not write prepared image")
                seen[digest] = group
                records.append({"path": relative.as_posix(), "label": label, "group": group, "split": split,
                                "original_file": original, "image_sha256": digest})
            groups.add(group)
            if len(records) // 2 >= args.pairs:
                break
    manifest = {"source": SOURCE, "source_revision": REVISION, "genuine_manipulated_media": True,
                "manipulation": "Stable Diffusion facial inpainting; paired original IMDB-WIKI photos",
                "grouping": "original filename leading identifier; source-group separation, not independently verified identity separation",
                "preprocessing": "Haar-detected largest face, margin=0.2, resize=224",
                "archive_sha256": {name: file_hash(archives / f"{name}.zip") for name in ("wiki", "inpainting")},
                "records": records}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    from .train_manifest import load_manifest
    _, _, counts = load_manifest(out / "manifest.json")
    print(json.dumps({"manifest": str(out / "manifest.json"), "groups": len(groups), "splits": counts}), flush=True)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", default="data/archives")
    parser.add_argument("--out", default="data/genuine_dff")
    parser.add_argument("--pairs", type=int, default=2000)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if args.pairs < 20:
        parser.error("Use at least 20 pairs; substantially more are needed for meaningful evaluation")
    prepare(args)


if __name__ == "__main__":
    main()

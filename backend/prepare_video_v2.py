"""Expand LOCAL video research data without reusing observed test groups.

Author-published revision-pinned sources only. Licences remain in v1 folders.
Old test is diagnostic only. Nothing is pushed, deployed or redistributed.
"""
import argparse
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import random
import shutil
import tarfile
import threading
import zipfile
from urllib.parse import quote

import cv2
import numpy as np
from PIL import Image
import requests

from prepare_video_manipulations import RemoteZip, frame_digest

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/video-training-v2-20261006'
OLD_GEN = ROOT / 'data/video-training-comgenvid-20261006'
OLD_MANIP = ROOT / 'data/video-training-manipulations-20261006'
SEED = 20661006
REPO = 'OmerXYZ/comgenvid'
REV = 'c5093999e799c897c977a8699da95ebbc59cc9cb'


def digest(path):
    if path.is_dir():
        return frame_digest(path)
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def old_rows():
    rows = []
    for folder, filename in [(OLD_GEN, 'manifest.json'), (OLD_MANIP, 'faceswap_manifest.json'),
                             (OLD_MANIP, 'lipsync_manifest.json')]:
        for row in json.loads((folder / filename).read_text()):
            row['path'] = str((folder / row['path']).resolve())
            row['original_split'] = row['split']
            if row['split'] == 'test':
                row['split'] = 'diagnostic'
            rows.append(row)
    return rows


def group(row):
    stem = Path(row['file_name']).stem
    identity = stem.rsplit('_', 2)[0] if row['source_model'] == 'MSVD' else stem.split('_')[0]
    return row['source_model'] + ':' + identity


def expand_generated():
    target = DATA / 'generated_manifest.json'
    if target.exists():
        return json.loads(target.read_text())
    excluded = {row['group'] for row in old_rows()}
    response = requests.get(f'https://huggingface.co/datasets/{REPO}/resolve/{REV}/metadata.jsonl', timeout=60)
    response.raise_for_status()
    buckets = defaultdict(dict)
    for row in map(json.loads, response.text.splitlines()):
        if row['source_model'] in ('MSVD', 'Sora', 'VEO3') and min(row['width'], row['height']) >= 224 and group(row) not in excluded:
            buckets[row['source_model']].setdefault(group(row), row)
    rng = random.Random(SEED)
    rows = []
    used = sum(p.stat().st_size for p in DATA.glob('*.mp4'))
    lock = threading.Lock()

    def download(row):
        nonlocal used
        relative = hashlib.sha256(row['file_name'].encode()).hexdigest()[:24] + '.mp4'
        path = DATA / relative
        if not path.exists():
            url = f'https://huggingface.co/datasets/{REPO}/resolve/{REV}/' + quote(row['file_name'], safe='/')
            try:
                with requests.get(url, stream=True, timeout=(20, 90)) as res:
                    res.raise_for_status()
                    if int(res.headers.get('Content-Length', '0')) > 8 * 2**20:
                        return None
                    content = bytearray()
                    for chunk in res.iter_content(256 * 1024):
                        content.extend(chunk)
                        if len(content) > 8 * 2**20:
                            return None
                    with lock:
                        if used + len(content) > 1100 * 2**20 or shutil.disk_usage(DATA).free < 2 * 2**30:
                            raise RuntimeError('Dataset disk budget reached')
                        pending = path.with_suffix('.partial')
                        pending.write_bytes(content)
                        pending.replace(path)
                        used += len(content)
            except requests.RequestException:
                return None
        cap = cv2.VideoCapture(str(path))
        try:
            count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if count < 6:
                return None
            for index in np.linspace(0, count - 1, 6).astype(int):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
                ok, frame = cap.read()
                if not ok:
                    return None
        finally:
            cap.release()
        return {'path': str(path.resolve()), 'source_model': row['source_model'], 'label': int(row['source_model'] != 'MSVD'),
                'group': group(row), 'sha256': digest(path), 'bytes': path.stat().st_size,
                'repository': REPO, 'revision': REV, 'file_name': row['file_name'], 'category': 'generated-video'}

    for source, requested in [('MSVD', 100), ('Sora', 50), ('VEO3', 50)]:
        candidates = list(buckets[source].values())
        rng.shuffle(candidates)
        accepted = []
        # Process only enough small batches to meet the bounded target.
        for offset in range(0, len(candidates), 6):
            with ThreadPoolExecutor(max_workers=2) as workers:
                for item in workers.map(download, candidates[offset:offset + min(6, requested - len(accepted))]):
                    if item:
                        accepted.append(item)
            print('new generated', source, len(accepted), '/', requested, 'download_MiB', round(used / 2**20), flush=True)
            if len(accepted) == requested:
                break
        if len(accepted) != requested:
            raise ValueError('Insufficient source clips within byte budget: ' + source)
        for index, row in enumerate(accepted):
            row['split'] = 'test' if index < requested * .2 else 'val' if index < requested * .4 else 'train'
        rows.extend(accepted)
    save(target, rows)
    return rows


def expand_faces():
    manifest = DATA / 'faces_manifest.json'
    if manifest.exists():
        return json.loads(manifest.read_text())
    old = [row for row in old_rows() if row['source_model'] in ('VidTIMIT', 'DeepfakeTIMIT-HQ')]
    roles = {tuple(sorted((r['target_identity'], r['swapped_identity']))): r['split'] for r in old}
    existing = {(r['target_identity'], r['source_sentence'], r['label'], r['source_model']) for r in old}
    members = {}
    rows = []
    with tarfile.open(OLD_MANIP / 'DeepfakeTIMIT.tar.gz') as archive:
        for member in archive.getmembers():
            if '/higher_quality/' in member.name and member.name.endswith('.avi'):
                target = Path(member.name).parent.name
                other = Path(member.name).stem.rsplit('-', 1)[-1]
                pair = tuple(sorted((target, other)))
                members.setdefault(pair, {}).setdefault(target, []).append(member.name)
        fresh = sorted(set(members) - set(roles))
        random.Random(SEED).shuffle(fresh)
        if len(fresh) != 4:
            raise ValueError('Expected four untouched swap pairs')
        for index, pair in enumerate(fresh):
            roles[pair] = 'test' if index < 2 else 'val'
        for pair, split in sorted(roles.items()):
            if split == 'diagnostic':
                continue
            for target in pair:
                candidates = sorted(members[pair][target])
                count = 3 if split == 'train' else 2 if pair in fresh else 1
                # Retain the v1 matched sentence plus two additional recordings.
                choices = [candidates[2]] + [n for n in candidates if n != candidates[2]]
                remote = None
                original = None
                for hq_name in choices[:count]:
                    sentence = Path(hq_name).name.split('-')[0]
                    for label, source in [(0, 'VidTIMIT'), (1, 'DeepfakeTIMIT-HQ'), (1, 'DeepfakeTIMIT-LQ')]:
                        if (target, sentence, label, source) in existing:
                            continue
                        directory = DATA / hashlib.sha256(f'{source}:{target}:{sentence}'.encode()).hexdigest()[:24]
                        directory.mkdir(exist_ok=True)
                        prefix = f'{target}/video/{sentence}/'
                        source_name = hq_name if source.endswith('HQ') else hq_name.replace('/higher_quality/', '/lower_quality/')
                        if len(list(directory.glob('*.jpg'))) != 6:
                            if label:
                                stream = archive.extractfile(source_name)
                                if stream is None:
                                    raise ValueError('Missing official swap variant')
                                temporary = DATA / (directory.name + '.avi')
                                payload = stream.read(12 * 2**20 + 1)
                                if len(payload) > 12 * 2**20:
                                    raise ValueError('Oversized swap video')
                                temporary.write_bytes(payload)
                                cap = cv2.VideoCapture(str(temporary))
                                try:
                                    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                                    if total < 6:
                                        raise ValueError('Too few swap frames')
                                    for j, frame_index in enumerate(np.linspace(0, total - 1, 6).astype(int)):
                                        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
                                        ok, frame = cap.read()
                                        if not ok:
                                            raise ValueError('Cannot decode swap frame')
                                        Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).save(directory / f'{j:02d}.jpg', quality=90)
                                finally:
                                    cap.release()
                            else:
                                if original is None:
                                    remote = RemoteZip(f'https://zenodo.org/records/158963/files/{target}.zip')
                                    original = zipfile.ZipFile(remote)
                                names = sorted(n for n in original.namelist() if n.startswith(prefix)
                                               and (Path(n).name.isdigit() or n.lower().endswith('.jpg')))
                                if len(names) < 6:
                                    raise ValueError('Missing matched real sequence')
                                for j, frame_index in enumerate(np.linspace(0, len(names) - 1, 6).astype(int)):
                                    image = Image.open(io.BytesIO(original.read(names[frame_index]))).convert('RGB')
                                    image.save(directory / f'{j:02d}.jpg', quality=90)
                        rows.append({'path': str(directory.resolve()), 'label': label, 'source_model': source, 'split': split,
                                     'group': 'VidTIMIT-swap-pair:' + ':'.join(pair), 'sha256': digest(directory),
                                     'target_identity': target, 'swapped_identity': next(p for p in pair if p != target),
                                     'source_sentence': sentence, 'file_name': source_name if label else prefix,
                                     'repository': 'https://zenodo.org/records/4068245' if label else 'https://zenodo.org/records/158963',
                                     'category': 'face-swap', 'provenance': 'Matched original plus HQ/LQ swap, six source frames; variants share identity pair.'})
                print('expanded face', target, 'new examples', len(rows), 'range_bytes', remote.received if remote else 0, flush=True)
    save(manifest, rows)
    return rows


def expand_lipsync():
    manifest = DATA / 'lipsync_manifest.json'
    if manifest.exists():
        return json.loads(manifest.read_text())
    old = [r for r in old_rows() if r['source_model'] in ('HDTF', 'X-Dub')]
    roles = {r['group'].split(':', 1)[1]: r['split'] for r in old}
    existing = {(r['source_model'], r['file_name']) for r in old}
    repo = 'Pinch-Research/lipsync-hdtf-training-data'
    rev = '288d7f355e87f8317bfb4d6b885f60e6ad1c2c22'
    base = f'https://huggingface.co/datasets/{repo}/resolve/{rev}/'
    response = requests.get(base + 'xdub_teacher_pairs_manifest.json', timeout=60)
    response.raise_for_status()
    grouped = defaultdict(list)
    for row in response.json():
        grouped[row['src_speaker'].rstrip('0123456789')].append(row)
    archive_repo = 'global-optima-research/HDTF'
    archive_rev = '6f9ed465f761b8378c690be4f86f090634281584'
    remote = RemoteZip(f'https://huggingface.co/datasets/{archive_repo}/resolve/{archive_rev}/clips.zip')
    archive = zipfile.ZipFile(remote)
    originals = defaultdict(list)
    for name in archive.namelist():
        if name.endswith('.mp4'):
            originals[Path(name).stem.split('_')[1].rstrip('0123456789')].append(name)
    fresh = sorted(s for s in grouped if s not in roles and len(originals[s]) >= 2 and len(grouped[s]) >= 2)
    random.Random(SEED).shuffle(fresh)
    if len(fresh) < 10:
        raise ValueError('Insufficient fresh HDTF speakers')
    for index, speaker in enumerate(fresh[:10]):
        roles[speaker] = 'test' if index < 4 else 'val' if index < 6 else 'train'
    rows = []
    for speaker, split in sorted(roles.items()):
        if split == 'diagnostic':
            continue
        count = 4 if speaker not in fresh and split == 'train' else 2
        choices = [(0, n) for n in sorted(originals[speaker])[:count]]
        choices += [(1, p['id']) for p in sorted(grouped[speaker], key=lambda p: p['id'])[:count]]
        for label, name in choices:
            source = 'X-Dub' if label else 'HDTF'
            if (source, name) in existing:
                continue
            path = DATA / (hashlib.sha256(('lip-v2:' + name).encode()).hexdigest()[:24] + '.mp4')
            if not path.exists():
                if label:
                    with requests.get(base + 'xdub_teacher_pairs/videos/' + name + '.mp4', stream=True, timeout=90) as res:
                        res.raise_for_status()
                        content = res.raw.read(12 * 2**20 + 1)
                else:
                    content = archive.read(name)
                if len(content) > 12 * 2**20:
                    raise ValueError('Oversized lip-sync clip')
                path.write_bytes(content)
            rows.append({'path': str(path.resolve()), 'label': label, 'group': 'HDTF-speaker:' + speaker, 'split': split,
                         'source_model': source, 'sha256': digest(path), 'bytes': path.stat().st_size,
                         'repository': repo if label else archive_repo, 'revision': rev if label else archive_rev,
                         'file_name': name, 'category': 'lip-sync', 'matching': 'Speaker matched, NOT identical source segment'})
        print('expanded lip speaker', speaker, 'new clips', len(rows), 'range_bytes', remote.received, flush=True)
    save(manifest, rows)
    return rows


def audit(rows):
    groups, hashes, identities = defaultdict(set), {}, defaultdict(set)
    for row in rows:
        groups[row['group']].add(row['split'])
        if row['sha256'] in hashes:
            raise ValueError('Duplicate data across combined manifest')
        hashes[row['sha256']] = row['label']
        if digest(Path(row['path'])) != row['sha256']:
            raise ValueError('Dataset file checksum changed')
        for identity in (row.get('target_identity'), row.get('swapped_identity')):
            if identity:
                identities[identity].add(row['split'])
    if any(len(s) > 1 for s in groups.values()) or any(len(s) > 1 for s in identities.values()):
        raise ValueError('Recording/creator/speaker/swap-identity leakage')
    if {r['group'] for r in rows if r['split'] == 'test'} & {r['group'] for r in old_rows()}:
        raise ValueError('New test contains previously observed groups')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=('generated', 'faces', 'lips', 'all'), default='all')
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    if args.stage == 'generated':
        expand_generated()
    elif args.stage == 'faces':
        expand_faces()
    elif args.stage == 'lips':
        expand_lipsync()
    else:
        rows = old_rows() + expand_generated() + expand_faces() + expand_lipsync()
        audit(rows)
        save(DATA / 'manifest.json', rows)
        print(json.dumps({'examples': len(rows), 'splits': dict(Counter(r['split'] for r in rows)),
                          'source_counts': dict(Counter(r['source_model'] for r in rows))}, indent=2), flush=True)

"""Bounded author-published research downloads; no gated dataset bypass.

ZIP range reads fetch selected entries only, never the multi-GB HDTF archive.
No raw data may be redistributed; preserve source licences and citations.
"""
import hashlib
import argparse
import io
import json
from pathlib import Path
import tarfile
import zipfile
from collections import defaultdict
import random
import cv2
import numpy as np
from PIL import Image

import requests

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/video-training-manipulations-20261006'


class RemoteZip(io.RawIOBase):
    def __init__(self, url):
        self.url, self.position, self.received = url, 0, 0
        self.cache_start, self.cache = 0, b''
        with requests.get(url, headers={'Range': 'bytes=0-0'}, stream=True, timeout=60) as res:
            res.raise_for_status()
            if res.status_code != 206:
                raise ValueError('Range reads unavailable: refuse full archive download')
            self.length = int(res.headers['Content-Range'].split('/')[-1])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else self.length + offset
        if not 0 <= self.position <= self.length:
            raise ValueError('Invalid archive offset')
        return self.position

    def read(self, size=-1):
        size = min(self.length - self.position, size if size >= 0 else self.length)
        if size == 0:
            return b''
        if self.cache_start <= self.position and self.position + size <= self.cache_start + len(self.cache):
            offset = self.position - self.cache_start
            self.position += size
            return self.cache[offset:offset + size]
        if size > 32 * 2**20 or self.received + size > 256 * 2**20:
            raise ValueError('Remote archive byte budget exceeded')
        start = self.position
        fetch_size = min(self.length - start, max(size, 64 * 1024))
        if self.received + fetch_size > 256 * 2**20:
            raise ValueError('Remote archive byte budget exceeded')
        end = start + fetch_size - 1
        # Query makes cache keys unique even on proxies that ignore Vary: Range.
        separator = '&' if '?' in self.url else '?'
        url = self.url + separator + f'range_start={start}&range_end={end}'
        with requests.get(url, headers={'Range': f'bytes={start}-{end}'}, stream=True, timeout=90) as res:
            res.raise_for_status()
            if res.status_code != 206 or not res.headers.get('Content-Range', '').startswith(f'bytes {start}-{end}/'):
                raise ValueError('Server ignored requested byte range')
            content = res.raw.read(fetch_size + 1)
        if len(content) != fetch_size:
            raise ValueError('Incomplete archive range')
        self.position += size
        self.received += fetch_size
        self.cache_start, self.cache = start, content
        return content[:size]


def get_face_archive():
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / 'DeepfakeTIMIT.tar.gz'
    expected = '226611200'
    info = requests.get('https://zenodo.org/api/records/4068245', timeout=60)
    info.raise_for_status()
    metadata = info.json()
    (DATA / 'DEEPFAKETIMIT_SOURCE.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    file = next(item for item in metadata['files'] if item['key'] == path.name)
    if str(file['size']) != expected:
        raise ValueError('Unexpected archive size')
    if not path.exists():
        with requests.get(file['links']['self'], stream=True, timeout=(20, 90)) as res:
            res.raise_for_status()
            received = 0
            with path.with_suffix('.partial').open('wb') as out:
                for block in res.iter_content(2**20):
                    received += len(block)
                    if received > int(expected):
                        raise ValueError('Archive exceeded pinned size')
                    out.write(block)
                    if received // 2**20 % 25 == 0:
                        print('face archive MiB', received // 2**20, flush=True)
            path.with_suffix('.partial').replace(path)
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'md5').hexdigest()
    if 'md5:' + actual != file['checksum']:
        raise ValueError('Official archive checksum mismatch')
    with tarfile.open(path) as archive:
        names = archive.getnames()
        print('face archive examples', names[:30], flush=True)
        for name in names:
            if name.lower().endswith(('.txt', '.md')):
                item = archive.extractfile(name)
                if item:
                    print(name, item.read(15000).decode('utf-8', errors='replace'), flush=True)


def prepare_lipsync():
    DATA.mkdir(parents=True, exist_ok=True)
    repo = 'Pinch-Research/lipsync-hdtf-training-data'
    revision = '288d7f355e87f8317bfb4d6b885f60e6ad1c2c22'
    base = f'https://huggingface.co/datasets/{repo}/resolve/{revision}/'
    response = requests.get(base + 'xdub_teacher_pairs_manifest.json', timeout=60)
    response.raise_for_status()
    pairs = response.json()
    card = requests.get(base + 'README.md', timeout=60)
    card.raise_for_status()
    (DATA / 'LIPSYNC_SOURCE_README.md').write_text(card.text, encoding='utf-8')
    grouped = defaultdict(list)
    for row in pairs:
        # Different recording suffixes still represent the same human identity.
        speaker = row['src_speaker'].rstrip('0123456789')
        grouped[speaker].append(row)
    speakers = sorted(grouped)
    random.Random(20261006).shuffle(speakers)
    archive_repo = 'global-optima-research/HDTF'
    archive_revision = '6f9ed465f761b8378c690be4f86f090634281584'
    remote = RemoteZip(f'https://huggingface.co/datasets/{archive_repo}/resolve/{archive_revision}/clips.zip')
    archive = zipfile.ZipFile(remote)
    originals = defaultdict(list)
    for name in archive.namelist():
        if name.endswith('.mp4'):
            speaker = Path(name).stem.split('_')[1].rstrip('0123456789')
            originals[speaker].append(name)
    speakers = [speaker for speaker in speakers if len(originals[speaker]) >= 2 and len(grouped[speaker]) >= 2][:12]
    if len(speakers) != 12:
        raise ValueError('Insufficient matching real/fake identities')
    rows = []
    for index, speaker in enumerate(speakers):
        split = 'test' if index < 2 else 'val' if index < 4 else 'train'
        selected = [(0, name, None) for name in sorted(originals[speaker])[:2]]
        selected += [(1, pair['id'], pair) for pair in sorted(grouped[speaker], key=lambda p: p['id'])[:2]]
        for label, name, pair in selected:
            output = DATA / (hashlib.sha256(('lip:' + name).encode()).hexdigest()[:24] + '.mp4')
            if not output.exists():
                if label == 0:
                    content = archive.read(name)
                else:
                    with requests.get(base + 'xdub_teacher_pairs/videos/' + name + '.mp4', stream=True, timeout=90) as res:
                        res.raise_for_status()
                        content = res.raw.read(12 * 2**20 + 1)
                if len(content) > 12 * 2**20:
                    raise ValueError('Lip-sync clip exceeds byte budget')
                output.write_bytes(content)
            with output.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            rows.append({'path': str(output.resolve()), 'label': label, 'group': 'HDTF-speaker:' + speaker,
                         'split': split, 'source_model': 'X-Dub' if label else 'HDTF', 'sha256': digest,
                         'bytes': output.stat().st_size, 'category': 'lip-sync' if label else 'real',
                         'repository': repo if label else archive_repo, 'revision': revision if label else archive_revision,
                         'file_name': name, 'matching': 'speaker matched, NOT identical source segment'})
        print('lip-sync speakers', index + 1, '/ 12; clips', len(rows), 'archive_bytes', remote.received, flush=True)
    (DATA / 'lipsync_manifest.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')


def frame_digest(path):
    digest = hashlib.sha256()
    for item in sorted(path.glob('*.jpg')):
        digest.update(item.name.encode())
        digest.update(item.read_bytes())
    return digest.hexdigest()


def prepare_faces():
    path = DATA / 'DeepfakeTIMIT.tar.gz'
    if not path.exists():
        get_face_archive()
    # Preserve original licence notice in full (research-only use).
    res = requests.get('https://conradsanderson.id.au/vidtimit/', timeout=60)
    res.raise_for_status()
    (DATA / 'VIDTIMIT_LICENSE_SOURCE.html').write_text(res.text, encoding='utf-8')
    members = {}
    with tarfile.open(path) as archive:
        for member in archive.getmembers():
            if '/higher_quality/' in member.name and member.name.endswith('.avi'):
                target = Path(member.name).parent.name
                swapped = Path(member.name).stem.rsplit('-', 1)[-1]
                pair = tuple(sorted((target, swapped)))
                members.setdefault(pair, {}).setdefault(target, []).append(member.name)
        pairs = sorted(members)
        random.Random(20261006).shuffle(pairs)
        pairs = [p for p in pairs if len(members[p]) == 2][:12]
        if len(pairs) != 12:
            raise ValueError('Need twelve distinct swap pairs')
        rows = []
        for index, pair in enumerate(pairs):
            split = 'test' if index < 2 else 'val' if index < 4 else 'train'
            for target in pair:
                # One full source recording per person, not many frame samples
                # masquerading as independent training videos.
                selected = sorted(members[pair][target])[2]
                sentence = Path(selected).name.split('-')[0]
                prefix = f'{target}/video/{sentence}/'
                group = 'VidTIMIT-swap-pair:' + ':'.join(pair)
                real_dir = DATA / hashlib.sha256(('real:' + target + ':' + sentence).encode()).hexdigest()[:24]
                fake_dir = DATA / hashlib.sha256(('fake:' + selected).encode()).hexdigest()[:24]
                fake_dir.mkdir(exist_ok=True)
                if len(list(fake_dir.glob('*.jpg'))) != 6:
                    temporary_video = DATA / (fake_dir.name + '.avi')
                    stream = archive.extractfile(selected)
                    if stream is None:
                        raise ValueError('Missing official fake video')
                    temporary_video.write_bytes(stream.read(12 * 2**20 + 1))
                    cap = cv2.VideoCapture(str(temporary_video))
                    try:
                        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        if count < 6:
                            raise ValueError('Incomplete face-swap source video')
                        for j, frame_index in enumerate(np.linspace(0, count - 1, 6).astype(int)):
                            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
                            ok, frame = cap.read()
                            if not ok:
                                raise ValueError('Unreadable face-swap source frame')
                            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                            image.save(fake_dir / f'{j:02d}.jpg', quality=90)
                    finally:
                        cap.release()
                real_dir.mkdir(exist_ok=True)
                if len(list(real_dir.glob('*.jpg'))) != 6:
                    remote = RemoteZip(f'https://zenodo.org/records/158963/files/{target}.zip')
                    original = zipfile.ZipFile(remote)
                    images = sorted(n for n in original.namelist() if n.startswith(prefix)
                                    and (Path(n).name.isdigit() or n.lower().endswith('.jpg')))
                    if len(images) < 6:
                        raise ValueError('Missing matched authentic source sequence')
                    for j, frame_index in enumerate(np.linspace(0, len(images) - 1, 6).astype(int)):
                        image = Image.open(io.BytesIO(original.read(images[frame_index]))).convert('RGB')
                        image.save(real_dir / f'{j:02d}.jpg', quality=90)
                    print('real source frames', target, sentence, 'download_bytes', remote.received, flush=True)
                for label, directory in ((0, real_dir), (1, fake_dir)):
                    rows.append({'path': str(directory.resolve()), 'label': label, 'group': group, 'split': split,
                                 'source_model': 'DeepfakeTIMIT-HQ' if label else 'VidTIMIT',
                                 'sha256': frame_digest(directory), 'bytes': sum(p.stat().st_size for p in directory.glob('*.jpg')),
                                 'category': 'face-swap' if label else 'real', 'target_identity': target,
                                 'swapped_identity': pair[0] if pair[1] == target else pair[1],
                                 'file_name': selected if label else prefix, 'source_sentence': sentence,
                                 'provenance': 'Six uniform video frames, matched original recording; both swap identities grouped.',
                                 'repository': 'https://zenodo.org/records/4068245' if label else 'https://zenodo.org/records/158963'})
            print('face-swap pairs', index + 1, '/ 12; recordings', len(rows), flush=True)
    (DATA / 'faceswap_manifest.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--lip-sync', action='store_true')
    parser.add_argument('--face-pairs', action='store_true')
    args = parser.parse_args()
    if args.lip_sync:
        prepare_lipsync()
    elif args.face_pairs:
        prepare_faces()
    else:
        get_face_archive()

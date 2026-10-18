"""Bounded v2 expansion for video detection: fresh generators plus fresh
face-swap / lip-sync / talking-head sources.

Carries every v2 row (observed val/test become diagnostic) and adds bounded
subsets of the newly fetched public sources:

- ShareVeo3 (HF)      -> Veo3 text-to-video clips
- GenVidBench (HF)    -> Keling image-to-video + OpenAI Sora scene clips
- AIGVDBench (HF)     -> Pika / Vidu / Luma / OpenSora / Gen-2 clips
- Lipsync-A (HF)      -> DaGAN / DINet / EAT / InfiniteTalk / IP_LAP pairs
- DF40 (HF)           -> deepfacelab / facevid2vid / sadtalker / wav2lip and
                         inswap / faceswap / fsgan / blendface clips
- TalkingHeadBench    -> AniPortrait / EmoPortrait / Hallo / Hallo2 /
                         LivePortrait / Hallo3 fakes
- HDTF videos (HF)    -> fresh real talking-head clips

Observed data never selects or tests: every v2 val/test row becomes
diagnostic, and a fresh test may only contain groups the v2 manifest has
never seen. Local research only; candidates stay inactive, nothing is
pushed or redistributed.
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import re
import tarfile
import time
import zipfile

from prepare_video_manipulations import frame_digest

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/video-training-v3-20261018'
V2_DATA = ROOT / 'data/video-training-v2-20261006'
NEW = ROOT / 'data/new-datasets'
SEED = 20661018

LIPSYNC_A_FAKES = 35
LIPSYNC_A_REALS = 35
DF40_LIP_FAKES = 40
DF40_LIP_REALS = 30
TALKINGHEAD_FAKES = 30
VEO3_CAP = 70
KELING_CAP = 70
SORA_CAP = 51
HDTF_REAL_CAP = 100
DF40_SWAP_FAKES = 40
DF40_SWAP_REALS = 25
AIGVD_CAP = 40

TOKEN_PATTERNS = (re.compile(r'(?<![A-Za-z0-9])id\d{1,5}(?![0-9])'),
                  re.compile(r'(?<![A-Za-z0-9])p\d{2,3}(?![0-9])'),
                  re.compile(r'Clip[+-][\w-]{4,}'),
                  re.compile(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{11}(?![A-Za-z0-9_-])'))
SELECTION_FIELDS = ('identity_image_from', 'identity_video_from', 'driving_video_from',
                    'driving_audio_from', 'real_video_from')


def save(path, value):
    pending = Path(path).with_suffix('.partial.json')
    encoded = json.dumps(value, indent=2)
    for attempt in range(120):
        try:
            pending.write_text(encoded, encoding='utf-8')
            pending.replace(path)
            return
        except PermissionError:
            if attempt == 119:
                raise
            time.sleep(0.5)


def digest(path):
    path = Path(path)
    if path.is_dir():
        return frame_digest(path)
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pick(items, cap, salt):
    order = sorted(items)
    random.Random(f'{SEED}:{salt}').shuffle(order)
    return order[:cap]


class Families:
    def __init__(self):
        self.parent = {}

    def find(self, item):
        self.parent.setdefault(item, item)
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != root:
            self.parent[item], item = root, self.parent[item]
        return root

    def union(self, left, right):
        left, right = self.find(left), self.find(right)
        if left != right:
            self.parent[max(left, right)] = min(left, right)

    def link(self, tokens):
        tokens = sorted(tokens)
        for token in tokens[1:]:
            self.union(tokens[0], token)


def split_rows(rows, salt):
    groups = sorted({row['group'] for row in rows})
    random.Random(f'{SEED}:{salt}').shuffle(groups)
    count_test = max(1, int(len(groups) * .2))
    count_val = max(1, int(len(groups) * .2))
    test = set(groups[:count_test])
    val = set(groups[count_test:count_test + count_val])
    for row in rows:
        row['split'] = 'test' if row['group'] in test else 'val' if row['group'] in val else 'train'


def row_for(path, source, label, category, repository, file_name=None):
    path = Path(path)
    return {'path': str(path.resolve()), 'source_model': source, 'label': int(label),
            'group': None, 'split': None, 'sha256': digest(path),
            'bytes': path.stat().st_size, 'repository': repository,
            'file_name': file_name or path.name, 'category': category}


INVALID_CHARS = {'<': '_', '>': '_', ':': '_', '"': '_', '|': '_', '?': '_', '*': '_'}


def safe_member(name):
    parts = []
    for part in Path(name).parts:
        cleaned = ''.join(INVALID_CHARS.get(character, character) for character in part)
        parts.append(cleaned.rstrip(' .') or '_')
    return Path(*parts)


def write_member(stream, target):
    payload = stream.read()
    if len(payload) < 48 * 2**10:
        raise ValueError('Extracted member suspiciously small')
    target.parent.mkdir(parents=True, exist_ok=True)
    pending = target.with_suffix('.partial')
    pending.write_bytes(payload)
    pending.replace(target)
    return target


def pull_zip(zip_path, names, root):
    pulled = {}
    with zipfile.ZipFile(zip_path) as archive:
        for name in names:
            target = root / safe_member(name)
            if not target.exists():
                if not 48 * 2**10 <= archive.getinfo(name).file_size <= 64 * 2**20:
                    pulled[name] = None
                    continue
                write_member(archive.open(name), target)
            pulled[name] = target
    return pulled


def pull_tar(tar_path, names, root):
    pulled = {}
    with tarfile.open(tar_path) as archive:
        members = {member.name: member for member in archive.getmembers() if member.isfile()}
        for name in names:
            member = members.get(name)
            if member is None:
                pulled[name] = None
                continue
            target = root / safe_member(name)
            if not target.exists():
                if not 48 * 2**10 <= member.size <= 64 * 2**20:
                    pulled[name] = None
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    pulled[name] = None
                    continue
                write_member(stream, target)
            pulled[name] = target
    return pulled


def resolve(waiting):
    families = Families()
    for entry, tokens in waiting:
        families.link(tokens)
    for entry, tokens in waiting:
        entry['group'] = families.find(sorted(tokens)[0])
    return [entry for entry, _ in waiting]


def df40_tokens(prefix, method, name):
    stem = Path(name).stem
    if method == 'deepfacelab':
        return {f'{prefix}:deeplab:{stem}'}
    parts = Path(name).parts
    room = parts[1] if len(parts) > 2 else 'set'
    tokens = {f'{prefix}:{room}:{match}' for match in re.findall(r'id\d+', stem)}
    tokens.update(f'{prefix}:{room}:yt:{match}' for match in
                  re.findall(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{11}(?![A-Za-z0-9_-])', stem))
    return tokens or {f'{prefix}:{room}:{stem}'}


def build_lipsync_a():
    waiting = []
    base = NEW / 'lipsync_a'
    for method in ('DaGAN', 'DINet', 'EAT', 'InfiniteTalk', 'IP_LAP'):
        folder = base / method
        if not (folder / '1_fake').is_dir():
            print('lipsync_a not fetched yet:', method, flush=True)
            continue
        metadata = {}
        selection = folder / 'selection.json'
        if selection.exists():
            for entry in json.loads(selection.read_text()):
                stem = Path(str(entry['name'])).stem
                tokens = set()
                for field in SELECTION_FIELDS:
                    text = str(entry.get(field, ''))
                    for pattern in TOKEN_PATTERNS:
                        # Directory names such as VCTK-Corpus/VFHQ_videos are
                        # also 11 characters; real identity IDs carry digits.
                        tokens.update(token for token in pattern.findall(text)
                                      if any(character.isdigit() for character in token))
                metadata[stem] = tokens
                for field in ('driving_video', 'real_video'):
                    name = entry.get(field)
                    if name:
                        linked = Path(str(name)).stem
                        metadata.setdefault(linked, set()).update(tokens)
        for label, sub, cap, salt in ((1, '1_fake', LIPSYNC_A_FAKES, 'fake'),
                                      (0, '0_real', LIPSYNC_A_REALS, 'real')):
            files = [p for p in (folder / sub).glob('*.mp4')]
            for path in pick(files, cap, f'lipsync-a-{method}-{salt}'):
                tokens = {f'lipsynca:{method}:{path.stem}'}
                tokens.update(f'lipsynca:{token}' for token in metadata.get(path.stem, ()))
                waiting.append((row_for(path, f'LipsyncA-{method}', label, 'lip-sync',
                                        'https://huggingface.co/datasets/AnsonShe/LipSync-A'),
                                tokens))
    rows = resolve(waiting)
    split_rows(rows, 'lipsync-a')
    print('lipsync_a rows', len(rows), flush=True)
    return rows


def build_df40_lip():
    waiting = []
    base = NEW / 'df40_vid_lipsync' / 'test'
    for method in ('deepfacelab', 'facevid2vid', 'sadtalker', 'wav2lip'):
        zip_path = base / f'{method}.zip'
        if not zip_path.is_file():
            print('df40_vid_lipsync not fetched yet:', method, flush=True)
            continue
        with zipfile.ZipFile(zip_path) as archive:
            names = [n for n in archive.namelist()
                     if n.lower().endswith('.mp4') and '__MACOSX' not in n]
        if method == 'deepfacelab':
            chosen = ([(1, n) for n in pick([n for n in names if '/fake/' in n],
                                            DF40_LIP_FAKES, 'df40-lip-deeplab-fake')]
                      + [(0, n) for n in pick([n for n in names if '/real/' in n],
                                              DF40_LIP_REALS, 'df40-lip-deeplab-real')])
        else:
            chosen = [(1, n) for n in pick(names, DF40_LIP_FAKES, f'df40-lip-{method}')]
        pulled = pull_zip(zip_path, [n for _, n in chosen],
                          DATA / 'extracted' / 'df40_lip' / method)
        for label, name in chosen:
            path = pulled.get(name)
            if path is None:
                continue
            waiting.append((row_for(path, f'DF40Lip-{method}', label, 'lip-sync',
                                    'https://huggingface.co/datasets/ohjoonhee/DF40-Fake-Videos',
                                    file_name=name), df40_tokens('df40lip', method, name)))
    rows = resolve(waiting)
    split_rows(rows, 'df40-lip')
    print('df40 lipsync rows', len(rows), flush=True)
    return rows


def build_talkinghead():
    waiting = []
    fake_root = NEW / 'talkingheadbench' / 'fake'
    methods = (('AniPortraitAudio', fake_root / 'AniPortraitAudio'),
               ('AniPortraitVideo', fake_root / 'AniPortraitVideo'),
               ('EmoPortrait', fake_root / 'EmoPortrait'),
               ('Hallo', fake_root / 'Hallo'),
               ('Hallo2', fake_root / 'Hallo2'),
               ('LivePortrait', fake_root / 'LivePortrait'))
    extra = fake_root / 'additional_dataset'
    if extra.is_dir():
        methods += tuple((sub.name, sub) for sub in sorted(p for p in extra.iterdir() if p.is_dir()))
    for method, folder in methods:
        if not folder.is_dir():
            print('talkingheadbench not fetched yet:', method, flush=True)
            continue
        files = [p for p in folder.rglob('*.mp4')]
        for path in pick(files, TALKINGHEAD_FAKES, f'thb-{method}'):
            match = re.search(r'--([A-Za-z0-9_-]{11})_\d+--', path.name)
            token = f'thb:{match.group(1)}' if match else f'thb:{path.stem}'
            waiting.append((row_for(path, f'THB-{method}', 1, 'lip-sync',
                                    'https://huggingface.co/datasets/luchaoqi/TalkingHeadBench'),
                            {token}))
    rows = resolve(waiting)
    split_rows(rows, 'talkinghead')
    print('talkingheadbench rows', len(rows), flush=True)
    return rows


def build_shareveo3():
    tar_dir = NEW / 'shareveo3' / 'generated_videos_veo3_tar'
    tars = sorted(tar_dir.glob('*.tar'))
    if not tars:
        print('shareveo3 not fetched yet', flush=True)
        return []
    names = []
    for tar_path in tars:
        with tarfile.open(tar_path) as archive:
            names += [m.name for m in archive.getmembers()
                      if m.isfile() and m.name.lower().endswith('.mp4')]
    chosen = pick(names, VEO3_CAP, 'shareveo3')
    root = DATA / 'extracted' / 'shareveo3'
    pulled = {}
    for tar_path in tars:
        with tarfile.open(tar_path) as archive:
            available = {m.name for m in archive.getmembers() if m.isfile()}
        wanted = [n for n in chosen if n in available and n not in pulled]
        if wanted:
            pulled.update(pull_tar(tar_path, wanted, root))
    rows = []
    for name in chosen:
        path = pulled.get(name)
        if path is None:
            continue
        entry = row_for(path, 'ShareVeo3', 1, 'generated-video',
                        'https://huggingface.co/datasets/WenhaoWang/ShareVeo3',
                        file_name=name)
        entry['group'] = f'ShareVeo3:{Path(name).stem}'
        rows.append(entry)
    split_rows(rows, 'shareveo3')
    print('shareveo3 rows', len(rows), flush=True)
    return rows


def build_genvidbench():
    rows = []
    base = NEW / 'genvidbench_small' / 'GenVidBench' / '6.7m'
    for zip_name, source, cap, salt in (('keling.zip', 'Keling', KELING_CAP, 'keling'),
                                        ('OpenAI_Sora.zip', 'Sora-Scenes', SORA_CAP, 'sora-scenes')):
        zip_path = base / zip_name
        if not zip_path.is_file():
            print('genvidbench not fetched yet:', zip_name, flush=True)
            continue
        with zipfile.ZipFile(zip_path) as archive:
            names = [n for n in archive.namelist() if not n.endswith('/')
                     and '__MACOSX' not in n and Path(n).suffix.lower() in ('.mp4', '.mov')]
        chosen = pick(names, cap, salt)
        pulled = pull_zip(zip_path, chosen, DATA / 'extracted' / 'genvidbench' / salt)
        cohort = []
        for name in chosen:
            path = pulled.get(name)
            if path is None:
                continue
            entry = row_for(path, source, 1, 'generated-video',
                            'https://huggingface.co/datasets/jian-0/GenVidBench', file_name=name)
            entry['group'] = f'{source}:{Path(name).stem}'
            cohort.append(entry)
        split_rows(cohort, f'genvidbench-{salt}')
        rows.extend(cohort)
    print('genvidbench rows', len(rows), flush=True)
    return rows


def build_aigv():
    rows = []
    sources = (('aigvdbench_small', 'ClosedSource/pika.zip', 'AIGVD-Pika'),
               ('aigvdbench_small', 'ClosedSource/vidu.zip', 'AIGVD-Vidu'),
               ('aigvdbench_small', 'ClosedSource/Luma.zip', 'AIGVD-Luma'),
               ('aigvdbench_small', 'ClosedSource/Opensora.zip', 'AIGVD-OpenSora'),
               ('aigvdbench_gen2', 'ClosedSource/Gen2.zip', 'AIGVD-Gen2'))
    for folder, relative, source in sources:
        zip_path = NEW / folder / relative
        if not zip_path.is_file():
            print('aigvdbench not fetched yet:', relative, flush=True)
            continue
        with zipfile.ZipFile(zip_path) as archive:
            names = [n for n in archive.namelist() if not n.endswith('/')
                     and '__MACOSX' not in n and Path(n).suffix.lower() in ('.mp4', '.mov')
                     and '/real/' not in n.lower()]
        chosen = pick(names, AIGVD_CAP, f'aigv-{source}')
        pulled = pull_zip(zip_path, chosen, DATA / 'extracted' / 'aigv' / source)
        cohort = []
        for name in chosen:
            path = pulled.get(name)
            if path is None:
                continue
            entry = row_for(path, source, 1, 'generated-video',
                            'https://huggingface.co/datasets/AIGVDBench/AIGVDBench', file_name=name)
            entry['group'] = f'{source}:{Path(name).stem}'
            cohort.append(entry)
        split_rows(cohort, f'aigv-{source}')
        rows.extend(cohort)
    print('aigvdbench rows', len(rows), flush=True)
    return rows


def build_df40_swap():
    waiting = []
    base = NEW / 'df40_vid_swap' / 'test'
    for method, source in (('inswap', 'DF40Swap-Inswap'), ('faceswap', 'DF40Swap-FaceSwap'),
                           ('fsgan', 'DF40Swap-FSGAN'), ('blendface', 'DF40Swap-BlendFace')):
        zip_path = base / f'{method}.zip'
        if not zip_path.is_file():
            print('df40_vid_swap not fetched yet:', method, flush=True)
            continue
        with zipfile.ZipFile(zip_path) as archive:
            names = [n for n in archive.namelist()
                     if n.lower().endswith('.mp4') and '__MACOSX' not in n]
        fakes = [n for n in names if '/real/' not in n.lower()]
        reals = [n for n in names if '/real/' in n.lower()]
        chosen = ([(1, n) for n in pick(fakes, DF40_SWAP_FAKES, f'df40-swap-{method}-fake')]
                  + [(0, n) for n in pick(reals, DF40_SWAP_REALS, f'df40-swap-{method}-real')])
        pulled = pull_zip(zip_path, [n for _, n in chosen],
                          DATA / 'extracted' / 'df40_swap' / method)
        for label, name in chosen:
            path = pulled.get(name)
            if path is None:
                continue
            waiting.append((row_for(path, source, label, 'face-swap',
                                    'https://huggingface.co/datasets/ohjoonhee/DF40-Fake-Videos',
                                    file_name=name), df40_tokens('df40swap', method, name)))
    rows = resolve(waiting)
    split_rows(rows, 'df40-swap')
    print('df40 swap rows', len(rows), flush=True)
    return rows


def build_hdtf_real():
    zip_path = NEW / 'hdtf_real' / 'videos.zip'
    if not zip_path.is_file():
        print('hdtf_real not fetched yet', flush=True)
        return []
    with zipfile.ZipFile(zip_path) as archive:
        names = [n for n in archive.namelist()
                 if n.lower().endswith('.mp4') and '__MACOSX' not in n]
    chosen = pick(names, HDTF_REAL_CAP, 'hdtf-real')
    pulled = pull_zip(zip_path, chosen, DATA / 'extracted' / 'hdtf')
    rows = []
    for name in chosen:
        path = pulled.get(name)
        if path is None:
            continue
        entry = row_for(path, 'HDTF-Real', 0, 'real-video',
                        'https://huggingface.co/datasets/global-optima-research/HDTF',
                        file_name=name)
        entry['group'] = f'HDTF-v3:{Path(name).stem}'
        rows.append(entry)
    split_rows(rows, 'hdtf-real')
    print('hdtf real rows', len(rows), flush=True)
    return rows


def carry_v2(rows):
    v2 = json.loads((V2_DATA / 'manifest.json').read_text())
    for row in v2:
        row = dict(row)
        if row['split'] in ('val', 'test'):
            # Observed selection/evaluation rows never select or test again.
            row['split'] = 'diagnostic'
        rows.append(row)
    return v2


def observed_groups():
    return {row['group'] for row in json.loads((V2_DATA / 'manifest.json').read_text())}


def dedupe(rows):
    """Keep one row per exact content hash; identical bytes across sources are
    the same recording and would otherwise leak between split groups."""
    kept, seen, dropped = [], {}, []
    for row in rows:
        previous = seen.get(row['sha256'])
        if previous is None:
            seen[row['sha256']] = row
            kept.append(row)
            continue
        if row['label'] != previous['label']:
            raise ValueError('Conflicting labels for identical data: '
                             f"{previous['source_model']}/{previous['file_name']} vs "
                             f"{row['source_model']}/{row['file_name']}")
        dropped.append((row['source_model'], row['file_name']))
    if dropped:
        print('duplicate rows dropped:', len(dropped), flush=True)
        for entry in dropped[:20]:
            print('  dropped duplicate', entry, flush=True)
    return kept


def rebalance_test(rows, minimum=2):
    """Make the fresh test span at least ``minimum`` sources per class by
    promoting whole unobserved groups out of train/val. Groups move intact,
    so the recording/creator leakage guarantee is preserved."""
    observed = observed_groups()

    def sources(fold, label):
        return {row['source_model'] for row in rows
                if row['split'] == fold and row['label'] == label}

    def balanced():
        return all({row['label'] for row in rows if row['split'] == fold} == {0, 1}
                   for fold in ('train', 'val', 'test'))

    for label in (0, 1):
        while len(sources('test', label)) < minimum:
            known = sources('test', label)
            donors = {}
            for row in rows:
                if (row['split'] in ('train', 'val') and row['label'] == label
                        and row['source_model'] not in known
                        and row['group'] not in observed):
                    donors.setdefault(row['group'], row['split'])
            moved = False
            for group in sorted(donors, key=lambda item: (donors[item] != 'val', item)):
                members = [row for row in rows if row['group'] == group]
                previous = [(row, row['split']) for row in members]
                for row in members:
                    row['split'] = 'test'
                if balanced():
                    moved = True
                    print('  promoted group', group, 'to test for label', label, flush=True)
                    break
                for row, split in previous:
                    row['split'] = split
            if not moved:
                return


def audit(rows):
    groups, hashes = defaultdict(set), {}
    for row in rows:
        if row['label'] not in (0, 1) or row['split'] not in ('train', 'val', 'test', 'diagnostic'):
            raise ValueError('Invalid label/split')
        groups[row['group']].add(row['split'])
        if row['sha256'] in hashes:
            raise ValueError('Duplicate data across combined manifest')
        hashes[row['sha256']] = row['label']
        if digest(Path(row['path'])) != row['sha256']:
            raise ValueError('Dataset file checksum changed')
    if any(len(s) > 1 for s in groups.values()):
        raise ValueError('Recording/creator/speaker leakage')
    if {row['group'] for row in rows if row['split'] == 'test'} & observed_groups():
        raise ValueError('New test contains previously observed groups')
    for fold in ('train', 'val', 'test'):
        if {row['label'] for row in rows if row['split'] == fold} != {0, 1}:
            raise ValueError(f'{fold} split needs both classes')
    per_class = defaultdict(set)
    for row in rows:
        if row['split'] == 'test':
            per_class[row['label']].add(row['source_model'])
    if any(len(s) < 2 for s in per_class.values()):
        detail = {str(label): sorted(names) for label, names in per_class.items()}
        raise ValueError(f'Fresh test needs at least two sources per class: {detail}')


def extra_sources():
    found = []
    expected = (('aigvdbench_small', ['ClosedSource/pika.zip', 'ClosedSource/vidu.zip',
                                      'ClosedSource/Luma.zip', 'ClosedSource/Opensora.zip']),
                ('aigvdbench_gen2', ['ClosedSource/Gen2.zip']),
                ('df40_vid_swap', ['test/inswap.zip', 'test/faceswap.zip',
                                   'test/fsgan.zip', 'test/blendface.zip']),
                ('hdtf_real', ['videos.zip']))
    for folder, relatives in expected:
        if all((NEW / folder / relative).is_file() for relative in relatives):
            found.append(folder)
    return sorted(found)


def prepare():
    DATA.mkdir(parents=True, exist_ok=True)
    manifest = DATA / 'manifest.json'
    sidecar = DATA / 'extra_sources.json'
    signature = extra_sources()
    if manifest.exists() and sidecar.exists() and json.loads(sidecar.read_text()) == signature:
        rows = json.loads(manifest.read_text())
        audit(rows)
        return rows
    rows = []
    carried = len(carry_v2(rows))
    for builder in (build_lipsync_a, build_df40_lip, build_talkinghead, build_shareveo3,
                    build_genvidbench, build_aigv, build_df40_swap, build_hdtf_real):
        rows.extend(builder())
    rows = dedupe(rows)
    rebalance_test(rows)
    audit(rows)
    save(manifest, rows)
    save(sidecar, signature)
    print(json.dumps({'rows': len(rows), 'carried_from_v2': carried,
                      'fresh': len(rows) - carried,
                      'splits': dict(Counter(row['split'] for row in rows)),
                      'sources': dict(Counter(row['source_model'] for row in rows)),
                      'extra_sources': signature}, indent=2), flush=True)
    return rows


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()
    rows = prepare()
    print('manifest ready:', len(rows), 'rows')

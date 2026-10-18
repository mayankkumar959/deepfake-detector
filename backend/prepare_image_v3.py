"""Bounded v2 expansion for image detection: modern generators (+fresh swaps).

Carries every v2 row and adds bounded subsets of the newly fetched sources:

- OpenFakeTiny (HF)  -> gpt-image / Imagen / MJ v6-7 / flux / SD3.5 era fakes
                        plus in-the-wild real web photos.
- Tiny-GenImage (HF) -> ADM / BigGAN / GLIDE / Midjourney / SD 1.4 / 1.5 /
                        VQDM / Wukong fakes plus ImageNet reals.
- OpenForensics / DF40 swap crops are wired in once their downloads land
  (functions below skip loudly while the archives are absent).

Observed data never selects or tests: every v2 val/test row becomes
diagnostic, and the fresh test may only contain groups the v2 manifest has
never seen (at least two sources per class). Local research only; datasets
stay unpublished, candidates stay inactive.
"""
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import random
import sys
import time
import zipfile

# Windows consoles default to cp1252; dataset model names contain characters
# like U+2011 (non-breaking hyphen) that must not kill a long training run.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import pyarrow.parquet as pq
from PIL import Image

from prepare_image_v2 import DATA as V2_DATA, consolidate, image_info, save, sha

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/general-ai-training-v3-20261018'
NEW = ROOT / 'data/new-datasets'
SEED = 20261018

CAP_FAKE_PER_MODEL = 120
MAX_FAKE_MODELS = 12
CAP_REAL_PER_SOURCE = 100
CAP_REALS = 400
TINY_FAKE_PER_GENERATOR = 400
TINY_REALS = 300
OF_CAP_REAL = 500
OF_CAP_FAKE = 500
DF40_PAIRS_PER_METHOD = 150

OPENFAKE_REPO = 'https://huggingface.co/datasets/ComplexDataLab/OpenFakeTiny'
TINYGEN_REPO = 'https://huggingface.co/datasets/TheKernel01/Tiny-GenImage'
TINY_GENERATORS = ['Real', 'ADM', 'BigGAN', 'GLIDE', 'Midjourney', 'SD14', 'SD15', 'VQDM', 'Wukong']


def status(value):
    save(DATA / 'preparation_status.json', {'updated_at_unix': time.time(), **value})
    print(json.dumps(value), flush=True)


def store(repo, tag, identity, payload, rows, label, source):
    """Decode one stored image, save it locally under a stable hashed name."""
    slug = hashlib.sha256(f'{repo}|{identity}'.encode()).hexdigest()[:24]
    path = DATA / (slug + '.png')
    if not path.exists():
        with Image.open(io.BytesIO(payload)) as image:
            image.convert('RGB').save(path, format='PNG')
    try:
        info = image_info(path)
    except ValueError:
        # Same min-224 / visual-information guard as the other image sources.
        path.unlink(missing_ok=True)
        return False
    rows.append({'path': str(path), 'label': label, 'source': source,
                 'group': f'{tag}:{identity}', 'file_name': identity,
                 'publisher_archive': repo, 'sha256': sha(path), **info})
    return True


def select_indices(indices, cap, seed):
    """Deterministic subsample: seeded shuffle of positions, keep first `cap`."""
    order = sorted(range(len(indices)))
    random.Random(seed).shuffle(order)
    return {indices[position] for position in order[:cap]}


def parquet_meta(path, columns):
    table = pq.read_table(path, columns=columns)
    return {name: table[name].to_pylist() for name in columns}


def add_parquet(folder, repo, tag, group_column, model_names, fake_takes,
                fake_marker, max_reals, rows, min_bytes):
    """Bounded extraction from a downloaded HF parquet image dataset.

    Caps are applied per generator across the whole dataset (not per parquet
    file), so a multi-shard download cannot silently multiply the budget.
    """
    parquets = sorted(folder.rglob('*.parquet'))
    total = sum(path.stat().st_size for path in parquets)
    if total < min_bytes:
        raise ValueError(f'{tag}: parquet download incomplete ({total/2**30:.2f} GiB)')
    metas, buckets = [], defaultdict(list)
    for path in parquets:
        meta = parquet_meta(path, ['label', group_column])
        metas.append((path, meta))
        for position, (label, group) in enumerate(zip(meta['label'], meta[group_column])):
            if isinstance(group, str) and group.isdigit():
                group = int(group)
            buckets[(label, group)].append((path, position))
    planned, real_budget = set(), max_reals
    for (label, group), positions in buckets.items():
        if label == fake_marker:
            cap = fake_takes.get(group)
        else:
            cap = min(CAP_REAL_PER_SOURCE, real_budget)
        if not cap:
            continue
        order = sorted(range(len(positions)))
        random.Random(f'{SEED}:{tag}:{group}:{label}').shuffle(order)
        chosen = [positions[position] for position in order[:cap]]
        planned.update(chosen)
        if label != fake_marker:
            real_budget -= len(chosen)
    kept = Counter()
    for path, meta in metas:
        handle = pq.ParquetFile(path)
        index = 0
        for batch in handle.iter_batches(batch_size=16, columns=['image']):
            for offset in range(batch.num_rows):
                position = index + offset
                if (path, position) not in planned:
                    continue
                label_value = meta['label'][position]
                group_value = meta[group_column][position]
                if isinstance(group_value, str) and group_value.isdigit():
                    group_value = int(group_value)
                fake = label_value == fake_marker
                value = batch.column('image')[offset].as_py()
                payload = value.get('bytes')
                if not payload:
                    continue
                name = model_names.get(group_value, str(group_value)) if isinstance(group_value, int) else str(group_value)
                label = 1 if fake else 0
                if store(repo, tag, f'{path.name}:{position}', payload, rows,
                         label, f'{tag}:{name}'):
                    kept['fake' if fake else 'real'] += 1
                else:
                    kept['guard_skipped'] += 1
            index += batch.num_rows
        status({'status': 'running', 'source': tag, 'file': path.name, 'parsed': index,
                'fake': kept['fake'], 'real': kept['real'],
                'guard_skipped': kept['guard_skipped'], 'rows': len(rows)})
    status({'status': 'running', 'source': tag, 'done': True, **dict(kept)})
    if kept['fake'] < 100:
        raise ValueError(f'{tag}: too few fake images survived the guard')


def add_openfake_tiny(rows):
    folder = NEW / 'openfake_tiny'
    if not folder.exists():
        print('openfake_tiny not fetched yet; skipped', flush=True)
        return
    counts = Counter()
    for path in sorted(folder.rglob('*.parquet')):
        meta = parquet_meta(path, ['label', 'model'])
        for label, model in zip(meta['label'], meta['model']):
            if label == 'fake':
                counts[model] += 1
    # 'reddit' is a scraped source label, not a generator; keep the highest
    # volume real generator names instead of a random mix of tiny/noisy ones.
    models = [model for model, count in counts.most_common()
              if model != 'reddit' and count >= 10]
    chosen = sorted(models[:MAX_FAKE_MODELS])
    print('openfake fake models chosen:', {model: counts[model] for model in chosen}, flush=True)
    add_parquet(folder, OPENFAKE_REPO, 'OpenFakeTiny', 'model', None,
                {model: CAP_FAKE_PER_MODEL for model in chosen}, 'fake',
                CAP_REALS, rows, int(4.2 * 2**30))


def add_tiny_genimage(rows):
    folder = NEW / 'tiny_genimage'
    if not folder.exists():
        print('tiny_genimage not fetched yet; skipped', flush=True)
        return
    names = {index: name for index, name in enumerate(TINY_GENERATORS)}
    takes = {index: TINY_FAKE_PER_GENERATOR for index in range(1, len(TINY_GENERATORS))}
    add_parquet(folder, TINYGEN_REPO, 'TinyGenImage', 'generator', names, takes, 1,
                TINY_REALS, rows, int(7.2 * 2**30))


def stream_array(path, name):
    """Yield objects of a huge JSON file's top-level array without loading it."""
    decoder = json.JSONDecoder()
    chunk = 1 << 22
    with path.open('r', encoding='utf-8') as handle:
        buffer, index, found = '', 0, False
        while not found:
            more = handle.read(chunk)
            if not more:
                raise ValueError(f'Array not found in {path.name}: {name}')
            buffer += more
            key = buffer.find(f'"{name}"')
            if key == -1:
                buffer = buffer[-64:]
                continue
            bracket = buffer.find('[', key)
            if bracket == -1:
                continue
            buffer, index, found = buffer[bracket + 1:], 0, True
        while True:
            while True:  # skip separators, refill when the buffer runs out
                while index < len(buffer) and buffer[index] in ' \t\r\n,':
                    index += 1
                if index < len(buffer):
                    break
                more = handle.read(chunk)
                if not more:
                    return
                buffer, index = buffer[index:] + more, 0
            if buffer[index] == ']':
                return
            try:
                value, end = decoder.raw_decode(buffer, index)
            except ValueError:
                more = handle.read(chunk)
                if not more:
                    raise
                buffer, index = buffer[index:] + more, 0
                continue
            index = end
            if index > chunk:
                buffer, index = buffer[index:], 0
            yield value


def openforensics_labels():
    """File stem -> image label (1 when at least one face region is Fake)."""
    folder = NEW / 'openforensics_val'
    cache = folder / 'labels_cache.json'
    if cache.exists():
        return json.loads(cache.read_text())
    categories = {}
    for value in stream_array(folder / 'Val_poly.json', 'categories'):
        categories[int(value['id'])] = str(value['name']).lower()
    images = {}
    for value in stream_array(folder / 'Val_poly.json', 'images'):
        images[int(value['id'])] = Path(str(value['file_name'])).name
    fake_ids = {index for index, name in categories.items() if name == 'fake'}
    labels = {}
    for value in stream_array(folder / 'Val_poly.json', 'annotations'):
        stem = images.get(int(value['image_id']))
        if stem and int(value['category_id']) in fake_ids:
            labels[stem] = 1
    for stem in images.values():
        labels.setdefault(stem, 0)
    save(cache, labels)
    print('openforensics labels', dict(Counter(labels.values())), flush=True)
    return labels


def add_openforensics(rows):
    folder = NEW / 'openforensics_val'
    archive_path = folder / 'Val.zip'
    if not archive_path.exists():
        print('openforensics not fetched yet; skipped', flush=True)
        return
    if any(row['source'].startswith('OpenForensicsVal') for row in rows):
        print('openforensics already in manifest; skipped', flush=True)
        return
    labels = openforensics_labels()
    rng = random.Random(SEED)
    chosen = []
    for label, cap in ((0, OF_CAP_REAL), (1, OF_CAP_FAKE)):
        names = sorted(stem for stem, value in labels.items() if value == label)
        rng.shuffle(names)
        chosen.extend((label, stem) for stem in names[:cap])
    kept = Counter()
    repo = 'https://zenodo.org/records/5528418'
    with zipfile.ZipFile(archive_path) as archive:
        members = {Path(name).name: name for name in archive.namelist()
                   if name.lower().endswith('.jpg')}
        for label, stem in chosen:
            member = members.get(stem)
            if member is None:
                kept['missing'] += 1
                continue
            if archive.getinfo(member).file_size > 8 * 2**20:
                kept['oversized'] += 1
                continue
            if store(repo, 'OpenForensicsVal', f'val:{stem}', archive.read(member),
                     rows, label, f'OpenForensicsVal:{"fake" if label else "real"}'):
                kept['fake' if label else 'real'] += 1
            else:
                kept['guard_skipped'] += 1
    status({'status': 'running', 'source': 'OpenForensicsVal', **dict(kept)})
    # The validation archive is overwhelmingly fake faces; the real counterpart
    # set is tiny (single digits). Fakes are the point here, so only require a
    # usable fake cohort and never reject the source for its real count.
    if kept['fake'] < 100:
        raise ValueError('OpenForensics: too few images survived the guard')
    if kept['real'] < 1:
        print('openforensics has no real images; fake-only contribution', flush=True)


def add_df40_swaps(rows):
    folder = NEW / 'df40_img_swap'
    if not folder.exists():
        print('df40_img_swap not fetched yet; skipped', flush=True)
        return
    existing = {row['source'] for row in rows}
    for method in ('inswap', 'simswap', 'blendface', 'uniface'):
        source = f'DF40-{method}'
        zip_path = folder / f'{method}.zip'
        if source in existing:
            print(source, 'already in manifest; skipped', flush=True)
            continue
        if not zip_path.exists():
            print(source, 'zip not fetched yet; skipped', flush=True)
            continue
        with zipfile.ZipFile(zip_path) as archive:
            frames = defaultdict(list)
            for name in archive.namelist():
                if name.lower().endswith('.png') and '__MACOSX' not in name:
                    frames[name.split('/')[-2]].append(name)
            order = sorted(frames)
            random.Random(f'{SEED}:{method}').shuffle(order)
            kept = 0
            for pair in order[:DF40_PAIRS_PER_METHOD]:
                names = sorted(frames[pair])
                name = names[len(names) // 2]
                if store('https://huggingface.co/datasets/ManhQuangAI/DF40_train',
                         'DF40-swap', f'{method}:{pair}:{Path(name).name}',
                         archive.read(name), rows, 1, source):
                    # Same identity pair appears across methods: keep one family.
                    rows[-1]['group'] = f'DF40-swap:{pair}'
                    kept += 1
        status({'status': 'running', 'source': source, 'pairs': len(frames),
                'added': kept})
        if kept < 20:
            raise ValueError(f'DF40-{method}: too few frames survived the guard')


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
    seen = set()
    for row in json.loads((V2_DATA / 'manifest.json').read_text()):
        seen.add(row['group'])
        seen.add(row['original_group'])
    return seen


def audit(rows):
    seen = observed_groups()
    groups, hashes, pixels = defaultdict(set), set(), set()
    for row in rows:
        if row['label'] not in (0, 1) or row['split'] not in ('train', 'val', 'test', 'diagnostic'):
            raise ValueError('Invalid label/split')
        if sha(row['path']) != row['sha256']:
            raise ValueError('Image file checksum changed')
        if row['sha256'] in hashes or row['pixel_sha256'] in pixels:
            raise ValueError('Duplicate raw image or decoded pixels')
        hashes.add(row['sha256'])
        pixels.add(row['pixel_sha256'])
        groups[row['group']].add(row['split'])
    if any(len(roles) > 1 for roles in groups.values()):
        raise ValueError('Source/prompt/near-duplicate group leakage')
    test = [row for row in rows if row['split'] == 'test']
    if not test:
        raise ValueError('Fresh test is empty')
    if any(row['group'] in seen or row['original_group'] in seen for row in test):
        raise ValueError('Fresh test contains previously observed groups')
    for label in (0, 1):
        subset = [row for row in test if row['label'] == label]
        if len(subset) < 8 or len({row['source'] for row in subset}) < 2:
            raise ValueError('Fresh test needs at least two sources per class')


def prepare():
    DATA.mkdir(parents=True, exist_ok=True)
    manifest = DATA / 'manifest.json'
    if manifest.exists():
        rows = json.loads(manifest.read_text())
        before = len(rows)
        add_openforensics(rows)
        add_df40_swaps(rows)
        if len(rows) > before:
            status({'status': 'running', 'phase': 'extending_manifest',
                    'added': len(rows) - before})
            rows = consolidate(rows)
            audit(rows)
            save(manifest, rows)
        else:
            audit(rows)
        return rows

    # A crash mid-prepare must not force an hour of re-decoding. Completed
    # stages are checkpointed; the manifest is only written after consolidation.
    checkpoint = DATA / 'preparation_checkpoint.json'
    rows, done = [], set()
    if checkpoint.exists():
        payload = json.loads(checkpoint.read_text())
        rows, done = payload['rows'], set(payload['stages'])
        status({'status': 'running', 'phase': 'resuming_checkpoint',
                'rows': len(rows), 'stages': sorted(done)})

    def mark(stage, function, *arguments):
        if stage in done:
            status({'status': 'running', 'phase': 'checkpoint_skip', 'stage': stage})
            return
        function(*arguments)
        done.add(stage)
        save(checkpoint, {'stages': sorted(done), 'rows': rows})

    if not rows:
        carry_v2(rows)
        status({'status': 'running', 'carried_from_v2': len(rows)})
    mark('openfake', add_openfake_tiny, rows)
    mark('tinygen', add_tiny_genimage, rows)
    mark('openforensics', add_openforensics, rows)
    mark('df40', add_df40_swaps, rows)
    status({'status': 'running', 'phase': 'consolidating', 'rows': len(rows)})
    rows = consolidate(rows)
    audit(rows)
    save(manifest, rows)
    checkpoint.unlink(missing_ok=True)
    status({'status': 'finished', 'images': len(rows),
            'splits': dict(Counter(row['split'] for row in rows)),
            'source_counts': dict(Counter(row['source'] for row in rows))})
    return rows


if __name__ == '__main__':
    prepare()

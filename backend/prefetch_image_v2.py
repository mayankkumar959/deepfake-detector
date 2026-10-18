"""Parallel pre-downloader for the bounded RAISE/Synthbuster image subset.

Fetches only the missing selected ZIP entries with a small thread pool so the
sequential prepare_image_v2 downloader finds them already cached. This script
never writes the manifest: prepare_image_v2 still verifies entry CRCs, local
SHA256 hashes, deduplication and splits exactly as before. Distinct temp-file
suffixes keep a concurrent prepare_image_v2 run safe. Local-only research use.
"""
import hashlib
import json
import random
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

import prepare_image_v2 as prepare


def selected_names():
    """Reconstruct exactly the same bounded selection prepare() uses."""
    real = prepare.EntryReader(prepare.REAL_URL, 1646333296)
    fake = prepare.EntryReader(prepare.FAKE_URL, 12372557226)
    originals = {Path(n).stem: n for n in real.archive.namelist() if n.endswith('.png')}
    sources = defaultdict(dict)
    for name in fake.archive.namelist():
        if name.endswith('.png'):
            sources[name.split('/')[1]][Path(name).stem] = name
    if len(sources) != 9:
        raise ValueError('Expected nine documented Synthbuster generators')
    common = set(originals)
    for values in sources.values():
        common &= set(values)
    names = sorted(common)
    random.Random(prepare.SEED).shuffle(names)
    selected, total = [], 0
    for identity in names:
        sizes = [real.archive.getinfo(originals[identity]).file_size]
        sizes += [fake.archive.getinfo(s[identity]).file_size for s in sources.values()]
        size = sum(sizes)
        if max(sizes) > 8 * 2**20 or size > 32 * 2**20 or total + size > prepare.MAX_BYTES:
            continue
        selected.append(identity)
        total += size
        if len(selected) == prepare.GROUPS:
            break
    if len(selected) != prepare.GROUPS:
        raise ValueError('Selection reconstruction incomplete')
    return real, fake, originals, sources, selected


LOCAL = threading.local()


def readers():
    if not hasattr(LOCAL, 'real'):
        LOCAL.real = prepare.EntryReader(prepare.REAL_URL, 1646333296)
        LOCAL.fake = prepare.EntryReader(prepare.FAKE_URL, 12372557226)
    return LOCAL.real, LOCAL.fake


def fetch(scene):
    index, identity = scene
    real, fake = readers()
    jobs = [('RAISE-1k', real, originals[identity])]
    jobs += [(source, fake, values[identity]) for source, values in sorted(sources.items())]
    fetched = 0
    try:
        for source, reader, name in jobs:
            path = prepare.DATA / (hashlib.sha256(name.encode()).hexdigest()[:24] + '.png')
            if path.exists():
                continue
            payload = reader.read(name)
            pending = path.with_suffix('.prefetch.partial')
            pending.write_bytes(payload)
            pending.replace(path)
            fetched += 1
    except (OSError, ValueError) as exc:
        print('prefetch scene', index + 1, 'failed:', exc, flush=True)
        return index, -1
    return index, fetched


if __name__ == '__main__':
    prepare.DATA.mkdir(parents=True, exist_ok=True)
    status_path = prepare.DATA / 'preparation_status.json'
    done_scenes = 0
    if status_path.exists():
        try:
            done_scenes = int(json.loads(status_path.read_text())['matched_scenes'])
        except (KeyError, ValueError, json.JSONDecodeError):
            done_scenes = 0
    real, fake, originals, sources, selected = selected_names()
    todo = list(enumerate(selected))[done_scenes:]
    print('prefetch scenes', len(todo), 'after', done_scenes, 'of', len(selected), flush=True)
    start = time.monotonic()
    finished = 0
    with ThreadPoolExecutor(max_workers=4) as workers:
        for index, fetched in workers.map(fetch, todo):
            finished += 1
            print('prefetch scene', index + 1, '/', len(selected), 'new_files', fetched,
                  'done', finished, '/', len(todo), 'elapsed_s', round(time.monotonic() - start),
                  flush=True)
    print('prefetch complete', json.dumps({'todo': len(todo), 'elapsed_seconds': round(time.monotonic() - start)}), flush=True)

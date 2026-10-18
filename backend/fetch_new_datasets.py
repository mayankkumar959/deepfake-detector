"""Download the v3 training sources picked from dataset_research_report.md.

Local-only research pipeline: nothing here gets activated or deployed. Every
source below is open for programmatic download (no login, no form) and stays
packed on disk; the v3 prepare scripts slice bounded subsets out of these
archives. Licences are non-commercial research (CC BY-NC*) or permissive as
noted per group -- cite the original papers/datasets when reporting results.

Usage:
    python fetch_new_datasets.py --list
    python fetch_new_datasets.py openfake_tiny tiny_genimage ...

Groups run in the order given (default: the order listed below). Downloads
are resumable: HF snapshot_download skips complete files, Zenodo files resume
from a .part file. A provenance log lands in data/new-datasets/download_log.jsonl.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path

import requests

# The xet transfer experiment on this machine deleted earlier partial progress
# and stalled, so every launch stays on the plain HTTP downloader.
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')

DATA = Path(__file__).resolve().parent / 'data' / 'new-datasets'
LOG = DATA / 'download_log.jsonl'

# name: (kind, locator, patterns, size_gb, note)
GROUPS = {
    # ---- image v3: modern generators (fakes) + fresh face manipulation ----
    'openfake_tiny': ('hf', 'ComplexDataLab/OpenFakeTiny', None, 4.5,
                      'gpt-image/Imagen/MJ6-7/Ideogram/flux/sd3.5 + real web photos, CC BY-NC-4.0'),
    'tiny_genimage': ('hf', 'TheKernel01/Tiny-GenImage', None, 7.8,
                      'ADM/BigGAN/GLIDE/MJ/SD1.4/1.5/VQDM/Wukong + ImageNet reals, CC BY-NC-SA-4.0'),
    'openforensics_val': ('zenodo', 5528418, ['Val.zip', 'Val_poly.json'], 3.1,
                          'in-the-wild face-swap with masks, CC BY-4.0'),
    'df40_img_swap': ('hf', 'ManhQuangAI/DF40_train',
                      ['inswap.zip', 'simswap.zip', 'blendface.zip', 'uniface.zip'], 8.2,
                      'face-swap method crops from DF40, CC BY-NC-4.0 (mirror)'),
    'df40_img_extra': ('hf', 'ManhQuangAI/DF40_train',
                       ['faceswap.zip', 'fsgan.zip', 'e4s.zip', 'mobileswap.zip'], 7.6,
                       'extra face-swap methods from DF40, CC BY-NC-4.0 (mirror)'),
    # ---- video v3: modern generators + fresh face swap / lip-sync ----
    'shareveo3': ('hf', 'WenhaoWang/ShareVeo3',
                  ['generated_videos_veo3_tar/veo3_videos_1.tar',
                   'generated_videos_veo3_tar/veo3_videos_2.tar',
                   'generated_videos_veo3_tar/veo3_videos_3.tar'], 1.7,
                  'Veo 3 corpus slice, CC BY-NC-4.0 (VidProM)'),
    'genvidbench_small': ('hf', 'jian-0/GenVidBench',
                          ['GenVidBench/6.7m/OpenAI_Sora.zip', 'GenVidBench/6.7m/keling.zip'], 1.8,
                          'Sora + Kling clips, research use'),
    'df40_vid_lipsync': ('hf', 'ohjoonhee/DF40-Fake-Videos',
                         ['test/wav2lip.zip', 'test/sadtalker.zip', 'test/deepfacelab.zip',
                          'test/facevid2vid.zip'], 2.6,
                         'fresh lip-sync/re-enactment test clips, CC BY-NC-4.0 (mirror)'),
    'talkingheadbench': ('hf', 'luchaoqi/TalkingHeadBench',
                         ['fake/**', 'audio/**', '*.json'], 1.9,
                         'LivePortrait/AniPortrait/Hallo/Hallo2/EmoPortrait fakes, MIT'),
    'lipsync_a': ('hf', 'AnsonShe/LipSync-A', None, 0.5,
                  'paired real vs DINet lip-sync clips, CC BY-NC-SA-4.0'),
    'aigvdbench_small': ('hf', 'AIGVDBench/AIGVDBench',
                         ['ClosedSource/pika.zip', 'ClosedSource/vidu.zip',
                          'ClosedSource/Luma.zip', 'ClosedSource/Opensora.zip', 'Split/*'], 9.1,
                         'Pika/Vidu/Luma/OpenSora clips + splits, CC BY-4.0'),
    'df40_vid_swap': ('hf', 'ohjoonhee/DF40-Fake-Videos',
                      ['test/inswap.zip', 'test/faceswap.zip', 'test/fsgan.zip',
                       'test/blendface.zip'], 7.2,
                      'fresh face-swap test clips, CC BY-NC-4.0 (mirror)'),
    'aigvdbench_gen2': ('hf', 'AIGVDBench/AIGVDBench', ['ClosedSource/Gen2.zip'], 5.6,
                        'Runway Gen-2 clips, CC BY-4.0'),
    'hdtf_real': ('hf', 'global-optima-research/HDTF', ['videos.zip'], 5.2,
                  'real talking-head videos, research use (Zhang et al. CVPR 2021)'),
}
DEFAULT_ORDER = list(GROUPS)


def free_gb():
    return round(shutil.disk_usage(DATA).free / 2**30, 1)


def dir_bytes(path):
    total = 0
    for item in path.rglob('*'):
        if item.is_file() and '.cache' not in item.parts:
            total += item.stat().st_size
    return total


def hf_group(repo, patterns, dest):
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=repo, repo_type='dataset', allow_patterns=patterns or None,
                      local_dir=dest, max_workers=6)


def zenodo_download(record, key, dest, attempts=3):
    target = dest / key
    url = f'https://zenodo.org/records/{record}/files/{key}?download=1'
    if target.exists():
        print('  zenodo cached', key, flush=True)
        return
    expected = None
    try:
        head = requests.head(url, timeout=60, allow_redirects=True)
        expected = int(head.headers.get('Content-Length', 0)) or None
    except requests.RequestException:
        pass
    part = dest / (key + '.part')
    for attempt in range(1, attempts + 1):
        pos = part.stat().st_size if part.exists() else 0
        if expected and pos == expected:
            break
        headers = {'Range': f'bytes={pos}-'} if pos else {}
        started = time.monotonic()
        try:
            with requests.get(url, stream=True, timeout=(20, 120), headers=headers) as res:
                res.raise_for_status()
                if pos and res.status_code != 206:
                    pos = 0
                mode = 'ab' if pos else 'wb'
                done = pos
                with part.open(mode) as out:
                    for chunk in res.iter_content(2**20):
                        out.write(chunk)
                        done += len(chunk)
                        if done % (256 * 2**20) < 2**20:
                            rate = done / max(time.monotonic() - started, 1) / 2**20
                            print(f'  zenodo {key} {done/2**30:.2f} GB '
                                  f'({rate:.1f} MB/s this leg)', flush=True)
        except (requests.RequestException, OSError) as exc:
            print(f'  zenodo {key} attempt {attempt} failed: {exc!r}', flush=True)
            time.sleep(5 * attempt)
            continue
        if expected is None or part.stat().st_size == expected:
            break
    if expected and part.stat().st_size != expected:
        raise RuntimeError(f'{key}: incomplete {part.stat().st_size}/{expected} bytes')
    part.rename(target)
    print('  zenodo done', key, round(target.stat().st_size / 2**30, 2), 'GB', flush=True)


def run_group(name):
    kind, locator, patterns, size_gb, note = GROUPS[name]
    dest = DATA / name
    dest.mkdir(parents=True, exist_ok=True)
    print(f'[{name}] {kind} {locator} ~{size_gb} GB -- {note}', flush=True)
    print(f'[{name}] free before: {free_gb()} GB on data drive', flush=True)
    started = time.monotonic()
    status = 'ok'
    try:
        if kind == 'hf':
            hf_group(locator, patterns, dest)
        elif kind == 'zenodo':
            for key in patterns:
                zenodo_download(locator, key, dest)
        else:
            raise ValueError(f'unknown kind {kind}')
    except Exception as exc:  # keep the queue moving, report at the end
        status = f'error: {exc!r}'
        print(f'[{name}] FAILED: {exc!r}', flush=True)
    elapsed = round(time.monotonic() - started)
    got = dir_bytes(dest)
    print(f'[{name}] {status} in {elapsed}s, {got / 2**30:.2f} GB now on disk, '
          f'free after: {free_gb()} GB', flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps({'group': name, 'locator': str(locator), 'status': status,
                                 'seconds': elapsed, 'bytes': got, 'finished_unix': time.time()}) + '\n')
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('groups', nargs='*', help='group names (default: priority order)')
    parser.add_argument('--list', action='store_true', help='list groups and exit')
    args = parser.parse_args()
    if args.list:
        for name in DEFAULT_ORDER:
            kind, locator, _, size_gb, note = GROUPS[name]
            print(f'{name:20s} {size_gb:5.1f} GB  {kind:6s} {note}')
        return
    names = args.groups or DEFAULT_ORDER
    unknown = [n for n in names if n not in GROUPS]
    if unknown:
        raise SystemExit(f'unknown groups: {unknown}')
    DATA.mkdir(parents=True, exist_ok=True)
    total = sum(GROUPS[n][3] for n in names)
    print(f'fetch plan: {len(names)} groups, ~{total:.1f} GB total', flush=True)
    failures = []
    for name in names:
        if run_group(name) != 'ok':
            failures.append(name)
    print('fetch run complete', json.dumps({'groups': names, 'failures': failures,
                                            'free_gb': free_gb()}), flush=True)


if __name__ == '__main__':
    main()

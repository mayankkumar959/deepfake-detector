"""LOCAL-only compression-augmented video head. Never modifies production.

Frozen SigLIP; train a video classifier, not a full video foundation model.
Fresh test groups are evaluated only after validation-only model selection.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

import cv2
import imageio_ffmpeg
import joblib
import numpy as np
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import balanced_accuracy_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import torch

import train_video_candidate as old
from prepare_video_v2 import DATA, audit

OUT = old.ROOT / 'runs/candidate-video-v2-20261006'
CONFIG = {'version': 2, 'frames': 6, 'window_seconds': 2.0, 'border_crop': .08,
          'h264_crf': 35, 'max_edge': 480, 'preset': 'ultrafast',
          'features': 'SigLIP mean/std/absolute-delta + gray residual FFT gradient temporal statistics',
          'folder_augmentation': 'six sampled frames encoded at 3fps; NOT a full original transcode'}


def sample(path):
    path = Path(path)
    if path.is_dir():
        items = sorted(path.glob('*.jpg'))
        if len(items) != 6:
            raise ValueError('Expected six sampled source frames')
        images = [Image.open(p).convert('RGB') for p in items]
    else:
        cap = cv2.VideoCapture(str(path))
        try:
            count, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS)
            if count < 6 or not np.isfinite(fps) or fps <= 0:
                raise ValueError('Insufficient readable video')
            span = min(count - 1, int(2 * fps))
            start = (count - 1 - span) // 2
            images = []
            for index in np.linspace(start, start + span, 6).astype(int):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
                ok, frame = cap.read()
                if not ok:
                    raise ValueError('Could not decode sampled frame')
                images.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        finally:
            cap.release()
    result = []
    for image in images:
        w, h = image.size
        x, y = int(w * .08), int(h * .08)
        result.append(image.crop((x, y, w-x, h-y)).resize((224, 224)))
    old.require_visual_information(result)
    return result


def texture(images):
    """Source-agnostic visual measurements; no filename/codec/duration features."""
    seq, grays = [], []
    for image in images:
        gray = np.asarray(image.convert('L'), dtype=np.float32) / 255
        grays.append(gray)
        residual = gray - cv2.GaussianBlur(gray, (5, 5), 0)
        gx, gy = np.gradient(gray)
        magnitude = np.sqrt(gx*gx + gy*gy)
        spectrum = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(residual))))
        yy, xx = np.indices(gray.shape)
        radius = np.sqrt((xx-112)**2 + (yy-112)**2) / 159
        rings = [float(spectrum[(radius >= a) & (radius < b)].mean())
                 for a, b in zip(np.linspace(0, 1, 9)[:-1], np.linspace(0, 1, 9)[1:])]
        values = list(np.quantile(np.abs(residual), [.25, .5, .75, .9, .99]))
        values += list(np.quantile(magnitude, [.25, .5, .75, .9, .99])) + rings
        values += [float(gray.std()), float(residual.std()), float(cv2.Laplacian(gray, cv2.CV_32F).var())]
        seq.append(values)
    differences = np.abs(np.diff(np.stack(grays), axis=0))
    return np.concatenate([old.aggregate(np.array(seq)),
                           np.quantile(differences, [.25, .5, .75, .9, .99])]).astype(np.float32)


def extract(images, model, processor):
    with torch.inference_mode():
        # Six-image batch benchmarked against batch2: identical local features,
        # better CPU throughput. This candidate is not the 1GB cloud service.
        inputs = processor(images=images, return_tensors='pt')
        sequence = model.vision_model(pixel_values=inputs['pixel_values']).last_hidden_state.mean(dim=1).numpy()
    return np.concatenate([old.aggregate(sequence), texture(images)])


def transcode(path, target):
    if target.exists():
        return target
    executable = imageio_ffmpeg.get_ffmpeg_exe()
    command = [executable, '-hide_banner', '-loglevel', 'error', '-nostdin', '-n']
    path = Path(path)
    if path.is_dir():
        # Original JPEG samples have no reliable timestamp sequence. This is
        # deliberately documented separately from actual full-video encoding.
        items = sorted(path.glob('*.jpg'))
        if len(items) != 6 or [p.name for p in items] != ['%02d.jpg' % i for i in range(6)]:
            raise ValueError('Unexpected sampled frame naming')
        command += ['-framerate', '3', '-i', str(path / '%02d.jpg')]
    else:
        command += ['-threads', '1', '-i', str(path)]
    # Unique temporary name allows a safe resume even after a stopped encode.
    pending = target.with_name(target.stem + '.' + uuid.uuid4().hex + '.partial.mp4')
    command += ['-vf', "scale='min(iw,480)':'min(ih,480)':force_original_aspect_ratio=decrease:force_divisible_by=2",
                '-an', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '35',
                '-pix_fmt', 'yuv420p', '-threads', '1', '-movflags', '+faststart', str(pending)]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if proc.returncode:
        raise RuntimeError('H264 transcode failed: ' + proc.stderr[-600:])
    pending.replace(target)
    return target


def domain(row):
    source = row['source_model']
    if source == 'VidTIMIT' or source.startswith('DeepfakeTIMIT'):
        return 'face-swap'
    return 'lip-sync' if source in ('HDTF', 'X-Dub') else 'generated-video'


def weights(rows):
    counts = Counter((domain(r), r['label']) for r in rows)
    return np.array([len(rows)/(len(counts)*counts[domain(r), r['label']]) for r in rows])


def stamp():
    return {**CONFIG, 'encoder_sha256': old.sha(old.BASE / 'model.safetensors'),
            'processor_sha256': old.sha(old.BASE / 'preprocessor_config.json'),
            'config_sha256': old.sha(old.BASE / 'config.json')}


def evaluation(rows, labels, probs):
    result = old.metrics(labels, probs)
    result['examples'] = result.pop('videos')
    groups = sorted({r['group'] for r in rows})
    result['independent_source_groups'] = len(groups)
    correct = probs >= .5
    correct = correct == labels
    totals = np.array([[sum(correct[i] for i,r in enumerate(rows) if r['group']==g),
                        sum(r['group']==g for r in rows)] for g in groups])
    rng = np.random.default_rng(20661006)
    draws = rng.integers(0,len(groups),(1000,len(groups)))
    sums = totals[draws].sum(axis=1)
    result['group_bootstrap_accuracy_95_interval'] = np.quantile(sums[:,0]/sums[:,1],[.025,.975]).tolist()
    result['interval_note'] = 'Bootstrap source groups; tiny face/lip cohorts and unknown cross-source overlap limit inference. Wilson interval assumes independent examples.'
    return result


def collect(rows):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'h264').mkdir(exist_ok=True)
    config = stamp()
    config_path = OUT / 'feature_config.json'
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise ValueError('Feature configuration changed: use another output folder')
    old.save_json(config_path, config)
    old.save_json(OUT/'training_status.json',{'status':'running','phase':'feature_extraction','pid':os.getpid(),
                                           'completed':0,'total':len(rows),'started_at_unix':time.time()})
    model, processor = old.load_encoder()
    cv2.setNumThreads(1)
    clean, compressed = [], []
    start = time.monotonic()
    for index, row in enumerate(rows):
        key = row['sha256']
        cache = OUT / (key + '.npz')
        if cache.exists():
            with np.load(cache) as data:
                a, b = data['clean'], data['h264']
        else:
            original = Path(row['path'])
            a = extract(sample(original), model, processor)
            encoded = transcode(original, OUT / 'h264' / (key + '.mp4'))
            b = extract(sample(encoded), model, processor)
            pending = cache.with_suffix('.partial.npz')
            np.savez_compressed(pending, clean=a, h264=b)
            pending.replace(cache)
        clean.append(a)
        compressed.append(b)
        print('v2 features', index+1, '/', len(rows), 'elapsed_s', round(time.monotonic()-start), flush=True)
        old.save_json(OUT/'training_status.json',{'status':'running','phase':'feature_extraction','pid':os.getpid(),
                                               'completed':index+1,'total':len(rows),'elapsed_seconds':round(time.monotonic()-start),
                                               'updated_at_unix':time.time()})
    del model, processor
    clean, compressed = np.stack(clean), np.stack(compressed)
    if not np.isfinite(clean).all() or not np.isfinite(compressed).all():
        raise ValueError('Nonfinite video features')
    return clean, compressed


def train():
    rows = json.loads((DATA / 'manifest.json').read_text())
    audit(rows)
    clean, compressed = collect(rows)
    config = stamp()
    labels = np.array([r['label'] for r in rows])
    domains = np.array([domain(r) for r in rows])
    ids = {s: np.array([i for i, r in enumerate(rows) if r['split'] == s])
           for s in ('train', 'val', 'test', 'diagnostic')}
    fit, val = ids['train'], ids['val']
    old.save_json(OUT/'training_status.json',{'status':'running','phase':'validation_model_selection','pid':os.getpid(),
                                           'updated_at_unix':time.time()})
    trial_rows, best = [], None
    for use_texture in (False, True):
        width = clean.shape[1] if use_texture else 2304
        for c in (.001, .01, .1, 1):
            classifier = make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=1500, random_state=20661006))
            classifier.fit(np.concatenate([clean[fit,:width], compressed[fit,:width]]), np.tile(labels[fit],2),
                           logisticregression__sample_weight=np.tile(weights([rows[i] for i in fit]),2))
            predictions = classifier.predict(np.concatenate([clean[val,:width], compressed[val,:width]]))
            truth, groups = np.tile(labels[val],2), np.tile(domains[val],2)
            scores = {d: float(balanced_accuracy_score(truth[groups==d], predictions[groups==d])) for d in sorted(set(groups))}
            score = float(np.mean(list(scores.values())))
            trial_rows.append({'C':c, 'texture':use_texture, 'macro_domain_balanced_accuracy':score, 'domain_scores':scores})
            print('validation', trial_rows[-1], flush=True)
            if best is None or score > best[0]:
                best = score, classifier, width, c, use_texture
    for depth in (8, None):
        classifier = ExtraTreesClassifier(n_estimators=200,max_depth=depth,min_samples_leaf=3,
                                          max_features=.2,n_jobs=2,random_state=20661006)
        classifier.fit(np.concatenate([clean[fit],compressed[fit]]),np.tile(labels[fit],2),
                       sample_weight=np.tile(weights([rows[i] for i in fit]),2))
        predictions = classifier.predict(np.concatenate([clean[val],compressed[val]]))
        truth, groups = np.tile(labels[val],2), np.tile(domains[val],2)
        scores = {d:float(balanced_accuracy_score(truth[groups==d],predictions[groups==d])) for d in sorted(set(groups))}
        score = float(np.mean(list(scores.values())))
        trial_rows.append({'model':'extra-trees','max_depth':depth,'macro_domain_balanced_accuracy':score,'domain_scores':scores})
        print('validation',trial_rows[-1],flush=True)
        if best is None or score > best[0]:
            best = score,classifier,clean.shape[1],None,True
    _, classifier, width, c, use_texture = best
    pending = OUT / 'video_head.partial.joblib'
    joblib.dump(classifier, pending)
    pending.replace(OUT / 'video_head.joblib')
    report = {'status':'experimental_local_only', 'config':config, 'head_sha256':old.sha(OUT/'video_head.joblib'),
              'manifest_sha256':old.sha(DATA/'manifest.json'), 'selected_C':c, 'selected_texture':use_texture,
              'selected_model':type(classifier).__name__,
              'feature_width':width, 'validation_trials':trial_rows,
              'split_counts':{s:dict(Counter(rows[i]['source_model'] for i in ix)) for s,ix in ids.items()},
              'split_group_counts':{s:len({rows[i]['group'] for i in ix}) for s,ix in ids.items()},
              'limitations':['Frozen image encoder + trained video statistical head, not a fully fine-tuned video backbone.',
                  'Scores are uncalibrated classifier support, not authenticity probabilities.',
                  'Visual only: does not test audio or audio/video synchronisation.',
                  'H264 CRF35 stress is not actual WhatsApp transport.',
                  'Face cohorts use six selected frames; H264 augmentation is a sampled-sequence encode, not full originals.',
                  'HQ/LQ swaps and multiple clips from the same identity are dependent examples, not independent new recordings.',
                  'Small, source-limited benchmark; watermark, codec, generator and scene shortcuts remain possible.',
                  'Speaker-matched lip-sync examples are not identical original source segments.',
                  'Old observed test is diagnostic only; fresh test groups exclude every old group.',
                  'No guarantee for every camera video or unseen generation method.']}
    for fold in ('test', 'diagnostic'):
        ix = ids[fold]
        report[fold] = {}
        for name, values in [('clean',clean), ('h264',compressed)]:
            probs = classifier.predict_proba(values[ix,:width])[:,1]
            report[fold][name] = {'overall':evaluation([rows[i] for i in ix],labels[ix],probs), 'per_source':{},
                                  'predictions':[{'path':rows[i]['path'],'source':rows[i]['source_model'],
                                                  'label':int(labels[i]),'support':float(p)} for i,p in zip(ix,probs)]}
            full = np.array([not Path(rows[i]['path']).is_dir() for i in ix])
            report[fold][name]['full_video_only'] = evaluation([rows[i] for i,m in zip(ix,full) if m],labels[ix][full],probs[full])
            for source in sorted({rows[i]['source_model'] for i in ix}):
                mask = np.array([rows[i]['source_model']==source for i in ix])
                report[fold][name]['per_source'][source] = evaluation([rows[i] for i,m in zip(ix,mask) if m],labels[ix][mask],probs[mask])
    old.save_json(OUT/'report.json', report)
    old.save_json(OUT/'training_status.json',{'status':'finished_experimental','phase':'fresh_test_evaluated','pid':os.getpid(),
                                           'report':'report.json','updated_at_unix':time.time(),
                                           'fresh_clean':report['test']['clean']['overall'],
                                           'fresh_h264':report['test']['h264']['overall']})
    print(json.dumps({s:{v:r['overall'] for v,r in report[s].items()} for s in ('test','diagnostic')},indent=2),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predict',type=Path)
    parser.add_argument('--cache-old-only',action='store_true',help='Extract existing data while new public downloads finish; does not fit or evaluate.')
    args = parser.parse_args()
    if args.cache_old_only:
        from prepare_video_v2 import old_rows
        collect(old_rows())
    elif args.predict:
        report = json.loads((OUT/'report.json').read_text())
        if report['config'] != stamp() or old.sha(OUT/'video_head.joblib') != report['head_sha256']:
            raise ValueError('Candidate checksum/configuration mismatch')
        try:
            images = sample(args.predict)
        except ValueError as exc:
            print(json.dumps({'decision':'inconclusive','reason':str(exc)}))
            raise SystemExit(0)
        model, processor = old.load_encoder()
        values = extract(images,model,processor)[:report['feature_width']]
        head = joblib.load(OUT/'video_head.joblib')
        support = float(head.predict_proba(values[None])[0,1])
        print(json.dumps({'status':'experimental_local_only','visual_ai_support':support,
                          'decision':'real' if support<=.4 else 'fake' if support>=.6 else 'inconclusive',
                          'warning':'Uncalibrated visual score; no universal detection guarantee.'}))
    else:
        try:
            train()
        except Exception as exc:
            OUT.mkdir(parents=True,exist_ok=True)
            old.save_json(OUT/'training_status.json',{'status':'failed','pid':os.getpid(),'error':str(exc),
                                                   'updated_at_unix':time.time()})
            raise

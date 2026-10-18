"""Local-only multi-generator image head; queue CPU training after video.

Train/val/test groups are fixed by prepare_image_v2. Labels never change after
compression. No production activation, Git push or cloud usage is performed.
"""
import argparse
from collections import Counter
import ctypes
import io
import json
import os
from pathlib import Path
import time

import joblib
import numpy as np
from PIL import Image, ImageOps
from safetensors import safe_open
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import torch

import train_video_candidate as shared
from prepare_image_v2 import DATA, ROOT, audit, prepare, save, sha

OUT = ROOT/'runs/candidate-image-v2-20261006'
ACTIVE = ROOT/'runs/general-ai-trained-indoor-20261005'
VIEWS = ('clean','jpeg90','resize768_jpeg55','resize512_jpeg40')


def status(phase, **values):
    OUT.mkdir(parents=True,exist_ok=True)
    save(OUT/'training_status.json',{'status':'running','phase':phase,'pid':os.getpid(),
                                   'updated_at_unix':time.time(),**values})


def view(image, name):
    image = ImageOps.exif_transpose(image).convert('RGB')
    if name=='clean':
        return image.copy()
    if name not in VIEWS:
        raise ValueError('Unknown deterministic training view')
    quality = 90
    if name.startswith('resize'):
        edge,quality = (768,55) if name=='resize768_jpeg55' else (512,40)
        image = image.copy()
        image.thumbnail((edge,edge),Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer,format='JPEG',quality=quality)
    buffer.seek(0)
    result = Image.open(buffer).convert('RGB')
    result.load()
    return result


def weights(rows):
    counts = Counter((r['label'],r['source']) for r in rows)
    number = {label:len({r['source'] for r in rows if r['label']==label}) for label in (0,1)}
    # Equal class mass and equal source mass within each class.
    return np.array([len(rows)/(2*number[r['label']]*counts[r['label'],r['source']]) for r in rows])


def alive(pid):
    if os.name!='nt':
        try:
            os.kill(pid,0)
            return True
        except ProcessLookupError:
            return False
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
    handle = kernel.OpenProcess(0x1000,False,int(pid))
    if not handle:
        return False
    try:
        result = ctypes.c_ulong()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(result)):
            raise OSError('Could not inspect local video task')
        return result.value==259
    finally:
        kernel.CloseHandle(handle)


def wait_for_video():
    path = ROOT/'runs/candidate-video-v2-20261006/training_status.json'
    start = time.monotonic()
    while path.exists():
        try:
            state = json.loads(path.read_text())
        except json.JSONDecodeError:
            time.sleep(1)
            continue
        if state.get('status')!='running' or not alive(state['pid']):
            return
        if time.monotonic()-start>12*3600:
            raise TimeoutError('Local video queue wait exceeded 12 hours')
        status('waiting_for_video_cpu',video_pid=state['pid'],video_completed=state.get('completed'),video_total=state.get('total'))
        print('image training queued; video phase',state.get('phase'),'completed',state.get('completed'),flush=True)
        time.sleep(30)


def extract(images, model, processor):
    with torch.inference_mode():
        inputs = processor(images=images,return_tensors='pt')
        return model.vision_model(pixel_values=inputs['pixel_values']).last_hidden_state.mean(dim=1).numpy()


def feature_stamp():
    return {'encoder_sha256':sha(shared.BASE/'model.safetensors'),
            'processor_sha256':sha(shared.BASE/'preprocessor_config.json'),
            'config_sha256':sha(shared.BASE/'config.json'),'views':list(VIEWS),
            'features':'frozen SigLIP whole-image mean token embeddings, 768 dims','version':2}


def baseline(model):
    metadata = json.loads((ACTIVE/'model_meta.json').read_text())
    for name,digest in metadata['sha256'].items():
        if sha(ACTIVE/name)!=digest:
            raise ValueError('Current baseline artifact checksum failed')
    if sha(ACTIVE/'preprocessor_config.json')!=sha(shared.BASE/'preprocessor_config.json'):
        raise ValueError('Current baseline processor differs; comparison needs a separate encoder')
    with safe_open(ACTIVE/'model.safetensors',framework='pt',device='cpu') as tensors:
        state = model.state_dict()
        for key in tensors.keys():
            if key.startswith('vision_model.') and not torch.equal(state[key],tensors.get_tensor(key)):
                raise ValueError('Current baseline vision encoder differs')
        w = tensors.get_tensor('classifier.weight').numpy()
        b = tensors.get_tensor('classifier.bias').numpy()
    config = json.loads((ACTIVE/'config.json').read_text())
    ai = next(int(i) for i,label in config['id2label'].items() if label=='ai')
    human = 1-ai
    return w[ai]-w[human],float(b[ai]-b[human])


def sigmoid(values):
    return 1/(1+np.exp(-np.clip(values,-60,60)))


def metrics(rows, labels, scores):
    result = shared.metrics(labels,scores)
    result['images'] = result.pop('videos')
    result['source_scene_groups'] = len({r['group'] for r in rows})
    result['note'] = 'Sampled source-scene experiment; dependent generated variants are not independent scenes. Scores are uncalibrated.'
    return result


def train(skip_video_queue=False):
    if (OUT/'report.json').exists():
        raise ValueError('Completed experiment already exists; refusing to retune on its fresh test')
    status('preparing_dataset')
    rows = prepare()  # audits the loaded or rebuilt manifest before returning
    if not skip_video_queue:
        wait_for_video()
    status('loading_encoder',total=len(rows))
    model,processor = shared.load_encoder()
    config = feature_stamp()
    path = OUT/'feature_config.json'
    if path.exists() and json.loads(path.read_text())!=config:
        raise ValueError('Feature config changed; use a new candidate directory')
    save(path,config)
    baseline_weight,baseline_bias = baseline(model)
    features,start = [],time.monotonic()
    for index,row in enumerate(rows):
        cache = OUT/(row['sha256']+'.npz')
        if cache.exists():
            with np.load(cache) as data:
                values = data['features']
        else:
            with Image.open(row['path']) as image:
                images = [view(image,name) for name in VIEWS]
            values = extract(images,model,processor)
            pending = cache.with_suffix('.partial.npz')
            np.savez_compressed(pending,features=values)
            pending.replace(cache)
        if values.shape!=(len(VIEWS),768) or not np.isfinite(values).all():
            raise ValueError('Corrupt or incompatible image features')
        features.append(values)
        if (index+1)%10==0 or index+1==len(rows):
            # Throttled on purpose: frequent atomic swaps of the status file
            # can hit transient Windows/OneDrive locks (WinError 5).
            status('feature_extraction',completed=index+1,total=len(rows),elapsed_seconds=round(time.monotonic()-start))
        print('image v2 features',index+1,'/',len(rows),'elapsed_s',round(time.monotonic()-start),flush=True)
    features = np.stack(features)
    labels = np.array([r['label'] for r in rows])
    ids = {fold:np.array([i for i,r in enumerate(rows) if r['split']==fold]) for fold in ('train','val','test','diagnostic')}
    fit,val = ids['train'],ids['val']
    if any(len(np.unique(labels[ix]))!=2 for ix in ids.values()):
        raise ValueError('Every evaluation fold needs both ground-truth classes')
    x = features[fit].reshape(-1,768)
    y = np.repeat(labels[fit],len(VIEWS))
    sample_weights = np.repeat(weights([rows[i] for i in fit]),len(VIEWS))
    validation_sources = np.array([r['source'] for r in rows])[val]
    real_mask = labels[val]==0
    trials,best = [],None
    status('validation_model_selection')
    for c in (.001,.01,.1,1,10):
        head = make_pipeline(StandardScaler(),LogisticRegression(C=c,max_iter=2000,random_state=20261007))
        head.fit(x,y,logisticregression__sample_weight=sample_weights)
        scores = head.predict_proba(features[val].reshape(-1,768))[:,1].reshape(len(val),len(VIEWS))
        true_real = float(np.mean(scores[real_mask]<.5))
        fake_recalls = {source:float(np.mean(scores[validation_sources==source]>=.5))
                        for source in sorted(set(validation_sources[~real_mask]))}
        macro = .5*(true_real+float(np.mean(list(fake_recalls.values()))))
        trials.append({'C':c,'validation_macro_generator_balanced_accuracy':macro,
                       'real_recall':true_real,'fake_recall_by_source':fake_recalls})
        print('image validation',trials[-1],flush=True)
        if best is None or macro>best[0]:
            best = macro,head,c
    _,head,c = best
    # Train-only standardization folded into a compatible 2-logit SigLIP head.
    scaler,linear = head.steps[0][1],head.steps[1][1]
    weight = linear.coef_[0]/scaler.scale_
    bias = float(linear.intercept_[0]-weight@scaler.mean_)
    with torch.no_grad():
        model.classifier.weight.zero_(); model.classifier.bias.zero_()
        model.classifier.weight[0].copy_(torch.tensor(weight,dtype=torch.float32))
        model.classifier.bias[0]=bias
    calibration_check = features[fit[:8],0]
    with torch.inference_mode():
        exported_scores = model.classifier(torch.tensor(calibration_check,dtype=torch.float32)).softmax(dim=-1)[:,0].numpy()
    expected_scores = head.predict_proba(calibration_check)[:,1]
    export_error = float(np.max(np.abs(exported_scores-expected_scores)))
    if export_error>1e-5:
        raise ValueError('Compatible model head does not match its trained classifier')
    model.config.id2label={0:'ai',1:'hum'}
    model.config.label2id={'ai':0,'hum':1}
    export = OUT/'compatible_model'
    model.save_pretrained(export,safe_serialization=True)
    processor.save_pretrained(export)
    head_path = OUT/'image_head.joblib'
    joblib.dump(head,head_path)
    report = {'status':'experimental_local_only','selected_C':c,'validation_trials':trials,
              'compatible_head_max_score_difference':export_error,
              'features':config,'head_sha256':sha(head_path),'manifest_sha256':sha(DATA/'manifest.json'),
              'baseline_model_sha256':sha(ACTIVE/'model.safetensors'),
              'split_counts':{fold:dict(Counter(rows[i]['source'] for i in ix)) for fold,ix in ids.items()},
              'split_group_counts':{fold:len({rows[i]['group'] for i in ix}) for fold,ix in ids.items()},
              'limitations':['Frozen image encoder with a newly trained image classification head, not a fully fine-tuned backbone.',
                  'Known older generators only; not verified for every modern image generation system.',
                  'RAISE source-scene/prompt groups and pHash distance<=6 families share folds; unknown different scenes/bursts may still overlap.',
                  'Publisher pretrained encoder training-set overlap cannot be fully audited.',
                  'JPEG/resize proxies are not actual WhatsApp transport tests; ground truth stays unchanged.',
                  'All scores are uncalibrated model support, not proof or guaranteed authenticity probabilities.',
                  'Face domain uses paired IMDB-WIKI photos plus Stable Diffusion inpainting crops; its previously observed test split is diagnostic only, so no fresh face-domain test exists.',
                  'Small real-photo test cohort and source-specific shortcuts still limit generalization.',
                  'Old observed tests are diagnostic only; no fresh test used for selection.',
                  'Non-commercial academic datasets: retain citations/licences and do not redistribute raw images.']}
    status('fresh_test_evaluation')
    for fold in ('test','diagnostic'):
        ix = ids[fold]
        report[fold] = {}
        for j,name in enumerate(VIEWS):
            scores = head.predict_proba(features[ix,j])[:,1]
            before = sigmoid(features[ix,j]@baseline_weight+baseline_bias)
            report[fold][name]={'candidate':metrics([rows[i] for i in ix],labels[ix],scores),
                               'current_model':metrics([rows[i] for i in ix],labels[ix],before),'per_source':{},
                               'predictions':[{'path':rows[i]['path'],'source':rows[i]['source'],'label':int(labels[i]),
                                               'candidate_support':float(p),'current_support':float(q)} for i,p,q in zip(ix,scores,before)]}
            for source in sorted({rows[i]['source'] for i in ix}):
                mask = np.array([rows[i]['source']==source for i in ix])
                report[fold][name]['per_source'][source]={'candidate':metrics([rows[i] for i,m in zip(ix,mask) if m],labels[ix][mask],scores[mask]),
                                                        'current_model':metrics([rows[i] for i,m in zip(ix,mask) if m],labels[ix][mask],before[mask])}
    export_hashes = {name:sha(export/name) for name in ('model.safetensors','config.json','preprocessor_config.json')}
    save(export/'model_meta.json',{'task':'AI-generated versus real; compression preserves labels',
         'source':'https://zenodo.org/records/10066460','training':'Frozen SigLIP, new multi-generator head; four both-label JPEG/resize views',
         'calibrated':False,'sha256':export_hashes,'manifest_sha256':report['manifest_sha256'],
         'test_metrics':{**report['test']['clean']['candidate'],'samples':report['test']['clean']['candidate']['images']},
         'evaluation_scope':'Local multi-generator frozen-head study with source-scene grouping and JPEG/resize stress; small real-photo cohort, uncalibrated and not certified for every generator.',
         'limitations':report['limitations'],
         'licences':['Synthbuster CC-BY-NC-SA-4.0','RAISE non-commercial research and education; preserve licence and cite authors'],
         'active':False})
    report['compatible_model_sha256']=export_hashes['model.safetensors']
    save(OUT/'report.json',report)
    save(OUT/'training_status.json',{'status':'finished_experimental_not_activated','phase':'fresh_test_evaluated',
         'pid':os.getpid(),'updated_at_unix':time.time(),'report':'report.json',
         'clean':report['test']['clean']['candidate'],'compressed':report['test']['resize512_jpeg40']['candidate']})
    print(json.dumps({name:{key:value for key,value in record.items() if key in ('candidate','current_model')}
                      for name,record in report['test'].items()},indent=2),flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predict',type=Path)
    parser.add_argument('--skip-video-queue',action='store_true')
    args = parser.parse_args()
    if args.predict:
        report = json.loads((OUT/'report.json').read_text())
        if report['features']!=feature_stamp() or sha(OUT/'image_head.joblib')!=report['head_sha256']:
            raise ValueError('Candidate checksum/configuration mismatch')
        with Image.open(args.predict) as image:
            image = view(image,'clean')
        if min(image.size)<224 or np.asarray(image.convert('L')).std()<2:
            print(json.dumps({'decision':'inconclusive','reason':'Insufficient visual dimensions/detail'}))
            raise SystemExit(0)
        model,processor = shared.load_encoder()
        feature = extract([image],model,processor)
        head = joblib.load(OUT/'image_head.joblib')
        support = float(head.predict_proba(feature)[0,1])
        print(json.dumps({'status':'experimental_local_only','visual_ai_support':support,
                          'decision':'real' if support<=.4 else 'fake' if support>=.6 else 'inconclusive',
                          'warning':'Uncalibrated score, no universal accuracy guarantee.'}))
    else:
        try:
            train(args.skip_video_queue)
        except Exception as exc:
            OUT.mkdir(parents=True,exist_ok=True)
            save(OUT/'training_status.json',{'status':'failed','pid':os.getpid(),'error':str(exc),'updated_at_unix':time.time()})
            raise

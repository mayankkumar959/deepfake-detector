"""Bounded, private academic image experiment: matched RAISE/Synthbuster.

All nine generators for a source scene stay in the same fold as its real photo.
Local DeepFakeFace inpainting pairs add a face-manipulation domain; its
previously observed test split is demoted to diagnostic. Old observed tests and
near-duplicate families are diagnostic, never training.
No full 12GB ZIP download, no production changes, no redistribution.
"""
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import random
import shutil
import time
import zipfile

import cv2
import numpy as np
from PIL import Image, ImageOps
from pypdf import PdfReader
import requests

from prepare_video_manipulations import RemoteZip

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/general-ai-training-v2-20261006'
OLD = ROOT / 'data/general-ai-training-indoor'
FAKE_URL = 'https://zenodo.org/records/10066460/files/synthbuster.zip'
REAL_URL = 'https://www.grip.unina.it/download/prog/DMimageDetection/real_RAISE_1k.zip'
SEED = 20261007
GROUPS = 200
MAX_BYTES = 3 * 2**30


def save(path, value):
    pending = path.with_suffix('.partial.json')
    encoded = json.dumps(value, indent=2)
    # OneDrive/antivirus can briefly hold the destination open on Windows and
    # make the atomic swap fail with WinError 5; retry instead of killing a
    # hours-long training run over a one-second lock.
    for attempt in range(120):
        try:
            pending.write_text(encoded, encoding='utf-8')
            pending.replace(path)
            return
        except PermissionError:
            if attempt == 119:
                raise
            time.sleep(0.5)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def image_info(path):
    with Image.open(path) as image:
        image.load()
        image = ImageOps.exif_transpose(image).convert('RGB')
        if min(image.size)<224 or np.asarray(image.convert('L')).std()<2:
            raise ValueError('Insufficient image dimensions/detail: '+str(path))
        pixels = np.asarray(image)
        pixel_sha = hashlib.sha256(str(pixels.shape).encode()+pixels.tobytes()).hexdigest()
        gray = np.asarray(image.convert('L').resize((32,32)),dtype=np.float32)
        dct = cv2.dct(gray)[:8,:8].flatten()
        bits = dct > np.median(dct[1:])
        bits[0] = False
        phash = int.from_bytes(np.packbits(bits).tobytes(),'big')
        return {'pixel_sha256':pixel_sha,'phash64':f'{phash:016x}','width':image.width,'height':image.height}


class EntryReader:
    def __init__(self,url,expected_length):
        self.url,self.expected_length,self.total = url,expected_length,0
        self.reset()

    def reset(self):
        self.remote = RemoteZip(self.url)
        if self.remote.length != self.expected_length:
            raise ValueError('Pinned publisher archive size changed')
        self.archive = zipfile.ZipFile(self.remote)

    def read(self,name):
        info = self.archive.getinfo(name)
        if info.file_size>8*2**20:
            raise ValueError('Oversized selected image')
        for attempt in range(3):
            if self.remote.received+info.compress_size+2*2**20>240*2**20:
                self.total += self.remote.received
                self.reset()
            try:
                return self.archive.read(name) # zipfile verifies the entry CRC.
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(2)
                self.total += self.remote.received
                self.reset()


def consolidate(rows):
    """Group matched scenes and perceptually close images before assigning folds."""
    parent = {r['group']:r['group'] for r in rows}
    def find(g):
        while parent[g]!=g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g
    def union(a,b):
        a,b = find(a),find(b)
        if a!=b:
            parent[max(a,b)] = min(a,b)
    exact,pixels,unique = {},{},[]
    for row in rows:
        previous = pixels.get(row['pixel_sha256'])
        if previous:
            if previous['label']!=row['label']:
                raise ValueError('Conflicting ground truth for identical decoded pixels')
            union(previous['group'],row['group'])
            # Keep observed diagnostic role even when dropping duplicate data.
            if row.get('split')=='diagnostic':
                previous['split']='diagnostic'
            continue
        pixels[row['pixel_sha256']] = row
        exact[row['sha256']] = row
        unique.append(row)
    for i,row in enumerate(unique):
        value = int(row['phash64'],16)
        for other in unique[:i]:
            if (value ^ int(other['phash64'],16)).bit_count() <= 6:
                union(row['group'],other['group'])
    roles = defaultdict(set)
    for row in rows:
        if row.get('split'):
            roles[find(row['group'])].add(row['split'])
    fresh = sorted({find(r['group']) for r in unique if not roles[find(r['group'])]})
    random.Random(SEED).shuffle(fresh)
    for i,g in enumerate(fresh):
        roles[g].add('test' if i<int(len(fresh)*.15) else 'val' if i<int(len(fresh)*.3) else 'train')
    for row in unique:
        row['original_group'] = row['group']
        row['group'] = find(row['group'])
        available = roles[row['group']]
        row['split'] = next(iter(available)) if len(available)==1 else 'diagnostic'
    return unique


def audit(rows):
    groups,hashes,pixels = defaultdict(set),set(),set()
    for row in rows:
        if row['label'] not in (0,1) or row['split'] not in ('train','val','test','diagnostic'):
            raise ValueError('Invalid label/split')
        if sha(row['path']) != row['sha256']:
            raise ValueError('Image file checksum changed')
        if row['sha256'] in hashes or row['pixel_sha256'] in pixels:
            raise ValueError('Duplicate raw image or decoded pixels')
        hashes.add(row['sha256']); pixels.add(row['pixel_sha256'])
        groups[row['group']].add(row['split'])
    if any(len(s)>1 for s in groups.values()):
        raise ValueError('Source/prompt/near-duplicate group leakage')
    test = [r for r in rows if r['split']=='test']
    if not test or any(not r['original_group'].startswith('RAISE-scene:') for r in test):
        raise ValueError('Fresh test contains previously observed groups')
    for label in (0,1):
        if sum(r['label']==label for r in test)<8:
            raise ValueError('Insufficient fresh test examples')


def prepare():
    DATA.mkdir(parents=True,exist_ok=True)
    manifest = DATA/'manifest.json'
    if manifest.exists():
        rows = json.loads(manifest.read_text())
        audit(rows)
        return rows
    info = requests.get('https://zenodo.org/api/records/10066460',timeout=60)
    info.raise_for_status()
    record = info.json()
    if record['metadata']['license']['id']!='cc-by-nc-sa-4.0':
        raise ValueError('Publisher licence changed: inspect before continuing')
    save(DATA/'SYNTHBUSTER_SOURCE.json',record)
    fake,real = EntryReader(FAKE_URL,12372557226),EntryReader(REAL_URL,1646333296)
    for name in ('readme.md','LICENCE.txt','prompts.csv'):
        (DATA/name).write_bytes(fake.read('synthbuster/'+name))
    license_data = real.read('real_RAISE_1k/RAISE_License.pdf')
    (DATA/'RAISE_License.pdf').write_bytes(license_data)
    license_text = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(license_data)).pages)
    (DATA/'RAISE_License.txt').write_text(license_text,encoding='utf-8')
    if not ('research' in license_text.lower() and 'commercial' in license_text.lower()):
        raise ValueError('Unexpected RAISE licence text: inspect before continuing')
    originals = {Path(n).stem:n for n in real.archive.namelist() if n.endswith('.png')}
    sources = defaultdict(dict)
    for name in fake.archive.namelist():
        if name.endswith('.png'):
            sources[name.split('/')[1]][Path(name).stem] = name
    if len(sources)!=9:
        raise ValueError('Expected nine documented Synthbuster generators')
    common = set(originals)
    for values in sources.values():
        common &= set(values)
    names = sorted(common)
    random.Random(SEED).shuffle(names)
    selected,total = [],0
    for identity in names:
        sizes = [real.archive.getinfo(originals[identity]).file_size]
        sizes += [fake.archive.getinfo(s[identity]).file_size for s in sources.values()]
        size = sum(sizes)
        if max(sizes)>8*2**20 or size>32*2**20 or total+size>MAX_BYTES:
            continue
        selected.append(identity);total+=size
        if len(selected)==GROUPS:
            break
    if len(selected)!=GROUPS or shutil.disk_usage(DATA).free<total+2*2**30:
        raise ValueError('Need space for bounded subset plus 2GiB reserve')
    rows = []
    for index,identity in enumerate(selected):
        jobs = [('RAISE-1k',0,real,originals[identity])]
        jobs += [(source,1,fake,values[identity]) for source,values in sorted(sources.items())]
        for source,label,reader,name in jobs:
            path = DATA/(hashlib.sha256(name.encode()).hexdigest()[:24]+'.png')
            if not path.exists():
                if shutil.disk_usage(DATA).free<2*2**30:
                    raise ValueError('Disk free-space reserve reached')
                payload = reader.read(name)
                pending = path.with_suffix('.partial')
                pending.write_bytes(payload);pending.replace(path)
            rows.append({'path':str(path.resolve()),'label':label,'source':source,
                         'group':'RAISE-scene:'+identity,'sha256':sha(path),'file_name':name,
                         'publisher_archive':reader.url,**image_info(path)})
        save(DATA/'preparation_status.json',{'status':'running','matched_scenes':index+1,'target':GROUPS,
                                           'images':len(rows),'updated_at_unix':time.time()})
        print('image v2 matched scenes',index+1,'/',GROUPS,'images',len(rows),flush=True)
    for row in json.loads((OLD/'manifest.json').read_text())['records']:
        row = dict(row)
        row['path'] = str((OLD/row['path']).resolve())
        row['split'] = 'diagnostic' if row['split']=='test' else row['split']
        try:
            row.update(image_info(row['path']))
        except ValueError:
            # Match the website's existing min224/visual-information guard.
            # Excluded examples are not silently resized or relabelled.
            continue
        rows.append(row)
    face_manifest = ROOT/'data/genuine_dff/manifest.json'
    if face_manifest.exists():
        face_source = json.loads(face_manifest.read_text(encoding='utf-8'))
        for record in face_source['records']:
            path = (face_manifest.parent/record['path']).resolve()
            row = {'path':str(path),'label':int(record['label']),
                   'source':'DeepFakeFace-real' if int(record['label'])==0 else 'DeepFakeFace-inpaint',
                   'group':'DFF-identity:'+str(record['group']),
                   'split':'diagnostic' if record['split']=='test' else record['split'],
                   'file_name':record['original_file'],'publisher_archive':face_source['source'],
                   'sha256':sha(path)}
            try:
                row.update(image_info(path))
            except ValueError:
                # Same min224/visual-information guard as the website inputs.
                continue
            rows.append(row)
    rows = consolidate(rows)
    audit(rows)
    save(manifest,rows)
    save(DATA/'preparation_status.json',{'status':'finished','images':len(rows),
                                       'splits':dict(Counter(r['split'] for r in rows)),
                                       'source_counts':dict(Counter(r['source'] for r in rows)),
                                       'updated_at_unix':time.time()})
    print(json.dumps(json.loads((DATA/'preparation_status.json').read_text()),indent=2),flush=True)
    return rows


if __name__=='__main__':
    prepare()

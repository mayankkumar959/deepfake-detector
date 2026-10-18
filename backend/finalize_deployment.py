"""Point Docker/deploy configuration at an assembled active package.

Does not commit, push or deploy. Run after package_active.py.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
REPO_SLUG = 'mayankkumar959/deepfake-detector'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path,
                        default=ROOT / 'runs/active-image-video-20261018')
    parser.add_argument('--branch', default='main')
    args = parser.parse_args()

    package_path = args.package / 'PACKAGE.json'
    if not package_path.is_file():
        raise SystemExit(f'Missing package manifest: {package_path}')
    package = json.loads(package_path.read_text(encoding='utf-8'))
    model_sha = package['model.safetensors_sha256']
    model_dir = args.package.resolve().relative_to(ROOT.resolve()).as_posix()
    url = (f'https://media.githubusercontent.com/media/{REPO_SLUG}/{args.branch}/'
           f'backend/{model_dir}/model.safetensors')

    dockerfile = ROOT / 'Dockerfile'
    text = dockerfile.read_text(encoding='utf-8')
    text = re.sub(r'^ARG MODEL_DIR=.*$', f'ARG MODEL_DIR={model_dir}', text, flags=re.M)
    text = re.sub(r'^ARG MODEL_WEIGHTS_URL=.*$', f'ARG MODEL_WEIGHTS_URL={url}', text, flags=re.M)
    text = re.sub(r'^ARG MODEL_WEIGHTS_SHA256=.*$',
                  f'ARG MODEL_WEIGHTS_SHA256={model_sha}', text, flags=re.M)
    dockerfile.write_text(text, encoding='utf-8')

    compose = REPO / 'docker-compose.yml'
    if compose.is_file():
        compose_text = compose.read_text(encoding='utf-8')
        compose_text = re.sub(
            r'MODEL_DIR: \$\{FORTEXA_MODEL_DIR:-[^}]+\}',
            f'MODEL_DIR: ${{FORTEXA_MODEL_DIR:-{model_dir}}}',
            compose_text)
        compose.write_text(compose_text, encoding='utf-8')

    attributes = REPO / '.gitattributes'
    if attributes.is_file():
        attr_text = attributes.read_text(encoding='utf-8')
        line = f'backend/{model_dir}/model.safetensors filter=lfs diff=lfs merge=lfs -text'
        if line not in attr_text:
            attr_text = attr_text.rstrip() + '\n' + line + '\n'
            attr_text += f'backend/{model_dir}/*.json -text\n'
            attributes.write_text(attr_text, encoding='utf-8')

    print('updated:', dockerfile)
    print('updated:', compose)
    print('updated:', attributes)
    print('MODEL_DIR=' + model_dir)
    print('MODEL_WEIGHTS_URL=' + url)
    print('MODEL_WEIGHTS_SHA256=' + model_sha)
    print('\nNext (manual, after reviewing):')
    print('  git add backend/app backend/Dockerfile backend/package_active.py backend/verify_video_runtime.py')
    print('  git add backend/runs/active-image-video-20261018 deploy-railway.ps1 docker-compose.yml .gitattributes')
    print('  git add -f backend/runs/active-image-video-20261018/model.safetensors')
    print('  git commit -m "Integrate and package image+video deepfake detectors"')
    print('  git push')
    print('  .\\deploy-railway.ps1 -StageOnly')
    print('  .\\deploy-railway.ps1')


if __name__ == '__main__':
    main()

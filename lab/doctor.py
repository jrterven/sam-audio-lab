"""Check installation without downloading model weights: python -m lab.doctor."""
import argparse
import importlib.metadata
import json
import subprocess
import sys

from .config import AUDIO_PYTHON, VISION_PYTHON, FFMPEG, FFPROBE, ROOT, DATA, MODELS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio-only', action='store_true', help='Omitir el entorno de visión opcional')
    parser.add_argument('--check-access', action='store_true', help='Comprobar permisos en Hugging Face; requiere Internet')
    args = parser.parse_args()
    failures = []

    def check(name, fn):
        try:
            result = fn()
            print(f'OK  {name}: {result}', flush=True)
        except Exception as exc:
            failures.append(name)
            print(f'ERROR  {name}: {exc}', flush=True)

    def command(*cmd):
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout)[-1500:])
        return result.stdout.strip()

    print(f'Python del servidor: {sys.executable}\nDatos: {DATA}')
    check('FFmpeg', lambda: command(FFMPEG, '-version').splitlines()[0])
    check('ffprobe', lambda: command(FFPROBE, '-version').splitlines()[0])
    check('API', lambda: ', '.join(f'{p} {importlib.metadata.version(p)}' for p in ('fastapi', 'uvicorn', 'python-multipart')))
    audio_check = '''
import torch, torchaudio, transformers
from torchcodec.decoders import VideoDecoder, AudioDecoder
from sam_audio import SAMAudio, SAMAudioProcessor
from core.vision_encoder import pe
from lab.device import select_device
device = select_device(torch)
x = torch.ones(4, device=device)
assert float((x*x).sum().cpu()) == 4
video = VideoDecoder('examples/assets/office.mp4')
assert video[0].numel() > 0
assert AudioDecoder('examples/assets/office.mp4').get_all_samples().data.numel() > 0
print(f'torch={torch.__version__}, torchaudio={torchaudio.__version__}, transformers={transformers.__version__}, dispositivo={device}; decodificación OK')
'''
    check('SAM Audio', lambda: command(AUDIO_PYTHON, '-c', audio_check))
    if not args.audio_only:
        vision_check = '''
import torch, transformers, cv2, numpy, scipy
from transformers import Sam3Model, Sam3TrackerVideoModel, Sam3Processor, Sam3TrackerVideoProcessor
from lab.device import select_device
device = select_device(torch)
x = torch.ones(4, device=device)
assert float((x*x).sum().cpu()) == 4
print(f'torch={torch.__version__}, transformers={transformers.__version__}, dispositivo={device}; clases SAM 3 OK')
'''
        check('SAM 3 visual', lambda: command(VISION_PYTHON, '-c', vision_check))
    if args.check_access:
        repositories = dict(MODELS)
        if not args.audio_only:
            repositories['vision'] = 'facebook/sam3'
        for name, repo in repositories.items():
            # Check a small gated file with HEAD; never print or persist credentials.
            snippet = f'''
from huggingface_hub import get_hf_file_metadata, hf_hub_url, get_token
get_hf_file_metadata(hf_hub_url({json.dumps(repo)}, 'config.json'), token=get_token())
print('autorizado')
'''
            check(repo, lambda code=snippet: command(AUDIO_PYTHON, '-c', code))
    if not (ROOT/'web/dist/index.html').is_file():
        print('AVISO  Interfaz sin compilar. Ejecuta npm --prefix web ci y npm --prefix web run build.')
    if failures:
        print('Revisa docs/INSTALLATION.md y docs/TROUBLESHOOTING.md.')
        return 1
    print('Diagnóstico correcto. Esto no reemplaza una inferencia real con checkpoints.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

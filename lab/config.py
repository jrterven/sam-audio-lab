import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('SAM_LAB_DATA', ROOT / '.lab-data')).resolve()

def runtime_paths():
    # The server runs in the audio environment. Named conda environments are
    # siblings, regardless of the user's conda distribution or home directory.
    audio = os.environ.get('SAM_LAB_AUDIO_PYTHON', sys.executable)
    audio = str(Path(shutil.which(audio) or audio).expanduser().absolute())
    bin_dir = Path(audio).parent
    vision = os.environ.get('SAM_LAB_VISION_PYTHON', str(bin_dir.parent.parent / 'sam3-vision/bin/python'))
    vision = str(Path(shutil.which(vision) or vision).expanduser().absolute())
    ffmpeg = os.environ.get('SAM_LAB_FFMPEG') or (str(bin_dir / 'ffmpeg') if (bin_dir / 'ffmpeg').is_file() else shutil.which('ffmpeg') or 'ffmpeg')
    ffmpeg = shutil.which(ffmpeg) or str(Path(ffmpeg).expanduser())
    sibling = Path(ffmpeg).with_name('ffprobe')
    ffprobe = os.environ.get('SAM_LAB_FFPROBE') or (str(sibling) if sibling.is_file() else shutil.which('ffprobe') or 'ffprobe')
    return audio, vision, ffmpeg, ffprobe


AUDIO_PYTHON, VISION_PYTHON, FFMPEG, FFPROBE = runtime_paths()
MODELS = {name: f'facebook/sam-audio-{name}' for name in ('small', 'base', 'large')}
FPS = 25

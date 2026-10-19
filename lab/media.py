import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
import numpy as np
from .config import DATA, FFMPEG, FFPROBE, FPS


def command(args):
    p = subprocess.run(args, capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors='replace')[-3000:])
    return p.stdout


def probe(path):
    info = json.loads(command([FFPROBE, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)]))
    audio = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
    video = next((s for s in info['streams'] if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')), None)
    if audio is None:
        raise ValueError('The file does not contain an audio track.')
    duration = float(info['format'].get('duration', audio.get('duration', 0)))
    if duration <= 0:
        raise ValueError('Could not determine the file duration.')
    return {'duration': duration, 'video': video is not None,
            'width': video.get('width', 0) if video else 0, 'height': video.get('height', 0) if video else 0}


def peaks(path, duration):
    # Stream the entire source at 2 kHz; never decode a long recording in the browser.
    p = subprocess.Popen([FFMPEG, '-v', 'error', '-i', str(path), '-vn', '-ac', '1', '-ar', '2000', '-f', 'f32le', '-'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    bucket = max(1, int(duration * 2000 / 2400))
    values = []
    while chunk := p.stdout.read(bucket * 4):
        data = np.frombuffer(chunk, dtype='<f4')
        if len(data):
            values.append(float(np.max(np.abs(data))))
    if p.wait():
        raise RuntimeError('Could not analyze the waveform.')
    return values


def clip_key(media_id, start, end):
    return hashlib.sha256(f'{media_id}:{start:.6f}:{end:.6f}'.encode()).hexdigest()[:24]


def preview_audio(media):
    """Cache browser-compatible audio for the full file, independently of clips."""
    directory = DATA / 'media' / media['id']
    directory.mkdir(parents=True, exist_ok=True)
    preview = directory / 'preview.mp3'
    if not preview.exists():
        # Unique temporary files keep simultaneous requests from sharing a partial encode.
        with tempfile.NamedTemporaryFile(suffix='.mp3', dir=directory, delete=False) as f:
            temporary = Path(f.name)
        try:
            command([FFMPEG, '-y', '-v', 'error', '-i', str(DATA / media['path']),
                     '-map', '0:a:0', '-vn', '-c:a', 'libmp3lame', '-q:a', '3',
                     '-ar', '48000', str(temporary)])
            temporary.replace(preview)
        finally:
            temporary.unlink(missing_ok=True)
    return preview


def prepare_clip(media, start, end, progress=lambda *a: None):
    if start < 0 or end > media['duration'] + .05 or not 0 < end-start <= 30.001:
        raise ValueError('Clip is outside the file boundaries.')
    directory = DATA / 'clips' / clip_key(media['id'], start, end)
    directory.mkdir(parents=True, exist_ok=True)
    src = DATA / media['path']
    duration = end-start
    wav = directory / 'original.wav'
    if not wav.exists():
        progress('preprocess', 'Preparing audio at 48 kHz')
        command([FFMPEG, '-y', '-v', 'error', '-ss', str(start), '-i', str(src), '-t', str(duration), '-vn', '-ac', '1', '-ar', '48000', '-c:a', 'pcm_f32le', str(directory/'original.partial.wav')])
        (directory/'original.partial.wav').replace(wav)
    video = directory / 'preview.mp4'
    if media['video'] and not video.exists():
        progress('preprocess', 'Preparing video at 25 fps')
        command([FFMPEG, '-y', '-v', 'error', '-ss', str(start), '-i', str(src), '-t', str(duration), '-map', '0:v:0', '-map', '0:a:0', '-vf', "scale='min(1280,iw)':-2,fps=25", '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-c:a', 'aac', '-ac', '1', '-ar', '48000', '-movflags', '+faststart', str(directory/'preview.partial.mp4')])
        (directory/'preview.partial.mp4').replace(video)
    dimensions = probe(video) if media['video'] else {'width': 0, 'height': 0}
    return {'dir': str(directory), 'audio': str(wav), 'video': str(video) if media['video'] else None, 'duration': duration, 'width': dimensions['width'], 'height': dimensions['height']}


def export_video(media, recipe, audio, out):
    command([FFMPEG, '-y', '-v', 'error', '-ss', str(recipe['start']), '-i', str(DATA / media['path']), '-i', str(audio), '-t', str(recipe['end']-recipe['start']), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(out)])

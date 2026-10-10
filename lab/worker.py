"""Persistent, isolated inference process. Only JSON protocol lines reach the supervisor."""
import gc
import json
import os
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '60')
from .config import DATA, MODELS
from .device import select_device, synchronize, empty_cache
from .media import prepare_clip, probe, peaks, export_video

PREFIX = '@@SAMLAB@@'
_model = None
_model_name = None
_processor = None


def emit(kind, **body):
    print(PREFIX + json.dumps(dict(type=kind, **body), allow_nan=False), flush=True)


def progress(stage, message, **extra):
    emit('progress', stage=stage, message=message, **extra)


def relative(path):
    return str(Path(path).relative_to(DATA))


def separate(spec):
    global _model, _model_name, _processor
    import numpy as np
    import soundfile as sf
    import torch
    from huggingface_hub import snapshot_download, hf_hub_download
    from sam_audio import SAMAudio, SAMAudioProcessor
    from torchcodec.decoders import VideoDecoder
    torch.set_num_threads(8)
    recipe = spec['recipe']
    t0 = time.perf_counter()
    clip = prepare_clip(spec['media'], recipe['start'], recipe['end'], progress)
    prep = time.perf_counter()-t0
    device = select_device(torch)
    timings = {'preprocess': prep, 'download': 0., 'load': 0., 'visual': 0.}
    revision = None
    if _model_name != recipe['model']:
        _model = _processor = None
        gc.collect()
        empty_cache(torch, device)
        progress('download', f'Comprobando y descargando {recipe["model"].title()}')
        t = time.perf_counter()
        repo = MODELS[recipe['model']]
        directory = snapshot_download(repo, allow_patterns=['config.json', 'checkpoint.pt'], max_workers=2)
        config = json.loads((Path(directory)/'config.json').read_text())
        # Download encoder dependencies before timing model construction.
        text_name = config.get('text_encoder', {}).get('name', 't5-base')
        for file in ['config.json', 'spiece.model', 'tokenizer.json', 'tokenizer_config.json', 'model.safetensors']:
            try:
                hf_hub_download(text_name, file)
            except Exception as exc:
                if file in ('config.json', 'model.safetensors'):
                    raise exc
        timings['download'] = time.perf_counter()-t
        revision = Path(directory).name
        progress('load', f'Cargando SAM Audio {recipe["model"].title()} en {device.upper()}')
        t = time.perf_counter()
        _model = SAMAudio.from_pretrained(directory, span_predictor=None, text_ranker=None, visual_ranker=None).eval().to(device)
        _model.vision_encoder.batch_size = 8
        _processor = SAMAudioProcessor.from_pretrained(directory)
        _model_name = recipe['model']
        _model._lab_revision = revision
        synchronize(torch, device)
        timings['load'] = time.perf_counter()-t
    revision = _model._lab_revision
    audio, sr = sf.read(clip['audio'], dtype='float32')
    audio = torch.from_numpy(audio).unsqueeze(0)
    anchors = [(r['sign'], r['start']-recipe['start'], r['end']-recipe['start']) for r in recipe['regions']]
    batch = _processor(audios=[audio], descriptions=[recipe['prompt']], anchors=[anchors] if anchors else None).to(device)
    if spec.get('tracking'):
        progress('visual', 'Codificando el objeto seleccionado')
        t = time.perf_counter()
        tracking = spec['tracking']
        masks = np.load(DATA / tracking['masks'], mmap_mode='r')
        decoder = VideoDecoder(clip['video'], dimension_order='NCHW')
        count = int(batch.sizes[0])
        # Align to codec timestamps (40 ms), including the final padded audio token.
        indexes = np.minimum(np.arange(count), min(len(decoder), len(masks))-1)
        frames = decoder.get_frames_at(indices=indexes.tolist()).data
        selected = torch.from_numpy(masks[indexes]).unsqueeze(1).bool()
        # Match SAMAudioProcessor.mask_videos: selected pixels are zeroed.
        masked = frames * selected.eq(0)
        # Encode in small batches without moving the complete full-size video to Metal.
        features = _model.vision_encoder([masked]).transpose(1, 2)
        original_fn = _model._get_video_features
        _model._get_video_features = lambda video, audio_features: features
        synchronize(torch, device)
        timings['visual'] = time.perf_counter()-t
    else:
        original_fn = None
    torch.manual_seed(recipe['seed'])
    progress('separate', f'Separando {len(audio[0])/sr:.2f} s con {recipe["model"].title()}')
    t = time.perf_counter()
    try:
        with torch.inference_mode():
            result = _model.separate(batch, predict_spans=False, reranking_candidates=1)
        synchronize(torch, device)
    finally:
        if original_fn:
            _model._get_video_features = original_fn
    timings['separate'] = time.perf_counter()-t
    output = Path(spec['output'])
    output.mkdir(parents=True, exist_ok=True)
    files = {'original': relative(clip['audio'])}
    for name in ('target', 'residual'):
        samples = getattr(result, name)[0].detach().float().cpu().numpy()[:audio.shape[-1]]
        if len(samples) != audio.shape[-1] or not np.isfinite(samples).all():
            raise RuntimeError('El modelo generó audio inválido. Prueba un fragmento más corto.')
        path = output / f'{name}.wav'
        sf.write(path, samples, sr, subtype='FLOAT')
        files[name] = relative(path)
    timings['total'] = time.perf_counter()-t0
    info = {'files': files, 'timings': timings, 'device': device, 'revision': revision, 'torch': torch.__version__,
            'duration': audio.shape[-1]/sr, 'sample_rate': sr, 'rtf': timings['separate']/(audio.shape[-1]/sr),
            'video_width': clip['width'], 'video_height': clip['height'], 'peaks': peaks(clip['audio'], clip['duration']), 'model': recipe['model'], 'recipe': recipe, 'video': relative(clip['video']) if clip['video'] else None}
    (output/'run.json').write_text(json.dumps(info, indent=2))
    info['metadata'] = relative(output/'run.json')
    return info


def run(spec):
    kind = spec['operation']
    if kind == 'separate':
        return separate(spec)
    if kind in ('detect', 'track'):
        from .vision import vision_job
        return vision_job(spec, progress)
    if kind == 'import':
        progress('inspect', 'Leyendo archivo y forma de onda')
        info = probe(spec['path'])
        info['peaks'] = peaks(spec['path'], info['duration'])
        return info
    if kind == 'clip':
        clip = prepare_clip(spec['media'], spec['start'], spec['end'], progress)
        return dict(clip, audio=relative(clip['audio']), video=relative(clip['video']) if clip['video'] else None,
                    peaks=peaks(clip['audio'], clip['duration']))
    if kind == 'export':
        progress('export', 'Exportando el fragmento con el audio seleccionado')
        path = Path(spec['output']) / (spec['track']+'.mp4')
        path.parent.mkdir(parents=True, exist_ok=True)
        export_video(spec['media'], spec['recipe'], DATA/spec['audio'], path)
        return {'file': relative(path)}
    raise ValueError('Operación desconocida')


if __name__ == '__main__':
    for line in sys.stdin:
        try:
            spec = json.loads(line)
            result = run(spec)
            emit('result', result=result)
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            message = str(exc)
            if 'out of memory' in message.lower():
                message = 'Memoria insuficiente. Elige Small o un fragmento más corto. ' + message[:300]
            emit('error', message=message[-2000:])
            # Drop partially initialized or failed GPU state; the supervisor restarts us.
            break

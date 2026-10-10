"""SAM 3 text detection and point/mask video tracking in the vision environment."""
import gc
import time
from pathlib import Path
import numpy as np
from .config import DATA
from .device import select_device, synchronize, empty_cache
from .media import prepare_clip

_model = _processor = _kind = _device = None


def frames_from(path):
    import cv2
    cap = cv2.VideoCapture(path)
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()
    if not frames:
        raise ValueError('No se pudieron leer los fotogramas.')
    return frames


def load(kind, device, progress):
    global _model, _processor, _kind, _device
    import torch
    from transformers import Sam3Model, Sam3Processor, Sam3TrackerVideoModel, Sam3TrackerVideoProcessor
    from huggingface_hub import snapshot_download
    if (_kind, _device) == (kind, device) and _model is not None:
        return {'download': 0., 'load': 0.}
    _model = _processor = None
    gc.collect()
    empty_cache(torch, device)
    progress('download', 'Comprobando pesos de SAM 3 visual')
    t = time.perf_counter()
    directory = snapshot_download('facebook/sam3', allow_patterns=['*.json', '*.txt', 'model.safetensors'])
    download = time.perf_counter()-t
    progress('load', f'Cargando SAM 3 visual en {device.upper()}')
    t = time.perf_counter()
    # Load the canonical class: Transformers selects checkpoint conversion rules
    # by class name, so subclassing before from_pretrained loses backbone weights.
    cls, proc = (Sam3Model, Sam3Processor) if kind == 'detect' else (Sam3TrackerVideoModel, Sam3TrackerVideoProcessor)
    _model, loading_info = cls.from_pretrained(directory, dtype=torch.float32,
                                              attn_implementation='sdpa', output_loading_info=True)
    if loading_info.get('missing_keys') or loading_info.get('mismatched_keys') or loading_info.get('error_msgs'):
        _model = None
        raise RuntimeError('SAM 3 no cargó todos los pesos requeridos. Revisa la versión del entorno visual.')
    _model = _model.eval().to(device)
    if kind == 'track':
        from types import MethodType
        original_step = _model._run_single_frame_inference
        def refine_step(self, *args, **kwargs):
            # Pass the previous logits for click refinement after canonical loading.
            if kwargs.get('point_inputs') is not None:
                session = kwargs['inference_session']
                previous = session.output_dict_per_obj[kwargs['obj_idx']]
                old = previous['cond_frame_outputs'].get(kwargs['frame_idx']) or previous['non_cond_frame_outputs'].get(kwargs['frame_idx'])
                if old is not None:
                    kwargs['prev_sam_mask_logits'] = old['pred_masks'].to(session.inference_device).clamp(-32, 32)
            return original_step(*args, **kwargs)
        _model._run_single_frame_inference = MethodType(refine_step, _model)
    _processor = proc.from_pretrained(directory)
    _kind, _device = kind, device
    _model._lab_revision = Path(directory).name
    synchronize(torch, device)
    return {'download': download, 'load': time.perf_counter()-t}



def refinement_points(points, prior_mask):
    """Keep an interior positive reference when a mask receives only exclusions."""
    points = list(points)
    if prior_mask is None or not points or any(p['label'] == 1 for p in points):
        return points
    interior = prior_mask.astype(bool).copy()
    height, width = interior.shape
    yy, xx = np.ogrid[:height, :width]
    for p in points:
        radius = max(2, min(height, width) * .03)
        interior[(xx-p['x']*width)**2+(yy-p['y']*height)**2 < radius**2] = False
    # Choose inside the object, away from its boundary and negative clicks.
    for _ in range(3):
        padded = np.pad(interior, 1)
        eroded = interior & padded[:-2,1:-1] & padded[2:,1:-1] & padded[1:-1,:-2] & padded[1:-1,2:]
        if not eroded.any():
            break
        interior = eroded
    y, x = np.nonzero(interior)
    if len(x):
        index = np.argmin((x-x.mean())**2+(y-y.mean())**2)
        points.insert(0, {'x':float((x[index]+.5)/width), 'y':float((y[index]+.5)/height), 'label':1})
    return points


def infer(spec, frames, device, progress):
    import torch
    req = spec['request']
    operation = spec['operation']
    out = Path(spec['output'])
    out.mkdir(parents=True, exist_ok=True)
    t = time.perf_counter()
    if operation == 'detect':
        progress('detect', f'Buscando «{req["text"]}»')
        frame = frames[min(req['frame'], len(frames)-1)]
        inputs = _processor(images=frame, text=req['text'], return_tensors='pt').to(device)
        with torch.inference_mode():
            outputs = _model(**inputs)
        result = _processor.post_process_instance_segmentation(outputs, threshold=.5, mask_threshold=.5, target_sizes=inputs['original_sizes'].tolist())[0]
        masks = result['masks'].detach().cpu().numpy().astype(np.uint8)
        scores = result['scores'].detach().cpu().tolist()
        np.save(out/'masks.npy', masks)
        return {'count': len(masks), 'masks': str((out/'masks.npy').relative_to(DATA)), 'scores': scores,
                'frame': req['frame'], 'inference': time.perf_counter()-t, 'width': frame.shape[1], 'height': frame.shape[0]}
    progress('track', 'Preparando seguimiento del objeto')
    session = _processor.init_video_session(video=frames, inference_device=device, processing_device='cpu',
                                             video_storage_device='cpu', inference_state_device=device, dtype=torch.float32)
    h, w = frames[0].shape[:2]
    annotations = sorted(req['annotations'], key=lambda a:a['frame'])
    for a in annotations:
        frame = min(a['frame'], len(frames)-1)
        initial = None
        if a.get('tracking_id'):
            prior = spec['tracks'][a['tracking_id']]
            initial = np.load(DATA/prior['masks'], mmap_mode='r')[frame].copy()
            _processor.add_inputs_to_inference_session(session, frame_idx=frame, obj_ids=1, input_masks=initial)
            with torch.inference_mode():
                _model(inference_session=session, frame_idx=frame)
        elif a.get('detection_id'):
            detection = spec['detections'][a['detection_id']]
            initial = np.load(DATA/detection['masks'], mmap_mode='r')[a['candidate']].copy()
            _processor.add_inputs_to_inference_session(session, frame_idx=frame, obj_ids=1, input_masks=initial)
            with torch.inference_mode():
                _model(inference_session=session, frame_idx=frame)
        if a['points']:
            effective_points = refinement_points(a['points'], initial)
            points = [[[[p['x']*w, p['y']*h] for p in effective_points]]]
            labels = [[[p['label'] for p in effective_points]]]
            _processor.add_inputs_to_inference_session(session, frame_idx=frame, obj_ids=1,
                                                        input_points=points, input_labels=labels, clear_old_inputs=False)
            with torch.inference_mode():
                _model(inference_session=session, frame_idx=frame)
    masks = np.lib.format.open_memmap(out/'masks.npy', mode='w+', dtype=np.uint8, shape=(len(frames), h, w))
    masks[:] = 0
    processed = set()
    start = annotations[0]['frame']
    with torch.inference_mode():
        for reverse in ([False, True] if start > 0 else [False]):
            for result in _model.propagate_in_video_iterator(session, start_frame_idx=start, reverse=reverse):
                value = _processor.post_process_masks([result.pred_masks], original_sizes=[[h,w]], binarize=True)[0]
                array = value.detach().cpu().numpy().reshape(-1,h,w)[0]
                masks[result.frame_idx] = array.astype(np.uint8)
                processed.add(result.frame_idx)
                if len(processed) % 5 == 0 or len(processed) == len(frames):
                    progress('track', f'Siguiendo objeto · {len(processed)}/{len(frames)} fotogramas', progress=len(processed)/len(frames))
    masks.flush()
    visible = sum(bool(masks[i].any()) for i in range(len(masks)))
    if not visible:
        raise ValueError('El objeto no aparece en las máscaras. Añade un clic positivo o cambia la descripción.')
    return {'masks': str((out/'masks.npy').relative_to(DATA)), 'count': len(frames), 'visible_frames': visible,
            'width': w, 'height': h, 'fps': 25, 'inference': time.perf_counter()-t, 'annotations': annotations}


def vision_job(spec, progress):
    import torch
    torch.set_num_threads(8)
    total = time.perf_counter()
    req = spec['request']
    clip = prepare_clip(spec['media'], req['start'], req['end'], progress)
    frames = frames_from(clip['video'])
    prep = time.perf_counter()-total
    device = select_device(torch)
    fallback = None
    timings = {'download': 0., 'load': 0.}
    try:
        timings = load(spec['operation'], device, progress)
        result = infer(spec, frames, device, progress)
    except (RuntimeError, NotImplementedError) as exc:
        message = str(exc).lower()
        if 'out of memory' in message or device != 'mps' or not any(s in message for s in ['mps', 'metal', 'float64', 'not implemented']):
            raise
        fallback = str(exc)[:500]
        progress('fallback', 'Operación visual incompatible con Metal; reintentando en CPU')
        device = 'cpu'
        retry = load(spec['operation'], device, progress)
        timings = {k:timings[k]+retry[k] for k in timings}
        result = infer(spec, frames, device, progress)
    synchronize(torch, device)
    timings.update(preprocess=prep, visual=result.pop('inference'), total=time.perf_counter()-total)
    return dict(result, weights_verified=True, device=device, fallback=fallback, timings=timings, revision=_model._lab_revision,
                clip_video=str(Path(clip['video']).relative_to(DATA)), request=req)

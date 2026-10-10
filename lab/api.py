import asyncio
import json
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
import numpy as np
from PIL import Image
from fastapi import FastAPI, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import DATA, ROOT, MODELS, VISION_PYTHON
from . import store
from .jobs import jobs, TERMINAL
from .schemas import Recipe, VisionRequest, ExportRequest


@asynccontextmanager
async def lifespan(app):
    jobs.start()
    yield
    jobs.close()


app = FastAPI(title='SAM Audio Lab', lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])


@app.middleware('http')
async def local_origin(request: Request, call_next):
    origin = request.headers.get('origin')
    if origin and urlparse(origin).hostname not in ('localhost', '127.0.0.1'):
        return JSONResponse({'detail': 'Only local requests are allowed.'}, status_code=403)
    return await call_next(request)


@app.exception_handler(KeyError)
async def missing(request, exc):
    return JSONResponse({'detail': 'The requested resource was not found.'}, status_code=404)


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=422)


def safe_file(path):
    resolved = (DATA/path).resolve()
    if not resolved.is_relative_to(DATA) or not resolved.is_file():
        raise HTTPException(404, 'File not found.')
    return resolved


def public_job(j):
    return {k:v for k,v in j.items() if k != 'spec'}


@app.get('/api/state')
def state():
    return {'media': store.all_of('media'), 'projects': store.all_of('project'),
            'jobs': [public_job(j) for j in store.all_of('job')]}


@app.get('/api/models')
def models():
    from huggingface_hub import try_to_load_from_cache
    result = []
    for name, repo in MODELS.items():
        cached = try_to_load_from_cache(repo, 'checkpoint.pt')
        result.append({'id': name, 'repo': repo, 'cached': isinstance(cached, str) and Path(cached).is_file()})
    return {'audio': result, 'vision_installed': Path(VISION_PYTHON).exists()}


@app.post('/api/media')
def upload(file: UploadFile):
    record = store.save('media', {'name': Path(file.filename or 'file').name, 'status': 'importing'})
    directory = DATA/'media'/record['id']
    directory.mkdir(parents=True)
    # Preserve the extension only; user filenames never become filesystem paths.
    path = directory/('source'+Path(record['name']).suffix[:12].lower())
    try:
        with path.open('wb') as out:
            shutil.copyfileobj(file.file, out, length=1024*1024)
    except Exception:
        store.update(record['id'], status='error', error='Could not save the file.')
        raise
    record = store.update(record['id'], path=str(path.relative_to(DATA)))
    job = jobs.submit('import', {'path': str(path), 'media_id': record['id']})
    return {'media': record, 'job': public_job(job)}


@app.post('/api/example')
def example():
    original = ROOT/'examples/assets/office.mp4'
    for m in store.all_of('media'):
        if m['name'] == 'office.mp4' and m['status'] == 'ready':
            return {'media': m}
    class Sample:
        filename = 'office.mp4'
    with original.open('rb') as f:
        sample = Sample()
        sample.file = f
        return upload(sample)


@app.put('/api/projects/{project_id}')
def project(project_id: str, body: dict):
    # Projects are editable drafts; each execution saves a separate frozen recipe.
    if len(json.dumps(body)) > 100000:
        raise HTTPException(413, 'Project is too large.')
    return store.save('project', body, project_id)


def media_for(media_id, start, end, video=False):
    media = store.get(media_id, 'media')
    if media['status'] != 'ready':
        raise HTTPException(409, 'The file is not ready yet.')
    if not 0 <= start < end <= media['duration']+.05 or end-start > 30.001:
        raise HTTPException(422, 'Select a valid clip of up to 30 seconds.')
    if video and not media['video']:
        raise HTTPException(422, 'This operation requires a video.')
    return media


@app.post('/api/clips')
def clip(recipe: Recipe):
    media = media_for(recipe.media_id, recipe.start, recipe.end)
    return public_job(jobs.submit('clip', {'media': media, 'start': recipe.start, 'end': recipe.end}))


@app.post('/api/separate')
def separate(recipe: Recipe):
    media = media_for(recipe.media_id, recipe.start, recipe.end)
    if not (recipe.prompt.strip() or recipe.regions or recipe.tracking_id):
        raise HTTPException(422, 'Add a text prompt, a region, or a visual object.')
    spec = {'media': media, 'recipe': recipe.model_dump()}
    if recipe.tracking_id:
        track = store.get(recipe.tracking_id, 'job')
        if track['operation'] != 'track' or track['status'] != 'done':
            raise HTTPException(422, 'Complete object tracking first.')
        v = track['spec']['request']
        if v['media_id'] != recipe.media_id or abs(v['start']-recipe.start) > 1e-6 or abs(v['end']-recipe.end) > 1e-6:
            raise HTTPException(422, 'Tracking belongs to a different clip. Run tracking again.')
        spec['tracking'] = track['result']
    return public_job(jobs.submit('separate', spec))


def vision(request, operation):
    media = media_for(request.media_id, request.start, request.end, True)
    if operation == 'detect' and not request.text.strip():
        raise HTTPException(422, 'Describe the object you want to find.')
    if operation == 'track' and not request.annotations:
        raise HTTPException(422, 'Select an object or add a positive click.')
    spec = {'media': media, 'request': request.model_dump(), 'detections': {}, 'tracks': {}}
    for a in request.annotations:
        if a.tracking_id:
            prior = store.get(a.tracking_id, 'job')
            if prior['operation'] != 'track' or prior['status'] != 'done':
                raise HTTPException(422, 'Reference tracking is unavailable.')
            r = prior['spec']['request']
            if (r['media_id'], r['start'], r['end']) != (request.media_id, request.start, request.end):
                raise HTTPException(422, 'Tracking belongs to a different clip.')
            spec['tracks'][a.tracking_id] = prior['result']
        if a.detection_id:
            detection = store.get(a.detection_id, 'job')
            if detection['operation'] != 'detect' or detection['status'] != 'done':
                raise HTTPException(422, 'Detection is unavailable.')
            r = detection['spec']['request']
            if (r['media_id'], r['start'], r['end'], r['frame']) != (request.media_id, request.start, request.end, a.frame):
                raise HTTPException(422, 'The mask belongs to a different frame or clip.')
            if a.candidate >= detection['result']['count']:
                raise HTTPException(422, 'Object not found.')
            spec['detections'][a.detection_id] = detection['result']
    return public_job(jobs.submit(operation, spec))


@app.post('/api/vision/detect')
def detect(request: VisionRequest):
    return vision(request, 'detect')


@app.post('/api/vision/track')
def track(request: VisionRequest):
    return vision(request, 'track')


@app.get('/api/jobs/{job_id}')
def job(job_id: str):
    return public_job(store.get(job_id, 'job'))


@app.post('/api/jobs/{job_id}/cancel')
def cancel(job_id: str):
    return public_job(jobs.cancel(job_id))


@app.get('/api/events')
async def events(request: Request):
    async def stream():
        previous = None
        while not await request.is_disconnected():
            snapshot = json.dumps([public_job(j) for j in store.all_of('job')], ensure_ascii=False)
            if snapshot != previous:
                yield f'data: {snapshot}\n\n'
                previous = snapshot
            else:
                yield ': heartbeat\n\n'
            await asyncio.sleep(.75)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.get('/api/files/{path:path}')
def files(path: str, download: bool = False):
    file = safe_file(path)
    # Only public media artifacts; never expose the SQLite DB or job logs.
    if Path(path).parts[0] not in ('media', 'clips', 'results') or file.suffix not in ('.wav','.mp4','.mp3','.m4a','.flac','.ogg','.webm','.mov','.aac','.json','.png'):
        raise HTTPException(404)
    return FileResponse(file, filename=file.name if download else None)


@app.get('/api/masks/{job_id}/{frame}.png')
def mask(job_id: str, frame: int):
    j = store.get(job_id, 'job')
    if j['status'] != 'done' or j['operation'] not in ('track', 'detect'):
        raise HTTPException(404)
    masks = np.load(safe_file(j['result']['masks']), mmap_mode='r')
    if not 0 <= frame < len(masks):
        raise HTTPException(404)
    from io import BytesIO
    rgba = np.zeros((*masks[frame].shape, 4), dtype=np.uint8)
    rgba[masks[frame].astype(bool)] = [162, 244, 117, 150]
    out = BytesIO()
    Image.fromarray(rgba).save(out, format='PNG')
    return StreamingResponse(iter([out.getvalue()]), media_type='image/png', headers={'Cache-Control':'public, max-age=31536000, immutable'})


@app.post('/api/exports')
def export(request: ExportRequest):
    run = store.get(request.run_id, 'job')
    if run['status'] != 'done' or run['operation'] != 'separate':
        raise HTTPException(422, 'Result is unavailable.')
    spec = run['spec']
    if not spec['media']['video']:
        raise HTTPException(422, 'The original file is not a video.')
    return public_job(jobs.submit('export', {'media': spec['media'], 'recipe': spec['recipe'], 'audio': run['result']['files'][request.track], 'track': request.track}))


if (ROOT/'web/dist').exists():
    app.mount('/', StaticFiles(directory=ROOT/'web/dist', html=True), name='web')

"""Opt-in real model acceptance run. Requires a running local Lab server."""
import json
import time
from pathlib import Path
import httpx
import numpy as np
import soundfile as sf
from lab.config import DATA, ROOT, FFMPEG
from lab.media import command, probe

client = httpx.Client(base_url='http://127.0.0.1:8765', timeout=120)
report = {}


def submit(endpoint, payload):
    r=client.post(endpoint,json=payload)
    r.raise_for_status()
    job=r.json()
    return wait(job['id'])


def wait(job_id):
    last=None
    deadline=time.time()+1800
    while time.time()<deadline:
        j=client.get('/api/jobs/'+job_id).json()
        if j['message']!=last:
            print(job_id[:8],j['status'],j['message'],flush=True);last=j['message']
        if j['status'] in ('error','interrupted','cancelled'):
            raise RuntimeError(j)
        if j['status']=='done':return j
        time.sleep(2)
    raise TimeoutError(job_id)


def validate_audio(job):
    r=job['result']
    for name in ('target','residual'):
        samples,sr=sf.read(DATA/r['files'][name]);assert sr==48000
        assert len(samples)==round(r['duration']*sr) and np.isfinite(samples).all()
        assert np.max(np.abs(samples))>0
    assert r['device'] in ('mps', 'cuda', 'cpu')
    report[job['id']]={'device':r['device'],'model':r['model'],'duration':r['duration'],'timings':r['timings'],'rtf':r['rtf'],'recipe':r['recipe']}
    path=ROOT/'outputs/lab-validation.json';path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    state=client.get('/api/state').json()
    media=next((m for m in state['media'] if m['name']=='office.mp4' and m['status']=='ready'),None)
    if media is None:
        example=client.post('/api/example',json={}).json()
        if example.get('job'):wait(example['job']['id'])
        state=client.get('/api/state').json()
        media=next(m for m in state['media'] if m['id']==example['media']['id'])
    track=next((j for j in state['jobs'] if j['operation']=='track' and j['status']=='done'
                and j['result']['request']['media_id']==media['id']
                and j['result']['request']['start']==0 and j['result']['request']['end']==5),None)
    if track is None:
        detection=submit('/api/vision/detect',{'media_id':media['id'],'start':0,'end':5,'text':'person'})
        assert detection['result']['count']>0
        track=submit('/api/vision/track',{'media_id':media['id'],'start':0,'end':5,'annotations':[
            {'frame':0,'points':[],'detection_id':detection['id'],'candidate':0}]})
    report['visual_tracking']={k:v for k,v in track['result'].items() if k not in ('annotations','request')}
    base={'media_id':media['id'],'start':0,'end':5,'model':'small','prompt':'woman speaking','regions':[{'sign':'+','start':1,'end':2},{'sign':'-','start':3,'end':3.5}],'tracking_id':track['id'],'seed':42}
    job=submit('/api/separate',base);validate_audio(job)
    export=submit('/api/exports',{'run_id':job['id'],'track':'target'})
    info=probe(DATA/export['result']['file']);assert abs(info['duration']-5)<.1
    report['export']={'job_id':export['id'],'duration':info['duration']}
    for name in ('base','large'):
        payload=dict(base,model=name,prompt='man speaking',regions=[],tracking_id=None)
        job=submit('/api/separate',payload);validate_audio(job)
    # Create a long video using only the bundled public example.
    long=ROOT/'outputs/office-32s.mp4'
    command([FFMPEG,'-y','-v','error','-stream_loop','-1','-i',str(ROOT/'examples/assets/office.mp4'),'-t','32','-c:v','libx264','-preset','veryfast','-c:a','aac',str(long)])
    with long.open('rb') as f:
        r=client.post('/api/media',files={'file':('office-32s.mp4',f,'video/mp4')});r.raise_for_status()
    imported=r.json();wait(imported['job']['id'])
    payload=dict(base,media_id=imported['media']['id'],start=2,end=32,tracking_id=None,prompt='man speaking',regions=[{'sign':'+','start':3,'end':5},{'sign':'-','start':10,'end':11}])
    job=submit('/api/separate',payload);validate_audio(job)
    # Exercise real click-based tracking with corrections on two frames.
    visual=submit('/api/vision/track',{'media_id':media['id'],'start':0,'end':1.2,'frame':0,'text':'','annotations':[
        {'frame':0,'points':[{'x':.76,'y':.5,'label':1},{'x':.2,'y':.5,'label':0}]},
        {'frame':20,'points':[{'x':.76,'y':.5,'label':1},{'x':.5,'y':.15,'label':0}]}]})
    assert visual['result']['count']==30 and visual['result']['visible_frames']>=27 and visual['result']['weights_verified']
    report['click_tracking']={k:v for k,v in visual['result'].items() if k not in ('annotations','request')}
    (ROOT/'outputs/lab-validation.json').write_text(json.dumps(report,indent=2))
    print('SMOKE ACCEPTANCE PASSED',flush=True)

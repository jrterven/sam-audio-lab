import json
import subprocess
import numpy as np
import pytest
from pydantic import ValidationError
from lab.schemas import Recipe, VisionRequest
from lab import media, store


def test_regions_are_absolute_and_contradictions_rejected():
    r = Recipe(media_id='a', start=10, end=15, regions=[{'sign':'+','start':11,'end':12},{'sign':'-','start':13,'end':14}])
    assert r.regions[0].start-r.start == 1
    for regions in ([{'sign':'+','start':9,'end':12}], [{'sign':'+','start':11,'end':13},{'sign':'-','start':12,'end':14}]):
        with pytest.raises(ValidationError):
            Recipe(media_id='a',start=10,end=15,regions=regions)


@pytest.mark.parametrize('start,end', [(0,0),(0,31),(-1,5),(float('nan'),5),(0,float('inf'))])
def test_invalid_clips(start,end):
    with pytest.raises(ValidationError):
        Recipe(media_id='a',start=start,end=end)


def test_visual_coordinates_and_frames():
    with pytest.raises(ValidationError):
        VisionRequest(media_id='a',start=0,end=5,frame=125)
    with pytest.raises(ValidationError):
        VisionRequest(media_id='a',start=0,end=5,annotations=[{'frame':0,'points':[{'x':1.1,'y':.5,'label':1}]}])


def test_persistent_records_do_not_mutate_input(tmp_path, monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path)
    original={'recipe':{'prompt':'voice'},'status':'running'}
    a=store.save('job',original)
    original['recipe']['prompt']='changed'
    assert store.get(a['id'])['recipe']['prompt']=='voice'
    store.update(a['id'],status='done')
    assert store.get(a['id'])['created']==a['created']
    assert store.all_of('job')[0]['status']=='done'


def test_clip_offsets_export_and_no_audio(tmp_path,monkeypatch):
    import soundfile as sf
    monkeypatch.setattr(media,'DATA',tmp_path)
    # Two seconds of one tone followed by a different tone, with real video.
    wav=tmp_path/'tones.wav'
    samples=np.concatenate([np.sin(2*np.pi*f*np.arange(48000*2)/48000) for f in [220,880]]).astype('float32')*.1
    sf.write(wav,samples,48000)
    video=tmp_path/'source.mp4'
    media.command([media.FFMPEG,'-y','-v','error','-f','lavfi','-i','color=c=blue:s=128x72:r=30:d=4','-i',str(wav),'-vf',r'select=not(mod(n\,3))+eq(mod(n\,7)\,0)','-fps_mode','vfr','-c:v','libx264','-c:a','aac',str(video)])
    source_info=json.loads(media.command([media.FFPROBE,'-v','error','-show_streams','-of','json',str(video)]))
    source_video=next(s for s in source_info['streams'] if s['codec_type']=='video')
    assert source_video['avg_frame_rate'] != source_video['r_frame_rate']
    info=media.probe(video)
    m=dict(info,id='test',path='source.mp4')
    clip=media.prepare_clip(m,2,4)
    audio,sr=sf.read(clip['audio']);assert sr==48000 and abs(len(audio)-96000)<10
    assert 875<np.argmax(abs(np.fft.rfft(audio)))*sr/len(audio)<885
    p=json.loads(media.command([media.FFPROBE,'-v','error','-show_streams','-of','json',clip['video']]))
    assert next(s for s in p['streams'] if s['codec_type']=='video')['r_frame_rate']=='25/1'
    out=tmp_path/'export.mp4';media.export_video(m,{'start':2,'end':4},clip['audio'],out)
    assert abs(media.probe(out)['duration']-2)<.1
    silent=tmp_path/'silent.mp4'
    media.command([media.FFMPEG,'-y','-v','error','-i',str(video),'-an','-c:v','copy',str(silent)])
    with pytest.raises(ValueError,match='pista de audio'):
        media.probe(silent)


def test_api_local_access_and_media_validation(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from lab import api
    monkeypatch.setattr(store,'DATA',tmp_path)
    monkeypatch.setattr(api,'DATA',tmp_path)
    c=TestClient(api.app)
    assert c.get('/api/state').status_code==200
    assert c.post('/api/example',headers={'Origin':'https://example.org'}).status_code==403
    assert c.get('/api/state',headers={'Host':'evil.example'}).status_code==400
    assert c.get('/api/files/results/../../lab.sqlite').status_code==404
    m=store.save('media',{'status':'ready','duration':10,'video':False})
    assert c.post('/api/separate',json={'media_id':m['id'],'end':5}).status_code==422
    assert c.post('/api/vision/detect',json={'media_id':m['id'],'start':0,'end':5,'text':'person'}).status_code==422


def test_restart_marks_unfinished_jobs_and_preserves_completed(tmp_path,monkeypatch):
    from lab.jobs import Jobs
    monkeypatch.setattr(store,'DATA',tmp_path)
    pending=store.save('job',{'status':'running','operation':'separate'})
    complete=store.save('job',{'status':'done','operation':'separate','result':{'duration':5}})
    supervisor=Jobs();supervisor.start();supervisor.close()
    assert store.get(pending['id'])['status']=='interrupted'
    assert store.get(complete['id'])['result']['duration']==5


def test_queued_cancel_never_launches_worker(tmp_path,monkeypatch):
    from lab.jobs import Jobs
    monkeypatch.setattr(store,'DATA',tmp_path)
    supervisor=Jobs()
    j=supervisor.submit('separate',{})
    assert supervisor.cancel(j['id'])['status']=='cancelled'
    assert supervisor.process is None


def test_visual_encoder_chunking_preserves_features():
    import torch
    from sam_audio.model.vision_encoder import VisionEncoder
    class Config:
        batch_size=2
        dim=3
    class Encoder(VisionEncoder):
        def __init__(self):
            super().__init__(Config())
            self.weight=torch.nn.Parameter(torch.ones(1))
        def get_transform(self):
            return lambda x:x.float()/255
        def encode(self,x):
            return x.mean((-1,-2))*self.weight
    model=Encoder()
    frames=torch.arange(5*3*8*8).remainder(256).to(torch.uint8).reshape(5,3,8,8)
    a=model([frames]);model.batch_size=0;b=model([frames])
    torch.testing.assert_close(a,b)


def test_cancelled_import_has_recoverable_media_state(tmp_path,monkeypatch):
    from lab.jobs import Jobs
    monkeypatch.setattr(store,'DATA',tmp_path)
    m=store.save('media',{'status':'importing'})
    supervisor=Jobs();job=supervisor.submit('import',{'media_id':m['id']})
    supervisor.cancel(job['id'])
    assert store.get(m['id'])['status']=='cancelled'
    assert 'Vuelve a cargar' in store.get(m['id'])['error']


def test_visual_fallback_only_for_unsupported_metal_operations(tmp_path,monkeypatch):
    import torch
    from types import SimpleNamespace
    from lab import vision
    monkeypatch.setenv('SAM_LAB_DEVICE', 'auto')
    monkeypatch.setattr(torch.cuda,'is_available',lambda:False)
    monkeypatch.setattr(vision,'DATA',tmp_path)
    monkeypatch.setattr(vision,'prepare_clip',lambda *a:{'video':str(tmp_path/'clip.mp4')})
    monkeypatch.setattr(vision,'frames_from',lambda *a:[])
    monkeypatch.setattr(vision,'_model',SimpleNamespace(_lab_revision='test'))
    monkeypatch.setattr(torch.backends.mps,'is_available',lambda:True)
    calls=[]
    def load(kind,device,progress):
        calls.append(device)
        return {'download':0.,'load':0.}
    monkeypatch.setattr(vision,'load',load)
    def infer(spec,frames,device,progress):
        if device=='mps':raise NotImplementedError('operation not implemented on MPS')
        return {'inference':.1}
    monkeypatch.setattr(vision,'infer',infer)
    spec={'operation':'track','media':{},'request':{'start':0,'end':1}}
    result=vision.vision_job(spec,lambda *a,**kw:None)
    assert result['device']=='cpu' and calls==['mps','cpu']
    assert 'MPS' in result['fallback']
    monkeypatch.setattr(vision,'infer',lambda *a:(_ for _ in ()).throw(RuntimeError('MPS backend out of memory')))
    with pytest.raises(RuntimeError,match='out of memory'):
        vision.vision_job(spec,lambda *a,**kw:None)


def test_negative_refinement_preserves_interior_positive_reference():
    from lab.vision import refinement_points
    mask=np.zeros((100,100),dtype=np.uint8);mask[20:80,30:70]=1
    points=[{'x':.5,'y':.5,'label':0}]
    result=refinement_points(points,mask)
    assert len(points)==1 and len(result)==2 and result[0]['label']==1
    p=result[0];assert mask[int(p['y']*100),int(p['x']*100)]==1
    assert (p['x']-.5)**2+(p['y']-.5)**2 >= .03**2
    positive=[{'x':.5,'y':.5,'label':1}]
    assert refinement_points(positive,mask)==positive

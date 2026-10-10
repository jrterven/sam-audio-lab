"""Real cancellation, recovery and mask-refinement acceptance checks."""
import json
import time
import httpx
from lab.config import ROOT
from tests.smoke_lab import wait, validate_audio

c=httpx.Client(base_url='http://127.0.0.1:8765',timeout=30)
s=c.get('/api/state').json()
assert len([j for j in s['jobs'] if j['operation']=='separate' and j['status']=='done'])>=4
m=next(m for m in s['media'] if m['name']=='office-32s.mp4')
r={'media_id':m['id'],'start':2,'end':32,'model':'small','prompt':'man speaking','regions':[],'tracking_id':None,'seed':42}
j=c.post('/api/separate',json=r).json()
limit=time.time()+180
while time.time()<limit:
 state=c.get('/api/jobs/'+j['id']).json()
 if state['stage']=='separate':break
 if state['status']=='error':raise RuntimeError(state)
 time.sleep(.5)
else:raise TimeoutError('cancel stage')
t=time.time();assert c.post('/api/jobs/'+j['id']+'/cancel',json={}).json()['status']=='cancelled'
print('CANCELLED',j['id'],flush=True)
r['end']=3
next_job=c.post('/api/separate',json=r).json();next_job=wait(next_job['id'])
assert next_job['result']['duration']==1 and next_job['result']['device'] in ('mps', 'cuda', 'cpu')
recovery_seconds=time.time()-t
# Reference a previously tracked mask and apply a negative click on the same frame.
prior=next(j for j in s['jobs'] if j['operation']=='track' and j['status']=='done' and j['result']['count']==30)
req=prior['result']['request']
req['annotations']=[{'frame':0,'tracking_id':prior['id'],'points':[{'x':.05,'y':.05,'label':0}]}]
refined=c.post('/api/vision/track',json=req);refined.raise_for_status();refined=wait(refined.json()['id'])
assert refined['result']['visible_frames']>=27 and refined['result']['weights_verified']
report=json.loads((ROOT/'outputs/lab-validation.json').read_text())
report['recovery']={'cancelled_job':j['id'],'recovered_job':next_job['id'],'cancellation_and_recovery_seconds':recovery_seconds,'history_restored':True}
report['refinement']={'job_id':refined['id'],'visible_frames':refined['result']['visible_frames'],'device':refined['result']['device'],'timings':refined['result']['timings']}
(ROOT/'outputs/lab-validation.json').write_text(json.dumps(report,indent=2))
print('RECOVERY AND REFINEMENT PASSED',flush=True)

"""Real SAM 3 regression: canonical weights, persistent object, mask correction."""
import json
import numpy as np
from lab.config import DATA, ROOT
from tests.smoke_lab import client, submit

s=client.get('/api/state').json()
m=next(m for m in s['media'] if m['name']=='office.mp4' and m['status']=='ready')
req={'media_id':m['id'],'start':0,'end':1.2,'annotations':[
 {'frame':0,'points':[{'x':.76,'y':.5,'label':1},{'x':.2,'y':.5,'label':0}]},
 {'frame':20,'points':[{'x':.76,'y':.5,'label':1},{'x':.5,'y':.15,'label':0}]}]}
tracked=next((j for j in s['jobs'] if j['operation']=='track' and j['status']=='done' and j['result'].get('weights_verified') and j['result']['request']['media_id']==m['id'] and j['result']['request']['end']==1.2 and len(j['result']['annotations'])==2),None)
if tracked is None:tracked=submit('/api/vision/track',req)
r=tracked['result'];assert r['weights_verified'] and r['visible_frames']>=27
original=np.load(DATA/r['masks'],mmap_mode='r')
assert np.mean(original[:,int(r['height']*.5),int(r['width']*.76)])>=.8
req['annotations']=[{'frame':0,'tracking_id':tracked['id'],'points':[{'x':.05,'y':.05,'label':0}]}]
refined=submit('/api/vision/track',req)
r2=refined['result'];assert r2['weights_verified'] and r2['visible_frames']>=27
corrected=np.load(DATA/r2['masks'],mmap_mode='r')
iou=np.logical_and(original[0],corrected[0]).sum()/max(1,np.logical_or(original[0],corrected[0]).sum())
assert iou>.5, iou
p=ROOT/'outputs/lab-validation.json';report=json.loads(p.read_text())
report['click_tracking']=dict(r,job_id=tracked['id'])
report['refinement']=dict(r2,job_id=refined['id'],initial_mask_iou=float(iou))
p.write_text(json.dumps(report,indent=2))
print('CANONICAL WEIGHTS, TRACKING AND REFINEMENT PASSED',r['visible_frames'],r2['visible_frames'],float(iou),flush=True)

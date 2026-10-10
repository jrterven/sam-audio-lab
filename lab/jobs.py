import atexit
import json
import os
import queue
import signal
import subprocess
import threading
import time
from pathlib import Path
from . import store
from .config import AUDIO_PYTHON, VISION_PYTHON, FFMPEG, FFPROBE, DATA, ROOT

TERMINAL = {'done', 'error', 'cancelled', 'interrupted'}


class Jobs:
    def __init__(self):
        self.pending = queue.Queue()
        self.process = None
        self.runtime = None
        self.messages = queue.Queue()
        self.stopping = False
        self.thread = None
        self.lock = threading.RLock()

    def start(self):
        for j in store.all_of('job'):
            if j['status'] not in TERMINAL:
                store.update(j['id'], status='interrupted', message='The application restarted. You can run this test again.')
                if j['operation'] == 'import':
                    store.update(j['spec']['media_id'], status='interrupted', error='Import interrupted. Upload the file again.')
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def submit(self, operation, spec):
        with self.lock:
            job = store.save('job', {'operation': operation, 'spec': spec, 'status': 'queued', 'stage': 'queued', 'message': 'Queued', 'updated': time.time()})
            self.pending.put(job['id'])
        return job

    def cancel(self, job_id):
        with self.lock:
            job = store.get(job_id, 'job')
            if job['status'] not in TERMINAL:
                store.update(job_id, status='cancelled', message='Cancelled', updated=time.time())
                if job['operation'] == 'import':
                    store.update(job['spec']['media_id'], status='cancelled', error='Import cancelled. Upload the file again.')
        return store.get(job_id)

    def stop_process(self):
        p, self.process = self.process, None
        self.runtime = None
        if p and p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGTERM)
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            except ProcessLookupError:
                pass

    def close(self):
        self.stopping = True
        self.stop_process()

    def spawn(self, runtime):
        self.stop_process()
        executable = VISION_PYTHON if runtime == 'vision' else AUDIO_PYTHON
        if not Path(executable).exists():
            raise RuntimeError(f'Environment not found: {executable}. See docs/INSTALLATION.md.')
        env = dict(os.environ, PYTHONUNBUFFERED='1', SAM_LAB_DATA=str(DATA), TOKENIZERS_PARALLELISM='false',
                   SAM_LAB_AUDIO_PYTHON=AUDIO_PYTHON, SAM_LAB_VISION_PYTHON=VISION_PYTHON,
                   SAM_LAB_FFMPEG=FFMPEG, SAM_LAB_FFPROBE=FFPROBE)
        self.process = subprocess.Popen([executable, '-m', 'lab.worker'], cwd=ROOT, env=env, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, start_new_session=True)
        self.runtime = runtime
        messages = self.messages = queue.Queue()
        process = self.process
        def read():
            for line in process.stdout:
                messages.put(line)
            messages.put(None)
        threading.Thread(target=read, daemon=True).start()

    def loop(self):
        while not self.stopping:
            try:
                job_id = self.pending.get(timeout=.5)
            except queue.Empty:
                continue
            with self.lock:
                job = store.get(job_id)
                if job['status'] == 'cancelled':
                    continue
                store.update(job_id, status='running', stage='starting', message='Starting', updated=time.time())
            operation = job['operation']
            try:
                runtime = 'vision' if operation in ('detect', 'track') else 'audio'
                if self.runtime != runtime or self.process is None or self.process.poll() is not None:
                    self.spawn(runtime)
                spec = dict(job['spec'], operation=operation, output=str(DATA/'results'/job_id))
                self.process.stdin.write(json.dumps(spec)+'\n')
                self.process.stdin.flush()
                log = DATA/'logs'
                log.mkdir(exist_ok=True)
                with (log/f'{job_id}.log').open('a') as logfile:
                    while not self.stopping:
                        if store.get(job_id)['status'] == 'cancelled':
                            self.stop_process()
                            break
                        try:
                            line = self.messages.get(timeout=.2)
                        except queue.Empty:
                            continue
                        if line is None:
                            raise RuntimeError('The inference process stopped unexpectedly. You can try again.')
                        if not line.startswith('@@SAMLAB@@'):
                            logfile.write(line)
                            logfile.flush()
                            continue
                        event = json.loads(line[len('@@SAMLAB@@'):])
                        if event['type'] == 'progress':
                            store.update(job_id, stage=event['stage'], message=event['message'], progress=event.get('progress'), updated=time.time())
                        elif event['type'] == 'error':
                            raise RuntimeError(event['message'])
                        elif event['type'] == 'result':
                            with self.lock:
                                if store.get(job_id)['status'] == 'cancelled':
                                    break
                                result = event['result']
                                if operation == 'import':
                                    store.update(job['spec']['media_id'], **result, status='ready')
                                store.update(job_id, result=result, status='done', stage='done', message='Completed', updated=time.time())
                            break
            except Exception as exc:
                self.stop_process()
                with self.lock:
                    if store.get(job_id)['status'] != 'cancelled':
                        store.update(job_id, status='error', message=str(exc), updated=time.time())
                        if operation == 'import':
                            store.update(job['spec']['media_id'], status='error', error=str(exc))


jobs = Jobs()
atexit.register(jobs.close)

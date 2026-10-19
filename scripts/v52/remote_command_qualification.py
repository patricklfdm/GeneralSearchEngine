"""Real subprocess command-loss qualification, not engine/cloud measurements."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from . import remote_command as commands,cloud_suite as suite,measurement_runtime as runtime
from .evidence import need,digest,encoded

ROOT=Path(__file__).resolve().parents[2]


def worker(root,request_path):
    root=Path(root);owner=commands.read(root/'binding.json',commands.REQUEST_BYTES)
    store=commands.CommandStore(root,owner);request=commands.read(request_path,commands.REQUEST_BYTES)
    def handler(kind,payload,checkpoint):
        need(kind=='execute-history' and set(payload)=={'probe'} and payload['probe'] in ('complete','hold'),'command qualification probe only')
        # One forced marker represents handler entry. It is never an engine write.
        fd=os.open(root/'handler-entries.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(encoded(dict(commandId=request['commandId'],process=commands.process_identity()))+b'\n')
            stream.flush();os.fsync(stream.fileno())
        commands.sync_directory(root)
        if payload['probe']=='hold':
            end=time.monotonic()+20
            while time.monotonic()<end:checkpoint();time.sleep(.01)
            raise TimeoutError('qualification supervisor did not stop probe')
        return dict(execution='forced-marker-only',engineMutation=False)
    commands.write_once(Path(request_path).with_suffix('.reply.json'),store.execute(request,handler))


def until(predicate):
    end=time.monotonic()+10
    while time.monotonic()<end:
        if predicate():return
        time.sleep(.01)
    raise TimeoutError('qualification subprocess observation')


def run(output):
    root=Path(output).absolute();root.mkdir(parents=True,exist_ok=False)
    def source():return runtime.build.binding(ROOT,subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    original=source();processes=[];streams=[]
    receipt=dict(schema='gse-v52-command-qualification-v1',status='FAIL',sourceBinding=original,
                 execution='local-process-command-markers-only',syntheticSelection=True,engineWorkloadExecuted=False,
                 qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False,cases=[])
    try:
        # Explicit non-admission fixture: no physical build/package is claimed.
        fake=dict(source=original['source'],checkoutSha256=original['checkoutSha256'],sequence=uuid.uuid4().hex,
                  suiteSha256=suite.PLAN_SHA,programSha256=suite.model.PLAN_SHA,buildManifestSha256='0'*64,
                  packageSha256='0'*64,controlsManifestSha256=suite.load()['controlsManifestSha256'])
        selected=suite.selection(fake,'experiment',uuid.uuid4().hex)
        owner=commands.binding(selected,selected['member']['histories'][0],'node-1',commands.boot_id(),uuid.uuid4().hex)
        store=commands.CommandStore(root/'guest',owner,create=True)
        def spawn(value,label):
            path=root/(label+'.request.json');commands.write_once(path,value,commands.REQUEST_BYTES)
            out=(root/(label+'.stdout')).open('xb');err=(root/(label+'.stderr')).open('xb');streams.extend((out,err))
            proc=subprocess.Popen([sys.executable,'-m','scripts.v52.remote_command_qualification','--worker',store.root,'--request',path],
                                  cwd=ROOT,stdout=out,stderr=err,start_new_session=True)
            processes.append(proc);return proc
        def count():
            p=store.root/'handler-entries.jsonl';return len(p.read_text().splitlines()) if p.exists() else 0
        value=commands.request(owner,uuid.uuid4().hex,'execute-history',dict(probe='complete'))
        class LostReply:
            submits=0
            def submit(self,request,deadline):
                self.submits+=1;spawn(request,'lost-response');raise ConnectionError('initial connection lost')
            def query(self,request,deadline):return store.query(request)
        transport=LostReply();result=commands.submit_and_observe(transport,value,owner)
        need(result['state']=='SUCCEEDED' and transport.submits==count()==1,'command duplicate/lost original result')
        receipt['cases'].append(dict(name='lost-initial-response',status='PASS',submits=1,handlerEntries=1))
        duplicate=spawn(value,'duplicate');need(duplicate.wait(timeout=10)==0 and count()==1,'duplicate process reentered handler')
        receipt['cases'].append(dict(name='separate-duplicate-process',status='PASS',handlerEntries=1))
        held=commands.request(owner,uuid.uuid4().hex,'execute-history',dict(probe='hold'))
        victim=spawn(held,'kill');until(lambda:count()==2)
        original_process=store.query(held)['process'];need(original_process['pid']==victim.pid,'owned probe process')
        victim.kill();victim.wait(timeout=10)
        need(store.query(held)['state']=='UNCERTAIN','killed probe not detected')
        duplicate=spawn(held,'killed-duplicate');need(duplicate.wait(timeout=10)==0 and count()==2,'killed handler replayed')
        receipt['cases'].append(dict(name='sigkill-after-entry',status='PASS',originalProcess=original_process,
                                    exitCode=victim.returncode,uncertaintyRetained=True,handlerEntries=2,receiptState='UNCERTAIN'))
        cancelled=commands.request(owner,uuid.uuid4().hex,'execute-history',dict(probe='hold'))
        proc=spawn(cancelled,'cancel');until(lambda:count()==3);store.cancel(cancelled)
        need(proc.wait(timeout=10)==0 and store.query(cancelled)['state']=='CANCELLED','cooperative cancellation missing')
        need(count()==3,'cancellation replayed handler')
        receipt['cases'].append(dict(name='cancel-after-entry',status='PASS',handlerEntries=3))
        need(source()==original,'command qualification source changed');receipt['status']='PASS'
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        cleanup=[]
        for proc in processes:
            forced=proc.poll() is None
            if forced:
                # Only these owned Popen instances can be stopped here.
                try:proc.wait(timeout=5);forced=False
                except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
            cleanup.append(dict(pid=proc.pid,exitCode=proc.returncode,reaped=proc.poll() is not None,forcedCleanup=forced))
        for stream in streams:stream.close()
        receipt['processCleanup']=cleanup
        if any(row['forcedCleanup'] for row in cleanup):receipt['status']='FAIL'
        commands.write_once(root/'receipt.json',receipt)
    need(receipt['status']=='PASS','command qualification cleanup failed');return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',nargs='?');p.add_argument('--worker');p.add_argument('--request');a=p.parse_args()
    if a.worker:
        need(a.request and not a.output,'command worker arguments');worker(a.worker,a.request)
    else:
        need(a.output and not a.request,'command qualification arguments');run(a.output)

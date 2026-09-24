"""Real subprocess/receipt/collection qualification; no GSE or cloud workload claim."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
from . import performance_model as m, cloud_workload_contract as contract
from . import remote_command as command, remote_collection as collection, remote_schedule as schedule
from .remote_schedule_evidence import validate as validate_schedule

ROOT = Path(__file__).resolve().parents[2]


def worker(root, request_path):
    root = Path(root)
    owner = command.read(root/'binding.json')
    store = command.CommandStore(root,owner)
    request = command.read(request_path)
    def handler(kind,payload,checkpoint):
        m.need(kind == 'window' and payload['probe'] in ('complete','hold'), 'qualification handler only')
        # This durable append stands in for one irreversible handler entry. It is
        # deliberately not labelled an engine mutation or protocol observation.
        log = root/'handler-entries.jsonl'
        fd = os.open(log,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(m.canonical(dict(commandId=request['commandId'],pid=os.getpid()))+b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        command.sync_directory(root)
        if payload['probe'] == 'hold':
            deadline = time.monotonic()+20
            while time.monotonic() < deadline:
                checkpoint()
                time.sleep(.01)
            raise TimeoutError('qualification supervisor failed to release/stop worker')
        return dict(outcome='SUCCESS',execution='receipt-probe-only')
    command.write_once(request_path.with_suffix('.reply.json'),store.execute(request,handler))


def until(predicate,seconds=5):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.01)
    raise TimeoutError('qualification observation deadline')


def qualify(root):
    root=Path(root).absolute()
    root.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v51-remote-foundation-qualification-v1',execution='local-remote-control-only',
                 status='FAIL',paidCloud=False,engineWorkloadExecuted=False,fullRemoteQualification=False,
                 workloadSha256=contract.PLAN_SHA256,cases=[])
    children=[]
    logs=[]
    try:
        source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,timeout=5).strip()
        files=sorted((ROOT/'scripts/v51').glob('remote_*.py'))
        sources={str(p.relative_to(ROOT)):m.sha(p.read_bytes()) for p in files}
        command.write_once(root/'source-files.json',sources)
        receipt.update(source=source,sourceFilesSha256=m.sha(m.canonical(sources)))
        owner=command.binding(source,m.sha(m.canonical(sources)),uuid.uuid4().hex,'node-1')
        store=command.CommandStore(root/'guest',owner,create=True)
        command.write_once(root/'workload.json',contract.load())
        def spawn(request,label):
            path=root/(label+'.request.json')
            command.write_once(path,request)
            out=(root/(label+'.stdout')).open('xb');err=(root/(label+'.stderr')).open('xb')
            logs.extend((out,err))
            proc=subprocess.Popen([sys.executable,'-m','scripts.v51.remote_qualification','--worker',store.root,'--request',path],
                                  cwd=ROOT,stdout=out,stderr=err,start_new_session=True)
            children.append(proc)
            return proc
        def count():
            path=store.root/'handler-entries.jsonl'
            return len(path.read_text().splitlines()) if path.exists() else 0
        request=command.request(owner,uuid.uuid4().hex,'window',dict(probe='complete'))
        class DroppedReply:
            submits=0
            def submit(self,value,deadline):
                self.submits+=1
                spawn(value,'lost-response')
                raise ConnectionError('controller lost initial connection')
            def query(self,value,deadline):return store.query(value)
        transport=DroppedReply()
        result=command.submit_and_observe(transport,request,time.monotonic()+10)
        m.need(result['state']=='SUCCEEDED' and transport.submits==count()==1,'lost response caused replay/lost result')
        receipt['cases'].append(dict(name='lost-response',status='PASS',submits=transport.submits,handlerEntries=count()))
        # A second process retries the exact command; it must return the receipt.
        duplicate=spawn(request,'duplicate')
        m.need(duplicate.wait(timeout=5)==0 and count()==1,'duplicate process replayed command')
        receipt['cases'].append(dict(name='duplicate-process',status='PASS',handlerEntries=count()))

        held=command.request(owner,uuid.uuid4().hex,'window',dict(probe='hold'))
        victim=spawn(held,'killed-handler')
        until(lambda:count()==2)
        victim.kill();victim.wait(timeout=5)
        m.need(store.query(held)['state']=='RUNNING','crash falsely terminal')
        duplicate=spawn(held,'after-crash')
        m.need(duplicate.wait(timeout=5)==0 and count()==2,'crashed handler replayed')
        receipt['cases'].append(dict(name='sigkill-after-handler-entry',status='PASS',originalPid=victim.pid,
                                    exitCode=victim.returncode,receiptState='RUNNING',handlerEntries=count(),uncertaintyRetained=True))

        cancelled=command.request(owner,uuid.uuid4().hex,'window',dict(probe='hold'))
        proc=spawn(cancelled,'cancelled-handler')
        until(lambda:count()==3)
        store.cancel(cancelled)
        m.need(proc.wait(timeout=5)==0 and store.query(cancelled)['state']=='CANCELLED','cancel did not stop handler')
        receipt['cases'].append(dict(name='cancel-after-entry',status='PASS',handlerEntries=count()))

        # Full frozen tapes use a deterministic guest clock; these are scheduler
        # state-machine traces, explicitly not timed rich engine executions.
        schedules=[]
        for preset,cell in [('canonical','healthy'),('experiment','healthy'),('canonical','read-heavy'),('canonical','sustained')]:
            for spec in schedule.windows(cell,preset):
                events=[]
                state=schedule.WindowState(spec,10**9,events.append)
                for call in spec['calls']:
                    now=state.start+call['dueMillis']*10**6+call['lane']*1000
                    m.need(state.offer(call,now) and state.invoke(call['ordinal'],now),'frozen tape rejected')
                    state.complete(call['ordinal'],now+500,{'outcome':'SUCCESS','execution':'synthetic-scheduler-callback'})
                result=state.finish(state.start+spec['durationNanos'])
                m.need(result['status']=='PASS','frozen scheduler rejected')
                schedules.append(dict(spec=spec,events=events,result=result,validation=validate_schedule(spec,events,result)))
        command.write_once(root/'scheduler-traces.json',schedules)
        receipt['cases'].append(dict(name='full-frozen-arrival-accounting',status='PASS',calls=sum(len(s['spec']['calls']) for s in schedules),
                                    execution='deterministic-clock-only'))
        receipt['status']='CONTROL_CHECKS_PASSED'
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error))
        raise
    finally:
        cleanup=[]
        for proc in children:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            cleanup.append(dict(pid=proc.pid,exitCode=proc.returncode,reaped=proc.poll() is not None))
        for stream in logs:stream.close()
        receipt['processCleanup']=cleanup
        command.write_once(root/'receipt.json',receipt)
    parts=root.parent/(root.name+'-parts')
    binding_sha=m.sha(m.canonical(owner))
    final=dict(schema='gse-v51-remote-foundation-result-v1',status='FAIL',execution=receipt['execution'],
               controlReceiptSha256=m.sha((root/'receipt.json').read_bytes()),
               cases=len(receipt['cases']),paidCloud=False,fullRemoteQualification=False)
    try:
        collection.pack(root,parts,binding_sha)
        final['collection']=collection.unpack(parts,root.parent/(root.name+'-replayed'),binding_sha)
        final['status']='PASS'
    except BaseException as error:
        final['failure']=dict(type=type(error).__name__,message=str(error))
        raise
    finally:
        command.write_once(root.parent/(root.name+'-result.json'),final)
    print(m.canonical(final).decode(),flush=True)
    return final



if __name__=='__main__':
    def terminated(*_):
        raise TimeoutError('qualification process terminated')
    signal.signal(signal.SIGTERM,terminated)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',nargs='?')
    parser.add_argument('--worker',type=Path)
    parser.add_argument('--request',type=Path)
    args=parser.parse_args()
    if args.worker:
        m.need(args.request is not None,'worker request required')
        worker(args.worker,args.request)
    else:
        m.need(args.output is not None,'qualification output required')
        qualify(args.output)

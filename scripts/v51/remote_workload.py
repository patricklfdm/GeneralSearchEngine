"""Local guest path for the full frozen rich tapes. No cloud admission or paid dispatch."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import threading
import time
import uuid
from . import performance_harness as base,performance_model as m,performance_plan as local
from . import cloud_workload_contract as contract,remote_schedule as scheduler,remote_command as commands
from . import remote_schedule_evidence,performance_semantics as semantic
from .storage_inspector import inventory
from .remote_jvm import Worker

from .remote_rich_plan import MODES, CELLS
MAINS=dict(zip(MODES,('admission.V51CloudLocal','replication.V51CloudConfigured','replication.V51CloudAutomatic')))


class Run(base.Run):
    def __init__(self,root,plan):
        super().__init__(root,plan)
        self.work_deadline=self.started+2400*10**9
        self.deadline=self.work_deadline

    @contextmanager
    def stage(self,name,seconds):
        row=dict(name=name,startNanos=time.monotonic_ns(),status='FAIL');self.stages.append(row)
        old=self.deadline;self.deadline=min(self.work_deadline,row['startNanos']+seconds*10**9)
        try:
            yield
            self.remaining();row['status']='PASS'
        finally:
            row['endNanos']=time.monotonic_ns();self.deadline=old
            base.save(self.root/'stages.json',self.stages)


def run_cell(run,root,mode,adapter,source,cell,preset):
    start=time.monotonic_ns()
    base.group_directory(root)
    cp=adapter['cp']
    if mode!='published-v4.4-local':
        run.process(run.java(cp,MAINS[mode],root,'setup',run.root/'plan.json',source),'bootstrap',root)
    workers=[]
    if mode=='published-v4.4-local':
        workers=[Worker(run,root,'local',run.java(cp,MAINS[mode],root,'run',run.root/'plan.json',source))]
        active=workers[0]
    else:
        workers=[Worker(run,root,'node-'+str(i),run.java(cp,MAINS[mode],root,i,run.root/'plan.json',source)) for i in (1,2,3)]
        active=None
        if mode=='published-v5.0-configured':
            active=workers[0];active.command('activate')
        else:
            while active is None:
                m.need(time.monotonic_ns()-start<30*10**9,'guest activation ceiling')
                for worker in workers:
                    status=worker.command('status')['status']
                    m.need(status['state']!='FAILED','guest activation failed')
                    if status['state']=='LEADER_READY':active=worker;break
                if active is None:time.sleep(.05)
    owner=commands.binding(run.source,m.sha(m.canonical(adapter)),uuid.uuid4().hex,'node-1' if active.node=='local' else active.node)
    store=commands.CommandStore(root/'commands',owner,create=True)
    rows=[];windows=[]
    for spec in scheduler.windows(cell,preset):
        for worker in workers:worker.command('configure',window=spec['window'])
        window_dir=root/spec['window'];window_dir.mkdir()
        events=[];lock=threading.Lock()
        def observe(row):
            with lock:
                events.append(row)
                with (window_dir/'arrivals.jsonl').open('ab') as out:out.write(m.canonical(row)+b'\n')
        def operation(call):
            response=active.command('call',**call)
            result=dict(response['call'],opId=response['opId'],node=active.node,pid=active.proc.pid)
            with lock:rows.append(result)
            return dict(outcome=result['outcome'],opId=response['opId'],resultSha256=m.sha(m.canonical(response)))
        request=commands.request(owner,uuid.uuid4().hex,'window',dict(cell=cell,preset=preset,window=spec['window']))
        def execute(kind,payload,checkpoint):
            checkpoint()
            result=scheduler.execute_window(cell,preset,spec['window'],operation,observe,lambda:store.cancelled(request))
            base.save(window_dir/'spec.json',spec);base.save(window_dir/'result.json',result)
            result['validation']=remote_schedule_evidence.validate(spec,events,result)
            m.need(result['status']=='PASS','frozen guest window failed: '+str(result))
            return result
        receipt=store.execute(request,execute)
        base.save(window_dir/'receipt.json',receipt)
        m.need(receipt['state']=='SUCCEEDED','window command failed: '+str(receipt))
        windows.append(dict(window=spec['window'],commandId=request['commandId'],requestSha256=receipt['requestSha256']))
        print(json.dumps(dict(cell=cell,mode=mode,window=spec['window'],status='EXECUTED')),flush=True)
    base.save(root/'calls.json',sorted(rows,key=lambda r:r['ordinal']))
    base.save(root/'windows.json',windows)
    # Published V4.4 rejects backup after index recreation (documented in 6A).
    # Its final checkpoint remains the independent durable state observation.
    if mode=='published-v4.4-local':active.command('checkpoint')
    else:active.command('backup')
    if mode=='published-v5.0-configured':
        for worker in workers:
            if worker is not active:active.command('catchup',peer=worker.node)
    elif mode=='candidate-v5.1-automatic':
        floor=active.command('status')['status']['provenIndex']
        while True:
            states=[worker.command('status')['status'] for worker in workers]
            m.need(all(s['state']!='FAILED' for s in states),'guest convergence failed')
            if all(s['provenIndex']>=floor for s in states):break
            run.remaining();time.sleep(.1)
    for worker in workers:worker.stop()
    restore_root=root/'restored-check';restore_root.mkdir()
    control=run.adapters[MODES[0]]['cp']
    if mode=='published-v4.4-local':
        args=run.java(control,MAINS[MODES[0]],root,'reopen',run.root/'plan.json',source)
    else:
        args=run.java(control,MAINS[MODES[0]],restore_root,'restore',run.root/'plan.json',root/'export')
    run.process(args,'restore',restore_root)
    return dict(cell=cell,mode=mode,directory=root.name,active=active.node,startNanos=start,endNanos=time.monotonic_ns(),
                calls=len(rows),binding=owner)


def run(output,preset='canonical',only=None,*,selected=None,source_seed=None):
    m.need(selected is None or (only is None and tuple(selected)==tuple(c for c in CELLS if c in selected)),
           'invalid rich cell selection')
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    runner=Run(root,local.load())
    base.save(root/'plan.json',runner.plan);base.save(root/'cloud-plan.json',contract.load())
    receipt=dict(schema='gse-v51-remote-rich-execution-v1',status='FAIL',execution='local-guest-rich-workload-only',
                 paidCloud=False,fullRemoteQualification=False,preset=preset,cells=[])
    try:
        with runner.stage('preparation',600):
            runner.source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=base.ROOT,text=True,timeout=5).strip()
            receipt['source']=runner.source
            paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=base.ROOT,timeout=10).decode().split('\0')
            base.save(root/'source-inventory.json',{p:m.sha((base.ROOT/p).read_bytes()) for p in sorted(set(paths)) if p and (base.ROOT/p).is_file()})
            receipt['sourceInventorySha256']=m.sha((root/'source-inventory.json').read_bytes())
            receipt['controls']=m.strict_json(runner.process([sys.executable,'-m','scripts.v51.controls',base.ROOT/'target/v51-controls'],'resolve-controls'))
            receipt['adapters']=runner.adapters=base.compile_adapters(runner,base.ROOT/'target/v51-controls')
            receipt['evidenceWriterChecks']=[]
            for kind in ('bound-count','bound-bytes','write-failure'):
                checked=runner.process(runner.java(receipt['adapters'][MODES[0]]['cp'],'admission.V51CloudJournalCheck',
                                       root/'writer-checks'/kind,kind),'writer-'+kind)
                receipt['evidenceWriterChecks'].append(m.strict_json(checked))
            source=root/'source'
            if source_seed is None:
                runner.process(runner.java(receipt['adapters'][MODES[0]]['cp'],'admission.V51CloudLocal',root,'prepare',root/'plan.json',source),'prepare-source')
            else:
                # The caller has validated the portable input and its source/build binding.
                shutil.copytree(source_seed,source)
            receipt['sourceBackup']=semantic.source_backup(source,m.initial(runner.plan))
            base.save(root/'source-before.json',inventory(source))
        for cell,mode in CELLS if selected is None else selected:
            label=cell+'-'+mode
            if only and only!=label:continue
            seconds=300 if cell=='healthy' else 180 if cell=='read-heavy' else 240
            with runner.stage(label,seconds):
                receipt['cells'].append(run_cell(runner,root/label,mode,receipt['adapters'][mode],source,cell,preset))
                base.save(root/'execution.json',receipt)
        base.save(root/'source-after.json',inventory(source))
        receipt['status']='EXECUTED'
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        runner.deadline=time.monotonic_ns()+60*10**9
        errors=[]
        for worker in runner.workers:
            try:worker.stop(failed=True)
            except BaseException as error:errors.append(str(error))
        receipt['cleanupErrors']=errors
        if errors:receipt['status']='FAIL'
        receipt['elapsedNanos']=time.monotonic_ns()-runner.started
        base.save(root/'execution.json',receipt)
    m.need(receipt['status']=='EXECUTED','guest execution/cleanup failed')
    print(json.dumps(dict(status='EXECUTED',root=str(root),paidCloud=False,independentValidation='pending')),flush=True)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');parser.add_argument('--preset',choices=('canonical','experiment'),default='canonical');parser.add_argument('--only')
    args=parser.parse_args()
    def terminate(*_):raise TimeoutError('guest qualification terminated')
    signal.signal(signal.SIGTERM,terminate)
    run(args.output,args.preset,args.only)

"""Owned public JVM integration for the frozen 512-slot boundary. No paid execution."""
import argparse
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time
import tempfile
from . import performance_harness as h, performance_model as m, performance_plan as plan, performance_semantics as semantic
from . import public_qualification_harness as q, remote_collection as collection, storage_inspector as storage

NODES=('node-1','node-2','node-3')


class Worker(q.Worker):
    def __init__(self,root,node,cp,history,generation,flags):
        self.root,self.node,self.history,self.generation=root,node,history,generation
        self.lock=threading.Lock();self.pending={};self.serial=0;self.startup=queue.Queue(1);self.consumer='full-size-runtime'
        self.log=(root/f'{node}-g{generation}-stderr.log').open('xb')
        args=['java',*flags,'-cp',cp,h.PACKAGE+'replication.V51FullSizeRuntime',str(root),node[-1],str(generation)]
        self.started=time.monotonic_ns();self.proc=subprocess.Popen(args,cwd=h.ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True)
        self.identity=dict(node=node,generation=generation,pid=self.proc.pid,args=args,startNanos=self.started,
                           linuxStartTicks=Path(f'/proc/{self.proc.pid}/stat').read_text().rsplit(')',1)[1].split()[19])
        self.reader=threading.Thread(target=self.read,daemon=True);self.reader.start()
        try:m.need(self.startup.get(timeout=30)['status']=='STARTED','public full-size startup')
        except BaseException:self.stop(kill=True);raise

    def finish(self,expected=0):
        try:self.stop(kill=expected!=0)
        finally:self.identity.update(endNanos=time.monotonic_ns(),exitCode=self.proc.returncode)
        m.need(self.proc.returncode==expected,'unexpected public voter exit')


def mutation(ordinal):
    m.need(1<=ordinal<=511,'full-size public mutation bound')
    return dict(key=1+(ordinal-1)%64,revision=1+(ordinal-1)//64)


def replace(path,value):
    staging=path.with_suffix('.pending');staging.write_text(value);staging.replace(path)


def execute(root,cp,flags):
    history=[];workers={};identities=[];generations={};revision=0
    receipt=dict(status='FAIL',processes=identities,scope='public-512-slot-boundary',paidCloud=False)
    deadline=time.monotonic()+600
    def wait(action,label,seconds=45):
        end=min(deadline,time.monotonic()+seconds)
        while time.monotonic()<end:
            result=action()
            if result:return result
            time.sleep(.05)
        raise ValueError(label)
    def start(node):
        generation=generations.get(node,0)+1;generations[node]=generation
        w=Worker(root,node,cp,history,generation,flags);workers[node]=w;identities.append(w.identity);return w
    def stop(node,code=0):
        w=workers.pop(node);w.finish(code)
    def status():return {n:w.call('status') for n,w in workers.items()}
    def leader():
        def choose():
            states=status();m.need(all(s['state']!='FAILED' for s in states.values()),'failed public voter: '+str(states))
            return next(((n,workers[n]) for n,s in states.items() if s['state']=='LEADER_READY'),None)
        return wait(choose,'public full-size leader unavailable')
    def update(w):
        nonlocal revision
        revision+=1;return w.call('update',**mutation(revision))
    def stable_read():
        for _ in range(4):
            n,w=leader();result=w.send('read').result(timeout=20)
            m.need(result is not None,'public read disconnected')
            if result['outcome']=='SUCCESS':return n,w,result
            m.need(result['outcome']=='NOT_APPLICABLE' and result.get('reasonCode') in q.RECOVERY_REASONS,'unexpected public read refusal')
        raise ValueError('public read did not recover')
    def fill(target):
        n,w=leader()
        while True:
            cut=w.call('status')['provenIndex'];m.need(cut<=target,'public fill overshot declared cut')
            if cut==target:
                print(m.canonical(dict(stage='public-fill',index=cut,status='PASS')).decode(),flush=True);return n,w
            update(w);wait(lambda:w.call('status')['provenIndex']>cut,'public update status did not advance',10)
    def signals(node):
        rows=[]
        for p in sorted(root.glob(node+'-g*-signals.jsonl')):rows.extend(m.strict_json(v) for v in p.read_bytes().split(b'\n')[:-1])
        return rows
    def observed(node,event,after=0):return next((r for r in signals(node) if r['event']==event and r['localNanos']>after),None)
    def converged(cut):return all(s['provenIndex']>=cut for s in status().values())
    def partition(node):replace(root/'network-rules.txt',''.join(f'{a} {b} BEFORE_REQUEST_WRITE *\n' for a in NODES for b in NODES if a!=b and node in (a,b)))
    try:
        for n in NODES:start(n)
        old,w=fill(480);receipt['chosenAt']=w.call('status')['provenIndex']+1
        replace(root/(old+'-arm.txt'),'CHOSEN\nhalt\n')
        revision+=1;pending=w.send('update',**mutation(revision));receipt['uncertainOpId']=history[-1]['opId']
        wait(lambda:observed(old,'CUT_REACHED'),'chosen response cut missing');w.proc.wait(timeout=10)
        stop(old,71);m.need(pending.result(timeout=5) is None,'halted mutation fabricated response')
        active,w,_=stable_read();receipt['recoveryLeader']=active
        start(old);wait(lambda:converged(w.call('status')['provenIndex']),'retained voter rejoin failed')
        active,w,_=stable_read();before=time.monotonic_ns()
        replace(root/(active+'-arm.txt'),'READ_CAPTURED\npause\n')
        pinned=w.send('read');receipt['pinnedOpId']=history[-1]['opId']
        wait(lambda:observed(active,'CUT_REACHED',before),'public read capture missing')
        partition(active)
        # The isolated READY hint is excluded; only the surviving majority can progress.
        pinned_worker=workers.pop(active)
        try:
            new,w,_=stable_read();update(w);receipt['pinMajorityLeader']=new
            majority_cut=w.call('status')['provenIndex']
        finally:workers[active]=pinned_worker
        replace(root/'network-rules.txt','')
        # A held public view owns the application worker; release it before awaiting reconstruction.
        wait(lambda:observed(active,'FORCE',before),'pinned voter did not observe a newer promise')
        (root/(active+'-release')).touch();answer=pinned.result(timeout=20)
        m.need(answer is not None and answer['outcome']=='SUCCESS','pinned public read failed')
        wait(lambda:workers[active].call('status')['provenIndex']>=majority_cut,'released voter did not regain majority prefix')
        stable_read();wait(lambda:converged(max(s['provenIndex'] for s in status().values())),'post-pin convergence')
        active,w=fill(500)
        lagging=next(n for n in NODES if n!=active);stop(lagging);receipt['fullTransferNode']=lagging
        active,w=fill(511);last=w.call('read');receipt['finalReadOpId']=last['opId']
        wait(lambda:w.call('status')['provenIndex']==512,'final public read did not reach 512',10)
        wait(lambda:sum((root/active/g).is_dir() for g in ('generation-a','generation-b'))<=1,'checkpoint awaits durable floor cleanup')
        w.call('checkpoint');restart=time.monotonic_ns();start(lagging)
        wait(lambda:observed(lagging,'REJOIN_INSTALLED',restart),'full-size rejoin missing')
        wait(lambda:converged(512),'full-size final convergence')
        receipt['finalStatus']=status();m.need(all(s['provenIndex']==512 for s in receipt['finalStatus'].values()),'full-size slot cap')
        # No activation/read may append slot 513. Halt after real complete basis selection.
        for n in NODES:replace(root/(n+'-arm.txt'),'PROMISE_QUORUM\nhalt\n')
        stop(active);receipt['terminalStoppedLeader']=active
        cut=wait(lambda:next(((n,observed(n,'CUT_REACHED',restart)) for n in workers if observed(n,'CUT_REACHED',restart)),None),
                 'terminal full-size basis selection missing')
        n,event=cut;m.need(event['cut']=='PROMISE_QUORUM','wrong terminal cut');workers[n].proc.wait(timeout=10);stop(n,71)
        receipt['terminalNode']=n;receipt['status']='EXECUTED'
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        replace(root/'network-rules.txt','')
        for n in NODES:(root/(n+'-release')).touch()
        errors=[]
        for n,w in list(workers.items()):
            try:stop(n,71 if w.proc.poll()==71 else 0)
            except Exception as error:errors.append(str(error))
        receipt['cleanupErrors']=errors;h.save(root/'history.json',history);h.save(root/'runtime.json',receipt)
        m.need(not errors,'public full-size cleanup: '+str(errors))
    return receipt


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False);raw=root/'raw';raw.mkdir()
    admitted=plan.load();h.save(raw/'plan.json',admitted);runner=h.Run(raw,admitted)
    execution=dict(schema='gse-v51-full-size-runtime-v1',execution='local-public-full-size-runtime',status='FAIL',paidCloud=False,fullRemoteQualification=False,root=str(raw))
    try:
        execution['source']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=h.ROOT,text=True,timeout=10).strip()
        paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=h.ROOT,timeout=10).decode().split('\0')
        h.save(raw/'source-inventory.json',{p:m.sha((h.ROOT/p).read_bytes()) for p in sorted(set(paths)) if p and (h.ROOT/p).is_file()})
        execution['sourceInventorySha256']=m.sha((raw/'source-inventory.json').read_bytes())
        runner.process([sys.executable,'-m','scripts.v51.controls',h.ROOT/'target/v51-controls'],'resolve-controls')
        execution['adapters']=h.compile_adapters(runner,h.ROOT/'target/v51-controls')
        adapter=execution['adapters']['candidate-v5.1-automatic'];cp=adapter['cp'];source=h.ROOT/'scripts/v51/java/V51FullSizeRuntime.java'
        classes=raw/'classes-candidate-v5.1-automatic';runner.process(['javac','--release','21','-proc:none','-cp',cp,'-d',classes,source],'compile-full-size-runtime')
        adapter['classes']=storage.inventory(classes);adapter['sources'][str(source.relative_to(h.ROOT))]=m.sha(source.read_bytes())
        runner.process(runner.java(execution['adapters']['published-v4.4-local']['cp'],'admission.V51MeasuredLocal',raw,'prepare',raw/'plan.json',raw/'source'),'prepare-source')
        execution['sourceBackup']=semantic.source_backup(raw/'source',m.initial(admitted));h.group_directory(raw/'group')
        runner.process(runner.java(cp,'admission.V51MeasuredAutomatic',raw/'group','setup',raw/'plan.json',raw/'source'),'bootstrap')
        execute(raw/'group',cp,admitted['jvmArguments']);execution['status']='EXECUTED';h.save(raw/'execution.json',execution)
        from . import full_size_runtime_evidence as evidence
        result=evidence.validate(raw);h.save(raw/'validation.json',result);negatives=evidence.negatives(raw);h.save(raw/'negatives.json',negatives)
        binding=m.sha(m.canonical(execution));parts=collection.pack(raw,root/'parts',binding)
        with tempfile.TemporaryDirectory(prefix='v51-full-runtime-replay-') as temp:
            copied=Path(temp)/'raw';collection.unpack(root/'parts',copied,binding)
            m.need(evidence.validate(copied)==result,'relocated public full-size result')
            m.need(evidence.negatives(copied)==negatives,'relocated public full-size negatives')
        receipt=dict(status='PASS',execution=execution['execution'],paidCloud=False,fullRemoteQualification=False,validation=result,
                     negativeCases=len(negatives),bindingSha256=binding,parts=len(parts['parts']))
        h.save(root/'receipt.json',receipt);print(m.canonical(receipt).decode(),flush=True)
    except BaseException as error:
        failure=dict(type=type(error).__name__,message=str(error))
        if execution['status']!='EXECUTED':
            execution['failure']=failure;h.save(raw/'execution.json',execution)
        h.save(root/'receipt.json',dict(status='FAIL',execution=execution['execution'],failure=failure,paidCloud=False,fullRemoteQualification=False))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args()
    def terminate(*_):raise SystemExit('full-size runtime terminated')
    signal.signal(signal.SIGTERM,terminate);run(a.output)

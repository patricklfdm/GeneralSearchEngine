"""Frozen two-field fault programs through owned persistent JVMs; no cloud dispatch."""
import argparse
import json
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import threading
import time
import uuid
from . import performance_harness as base, performance_model as m, performance_plan as local
from . import cloud_workload_contract as contract, remote_command as commands
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_protocol_harness as protocol, public_fault_harness as fault
from . import public_trace, storage_inspector as storage

NODES=protocol.NODES
CASES=tuple(c['name'] for c in contract.load()['cells'][3:])


def documents(tag, size=64):
    return [dict(id=tag+i,value=(f'tag-{tag+i}-'+'x'*size)[:size]) for i in (0,1)]


def declaration(case):
    m.need(case in CASES,'unknown remote fault cell')
    return dict(case=case,seeds=[dict(tag=t,valueBytes=64) for t in (10,20,30)],
                targetTags=[40,60],progressTags=[100,110,120,130],refusalTag=90,
                operationIds=[f'call-{n:02d}' for n in range(1,25)],maximumProgressPairs=4,maximumFinalReads=4,maximumPublicCalls=24)


def describe(response):
    if response is None:return 'disconnected'
    return str({k:response[k] for k in ('kind','opId','outcome','reasonCode','reason') if k in response})


def availability(response, kind, capacity=False):
    m.need(response is not None and response['kind']==kind,'missing public response')
    if response['outcome']=='SUCCESS':return
    reasons=q.RECOVERY_REASONS|({'CAPACITY_EXCEEDED','STORAGE_FAILURE'} if capacity else set())
    m.need(response['outcome']==('NOT_SUBMITTED' if kind=='addAll' else 'NOT_APPLICABLE') and response.get('reasonCode') in reasons or
           kind=='addAll' and response['outcome']=='INDETERMINATE' and response.get('reasonCode') in q.UNCERTAIN_RECOVERY_REASONS,
           'unclassified remote fault outcome: '+describe(response))


class Cell:
    def __init__(self,run,root,cp,case,checkpoint=lambda:None):
        self.run,self.root,self.cp,self.case,self.checkpoint=run,root,cp,case,checkpoint
        self.healer=None;self.history=[];self.workers={};self.generations={};self.progress_count=0;self.final_count=0
        self.receipt=dict(case=case,status='FAIL',starts=[],stops=[],archives=[],events=[],progress=[],finalReads=[],rejoins=[])
        self.start=time.monotonic_ns()
        self.seconds=next(c['seconds'] for c in contract.load()['cells'] if c['name']==case)
        self.deadline=self.start+self.seconds*10**9
        self.receipt.update(startNanos=self.start,seconds=self.seconds)

    def remaining(self,ceiling=15,deadline=None):
        self.checkpoint()
        value=min(ceiling,(min(self.deadline,deadline or self.deadline)-time.monotonic_ns())/1e9)
        m.need(value>0,'remote fault deadline: '+self.case)
        return value

    def wait(self,fn,label,deadline=None):
        while True:
            self.remaining(deadline=deadline)
            value=fn()
            if value:return value
            time.sleep(min(.05,self.remaining(deadline=deadline)))

    def event(self,name,**data):
        row=dict(event=name,controllerNanos=time.monotonic_ns(),**data)
        self.receipt['events'].append(row);base.save(self.root/'receipt.json',self.receipt)
        return row

    def call(self,node,kind,**values):
        future=self.send(node,kind,**values)
        return future.result(timeout=self.remaining())

    def send(self,node,kind,**values):
        self.remaining()
        m.need(kind=='status' or len(self.history)<24,'remote public operation budget')
        if kind!='status':values['intentId']=f'call-{len(self.history)+1:02d}'
        return self.workers[node].send(kind,**values)

    def success(self,node,kind,**values):
        result=self.call(node,kind,**values)
        m.need(result is not None and result['outcome']=='SUCCESS','required public call: '+describe(result))
        return result

    def status(self,node,boundary=None):
        return self.success(node,'status',**({} if boundary is None else dict(boundary=boundary)))

    def rows(self,node):return public_trace.live_rows(self.root,node)

    def start_node(self,node):
        self.generations[node]=self.generations.get(node,0)+1
        row=dict(node=node,generation=self.generations[node],startNanos=time.monotonic_ns())
        self.receipt['starts'].append(row)
        worker=q.Worker(self.root,node,self.cp,self.history,row['generation'],'remote-fault',jvm_arguments=self.run.plan['jvmArguments'])
        self.workers[node]=worker
        row.update(pid=worker.proc.pid,readyNanos=time.monotonic_ns(),args=worker.proc.args,
                   linuxStartTicks=Path(f'/proc/{worker.proc.pid}/stat').read_text().rsplit(')',1)[1].split()[19])
        self.remaining()
        return worker

    def stop_node(self,node,kill=False,archive=False):
        worker=self.workers.pop(node)
        row=dict(node=node,pid=worker.proc.pid,generation=worker.generation,startNanos=time.monotonic_ns(),kill=kill)
        self.receipt['stops'].append(row)
        try:worker.stop(kill=kill)
        finally:row.update(endNanos=time.monotonic_ns(),exitCode=worker.proc.returncode)
        if archive:
            name=f'{node}-g{worker.generation}.tar.gz';path=self.root/'archives'/name;path.parent.mkdir(exist_ok=True)
            before=storage.inventory(self.root/node)
            with tarfile.open(path,'w:gz') as tar:tar.add(self.root/node,arcname=node)
            m.need(before==storage.inventory(self.root/node),'stopped authority changed during archive')
            self.receipt['archives'].append(dict(node=node,generation=worker.generation,path='archives/'+name,
                                               sha256=m.sha(path.read_bytes()),inventory=before,archivedNanos=time.monotonic_ns()))
        return row

    def leader(self,exclude=(),deadline=None):
        states={}
        def choose():
            for node in self.workers:
                if node in exclude and not (self.case.startswith('asymmetric-') and any(e['event']=='heal' for e in self.receipt['events'])):continue
                value=self.status(node);states[node]=value
                m.need(value['state']!='FAILED','remote voter failed: '+str(value))
                if value['state']=='LEADER_READY':return node
        return self.wait(choose,'no ready majority leader',deadline)

    def network(self,rules,name):
        row=self.event(name,rules=rules)
        protocol.network(self.root,rules)
        row['appliedNanos']=time.monotonic_ns()
        return row

    def isolate(self,node,name='fault-start'):
        return self.network([f'{a} {b} BEFORE_REQUEST_WRITE *' for a in NODES for b in NODES if a!=b and node in (a,b)],name)

    def hold(self,until):
        while time.monotonic_ns()<until:time.sleep(min(.05,self.remaining(),(until-time.monotonic_ns())/1e9))

    def arm(self,node,cut,mode='kill'):
        fault.replace(self.root/(node+'-arm.txt'),cut+'\n'+mode+'\n')
        self.event('armed',node=node,pid=self.workers[node].proc.pid,cut=cut,mode=mode)

    def reached(self,node,cut):
        pid=self.workers[node].proc.pid
        return self.wait(lambda:next((r for r in self.rows(node) if r['pid']==pid and r['event']=='CUT_REACHED' and r['cut']==cut),None),'missing fault cut')

    def progress(self,exclude=(),deadline=None):
        while self.progress_count<4:
            ordinal=self.progress_count;self.progress_count+=1
            node=self.leader(exclude,deadline)
            row=dict(node=node,tag=100+ordinal*10,startNanos=time.monotonic_ns())
            self.receipt['progress'].append(row)
            row['write']=self.call(node,'addAll',documents=documents(row['tag']))
            availability(row['write'],'addAll')
            row['read']=self.call(node,'read');availability(row['read'],'read')
            row['endNanos']=time.monotonic_ns();self.remaining(deadline=deadline)
            if all(row[k]['outcome']=='SUCCESS' for k in ('write','read')):return node
        raise ValueError('remote progress pairs exhausted')

    def final_read(self,exclude=()):
        while self.final_count<4:
            self.final_count+=1;node=self.leader(exclude)
            response=self.call(node,'read');availability(response,'read')
            self.receipt['finalReads'].append(response)
            if response['outcome']=='SUCCESS':return node,response
        raise ValueError('remote final reads exhausted')

    def rejoin(self,node,through,trigger=None):
        start=trigger or time.monotonic_ns();deadline=min(self.deadline,start+60*10**9)
        def observed():
            s=self.status(node)
            m.need(s['state']!='FAILED','rejoin voter failed')
            return s if s['provenIndex']>=through else None
        value=self.wait(observed,'remote rejoin floor',deadline)
        self.receipt['rejoins'].append(dict(node=node,pid=self.workers[node].proc.pid,through=through,startNanos=start,
                                           endNanos=time.monotonic_ns(),observed=value))
        self.status(node,'rejoined')

    def source(self,node,through):
        return self.wait(lambda:next((r for r in self.rows(node) if r['event']=='RECOVERY_FLOOR' and r['index']>=through),None),'no retained source')

    def refusal(self,node):
        result=[]
        if self.case=='minority-capacity':
            m.need(self.receipt['rejection']['pid']==self.workers[node].proc.pid and self.receipt['rejection']['event']=='RESOURCE_REJECTED','resource refusal lacks same-process rejection')
        for kind,args in [('addAll',dict(documents=documents(90))),('read',{})]:
            value=self.call(node,kind,**args);availability(value,kind,self.case=='minority-capacity')
            m.need(value['outcome']!='SUCCESS','faulted minority served client')
            result.append(value)
        self.receipt['refusals']=result

    def execute(self):
        base.group_directory(self.root)
        base.save(self.root/'declaration.json',declaration(self.case))
        base.save(self.root/'plan.json',self.run.plan);base.save(self.root/'cloud-plan.json',contract.load())
        (self.root/'cell.txt').write_text(self.case+'\n');(self.root/'resource-evidence').touch()
        self.run.deadline=self.deadline
        try:
            self.run.process(self.run.java(self.cp,'admission.V51RemoteFaultConsumer',self.root,'setup'),'bootstrap',self.root)
            if self.case=='minority-capacity':
                self.network([f'{a} {b} BEFORE_REQUEST_WRITE PREPARE' for a in NODES for b in NODES if a!=b and 'node-3' in (a,b)],'prepare-direction')
            for node in (NODES[:2] if self.case=='minority-capacity' else NODES):self.start_node(node)
            leader=self.leader(('node-3',) if self.case=='minority-capacity' else ())
            if self.case=='minority-capacity':
                self.start_node('node-3')
                self.network([],'prepare-heal')
                def stable_pair():
                    state=self.status(leader);bounded=self.status('node-3')
                    return state['state']=='LEADER_READY' and bounded['state']=='FOLLOWER' and state['epoch']==bounded['epoch']
                self.wait(stable_pair,'healthy pair did not fence bounded campaign')
            for tag in (10,20,30):self.success(leader,'addAll',documents=documents(tag))
            self.receipt['seedRead']=self.success(leader,'read')
            self.receipt['seedLeader']=leader
            through=self.status(leader)['provenIndex']
            for node in NODES:self.rejoin(node,through);self.status(node,'pre-fault')
            self.receipt['seedThrough']=through
            self.scenario(leader)
        except BaseException as error:
            self.receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
        finally:
            errors=[]
            if self.healer is not None:
                self.healer.cancel();self.healer.join(timeout=2)
                if self.healer.is_alive():errors.append('fault control timer did not stop')
            protocol.network(self.root,[])
            for node in NODES:
                (self.root/(node+'-release')).touch()
                (self.root/(node+'-slow-force')).unlink(missing_ok=True)
            for node in list(self.workers):
                try:self.stop_node(node)
                except BaseException as error:errors.append(str(error))
            self.receipt.update(endNanos=time.monotonic_ns(),cleanupErrors=errors)
            base.save(self.root/'history.json',self.history);base.save(self.root/'receipt.json',self.receipt)
        if self.case=='maintenance' and 'failure' not in self.receipt:
            self.run.process(self.run.java(self.run.control_cp,'admission.V51RemoteFaultRestore',self.root),'restore',self.root)
            self.receipt['endNanos']=time.monotonic_ns()
        self.remaining()
        m.need(not self.receipt['cleanupErrors'],'remote cleanup failed')
        self.receipt['status']='EXECUTED';base.save(self.root/'receipt.json',self.receipt)
        return dict(case=self.case,status='EXECUTED',calls=len(self.history),receiptSha256=m.sha((self.root/'receipt.json').read_bytes()))

    def scenario(self,old):
        case=self.case;target=next(n for n in NODES if n!=old)
        start=self.event('fault-request',node=old)['controllerNanos'];progress_deadline=start+60*10**9
        self.receipt['faultStartNanos']=start
        if case in ('leader-loss','entry-chosen','proof-quorum'):
            pending=None
            if case!='leader-loss':
                cut='ACCEPT_ACK_RECEIVED' if case=='entry-chosen' else 'PROOF_ACK_RECEIVED'
                self.arm(old,cut);pending=self.send(old,'addAll',documents=documents(40,512))
                self.receipt['cut']=self.reached(old,cut)
            self.stop_node(old,kill=True,archive=True)
            if pending is not None:m.need(pending.result(timeout=self.remaining()) is None,'killed mutation returned')
            active=self.progress(deadline=progress_deadline)
            through=self.status(active)['provenIndex'];restart=time.monotonic_ns();self.start_node(old);self.rejoin(old,through,restart)
        elif case=='group-restart':
            for node in NODES:self.stop_node(node,archive=True)
            restart=time.monotonic_ns()
            for node in NODES:self.start_node(node)
            active=self.progress(deadline=progress_deadline);through=self.status(active)['provenIndex']
            for node in NODES:self.rejoin(node,through,restart)
        elif case in ('isolated-old-leader','asymmetric-requests','asymmetric-responses','no-quorum'):
            if case=='isolated-old-leader':injection=self.isolate(old)
            else:
                barrier='AFTER_RESPONSE_READ' if case=='asymmetric-responses' else 'BEFORE_REQUEST_WRITE'
                rules=[f'{a} {b} {barrier} *' for a in NODES for b in NODES if a!=b and (case=='no-quorum' or a==old)]
                injection=self.network(rules,'fault-start')
            self.healer=threading.Timer(15,lambda:self.network([],'heal'))
            self.healer.start()
            # No-quorum refusal needs the previous fresh-heartbeat window to expire.
            if case in ('isolated-old-leader','no-quorum'):
                self.hold(injection['appliedNanos']+2*10**9);self.refusal(old)
            elif case=='asymmetric-responses':
                value=self.call(old,'addAll',documents=documents(40));availability(value,'addAll');self.receipt['directionalCall']=value
            if case!='no-quorum':active=self.progress(exclude=(old,),deadline=progress_deadline)
            self.healer.join(timeout=self.remaining(16));m.need(not self.healer.is_alive(),'fault timer did not heal')
            if case=='no-quorum':active=self.progress(deadline=progress_deadline)
            through=self.status(active)['provenIndex']
            for node in NODES:self.rejoin(node,through)
        elif case=='slow-follower':
            selected=next(r for r in reversed(self.rows(old)) if r['event']=='PROMISE_QUORUM')
            bases=storage.f.inspect(storage.raw(selected['selected']),'SELECTED')['bases']
            target=next(b['node'] for b in bases if b['node']!=old)
            self.event('slow-start',node=target,delayMillis=1500)
            (self.root/(target+'-slow-force')).touch();began=time.monotonic_ns()
            def release_delay():
                (self.root/(target+'-slow-force')).unlink(missing_ok=True);self.event('slow-end',node=target)
            self.healer=threading.Timer(15,release_delay);self.healer.start()
            active=self.progress(deadline=progress_deadline)
            self.wait(lambda:any(r['event']=='SLOW_FORCE_BEGIN' for r in self.rows(target)),'no delayed force')
            self.receipt['lag']=dict(leader=self.status(active),follower=self.status(target))
            self.healer.join(timeout=self.remaining(16));m.need(not self.healer.is_alive(),'slow force timer did not release')
            self.rejoin(target,self.status(active)['provenIndex'])
        elif case=='interrupted-transfer':
            selected=next(r for r in reversed(self.rows(old)) if r['event']=='PROMISE_QUORUM')
            pair={b['node'] for b in storage.f.inspect(storage.raw(selected['selected']),'SELECTED')['bases']}
            target=next(n for n in NODES if n not in pair)
            self.isolate(target);self.success(old,'addAll',documents=documents(40,4096))
            through=self.status(old)['provenIndex'];self.source(old,through)
            cut='STORAGE_CUT:TRANSFER_PROGRESS_BEFORE_ACK';self.arm(target,cut)
            self.network([],'heal');self.receipt['cut']=self.reached(target,cut)
            self.stop_node(target,kill=True,archive=True)
            restart=time.monotonic_ns();self.start_node(target);self.rejoin(target,through,restart)
            active=self.progress(deadline=progress_deadline)
        elif case=='maintenance':
            self.arm(old,'READ_CAPTURED','pause');pending=self.send(old,'read')
            self.receipt['cut']=self.reached(old,'READ_CAPTURED')
            self.isolate(old);active=self.progress(exclude=(old,),deadline=progress_deadline)
            through=self.status(active)['provenIndex'];self.source(active,through);self.network([],'heal')
            self.wait(lambda:any(r['event']=='REJOIN_INSTALLED' and r['localNanos']>self.receipt['cut']['localNanos'] for r in self.rows(old)),'pin did not overlap install')
            m.need(not pending.done(),'pinned read completed before release');self.event('release-pin',node=old)
            (self.root/(old+'-release')).touch();view=pending.result(timeout=self.remaining())
            m.need(view is not None and view['outcome']=='SUCCESS' and view['documents']==self.receipt['seedRead']['documents'],'pinned view changed')
            self.receipt['pinnedRead']=view;self.rejoin(old,through)
            # Public checkpoint capacity is transient while the old generation is pinned/cleaning.
            # Wait for diagnostic cleanup; no speculative maintenance retry outside the call cap.
            self.wait(lambda:any(r['event']=='PERFORMANCE_SAMPLE' and r['localNanos']>self.receipt['cut']['localNanos'] and r['queues'].get('pinsBytes')==0 for r in self.rows(old)),'released pin still retained')
            active=self.leader();self.success(active,'checkpoint');self.receipt['backup']=self.success(active,'backup')
        elif case=='minority-capacity':
            self.isolate('node-3')
            for tag in (40,60):self.success(old,'addAll',documents=documents(tag,20000))
            through=self.status(old)['provenIndex'];self.source(old,through);self.network([],'heal')
            def rejected_resource():
                rows=self.rows('node-3')
                for rejected in (r for r in rows if r['event']=='RESOURCE_REJECTED'):
                    for reply in rows:
                        if reply['event']=='REPLY' and reply['pid']==rejected['pid'] and reply['order']>rejected['order']:
                            message=json.loads(storage.raw(reply['frame'])[48:])
                            if message['type']=='REJECT' and message['payload']['reason']=='CAPACITY_EXCEEDED':return rejected
            self.receipt['rejection']=self.wait(rejected_resource,'no capacity rejection/reply')
            self.status('node-3','resource-rejected')
            self.refusal('node-3');active=self.progress(exclude=('node-3',),deadline=progress_deadline)
            self.stop_node('node-3',archive=True);self.start_node('node-3');self.final_read(exclude=('node-3',))
            self.stop_node(active,archive=True);self.start_node(active);self.final_read(exclude=('node-3',))
        else:raise ValueError(case)
        self.final_read(exclude=('node-3',) if case=='minority-capacity' else ())
        for node in self.workers:self.status(node,'post-fault')


def run(output,only=None):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    m.need(only is None or only in CASES,'unknown fault selection')
    runner=base.Run(root,local.load());runner.deadline=runner.work_deadline=runner.started+2400*10**9
    receipt=dict(schema='gse-v51-remote-faults-v1',status='FAIL',execution='local-guest-faults-only',paidCloud=False,
                 fullRemoteQualification=False,scope='targeted' if only else 'complete-twelve',cases=[])
    try:
        base.save(root/'plan.json',runner.plan);base.save(root/'cloud-plan.json',contract.load())
        source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=base.ROOT,text=True,timeout=5).strip();receipt['source']=source
        paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=base.ROOT,timeout=10).decode().split('\0')
        base.save(root/'source-inventory.json',{p:m.sha((base.ROOT/p).read_bytes()) for p in sorted(set(paths)) if p and (base.ROOT/p).is_file()})
        receipt['sourceInventorySha256']=m.sha((root/'source-inventory.json').read_bytes())
        runner.process([sys.executable,'-m','scripts.v51.controls',base.ROOT/'target/v51-controls'],'resolve-controls')
        adapters=base.compile_adapters(runner,base.ROOT/'target/v51-controls');receipt['adapters']=adapters
        cp=adapters['candidate-v5.1-automatic']['cp']
        control_dir=root/'restore-classes';control_dir.mkdir()
        control_cp=':'.join((str(root/'artifacts/general-search-engine-4.4.0.jar'),str(root/'artifacts/general-search-engine-replication-5.1.0-SNAPSHOT.jar'),str(control_dir)))
        module=base.ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission'
        runner.process(['javac','--release','21','-proc:none','-cp',control_cp,'-d',control_dir,module/'AdmissionJson.java',base.ROOT/'scripts/v51/java/PublicRuntimeConsumer.java',base.ROOT/'scripts/v51/java/V51RemoteFaultRestore.java'],'compile-restore')
        runner.control_cp=control_cp
        for case in CASES:
            if only and case!=only:continue
            owner=commands.binding(source,m.sha(m.canonical(adapters['candidate-v5.1-automatic'])),uuid.uuid4().hex,'node-1')
            store=commands.CommandStore(root/(case+'-commands'),owner,create=True)
            request=commands.request(owner,uuid.uuid4().hex,'fault',dict(cell=case))
            result=store.execute(request,lambda kind,payload,checkpoint:Cell(runner,root/case,cp,case,checkpoint).execute())
            row=dict(case=case,status='EXECUTED' if result['state']=='SUCCEEDED' else 'FAIL',command=result)
            receipt['cases'].append(row);base.save(root/'execution.json',receipt)
            print(json.dumps(dict(case=case,status=row['status'],error=result.get('error'))),flush=True)
            if result.get('error',{}).get('type') in ('SystemExit','KeyboardInterrupt'):raise SystemExit('fault matrix cancelled; evidence retained')
        m.need(all(c['status']=='EXECUTED' for c in receipt['cases']),'remote fault cells failed')
        receipt['status']='EXECUTED'
        return receipt
    except BaseException as error:receipt['failure']=str(error);raise
    finally:base.save(root/'execution.json',receipt)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');parser.add_argument('--only',choices=CASES);args=parser.parse_args()
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(SystemExit('remote faults terminated')))
    run(args.output,args.only)

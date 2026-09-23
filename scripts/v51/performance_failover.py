"""One frozen idle-leader kill/rejoin schedule; no case retries or hidden calls."""
import json
from pathlib import Path
import signal
import time
from . import public_qualification_harness as q, public_qualification_evidence as physical, public_history
from . import public_recovery_harness as recovery, public_trace, storage_inspector as storage, performance_model as model
from .performance_harness import save, group_directory
need = model.need


class Worker(q.Worker):
    def stop(self, kill=False):
        if self.proc.poll() is None:
            if kill:
                self.proc.kill()
            else:
                self.proc.stdin.write('{"kind":"close"}\n')
                self.proc.stdin.flush()
                self.proc.stdin.close()
        try:
            self.proc.wait(timeout=15)
            self.reader.join(timeout=2)
            need(kill or self.proc.returncode == 0, 'small worker close failure')
        finally:
            if self.proc.poll() is None:
                self.proc.kill()
                self.proc.wait(timeout=3)
            self.log.close()
            public_trace.finish(self.root, self.node, self.proc, self.generation)


def run(runner, adapter):
    root=runner.root/'failover';group_directory(root)
    save(root/'plan.json',runner.plan)
    (root/'pressure-evidence').touch()
    history=[];workers={};receipt=dict(status='FAIL',starts=[],stops=[],progress=[],finalReads=[])
    cp=adapter['cp']
    def start(node,generation=1):
        need(runner.remaining() >= 15,'insufficient small startup budget')
        started=time.monotonic_ns()
        worker=Worker(root,node,cp,history,generation,consumer='performance-small',jvm_arguments=runner.plan['jvmArguments'])
        workers[node]=worker
        receipt['starts'].append(dict(node=node,pid=worker.proc.pid,generation=generation,startNanos=started,readyNanos=time.monotonic_ns(),
                                     linuxStartTicks=Path(f'/proc/{worker.proc.pid}/stat').read_text().rsplit(')',1)[1].split()[19],
                                     args=['java',*runner.plan['jvmArguments'],'-cp',cp,q.PACKAGE+'replication.V51PublicWorker',str(root),node[-1],'performance-small',str(generation)]))
        return worker
    def result(future):
        value=future.result(timeout=runner.remaining(20))
        need(value is not None,'small response missing; attempt remains pending in history')
        return value
    def choose():
        while True:
            for node,worker in workers.items():
                status=result(worker.send('status'))
                need(status['outcome']=='SUCCESS' and status['state']!='FAILED','small runtime status failed')
                if status['state']=='LEADER_READY':return node,worker
            time.sleep(min(.05,runner.remaining()))
    tag=0
    def docs():
        nonlocal tag
        tag+=1
        return [dict(id=2*tag+i,value=f'phase6-{tag}-{i}') for i in (0,1)]
    def require_success(value):
        need(value['outcome']=='SUCCESS','healthy small call failed: '+str(value))
    def available(value,kind):
        if value['outcome']=='SUCCESS':return
        allowed=(value['outcome']==('NOT_SUBMITTED' if kind=='addAll' else 'NOT_APPLICABLE') and value.get('reasonCode') in q.RECOVERY_REASONS or
                 kind=='addAll' and value['outcome']=='INDETERMINATE' and value.get('reasonCode') in q.UNCERTAIN_RECOVERY_REASONS)
        need(allowed,'nonavailability failure in small progress: '+str(value))
    try:
        runner.process(runner.java(cp,'admission.V51SmallPerformanceConsumer',root,'setup'), 'bootstrap',root)
        for node in ('node-1','node-2','node-3'):start(node)
        old,active=choose()
        require_success(result(active.send('addAll',documents=docs())))
        require_success(result(active.send('read')))
        wave=[active.send(kind,**(dict(documents=docs()) if kind=='addAll' else {})) for kind in q.WAVE_KINDS]
        for future in wave:require_success(result(future))
        receipt['healthyCalls']=len(history)
        need(len(history)==6,'frozen healthy small schedule')
        last_read=max((h for h in history if h['kind']=='read' and h['outcome']=='SUCCESS'),key=lambda h:h['endNanos'])
        for worker in workers.values():require_success(result(worker.send('status',boundary='pre-fault')))
        stop=dict(node=old,pid=active.proc.pid,generation=1,startNanos=time.monotonic_ns(),lastReadOpId=last_read['opId'])
        active.stop(kill=True)
        stop.update(endNanos=time.monotonic_ns(),exitCode=active.proc.returncode)
        need(stop['exitCode']==-signal.SIGKILL,'small leader not SIGKILLed')
        stop['retained']=recovery.archive(root,old);stop['archivedNanos']=time.monotonic_ns()
        receipt['fault']=stop;receipt['stops'].append(stop);del workers[old]
        for worker in workers.values():require_success(result(worker.send('status',boundary='post-fault')))
        progress_start=len(history)
        for pair in range(4):
            node,active=choose()
            written=result(active.send('addAll',documents=docs()));available(written,'addAll')
            read=result(active.send('read'));available(read,'read')
            receipt['progress'].append(dict(node=node,write=written,read=read))
            if written['outcome']==read['outcome']=='SUCCESS':break
        else:raise ValueError('four progress pairs exhausted')
        receipt['postFaultCalls']=len(history)-progress_start
        post_cut=result(active.send('status'))['provenIndex']
        restarted=start(old,2)
        while True:
            state=result(restarted.send('status'))
            need(state['outcome']=='SUCCESS' and state['state']!='FAILED','rejoin status failed')
            if state['provenIndex']>=post_cut:break
            time.sleep(min(.1,runner.remaining()))
        for worker in workers.values():require_success(result(worker.send('status',boundary='rejoined')))
        receipt['rejoin']=dict(node=old,pid=restarted.proc.pid,through=post_cut,observed=state,observedNanos=time.monotonic_ns())
        for attempt in range(4):
            node,active=choose();read=result(active.send('read'));available(read,'read');receipt['finalReads'].append(read)
            if read['outcome']=='SUCCESS':break
        else:raise ValueError('four final read attempts exhausted')
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error))
        raise
    finally:
        errors=[]
        for worker in workers.values():
            stop=dict(node=worker.node,pid=worker.proc.pid,generation=worker.generation,startNanos=time.monotonic_ns())
            try:worker.stop()
            except BaseException as error:errors.append(str(error))
            stop.update(endNanos=time.monotonic_ns(),exitCode=worker.proc.returncode);receipt['stops'].append(stop)
        receipt['cleanupErrors']=errors
        save(root/'history.json',history);save(root/'receipt.json',receipt)
        if errors and 'failure' not in receipt:
            raise ValueError('small cleanup failed: '+str(errors))
    receipt['validation']=validate(root,receipt,history,runner.plan)
    receipt['status']='PASS';save(root/'receipt.json',receipt)
    print(json.dumps(dict(case='idle-leader-SIGKILL',status='PASS',calls=len(history))),flush=True)
    return receipt['validation']


def validate(root,receipt,history,admitted):
    root=Path(root);traces=physical.traces_at(root)
    need(receipt['healthyCalls']==6 and 1<=len(receipt['progress'])<=4 and 1<=len(receipt['finalReads'])<=4,'small schedule count')
    kinds=['addAll','read',*q.WAVE_KINDS]+['addAll','read']*len(receipt['progress'])+['read']*len(receipt['finalReads'])
    need([h['kind'] for h in history]==kinds and len(history)<=18 and all(h['outcome']=='SUCCESS' for h in history[:6]),'small history schedule/outcomes')
    need(any(a['startNanos']<b['startNanos']<a['endNanos'] for a in history[2:6] for b in history[2:6]),'small wave did not overlap')
    starts=receipt['starts'];need(len(starts)==4 and len({s['pid'] for s in starts})==4,'small distinct process generations')
    mapping={(s['node'],s['pid']):s['generation'] for s in starts}
    checked_history=public_history.check(history)
    checked_physical=physical.physical(root,history,process_generations=mapping)
    need(checked_physical['chosen']<=192 and checked_physical['chosen']-len(history)<=64,'small slot/recovery ceiling')
    need(not receipt['cleanupErrors'] and len(receipt['stops'])==4,'small cleanup evidence')
    responses=receipt['progress']
    need([h['response'] for h in history[6:6+2*len(responses)]]==[r[k] for r in responses for k in ('write','read')] and
         [h['response'] for h in history[6+2*len(responses):]]==receipt['finalReads'],'small progress receipt differs from history')
    for h in history[6:]:
        if h['outcome']!='SUCCESS':
            need(h.get('reasonCode') in admitted['failover']['availabilityReasons'] and
                 (h['outcome']==('NOT_SUBMITTED' if h['kind']=='addAll' else 'NOT_APPLICABLE') or
                  h['kind']=='addAll' and h['outcome']=='INDETERMINATE' and h['reasonCode'] in q.UNCERTAIN_RECOVERY_REASONS),'unclassified small availability refusal')
    fault=receipt['fault'];need(fault['exitCode']==-9 and fault['startNanos']<=fault['endNanos']<=fault['archivedNanos'],'fault request/exit/archive interval')
    read=next(h for h in history[:6] if h['opId']==fault['lastReadOpId'])
    need(read['pid']==fault['pid'] and read['node']==fault['node'] and read['endNanos']<=fault['startNanos'],'killed process did not own preceding successful read')
    old_rows=[r for r in traces[fault['node']] if r['pid']==fault['pid']]
    callback=next(r for r in old_rows if r['event']=='READ_CALLBACK' and r['opId']==read['opId'])
    capture=max((r for r in old_rows if r['event']=='READ_CAPTURED' and r['order']<callback['order']),key=lambda r:r['order'])
    later=[r for n,rows in traces.items() for r in rows if n!=fault['node'] and r['event']=='PUBLISHED'
           and physical.authority.f.inspect(physical.authority.raw(r['ballot']),'PROMISE')['epoch']>capture['epoch']]
    need(later,'survivor never published higher-epoch activation')
    # Archive verification checks original byte identities against the reopened authority.
    import tarfile
    before=receipt['fault']['retained'];archive=root/'before-reopen.tar.gz'
    need(storage.sha(archive.read_bytes())==before['sha256'],'small archive digest')
    with tarfile.open(archive) as tar:
        members=tar.getmembers()
        from pathlib import PurePosixPath
        need(len(members)<=4000 and sum(v.size for v in members)<=1<<30 and len({v.name for v in members})==len(members),'small archive bounds/duplicates')
        need(all((v.isdir() or v.isfile()) and 0<=v.size<=64<<20 and not PurePosixPath(v.name).is_absolute() and
                 '..' not in PurePosixPath(v.name).parts and v.name.split('/')[0]==fault['node'] for v in members),'small archive member type/path')
        files={v.name.removeprefix(fault['node']+'/'):tar.extractfile(v).read() for v in members if v.isfile()}
    need({k:dict(size=len(v),sha256=storage.sha(v)) for k,v in files.items()}==before['inventory'],'small archive inventory')
    for name in ('manifest.gsr','genesis.gsr','node.gsr','bootstrap-seal.gsr','bootstrap-prepared.gsr'):
        need(files[name]==(root/fault['node']/name).read_bytes(),'same-authority rejoin identity changed')
    restart=next(s for s in starts if s['generation']==2)
    need(restart['node']==fault['node'] and restart['pid']==receipt['rejoin']['pid'] and restart['startNanos']>fault['archivedNanos'],'reopen before frozen archive')
    post_read=next(h for h in history if h['opId']==receipt['progress'][-1]['read']['opId'])
    post_rows=[r for r in traces[post_read['node']] if r['pid']==post_read['pid']]
    post_callback=next(r for r in post_rows if r['event']=='READ_CALLBACK' and r['opId']==post_read['opId'])
    post_capture=max((r for r in post_rows if r['event']=='READ_CAPTURED' and r['order']<post_callback['order']),key=lambda r:r['order'])
    need(post_capture['index']<=receipt['rejoin']['through']<=192,'rejoin did not cover post-fault captured cut')
    retained=storage.inspect(root/fault['node'])
    need(retained['provenThrough']>=receipt['rejoin']['through'] and receipt['rejoin']['observed']['provenIndex']>=receipt['rejoin']['through'],'rejoin durable cut')
    need(max(s['readyNanos'] for s in starts[:3])<fault['startNanos'],'small voters did not overlap')
    for start in starts:
        stops=[s for s in receipt['stops'] if s['pid']==start['pid'] and s['node']==start['node'] and s['generation']==start['generation']]
        need(len(stops)==1 and start['startNanos']<=start['readyNanos']<=stops[0]['startNanos']<=stops[0]['endNanos'] and
             stops[0]['exitCode']==(-9 if start['pid']==fault['pid'] else 0) and start['linuxStartTicks'].isdigit(),'small process lifetime/exit')
        own=[r for r in traces[start['node']] if r['pid']==start['pid']]
        need([r['order'] for r in own]==list(range(1,len(own)+1)),'small observer event gap')
        identities=[r for r in own if r['event']=='PERFORMANCE_IDENTITY']
        need(len(identities)==1 and identities[0]['jvmArguments']==admitted['jvmArguments'] and
             identities[0]['generation']==start['generation'] and identities[0]['javaMajor']==21,'small process toolchain')
        identity=identities[0]
        need(identity['pid']==start['pid'] and identity['node']==start['node'] and identity['planFileSha256']==model.sha((root/'plan.json').read_bytes()),'small loaded identity')
        for kind in ('core','replication'):
            path=Path(identity[kind+'Source'])
            need(path.is_file() and model.sha(path.read_bytes())==identity[kind+'Sha256'],'small loaded artifact')
        need(start['args'][1:5]==admitted['jvmArguments'] and start['args'][6].split(':')[:2]==[identity['coreSource'],identity['replicationSource']],'small classpath identity')
        samples=[r for r in own if r['event']=='PERFORMANCE_SAMPLE']
        need(samples and all(0<r['heapUsedBytes']<=r['heapMaxBytes']<=512<<20 and
                            0<=r['retainedBytes']<=128<<20 for r in samples),'small required resource observations')
        need(samples[0]['boundary']=='start','small sample start boundary')
        required=('pre-fault',) if start['pid']==fault['pid'] else ('pre-close','rejoined') if start['generation']==2 else ('pre-fault','post-fault','rejoined','pre-close')
        need(all(any(r['boundary']==b for r in samples) for b in required),'missing fault resource boundary')
        need(sum(r['boundary']=='periodic' for r in samples)>=max(0,(samples[-1]['localNanos']-samples[0]['localNanos'])//1_000_000_000-1),'missing small periodic resources')
        need(all(r['threads']>0 and r['VmRSSBytes']>0 and r['queues']['pinsBytes']<=64<<20 and r['queues']['stagingBytes']<=64<<20 for r in samples),'small resource counters')
    campaigns=[]
    for node,rows in traces.items():
        for begin in [r for r in rows if r['event']=='CAMPAIGN_BEGIN']:
            ballot=physical.authority.f.inspect(physical.authority.raw(begin['ballot']),'PROMISE')
            own=[r for r in rows if r['pid']==begin['pid']]
            arms=[r for r in own if r['event']=='ELECTION_TIMER_ARMED' and r['order']<begin['order']]
            quorums=[r for r in own if r['event']=='PROMISE_QUORUM' and r['order']>begin['order'] and
                     physical.authority.f.inspect(physical.authority.raw(r['selected']),'SELECTED')['ballot']['epoch']==ballot['epoch']]
            publications=[r for r in own if r['event']=='PUBLISHED' and r['order']>begin['order'] and
                          physical.authority.f.inspect(physical.authority.raw(r['ballot']),'PROMISE')==ballot]
            value=dict(node=node,pid=begin['pid'],epoch=ballot['epoch'],beginNanos=begin['localNanos'],activated=bool(publications),
                       detectionNanos=begin['localNanos']-arms[-1]['localNanos'] if arms else None)
            if publications:
                need(quorums and begin['order']<quorums[0]['order']<publications[0]['order'],'activation before promise quorum')
                value.update(promiseQuorumNanos=quorums[0]['localNanos']-begin['localNanos'],
                             activationNanos=publications[0]['localNanos']-begin['localNanos'])
            campaigns.append(value)
    need(any(c['activated'] and c['epoch']>capture['epoch'] for c in campaigns),'post-fault campaign measurements absent')
    post=[h for h in history[6:] if h['outcome']=='SUCCESS']
    timing={}
    for kind in ('addAll','read'):
        first=min((h for h in post if h['kind']==kind),key=lambda h:h['endNanos'])
        previous=max(h['endNanos'] for h in history[:6] if h['kind']==kind)
        timing[kind]=dict(firstOpId=first['opId'],fromFaultRequestNanos=first['endNanos']-fault['startNanos'],
                          fromConfirmedExitNanos=first['endNanos']-fault['endNanos'],clientOutageNanos=first['endNanos']-previous)
        need(min(timing[kind][k] for k in ('fromFaultRequestNanos','fromConfirmedExitNanos','clientOutageNanos'))>=0,'cross-clock/reversed outage')
    return dict(status='PASS',calls=len(history),history=checked_history,physical=checked_physical,
                faultUncertaintyNanos=fault['endNanos']-fault['startNanos'],recovery=timing,campaigns=campaigns)

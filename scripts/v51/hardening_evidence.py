"""Read-only round, process, archive and resource checks for Phase 5A."""
import copy
import tarfile
from pathlib import Path
from . import runtime_evidence as a, storage_inspector as storage
from .public_promise_evidence import sealed_schedule
from .public_pressure_evidence import reservations
from .lifecycle_hardening_evidence import bounded_sample
from .storage_harness import need

CASES={'partition-accept-kill':'WIRE_AFTER_RESPONSE_READ_ACCEPT',
       'partition-proof-kill':'WIRE_AFTER_RESPONSE_READ_COMMIT_PROOF', 'whole-group-restart':None}
NODES={'node-1','node-2','node-3'}


def processes(traces, starts, stops):
    need(set(traces)==NODES and 3<=len(starts)<=12, 'process schedule bound')
    keys={(s['node'],s['pid']):s['generation'] for s in starts}
    need(len(keys)==len(starts)==len({s['pid'] for s in starts}), 'reused process identity')
    ended={s['pid']:s for s in stops}; need(len(ended)==len(stops), 'duplicate process termination')
    need(set(ended)<={s['pid'] for s in starts}, 'unknown process termination')
    for node in NODES:
        own=sorted((s for s in starts if s['node']==node),key=lambda s:s['generation'])
        need(own and [s['generation'] for s in own]==list(range(1,len(own)+1)) and len(own)<=4, 'noncontiguous process generations')
        for index,start in enumerate(own):
            need(type(start['generation']) is int and start['startNanos']<start['readyNanos'], 'invalid public startup interval')
            rows=[r for r in traces[node] if r['pid']==start['pid']]
            need(rows and all(r['generation']==start['generation'] and r['node']==node for r in rows), 'borrowed process trace')
            need(sum(r['event']=='STARTED' for r in rows)==1, 'missing distinct public startup')
            need([r['order'] for r in rows]==list(range(1,len(rows)+1)), 'missing/reordered local events')
            if index:
                prior=own[index-1]; stop=ended.get(prior['pid'])
                need(stop and stop['node']==node and stop['generation']==prior['generation']
                     and prior['readyNanos']<stop['startNanos']<stop['endNanos']<=stop['archivedNanos']<start['startNanos']
                     and stop['exitCode'] in (0,-9), 'restart before terminated archived owner')
            if start['pid'] not in ended or ended[start['pid']]['exitCode']==0:
                need(sum(r['event']=='CLOSED' for r in rows)==1, 'normal public owner did not close')
            else: need(not any(r['event']=='CLOSED' for r in rows), 'SIGKILL mislabeled normal close')
    observed={(n,r['pid']):r['generation'] for n,rows in traces.items() for r in rows}
    need(observed==keys, 'missing or undeclared process')
    return keys


def rounds(receipt):
    values=receipt['rounds']
    need(receipt['case'] in CASES and len(values)==3 and [v['number'] for v in values]==[1,2,3], 'missing fixed recovery rounds')
    previous=-1
    for value in values:
        need(previous<value['beginNanos']<value['endNanos'], 'overlapping/reordered recovery rounds')
        previous=value['endNanos']
    return values


def archive(root, stop):
    path=f"archives/round-{stop['round']}-{stop['node']}.tar.gz"
    need(stop['archive']==path and stop['retained']['node']==stop['node'], 'borrowed pre-reopen archive')
    encoded=(root/path).read_bytes(); need(storage.sha(encoded)==stop['retained']['sha256'], 'pre-reopen archive hash')
    with tarfile.open(root/path) as tar:
        members=tar.getmembers(); files={}
        for member in members:
            need(member.isdir() or member.isfile(), 'nonregular archived authority')
            if not member.isfile(): continue
            need(member.name.startswith(stop['node']+'/'), 'foreign archived voter')
            name=member.name.removeprefix(stop['node']+'/'); need(name not in files, 'duplicate archived member')
            files[name]=tar.extractfile(member).read()
    inventory={p:dict(size=len(data),sha256=storage.sha(data)) for p,data in files.items()}
    need(inventory==stop['retained']['inventory'], 'pre-reopen archive inventory')
    for name in ('manifest.gsr','genesis.gsr','node.gsr','bootstrap-prepared.gsr','bootstrap-seal.gsr'):
        need(files[name]==(root/stop['node']/name).read_bytes(), 'retained identity replaced between rounds')
    return files


def sample(traces, observed, *, after=0, expected=None, manifest=None):
    need(set(observed)==NODES, 'missing per-voter resource samples')
    for node,value in observed.items():
        status=value['status']; need(value['node']==node and value['observedNanos']>after and status['pending']==0, 'premature or non-drained sample')
        own=[r for r in traces[node] if r['event']=='LIFECYCLE_SAMPLE' and r.get('opId')==status['opId']]
        need(len(own)==1 and own[0]['pid']==value['pid'] and own[0]['generation']==value['generation']
             and own[0]['sample']==status['sample'], 'unobserved/borrowed resource sample')
        bounded_sample(status['sample'],drained=True)
        if expected is not None:
            # Followers retain authority but only a ready leader publishes an application view.
            # Bind the last acknowledged bulk to its real accepted index, then require local proof.
            indices=[]
            for rows in traces.values():
                for row in rows:
                    if row['event']!='FORCE' or row.get('kind')!='ACCEPT': continue
                    accepted=a.frame(row['record'],'ACCEPT',manifest)
                    entry=a.frame(accepted['entry'],'ENTRY',manifest)
                    if entry['operation']==4 and [dict(id=k,value=v) for k,v in a.documents_command(a.raw(entry['payload']))]==expected[-2:]:
                        indices.append(entry['index'])
            need(indices and len(set(indices))==1, 'round final bulk lacks an unambiguous accepted index')
            proven=[]
            for row in traces[node]:
                if row['pid']!=value['pid'] or row['order']>=own[0]['order']: continue
                if row['event']=='FORCE' and row.get('kind')=='PROOF':
                    proven.append(a.frame(row['record'],'PROOF',manifest)['index'])
                elif row['event'] in ('PUBLISHED','REJOIN_INSTALLED'):
                    proven.append(len(a.frame(row['snapshot'],'SNAPSHOT',manifest)['anchors']))
            need(proven and max(proven)>=indices[0], 'rejoined voter lacks proven round prefix')


def validate(root, traces, history, receipt, starts, stops):
    root=Path(root); schedule=rounds(receipt); identities=processes(traces,starts,stops)
    manifest=sealed_schedule(root,'node-3'); calls={h['opId']:h for h in history}
    need(len(calls)==len(history)<=48, 'hardening history bound or duplicate call')
    admitted=a.f.inspect(a.raw(a.f.inspect(a.raw(a.f.inspect((root/'node-1/bootstrap-seal.gsr').read_bytes(),'SEAL')['receipt']),'RECEIPT')['plan']),'PLAN')
    need(all(v['bounds']['maxPendingClientOperations']==4 and v['bounds']['snapshotChunkBytes']==4096
             and v['bounds']['maxFrameBytes']==1<<20 and v['bounds']['requestTimeoutMillis']==1200 and v['policy']['operationTimeoutMillis']==9600 for v in admitted['targets']), 'changed hardening bounds')
    for h in history:
        need(identities.get((h['node'],h['pid']))==h['generation'], 'borrowed client process')
        invoked=[r for r in traces[h['node']] if r['event']=='CLIENT_INVOKE' and r.get('opId')==h['opId']]
        need(len(invoked)==1 and invoked[0]['pid']==h['pid'], 'missing client invocation')
        if h['outcome']!='PENDING':
            completed=[r for r in traces[h['node']] if r['event'] in ('CLIENT_SUCCESS','CLIENT_FAILURE') and r.get('opId')==h['opId']]
            need(len(completed)==1 and completed[0]['pid']==h['pid'] and completed[0]['order']>invoked[0]['order']
                 and completed[0]['outcome']==h['outcome'] and completed[0].get('reasonCode')==h.get('reasonCode'), 'fabricated client completion')
    def operation(row,key,kind):
        value=calls[row[key]]
        need(value['kind']==kind and value['outcome']=='SUCCESS' and row['beginNanos']<value['startNanos']<value['endNanos']<row['endNanos'], 'missing in-round public service: '+key)
        return value
    sample(traces,receipt['baseline'])
    declared=[stop for row in schedule for stop in row['stops']]
    need(declared==stops, 'rounds omitted/reordered terminations')
    dead={s['pid'] for s in stops if s['exitCode']==-9}
    wire=lambda encoded:a.f.wire(a.raw(encoded),manifest)
    accounting={node:reservations(rows,wire,1<<20,terminated_pids=dead&{r['pid'] for r in rows}) for node,rows in traces.items()}
    previous=[]; held_indices=[]
    for row in schedule:
        before=operation(row,'beforeRead','read'); recovered=operation(row,'recoveredRead','read')
        write=operation(row,'resumedWrite','addAll'); final=operation(row,'finalRead','read')
        if previous: need(before['documents']==previous, 'previous round acknowledged prefix lost')
        need(recovered['endNanos']<write['startNanos']<write['endNanos']<final['startNanos']
             and final['documents']==row['expected'], 'recovered write/read cut changed')
        previous=row['expected']; sample(traces,row['drained'],after=final['endNanos'],expected=previous,manifest=manifest)
        for stop in row['stops']:
            need(stop['round']==row['number'], 'stop belongs to another round'); files=archive(root,stop)
            later=[s for s in starts if s['node']==stop['node'] and s['generation']==stop['generation']+1]
            need(len(later)==1 and later[0]['readyNanos']<recovered['startNanos'], 'no retained restart before recovered read')
        if receipt['case']=='whole-group-restart':
            need({s['node'] for s in row['stops']}==NODES and len(row['stops'])==3 and all(s['exitCode']==0 for s in row['stops']), 'incomplete whole-group close')
            cutoff=max(s['archivedNanos'] for s in row['stops'])
            need(cutoff<=row['allStoppedNanos']<min(s['startNanos'] for s in starts if s['generation']==row['number']+1), 'group restarted before all archives existed')
            ids=row['denied']; need(len(ids)==2 and len(set(ids))==2, 'missing minority read/write')
            for identity,kind,outcome in zip(ids,('read','addAll'),('NOT_APPLICABLE','NOT_SUBMITTED')):
                op=calls[identity]
                need(op['node']==row['oldLeader'] and op['pid']==row['oldPid'] and op['kind']==kind and op['outcome']==outcome
                     and op.get('reasonCode') in ('NOT_LEADER','QUORUM_UNAVAILABLE','STALE_EPOCH','NOT_READY')
                     and row['minorityNanos']<op['startNanos']<op['endNanos']<row['stops'][-1]['startNanos'], 'unsafe minority service')
            need(max(s['archivedNanos'] for s in row['stops'][:-1])<=row['minorityNanos'], 'minority had not lost both peers')
            continue
        old=row['oldLeader']; pause=row['pause']; held=calls[row['uncertainWrite']]
        own=[r for r in traces[old] if r['pid']==row['oldPid']]
        need(pause in own and pause['generation']==row['oldGeneration'] and pause['event']=='CUT_REACHED'
             and pause['cut']==CASES[receipt['case']] and pause['mode']=='pause', 'wrong combined crash cut')
        before_pause=[r for r in own if r['order']<pause['order']]
        need(before_pause and before_pause[-1]['event']==CASES[receipt['case']], 'pause lacks original acknowledgement')
        boundary=before_pause[-1]; req=wire(boundary['request']); ack=wire(boundary['frame'])
        expected_kind='ACCEPT' if receipt['case']=='partition-accept-kill' else 'COMMIT_PROOF'
        need(req['type']==expected_kind and ack['type']==expected_kind+'_ACK' and req['sender']==old, 'wrong delayed wire type')
        need(not any(r['event']=='CUT_RELEASED' or r['event']=='RECEIVED' and r.get('request')==boundary['request'] for r in own if r['order']>pause['order']), 'held acknowledgement delivered before crash')
        need(held['kind']=='addAll' and held['pid']==pause['pid'] and held['outcome'] in ('PENDING','INDETERMINATE'), 'held operation falsely resolved')
        need(len(row['stops'])==1 and row['stops'][0]['pid']==pause['pid'] and row['stops'][0]['exitCode']==-9, 'paused process not killed')
        stop=row['stops'][0]
        if held['outcome']=='PENDING': need(held.get('disconnectNanos') is not None and held['endNanos'] is None and held['disconnectNanos']<=stop['endNanos'], 'pending operation did not disconnect with killed owner')
        majority=operation(row,'majorityRead','read'); advanced=operation(row,'majorityWrite','addAll'); after_write=operation(row,'majorityAfterWriteRead','read')
        need(row['newLeader']!=old and all(h['node']==row['newLeader'] for h in (majority,advanced,after_write))
             and row['partitionNanos']<majority['startNanos']<majority['endNanos']<advanced['startNanos']
             and advanced['endNanos']<after_write['startNanos']<after_write['endNanos']<stop['startNanos']
             and stop['archivedNanos']<row['healNanos']<recovered['startNanos'], 'fault overlap or majority progress missing')
        need(any(r['event']=='NETWORK_DROP' and (w:=wire(r['request']))['sender']==old and w['recipient']!=old
                 for r in own if r['order']>pause['order']), 'old leader was not actually isolated')
        need(all(d in majority['documents'] and d in final['documents'] for d in held['documents']), 'chosen uncertain bulk lost')
        votes=[]
        for node,rows in traces.items():
            for r in rows:
                if r['event']!='FORCE' or r['kind']!='ACCEPT': continue
                vote=a.frame(r['record'],'ACCEPT',manifest); entry=a.frame(vote['entry'],'ENTRY',manifest)
                if entry['operation']==4 and [dict(id=k,value=v) for k,v in a.documents_command(a.raw(entry['payload']))]==held['documents']:
                    votes.append((node,r,vote,entry))
        original=[v for v in votes if v[0]==old and v[1]['pid']==pause['pid'] and v[1]['order']<boundary['order'] and v[2]['epoch']==req['epoch']]
        need(len(original)==1 and len({v[0] for v in votes if v[2]['epoch']==req['epoch']})>=2, 'held value lacked original durable quorum')
        _,_,vote,entry=original[0]
        need(all(v[2]['entry']==vote['entry'] for v in votes), 'chosen payload changed across rounds')
        target=a.frame(req['payload']['acceptance'],'ACCEPT',manifest) if expected_kind=='ACCEPT' else a.frame(req['payload']['proof'],'PROOF',manifest)
        target_index=a.frame(target['entry'],'ENTRY',manifest)['index'] if expected_kind=='ACCEPT' else target['index']
        need(target_index==entry['index'] and target['entryDigest']==vote['entryDigest'], 'paused a different operation')
        need(not held_indices or entry['index']>held_indices[-1], 'rounds reused old operation index'); held_indices.append(entry['index'])
        need(any(r['event']=='PUBLISHED' and (snapshot:=a.frame(r['snapshot'],'SNAPSHOT',manifest))['anchors'][entry['index']-1]['entryDigest']==vote['entryDigest']
                 and a.frame(snapshot['terminalProof'],'PROOF',manifest)['epoch']>req['epoch'] for r in traces[row['newLeader']]
                 if r['event']=='PUBLISHED' and len(a.frame(r['snapshot'],'SNAPSHOT',manifest)['anchors'])>=entry['index']), 'no higher-epoch publication of held entry')
    need(previous==receipt['expected'], 'final hardening projection mismatch')
    return dict(status='PASS',rounds=3,processes=len(starts),archivedDisks=len(stops),heldIndices=held_indices,transport=accounting)


def negatives(root,traces,history,receipt,starts,stops):
    names=['missing-round','reordered-rounds','false-generation','overlapping-owner','borrowed-archive','missing-sample','missing-follower-proof','leaked-timer','lost-prior-prefix']
    names+=['false-minority-success'] if receipt['case']=='whole-group-restart' else ['missing-held-force','delivered-ack','false-held-success']
    result=[]
    for name in names:
        t=copy.deepcopy(traces); h=copy.deepcopy(history); r=copy.deepcopy(receipt); s=copy.deepcopy(starts); z=copy.deepcopy(stops)
        if name=='missing-round': r['rounds'].pop()
        elif name=='reordered-rounds': r['rounds'].reverse()
        elif name=='false-generation': s[-1]['generation']+=1
        elif name=='overlapping-owner': s[-1]['startNanos']=s[0]['startNanos']
        elif name=='borrowed-archive': z[0]['archive']='archives/other.tar.gz';r['rounds'][0]['stops'][0]=z[0]
        elif name=='missing-sample': del r['rounds'][-1]['drained']['node-3']
        elif name=='missing-follower-proof':
            for x in t['node-3']:
                if x['event'] in ('PUBLISHED','REJOIN_INSTALLED') or x['event']=='FORCE' and x['kind']=='PROOF': x['event']='WRITE'
        elif name=='leaked-timer':
            value=r['rounds'][-1]['drained']['node-3'];value['status']['sample']['deadlinesQueue']=1
            next(x for x in t['node-3'] if x['event']=='LIFECYCLE_SAMPLE' and x['opId']==value['status']['opId'])['sample']['deadlinesQueue']=1
        elif name=='lost-prior-prefix': next(op for op in h if op['opId']==r['rounds'][1]['beforeRead'])['documents']=[]
        elif name=='false-minority-success': next(op for op in h if op['opId']==r['rounds'][0]['denied'][0])['outcome']='SUCCESS'
        elif name=='missing-held-force':
            pause=r['rounds'][0]['pause']; node=r['rounds'][0]['oldLeader']
            for x in t[node]:
                if x['pid']==pause['pid'] and x['event']=='FORCE' and x['kind']=='ACCEPT': x['event']='WRITE'
        elif name=='delivered-ack':
            pause=r['rounds'][0]['pause']; node=r['rounds'][0]['oldLeader']
            row=next(x for x in t[node] if x['pid']==pause['pid'] and x['order']>pause['order']);row.update(event='CUT_RELEASED')
        else: next(op for op in h if op['opId']==r['rounds'][0]['uncertainWrite'])['outcome']='SUCCESS'
        try: validate(root,t,h,r,s,z)
        except ValueError as error: result.append(dict(case=name,status='REJECTED',reason=str(error)))
        else: raise ValueError('hardening oracle admitted '+name)
    return result

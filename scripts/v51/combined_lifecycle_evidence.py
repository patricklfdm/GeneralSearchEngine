"""Independent overlap, authority, process and accounting checks for Phase 5B."""
import copy
import json
from pathlib import Path
import tarfile
from . import runtime_evidence as a, hardening_evidence as repeated
from .hardening_evidence import processes
from .lifecycle_hardening_evidence import bounded_sample
from .public_promise_evidence import sealed_schedule
from .public_pressure_evidence import reservations
from .storage_harness import need

CASES={'torn-accept-pressure','torn-proof-pressure','cancel-chosen-recovery','close-pinned-recovery'}
NODES={'node-1','node-2','node-3'}


def overlap(calls, identities, begin, end, *, owner=None):
    need(begin<end and identities and len(set(identities))==len(identities),'invalid overlap window')
    for identity in identities:
        op=calls[identity]
        need(op['outcome']=='SUCCESS' and begin<op['startNanos']<op['endNanos']<end
             and (owner is None or op['node']==owner),'public service outside combined fault window')


def pressure(rows, accounting, target, decode, owner='node-3'):
    held=[r for r in rows if r['event']=='PRESSURE_HELD']; released=[r for r in rows if r['event']=='PRESSURE_RELEASED']
    need(len(held)==len(released)==2 and len({r['hold'] for r in held})==2,'two occupied peer lanes required')
    need(len({r['pid'] for r in held+released})==1,'pressure borrowed another process')
    for row in held:
        request=decode(row['request'])
        need(row['barrier']=='BEFORE_REQUEST_WRITE' and request['recipient']==target and request['sender']==owner,'wrong quarantine pressure peer')
        match=[r for r in released if r['hold']==row['hold']]
        need(len(match)==1 and match[0]['order']>row['order'],'pressure release missing or early')
        need(any(r['event']=='TRANSPORT' and r['pid']==row['pid'] and r['transition']=='OUTBOUND_ADMITTED'
                 and r['request']==row['request'] and r['order']<row['order'] for r in rows),'hold lacks real reservation')
    begin=max(r['order'] for r in held); end=min(r['order'] for r in released)
    need(any(v['row']['transition']=='OUTBOUND_REJECTED' and v['row']['pid']==held[0]['pid']
             and v['count']==2 and v['peer']==target and begin<v['row']['order']<end for v in accounting['rejected']),
         'pressure lacks rejection with both exact peer slots occupied')
    return held,released


def samples(traces, observed, members, after, *, floor=0, manifest=None):
    need(set(observed)==members,'missing healthy voter resource sample')
    for node,value in observed.items():
        status=value['status']; own=[r for r in traces[node] if r['event']=='LIFECYCLE_SAMPLE' and r['opId']==status['opId']]
        need(len(own)==1 and own[0]['pid']==value['pid'] and own[0]['generation']==value['generation']
             and own[0]['sample']==status['sample'] and value['node']==node and value['observedNanos']>after
             and status['pending']==0,'borrowed or premature drained sample')
        bounded_sample(status['sample'],drained=True)
        if floor:
            indices=[]
            for row in traces[node]:
                if row['pid']!=value['pid'] or row['order']>=own[0]['order']:continue
                if row['event']=='FORCE' and row.get('kind')=='PROOF':indices.append(a.frame(row['record'],'PROOF',manifest)['index'])
                if row['event'] in ('REJOIN_INSTALLED','PUBLISHED'):indices.append(len(a.frame(row['snapshot'],'SNAPSHOT',manifest)['anchors']))
            need(indices and max(indices)>=floor,'healthy voter lacks durable final bulk prefix')


def quarantine(root, traces, history, receipt, manifest):
    target=receipt['target']; partial=receipt['partial']; kind=receipt['kind']
    need(kind==('ACCEPT' if receipt['case']=='torn-accept-pressure' else 'PROOF') and
         (target==receipt['oldLeader'])==(kind=='ACCEPT') and target!='node-3','wrong torn-authority site')
    need([r for r in traces[target] if r['event']=='PARTIAL_WRITE_FAILURE']==[partial] and partial['kind']==kind,'borrowed torn append')
    a.storage.torn_append(root/target,partial)
    need(a.storage.inventory(root/target)==receipt['quarantinedInventory'],'quarantine bytes changed')
    archive=root/'quarantined.tar.gz'; need(a.storage.sha(archive.read_bytes())==receipt['quarantinedArchiveSha256'],'quarantine archive hash')
    with tarfile.open(archive) as tar:
        files={m.name.removeprefix(target+'/'):dict(size=m.size,sha256=a.storage.sha(tar.extractfile(m).read())) for m in tar.getmembers() if m.isfile()}
    need(files==receipt['quarantinedInventory'],'quarantine archive inventory')
    probes=receipt['probes']; need(len(probes)==2 and len({v['pid'] for v in probes}|{partial['pid']})==3,'missing independent rejected restarts')
    for index,probe in enumerate(probes,1):
        need(probe==json.loads((root/f'quarantine-probe-{index}.stdout').read_text()) and probe['state']=='FAILED'
             and probe['outcome']=='NOT_APPLICABLE' and probe.get('reasonCode') in ('INTEGRITY_FAILURE','STORAGE_FAILURE'),'damaged authority reopened')
        need(json.loads((root/f'quarantine-probe-{index}-inventory.json').read_text())==files,'rejected startup changed authority')
    need(not any(r['pid']==partial['pid'] and r['order']>partial['order'] and r['event'] in ('FORCE','PUBLISHED') for r in traces[target]),'quarantined voter continued authority')
    calls={op['opId']:op for op in history}; failed=calls[receipt['uncertainWrite']]
    need(failed['kind']=='addAll' and failed['outcome']=='INDETERMINATE' and failed['node']==receipt['oldLeader'],'torn write lost uncertainty')
    need(len(receipt['denied'])==2,'missing quarantined refusals')
    for identity,kind_call in zip(receipt['denied'],('read','addAll')):
        op=calls[identity]; need(op['kind']==kind_call and op['node']==target and op.get('reasonCode')=='STORAGE_FAILURE'
             and op['outcome']==('NOT_APPLICABLE' if kind_call=='read' else 'NOT_SUBMITTED'),'unsafe quarantine public outcome')
    for key in ('survivingRead','duringRead','duringAfterWriteRead','finalRead'):
        op=calls[receipt[key]]
        need(op['outcome']=='SUCCESS' and op['node']!=target and all((d in op['documents'])==(kind=='PROOF') for d in failed['documents']),
             'torn append changed chosen boundary')
    if kind=='PROOF':
        matching=[]
        for row in traces[receipt['oldLeader']]:
            if row['event']!='FORCE' or row.get('kind')!='PROOF':continue
            raw=a.raw(row['record']); tail=a.raw(partial['after'])[len(a.raw(partial['before'])):]
            if raw.startswith(tail):matching.append(raw)
        need(matching and len(set(matching))==1,'torn follower proof lacks complete leader force')
    return dict(kind=kind,node=target,rejectedStartups=len(probes))


def validate(root,traces,history,receipt,starts,stops):
    root=Path(root);case=receipt['case']; need(case in CASES,'unknown combined lifecycle case')
    identities=processes(traces,starts,stops); need(len(starts)==4 and len(stops)==(2 if case.startswith('torn-') else 1),'wrong combined process schedule')
    manifest=sealed_schedule(root,'node-3'); wire=lambda encoded:a.f.wire(a.raw(encoded),manifest)
    plan=a.f.inspect(a.raw(a.f.inspect(a.raw(a.f.inspect((root/'node-1/bootstrap-seal.gsr').read_bytes(),'SEAL')['receipt']),'RECEIPT')['plan']),'PLAN')
    need(all(t['bounds']['maxPendingClientOperations']==4 and t['bounds']['snapshotChunkBytes']==4096 and t['bounds']['maxFrameBytes']==1<<20 and
             t['bounds']['requestTimeoutMillis']==1200 and t['policy']['operationTimeoutMillis']==9600 for t in plan['targets']),'changed combined resource/deadline bounds')
    accounting={node:reservations(rows,wire,1<<20) for node,rows in traces.items()}
    calls={op['opId']:op for op in history}; need(len(calls)==len(history),'duplicate combined operation')
    for op in history:
        own=traces[op['node']]; begins=[r for r in own if r['event']=='CLIENT_INVOKE' and r.get('opId')==op['opId']]
        ends=[r for r in own if r['event'] in ('CLIENT_SUCCESS','CLIENT_FAILURE') and r.get('opId')==op['opId']]
        need(len(begins)==len(ends)==1 and begins[0]['pid']==ends[0]['pid']==op['pid']
             and identities.get((op['node'],op['pid']))==op['generation'] and begins[0]['order']<ends[0]['order']
             and ends[0]['outcome']==op['outcome'] and ends[0].get('reasonCode')==op.get('reasonCode'),'public combined response binding')
    restart=receipt['restart'];need(restart in stops and restart['exitCode']==0,'healthy restart was not archived after graceful close')
    repeated.archive(root,restart)
    new=[s for s in starts if s['node']==restart['node'] and s['generation']==2];need(len(new)==1,'missing retained process restart')
    recovered=calls[receipt['recoveredRead']];write=calls[receipt['resumedWrite']];final=calls[receipt['finalRead']]
    need(new[0]['readyNanos']<recovered['startNanos']<recovered['endNanos']<write['startNanos']<write['endNanos']<final['startNanos']
         and all(h['outcome']=='SUCCESS' for h in (recovered,write,final)) and final['documents']==receipt['expected'],'missing recovered public service')
    indices=[]
    for rows in traces.values():
        for row in rows:
            if row['event']=='FORCE' and row.get('kind')=='ACCEPT':
                entry=a.frame(a.frame(row['record'],'ACCEPT',manifest)['entry'],'ENTRY',manifest)
                if entry['operation']==4 and [dict(id=k,value=v) for k,v in a.documents_command(a.raw(entry['payload']))]==write['documents']:indices.append(entry['index'])
    need(indices and len(set(indices))==1,'missing final acknowledged bulk')
    healthy=NODES-{receipt['target']} if case.startswith('torn-') else NODES
    samples(traces,receipt['baseline'],NODES,0)
    samples(traces,receipt['drained'],healthy,final['endNanos'],floor=indices[0],manifest=manifest)
    if case.startswith('torn-'):
        detail=quarantine(root,traces,history,receipt,manifest)
        stopped=receipt['quarantinedStop'];need(stopped in stops and stopped['node']==receipt['target'] and stopped['exitCode']==0
             and receipt['releaseNanos']<stopped['startNanos']<stopped['endNanos']<=stopped['archivedNanos'],
             'quarantined endpoint closed before pressure recovery finished')
        need(all(calls[v]['endNanos']<receipt['pressureStartNanos'] for v in receipt['denied']),
             'pressure preceded quarantined public refusals')
        owner=receipt['pressureOwner']
        need(owner not in (receipt['target'],'node-3') and restart['node']=='node-3','restart borrowed damaged authority or pressure owner')
        held,released=pressure(traces[owner],accounting[owner],receipt['target'],wire,owner)
        full=max(r['order'] for r in held); end=min(r['order'] for r in released)
        for key in ('duringRead','duringWrite','duringAfterWriteRead'):
            replies=[r for r in traces[owner] if r['event']=='CLIENT_SUCCESS' and r.get('opId')==receipt[key]]
            need(len(replies)==1 and replies[0]['pid']==held[0]['pid'] and full<replies[0]['order']<end,'public response escaped pressure interval')
        need(receipt['pressureStartNanos']<restart['startNanos']<new[0]['readyNanos']<receipt['releaseNanos'],'restart did not overlap pressure')
        overlap(calls,[receipt[k] for k in ('duringRead','duringWrite','duringAfterWriteRead')],new[0]['readyNanos'],receipt['releaseNanos'],owner=owner)
        need(any(r['pid']==new[0]['pid'] and r['event']=='FORCE' and r.get('kind')=='ACCEPT'
                 for r in traces[restart['node']]),'restarted healthy voter never accepted recovery work')
    else:
        old=receipt['oldLeader']; pause=receipt['pause']; held=calls[receipt['heldOperation']]
        own=[r for r in traces[old] if r['pid']==held['pid']];released=[r for r in own if r['event']=='CUT_RELEASED']
        need(pause in own and pause['event']=='CUT_REACHED' and pause['mode']=='pause' and len(released)==1
             and released[0]['order']>pause['order'] and restart['node']==old,'missing original recovery hold/release')
        need(any(r['event']=='NETWORK_DROP' and r['order']>pause['order'] for r in own),'old leader was not isolated')
        overlap(calls,[receipt[k] for k in ('majorityRead','majorityWrite','majorityAfterWriteRead')],receipt['partitionNanos'],receipt['healNanos'],owner=receipt['newLeader'])
        need(receipt['newLeader']!=old and receipt['healNanos']<receipt['releaseNanos']<restart['startNanos'],'missing healed then retained recovery')
        if case.startswith('cancel-'):
            need(pause['cut']=='WIRE_AFTER_RESPONSE_READ_ACCEPT' and held['kind']=='addAll' and held['outcome']=='CANCELLED','wrong cancellation boundary/outcome')
            cancelled=calls[receipt['cancel']]; cancel=[r for r in own if r['event']=='CLIENT_CANCEL' and r.get('target')==held['opId']]
            need(len(cancel)==1 and cancel[0]['cancelled'] is True and pause['order']<cancel[0]['order']<released[0]['order']
                 and cancelled['outcome']=='SUCCESS' and cancelled['response']['cancelled'] is True,'original future not cancelled while chosen ACK held')
            boundary=next(r for r in own if r['order']==pause['order']-1);req=wire(boundary['request']);ack=wire(boundary['frame'])
            need(req['type']=='ACCEPT' and ack['type']=='ACCEPT_ACK' and req['sender']==old,'wrong held acknowledgement')
            vote=a.frame(req['payload']['acceptance'],'ACCEPT',manifest);entry=a.frame(vote['entry'],'ENTRY',manifest)
            need(entry['operation']==4 and [dict(id=k,value=v) for k,v in a.documents_command(a.raw(entry['payload']))]==held['documents'],'held ACK borrowed another write')
            voters={n for n,rows in traces.items() for r in rows if r['event']=='FORCE' and r.get('kind')=='ACCEPT' and r['record']==req['payload']['acceptance']}
            need(len(voters)>=2,'cancelled bulk lacked original entry quorum')
            higher=receipt['higherPromise'];need(higher in own and higher['event']=='FORCE' and higher['kind']=='PROMISE'
                 and pause['order']<higher['order']<released[0]['order'] and a.frame(higher['record'],'PROMISE',manifest)['epoch']>req['epoch'],'stale ACK not fenced before release')
            need(all(d in calls[receipt['majorityRead']]['documents'] and d in final['documents'] for d in held['documents']),'chosen cancelled bulk lost')
            detail=dict(cancelledChosenIndex=entry['index'])
        else:
            need(pause['cut']=='READ_CAPTURED' and held['kind']=='read' and held['outcome']=='SUCCESS' and held['documents']==receipt['oldDocuments'],'pinned old read changed')
            installed=receipt['installed'];need(installed in own and installed['event']=='REJOIN_INSTALLED'
                 and pause['order']<installed['order']<released[0]['order'],'recovery never overlapped captured view')
            snapshot=a.frame(installed['snapshot'],'SNAPSHOT',manifest);_,docs=a.application(a.raw(snapshot['application']))
            need(len(snapshot['anchors'])>receipt['seedIndex'] and all(docs.get(d['id'])==d['value'] for d in calls[receipt['majorityWrite']]['documents']), 'installed snapshot lacks newer majority write')
            for key,kind,reason,outcome in [('closing','closeHandle','DEADLINE_EXCEEDED','NOT_APPLICABLE'),('duplicate','duplicateStart','STORAGE_FAILURE','NOT_APPLICABLE'),('closedRejection','addAll','CLOSED','NOT_SUBMITTED')]:
                op=calls[receipt[key]];need(op['kind']==kind and op['node']==old and op['outcome']==outcome and op.get('reasonCode')==reason,'close lost view/ownership safety')
                finish=next(r for r in own if r['event']=='CLIENT_FAILURE' and r.get('opId')==op['opId'])
                need(installed['order']<finish['order']<released[0]['order'],'close refusal outside recovery hold')
            overlap(calls,[receipt['whileClosingWrite'],receipt['whileClosingRead']],calls[receipt['closing']]['startNanos'],receipt['releaseNanos'],owner=receipt['newLeader'])
            need(all(calls[receipt[k]]['kind']=='closeHandle' and calls[receipt[k]]['outcome']=='SUCCESS' and
                     calls[receipt[k]]['startNanos']>held['endNanos'] for k in ('closed','closedAgain')),'close did not finish idempotently after read release')
            detail=dict(installedIndex=len(snapshot['anchors']),oldDocuments=len(held['documents']))
    return dict(status='PASS',detail=detail,processes=len(identities),accounting={n:dict(peaks=v['peaks'],reservations=v['reservations'],rejections=len(v['rejected'])) for n,v in accounting.items()})


def negatives(root,traces,history,receipt,starts,stops):
    results=[]
    def rejected(name,t=traces,h=history,r=receipt,s=starts,e=stops):
        try:validate(root,t,h,r,s,e)
        except (ValueError,KeyError,IndexError) as error:results.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('combined oracle admitted '+name)
    changed=copy.deepcopy(starts);changed[-1]['pid']=changed[0]['pid'];rejected('borrowed-restart-process',s=changed)
    changed=copy.deepcopy(receipt);changed['restart']['retained']['sha256']='0'*64;rejected('borrowed-retained-archive',r=changed)
    changed=copy.deepcopy(receipt);changed['drained'].pop(next(iter(changed['drained'])));rejected('missing-healthy-sample',r=changed)
    changed=copy.deepcopy(receipt);next(iter(changed['drained'].values()))['status']['sample']['deadlinesQueue']=1;rejected('leaked-public-timer',r=changed)
    changed=copy.deepcopy(traces)
    for rows in changed.values():
        for row in reversed(rows):
            if row['event']=='TRANSPORT' and row['transition'].endswith('_RELEASED'):rows.remove(row);break
    rejected('missing-transport-release',t=changed)
    changed=copy.deepcopy(history);next(h for h in changed if h['opId']==receipt['finalRead'])['documents']=[];rejected('lost-final-prefix',h=changed)
    if receipt['case'].startswith('torn-'):
        changed=copy.deepcopy(receipt);changed['probes'][0]['outcome']='SUCCESS';rejected('quarantine-admitted',r=changed)
        changed=copy.deepcopy(receipt);changed['partial']['after']=changed['partial']['before'];rejected('missing-real-torn-append',r=changed)
        changed=copy.deepcopy(receipt);changed['releaseNanos']=changed['restart']['startNanos'];rejected('pressure-released-before-restart',r=changed)
        changed=copy.deepcopy(traces)
        for row in changed[receipt['pressureOwner']]:
            if row['event']=='TRANSPORT' and row['transition']=='OUTBOUND_REJECTED':row['transition']='INBOUND_REJECTED'
        rejected('missing-exact-peer-rejection',t=changed)
    else:
        changed=copy.deepcopy(receipt);changed['pause']['cut']='BEFORE_PUBLISH';rejected('wrong-overlapping-boundary',r=changed)
        changed=copy.deepcopy(receipt);changed['healNanos']=changed['partitionNanos'];rejected('no-majority-progress-while-partitioned',r=changed)
        changed=copy.deepcopy(history);next(h for h in changed if h['opId']==receipt['heldOperation'])['outcome']='SUCCESS' if receipt['case'].startswith('cancel-') else 'NOT_APPLICABLE'
        rejected('changed-held-call-outcome',h=changed)
        changed=copy.deepcopy(receipt);key='higherPromise' if receipt['case'].startswith('cancel-') else 'installed';changed[key]['pid']=-1
        rejected('borrowed-recovery-witness',r=changed)
    return results

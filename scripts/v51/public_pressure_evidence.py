"""Independent reservation accounting and force-delay/public-service evidence."""
import copy
import json
from pathlib import Path
from . import runtime_evidence as a
from .storage_harness import need


def reservations(rows, decode, maximum_frame):
    live={}; seen=set(); peaks=dict(inbound=0,outbound=0,bytes=0); rejected=[]
    for row in rows:
        if row['event']!='TRANSPORT':continue
        transition=row['transition']; direction,action=transition.split('_');key=(row['pid'],row['reservation'])
        need(direction in ('INBOUND','OUTBOUND') and action in ('ADMITTED','RELEASED','REJECTED'),'unknown accounting transition')
        request=decode(row['request']) if direction=='OUTBOUND' else None
        peer=request['recipient'] if request else None
        encoded=a.raw(row['request']) if request else b''
        if action=='REJECTED':
            need(row['reservation']==0 and row['bytes']==0,'rejected exchange reserved capacity')
            count=sum(v['pid']==row['pid'] and v['direction']==direction and (direction=='INBOUND' or v['peer']==peer) for v in live.values())
            rejected.append(dict(row=row,count=count,peer=peer));continue
        need(row['reservation']>0 and row['bytes']==(len(encoded) if request else 0),'reservation byte identity')
        if action=='ADMITTED':
            need(key not in seen,'duplicate reservation identity');seen.add(key)
            live[key]=dict(pid=row['pid'],direction=direction,peer=peer,bytes=row['bytes'],request=row.get('request'))
        else:
            need(key in live,'release without reservation')
            value=live.pop(key)
            need((value['direction'],value['bytes'],value['request'])==(direction,row['bytes'],row.get('request')),'changed reservation release')
        own=[v for v in live.values() if v['pid']==row['pid']]
        inbound=sum(v['direction']=='INBOUND' for v in own);outbound=[v for v in own if v['direction']=='OUTBOUND'];queued=sum(v['bytes'] for v in outbound)
        need(inbound<=8 and len(outbound)<=4 and all(sum(v['peer']==p for v in outbound)<=2 for p in {v['peer'] for v in outbound}),'transport admission bound exceeded')
        need(queued<=maximum_frame*4 and all(v['bytes']<=maximum_frame for v in outbound),'transport byte bound exceeded')
        peaks={k:max(peaks[k],v) for k,v in dict(inbound=inbound,outbound=len(outbound),bytes=queued).items()}
    need(not live,'transport reservations leaked after public close')
    need(seen,'missing actual transport accounting')
    return dict(peaks=peaks,rejected=rejected,reservations=len(seen))


def delayed_force(rows,cut,kind,timeout_millis):
    own=[r for r in rows if r['pid']==cut['pid']]
    reached=[r for r in own if r['event']=='CUT_REACHED']
    need(reached==[cut] and cut['cut']==kind+'_AFTER_WRITE' and cut['mode']=='pause','wrong slow-force boundary')
    before=[r for r in own if r['order']<cut['order']]
    need(before and before[-1]['event']==kind+'_AFTER_WRITE' and before[-1].get('record'),'missing actual pre-force bytes')
    record=before[-1]['record'];a.f.inspect(a.raw(record),kind)
    releases=[r for r in own if r['event']=='CUT_RELEASED' and r['cut']==kind+'_AFTER_WRITE']
    need(len(releases)==1 and releases[0]['order']>cut['order'],'missing slow-force release');release=releases[0]
    need(release['localNanos']-cut['localNanos']>=timeout_millis*1_000_000,'force pause did not span request deadline')
    forces=[r for r in own if r['event']=='FORCE' and r['kind']==kind and r['record']==record]
    need(forces and all(r['order']>release['order'] for r in forces),'force reported before delay was released')
    return dict(record=record,release=release,firstForce=forces[0])


def validate(root,traces,history,receipt):
    root=Path(root);case=receipt['case'];leader=receipt['leader'];target=receipt['target']
    need(case in ('outbound-saturation','inbound-saturation','slow-follower-accept','slow-follower-proof','slow-leader-accept'),'unknown pressure case')
    encoded=(root/'node-1/manifest.gsr').read_bytes();manifest=dict(a.f.inspect(encoded,'MANIFEST'),digest=encoded[16:48].hex())
    def wire(value):return a.f.wire(a.raw(value),manifest)
    seal=a.f.inspect((root/'node-1/bootstrap-seal.gsr').read_bytes(),'SEAL');admitted=a.f.inspect(a.raw(seal['receipt']),'RECEIPT')
    plan=a.f.inspect(a.raw(admitted['plan']),'PLAN');need(a.raw(plan['manifest'])==encoded,'pressure bootstrap binding')
    need(plan['targets'][2]['policy']['minElectionTimeoutMillis']==600000 and leader!='node-3','pressure election policy')
    expected_pending=1 if case=='slow-leader-accept' else 16
    need(all(t['bounds']['maxPendingClientOperations']==expected_pending and t['bounds']['requestTimeoutMillis']==1200 for t in plan['targets']),'pressure bounds not sealed')
    accounting={n:reservations(rows,wire,plan['targets'][0]['bounds']['maxFrameBytes']) for n,rows in traces.items()}
    proof=a.f.inspect(a.raw(receipt['seedProof']),'PROOF');peer=receipt['quorumPeer']
    need({r['voter'] for r in proof['receipts']}=={leader,peer} and peer!=leader,'seed quorum identity')
    need(any(r['event']=='FORCE' and r['kind']=='PROOF' and r['record']==receipt['seedProof'] for r in traces[leader]),'seed proof not observed')
    calls={op['opId']:op for op in history}
    resumed=calls[receipt['resumedWrite']]
    need(resumed['kind']=='addAll' and resumed['outcome']=='SUCCESS' and resumed['startNanos']>receipt['releaseNanos'],'missing successful work after pressure release')
    need(sum(r['event']=='CLIENT_SUCCESS' and r.get('opId')==resumed['opId'] and r['pid']==resumed['pid']
             for rows in traces.values() for r in rows)==1,'missing resumed client success observation')
    if case.endswith('saturation'):
        need(target=='node-3' and target not in (leader,peer),'pressure target is an active quorum voter')
        owner=leader if case=='outbound-saturation' else target
        holds=[r for r in traces[owner] if r['event']=='PRESSURE_HELD'];released=[r for r in traces[owner] if r['event']=='PRESSURE_RELEASED']
        count=2 if case=='outbound-saturation' else 8
        need(len(holds)==len(released)==count and len({(r['pid'],r['hold']) for r in holds})==count,'wrong number of held transport lanes')
        for hold in holds:
            req=wire(hold['request']);need(req['recipient']==target,'wrong pressure recipient')
            need(hold['barrier']==('BEFORE_REQUEST_WRITE' if case=='outbound-saturation' else 'BEFORE_RESPONSE_WRITE'),'wrong pressure boundary')
            matches=[r for r in released if (r['pid'],r['hold'])==(hold['pid'],hold['hold'])]
            need(len(matches)==1 and matches[0]['order']>hold['order'],'unmatched transport hold release')
            if case=='outbound-saturation':
                admitted=[r for r in traces[owner] if r['pid']==hold['pid'] and r['event']=='TRANSPORT' and r['transition']=='OUTBOUND_ADMITTED'
                          and r['request']==hold['request'] and r['order']<hold['order']]
                need(admitted,'held request lacked real outbound reservation')
            else:need(req['type']=='HANDSHAKE' and hold['request'] in json.loads((root/'pressure-probes.json').read_text()),'held inbound request not sent by controller')
        full=max(r['order'] for r in holds);end=min(r['order'] for r in released);pid=holds[0]['pid']
        need(all(r['pid']==pid for r in holds+released),'pressure mixed process generations')
        direction='OUTBOUND' if case=='outbound-saturation' else 'INBOUND'
        need(any(v['row']['transition']==direction+'_REJECTED' and v['row']['pid']==pid and full<v['row']['order']<end
                 and v['count']==count and (direction=='INBOUND' or v['peer']==target) for v in accounting[owner]['rejected']),'no rejection while all lanes occupied')
        if direction=='INBOUND':
            probe=receipt['rejectedProbe'];req=wire(probe['request'])
            need(req['recipient']==target and req['type']=='HANDSHAKE' and not a.raw(probe['response']) and probe['terminal'] in ('EOF','RESET'),'timeout/response is not inbound rejection')
        else:
            # Both public calls complete on the leader before its held requests are released.
            for key in ('duringWrite','duringRead'):
                successes=[r for r in traces[leader] if r['event']=='CLIENT_SUCCESS' and r.get('opId')==receipt[key]]
                need(len(successes)==1 and successes[0]['pid']==pid and full<successes[0]['order']<end,'healthy majority did not serve during outbound pressure')
        detail=dict(held=count,direction=direction)
    else:
        kind='PROOF' if case.endswith('proof') else 'ACCEPT';detail=delayed_force(traces[target],receipt['cut'],kind,1200)
        cut=receipt['cut'];release=detail['release'];record=detail['record']
        held=calls[receipt['heldOperation']]
        value=a.f.inspect(a.raw(record),kind)
        accepts=[value] if kind=='ACCEPT' else [a.f.inspect(a.raw(r['record']),'ACCEPT') for r in traces[leader]
                                               if r['event']=='FORCE' and r['kind']=='ACCEPT']
        matches=[]
        for accepted in accepts:
            if any(accepted[k]!=value[k] for k in ('epoch','proposer','incarnation','entryDigest')):continue
            entry=a.f.inspect(a.raw(accepted['entry']),'ENTRY')
            if entry['operation']==4 and [dict(id=k,value=v) for k,v in a.documents_command(a.raw(entry['payload']))]==held['documents']:
                matches.append(accepted)
        need(matches,'delayed force does not bind the held public bulk')
        for row in traces[target]:
            if row['event']!='REPLY' or row['pid']!=cut['pid'] or not cut['order']<row['order']<release['order']:continue
            req=wire(row['request']);reply=wire(row['frame'])
            need(not (req['payload'].get('acceptance' if kind=='ACCEPT' else 'proof')==record and reply['type'] in ('ACCEPT_ACK','COMMIT_PROOF_ACK')),'success ACK escaped an unforced record')
        if case=='slow-leader-accept':
            need(target==leader and len(receipt['rejectedOperations'])==2,'slow leader schedule')
            for opid,kind_call in zip(receipt['rejectedOperations'],('addAll','read')):
                op=calls[opid];need(op['kind']==kind_call and op['reasonCode']=='CAPACITY_EXCEEDED' and op['outcome']==('NOT_SUBMITTED' if kind_call=='addAll' else 'NOT_APPLICABLE'),'incorrect slow-force admission outcome')
                failures=[r for r in traces[leader] if r['event']=='CLIENT_FAILURE' and r.get('opId')==opid]
                need(len(failures)==1 and failures[0]['pid']==cut['pid'] and cut['order']<failures[0]['order']<release['order'],'rejection not during held force')
            success=[r for r in traces[leader] if r['event']=='CLIENT_SUCCESS' and r.get('opId')==receipt['heldOperation']]
            need(all(r['order']>detail['firstForce']['order'] for r in success),'leader acknowledged before its force')
            rejected_docs=calls[receipt['rejectedOperations'][0]]['documents']
            for rows in traces.values():
                for row in rows:
                    if row['event']!='FORCE' or row['kind']!='ACCEPT':continue
                    accept=a.f.inspect(a.raw(row['record']),'ACCEPT');entry=a.f.inspect(a.raw(accept['entry']),'ENTRY')
                    if entry['operation']==4:need([dict(id=k,value=v) for k,v in a.documents_command(a.raw(entry['payload']))]!=rejected_docs,'rejected public write was accepted')
        else:
            need(target==peer,'slow follower is not the observed quorum peer')
            need(calls[receipt['heldOperation']]['outcome']=='INDETERMINATE','slow peer hid an uncertain write')
        held=calls[receipt['heldOperation']];resolved=calls[receipt['resolvedRead']]
        need(sum(op['kind']=='addAll' and op['documents']==held['documents'] for op in history)==1,'held mutation was replayed')
        need(held['outcome']=='SUCCESS' or held['outcome']=='INDETERMINATE' and held.get('reasonCode') in
             ('NOT_LEADER','NOT_READY','QUORUM_UNAVAILABLE','STALE_EPOCH','DEADLINE_EXCEEDED'),'invalid held write outcome')
        need(resolved['kind']=='read' and resolved['outcome']=='SUCCESS' and resolved['startNanos']>receipt['releaseNanos'],'missing public resolution after force release')
        detail=dict(kind=kind,delayNanos=release['localNanos']-cut['localNanos'])
    if case.endswith('saturation'):
        for key,kind in (('duringWrite','addAll'),('duringRead','read')):
            op=calls[receipt[key]]
            need(op['kind']==kind and op['outcome']=='SUCCESS' and op['node']!=target and receipt['pressureStartNanos']<op['startNanos']<op['endNanos']<receipt['releaseNanos'],'healthy majority service outside pressure window')
    return dict(status='PASS',detail=detail,accounting={n:dict(peaks=v['peaks'],reservations=v['reservations'],rejections=len(v['rejected'])) for n,v in accounting.items()})


def negatives(root,traces,history,receipt):
    changes=[];target=receipt['target'];case=receipt['case']
    for name,remove in [('missing-accounting',lambda r:r['event']=='TRANSPORT'),
                        ('missing-release',lambda r:r['event']=='TRANSPORT' and r['transition'].endswith('_RELEASED')),
                        ('missing-success',lambda r:r['event']=='CLIENT_SUCCESS')]:
        changed={n:[r for r in rows if not remove(r)] for n,rows in traces.items()};changes.append((name,changed,history,receipt))
    changed=copy.deepcopy(history);next(h for h in changed if h['opId']==receipt['resumedWrite']).update(outcome='NOT_SUBMITTED')
    changes.append(('missing-resumed-write',traces,changed,receipt))
    if case.endswith('saturation'):
        for event in ('PRESSURE_HELD','PRESSURE_RELEASED'):
            changed={n:[r for r in rows if r['event']!=event] for n,rows in traces.items()};changes.append(('missing-'+event,changed,history,receipt))
        if case=='inbound-saturation':
            claim=copy.deepcopy(receipt);claim['rejectedProbe']['terminal']='TIMEOUT';changes.append(('timeout-as-rejection',traces,history,claim))
    else:
        changed=copy.deepcopy(history);next(h for h in changed if h['opId']==receipt['heldOperation']).update(outcome='NOT_SUBMITTED')
        changes.append(('uncertain-as-retryable',traces,changed,receipt))
        claim=copy.deepcopy(receipt);claim['resolvedRead']=receipt['heldOperation'];changes.append(('missing-resolution-read',traces,history,claim))
        for event in ('CUT_REACHED','CUT_RELEASED'):
            changed=copy.deepcopy(traces);changed[target]=[r for r in changed[target] if r['event']!=event];changes.append(('missing-'+event,changed,history,receipt))
        changed=copy.deepcopy(traces)
        for row in changed[target]:
            if row['event']=='CUT_RELEASED':row['localNanos']=receipt['cut']['localNanos']+1
        changes.append(('delay-shorter-than-deadline',changed,history,receipt))
    results=[]
    for name,changed,calls,claim in changes:
        try:validate(root,changed,calls,claim)
        except ValueError as error:results.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('pressure oracle admitted '+name)
    return results

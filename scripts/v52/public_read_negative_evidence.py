"""N01–N16 mutations of independently validated actual public histories."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from scripts.v51 import format_encoder
from scripts.v51 import performance_bundle as bundle
from . import public_reads_evidence as e, public_read_lifecycle_evidence as lifecycle, token
from .evidence import need

META=set(lifecycle.META)


def b64(value):return base64.b64encode(value).decode()


def schedule(root,traces,history,processes):
    details=e.read(root/'read-negatives.json');by_id={a['opId']:a for a in history}
    need(details['scenario']=='negative-qualification','negative schedule identity')
    for process in processes:lifecycle.ownership([r for r in traces[process['node']] if r['pid']==process['pid']])
    for key,reason in (('deadlineOp','DEADLINE_EXCEEDED'),('cancelledOp','CancellationException')):
        call=by_id[details[key]];need(call['reasonCode']==reason and call['outcome']!='SUCCESS','negative original rejection category')
        own=traces[call['node']]
        need(not any(r['event']=='REPLICA_READ_CALLBACK' and r['opId']==call['opId'] for r in own),'negative rejected callback appeared')
        failures=[r for r in own if r['event']=='CLIENT_FAILURE' and r['opId']==call['opId']]
        need(len(failures)==1 and failures[0]['reasonCode']==reason,'negative original worker rejection')
    deadline=by_id[details['deadlineOp']]
    need(deadline['policy']=='AT_LEAST_INDEX' and deadline['waitTimeoutMillis']==100 and
         token.decode(e.physical.raw(deadline['minimum']))['index']==(1<<63)-1,'negative deadline schedule changed')
    cancel=by_id[details['cancelOp']];target=by_id[details['cancelledOp']]
    need(cancel['kind']=='cancel' and cancel['target']==target['opId'] and cancel['response']['cancelled'] and
         target['endNanos']<=cancel['endNanos'],'negative original future cancellation')
    for call in history:
        if call['kind']!='cancel':continue
        rows=[r for r in traces[call['node']] if r['event']=='CLIENT_SUCCESS' and r['opId']==call['opId']]
        need(len(rows)==1 and call['response']=={k:v for k,v in rows[0].items() if k not in META},'negative cancellation response binding')
    cuts=[r for r in traces[target['node']] if r['event'] in ('CUT_REACHED','CUT_RELEASED') and r['cut']=='REPLICA_READ_BEFORE_DISPATCH']
    need(len(cuts)==2 and [r['event'] for r in cuts]==['CUT_REACHED','CUT_RELEASED'],'negative pre-capture pause missing')
    failure=next(r for r in traces[target['node']] if r['event']=='CLIENT_FAILURE' and r['opId']==target['opId'])
    need(cuts[0]['order']<failure['order']<cuts[1]['order'],'negative cancellation not before capture')
    need(all(a['outcome']=='SUCCESS' or a['opId'] in (deadline['opId'],target['opId']) for a in history),'undeclared negative schedule failure')


def rejected(name,expected,action):
    try:action()
    except ValueError as error:
        need(str(error)==expected,'unrelated '+name+' rejection: '+str(error))
        return dict(case=name,status='REJECTED',reason=str(error))
    raise ValueError('invalid public read evidence accepted: '+name)


def negatives(root,binding,queries):
    root=Path(root);original=e.traces_at(root);history=e.read(root/'history.json')
    # An invalid original must abort before any mutation is counted.
    e.validate(root,binding,queries,traces=original,history=history)
    details=e.read(root/'read-negatives.json');results=[]
    def rows(traces):return [r for own in traces.values() for r in own]
    def capture(traces):return next(r for r in rows(traces) if r['event']=='REPLICA_READ_CAPTURE_VALIDATED' and r['policy']=='LEADER_STRONG')
    def success(traces):return next(r for r in rows(traces) if r['event']=='CLIENT_SUCCESS' and r['kind']=='read' and r['policy']=='LEADER_STRONG')
    def run(name,reason,mutate):
        traces=copy.deepcopy(original);calls=copy.deepcopy(history);mutate(traces,calls)
        results.append(rejected(name,reason,lambda:e.validate(root,binding,queries,traces=traces,history=calls)))
    for label,field,value in (('N01-wrong-group','groupId',None),
                              ('N02-wrong-history','historyId',None),
                              ('N03-wrong-manifest','manifestDigest','ab'*32),('N04-ahead-index','index',(1<<63)-1)):
        def change(traces,calls,field=field,value=value):
            row=capture(traces);decoded=token.decode(e.physical.raw(row['token']))
            if value is None:value=str(uuid.UUID(int=uuid.UUID(decoded[field]).int^1))
            need(decoded[field]!=value,'mutation did not change token')
            decoded[field]=value;row['token']=b64(token.encode(decoded))
        run(label,'read token does not identify captured publication',change)
    def unproven(traces,calls):
        row=next(r for r in rows(traces) if r['event']=='LOCAL_PUBLISHED' and e.physical.f.inspect(e.physical.raw(r['snapshot']),'SNAPSHOT')['anchors'])
        snapshot=e.physical.f.inspect(e.physical.raw(row['snapshot']),'SNAPSHOT');snapshot['terminalProof']=None
        row['snapshot']=b64(format_encoder.encode('SNAPSHOT',snapshot))
    run('N05-accepted-without-proof','terminal proof presence',unproven)
    def no_publication(traces,calls):
        cut=capture(traces);own=traces[cut['node']]
        published=next(r for r in own if r['event']=='PUBLISHED' and len(e.physical.f.inspect(e.physical.raw(r['snapshot']),'SNAPSHOT')['anchors'])==cut['index'])
        own.remove(published);own.insert(own.index(cut)+1,published)
        for order,row in enumerate(own,1):row['order']=order
    run('N06-publication-after-capture','read lacks exact current publication',no_publication)
    run('N07-other-query-cut','query differs from published V4.4 prefix replay',lambda t,h:success(t).update(report={}))
    run('N08-missing-own-barrier','fresh strong read barrier',lambda t,h:capture(t).update(barrierIndex=-1))
    run('N08-wrong-capture-epoch','fresh strong read barrier',lambda t,h:capture(t).update(barrierEpoch=-1))
    def false_success(traces,calls,key):
        identity=details[key];response=copy.deepcopy(success(traces));failure=next(r for r in rows(traces) if r['event']=='CLIENT_FAILURE' and r['opId']==identity)
        for field in META:response[field]=failure[field]
        response.update(event='CLIENT_SUCCESS',opId=identity,kind='read',outcome='SUCCESS',policy=next(a for a in calls if a['opId']==identity)['policy'])
        failure.clear();failure.update(response)
        call=next(a for a in calls if a['opId']==identity);call.update(outcome='SUCCESS',response={k:v for k,v in response.items() if k not in META});call.pop('reasonCode',None)
    run('N09-timeout-as-stale-success','success before view release',lambda t,h:false_success(t,h,'deadlineOp'))
    run('N10-cancelled-as-success','success before view release',lambda t,h:false_success(t,h,'cancelledOp'))
    run('N10-capture-at-deadline','read deadline/order/policy',lambda t,h:capture(t).update(captureNanos=capture(t)['deadlineNanos']))
    def forged_order(traces,calls):
        first=next(a for a in calls if a['kind']=='read' and a['policy']=='LEADER_STRONG');write=next(a for a in calls if a['kind']=='addAll')
        own=traces[first['node']];reply=next(r for r in own if r['event']=='CLIENT_SUCCESS' and r['opId']==write['opId']);own.remove(reply)
        invoked=next(r for r in own if r['event']=='CLIENT_INVOKE' and r['opId']==first['opId']);own.insert(own.index(invoked)+1,reply)
        reply['localNanos']=invoked['localNanos']+1
        for order,row in enumerate(own,1):row['order']=order
        # Controller timestamps still claim confirmation first; the worker contradicts it.
        need(write['endNanos']<first['startNanos'],'original confirmation order')
    run('N11-forged-confirmation-order','worker confirmed-write-before-token ordering',forged_order)
    def missing_release(traces,calls):
        cut=capture(traces);own=traces[cut['node']]
        row=next(r for r in own if r['event']=='REPLICA_READ_RELEASED' and r['readId']==cut['readId']);own.remove(row)
    run('N12-unreleased-view-success','success before view release',missing_release)
    def reused_pin(traces,calls):
        cut=capture(traces);own=traces[cut['node']];released=next(r for r in own if r['event']=='REPLICA_READ_RELEASED' and r['readId']==cut['readId'])
        callback=next(r for r in reversed(own[:own.index(released)]) if r['event']=='REPLICA_READ_CALLBACK')
        own.insert(own.index(released)+1,copy.deepcopy(callback))
        for order,row in enumerate(own,1):row['order']=order
    run('N12-reused-released-pin','callback lacks own public capture',reused_pin)
    run('N13-missing-admission','read capture lacks own admission',lambda t,h:[own.__setitem__(slice(None),[r for r in own if r['event']!='REPLICA_READ_ADMITTED']) for own in t.values()])
    def premature_release(traces,calls):
        next(r for r in rows(traces) if r['event']=='REPLICA_READ_OWNERSHIP_RELEASED')['completionReturned']=False
    run('N13-premature-release','ownership released before actual completion',premature_release)
    run('N13-missing-timer','read counter conservation',lambda t,h:next(r for r in rows(t) if r['event']=='REPLICA_READ_ADMITTED').update(alarms=0))
    for field,value in (('source','0'*40),('attempt',-1),('artifacts',{})):
        changed=copy.deepcopy(binding);changed[field]=value
        results.append(rejected('N14-borrowed-'+field,'read source/build/run/attempt binding',lambda:e.validate(root,changed,queries)))
    run('N14-borrowed-process','read process/manifest identity',lambda t,h:capture(t).update(generation=99))
    # Bounded independent clones keep original evidence immutable, including across mounts.
    for variant in ('missing','altered','unmapped'):
        with tempfile.TemporaryDirectory(prefix='v52-negative-files-') as temp:
            clone=Path(temp)/'raw';shutil.copytree(root,clone);expected=binding
            if variant=='missing':(clone/'history.json').unlink()
            elif variant=='altered':
                changed=clone/'changed.tmp';changed.write_bytes(b'[]\n');changed.replace(clone/'history.json')
            else:
                expected=dict(binding,origin=str(clone));changed=clone/'changed.tmp';changed.write_text(json.dumps(expected));changed.replace(clone/'binding.json')
                inventory=clone/'inventory.tmp';members=bundle.members(clone);inventory.write_text(json.dumps(members));inventory.replace(clone/'bundle-members.json')
            reason='copied/stale seal path' if variant=='unmapped' else 'read raw inventory'
            results.append(rejected('N15-'+variant,reason,lambda:e.validate(clone,expected,queries)))
    for variant in ('version','reserved','trailing'):
        def malformed(traces,calls,variant=variant):
            row=capture(traces);body=bytearray(e.physical.raw(row['token'])[:80])
            if variant=='version':body[4]=2
            elif variant=='reserved':body[5]=1
            else:body.append(0)
            row['token']=b64(body+hashlib.sha256(token.DOMAIN+body).digest())
        run('N16-'+variant,'UNSUPPORTED_TOKEN_VERSION' if variant=='version' else 'INVALID_TOKEN',malformed)
    need({r['case'][:3] for r in results}=={f'N{i:02d}' for i in range(1,17)},'incomplete targeted negative matrix')
    return results

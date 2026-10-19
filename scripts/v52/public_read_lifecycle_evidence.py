"""Observed ownership, original Future outcomes, close and retained process authority."""
import copy
from pathlib import Path
from . import public_reads_evidence as e, token
from .evidence import need
from scripts.v51 import performance_bundle as bundle

CASES=tuple('lifecycle-'+name for name in (
    'cancel-waiting','cancel-queued','cancel-before-capture','cancel-captured','cancel-completion',
    'close-waiting','close-captured','cancel-captured-halt','cancel-captured-kill','close-captured-halt','close-captured-kill'))
ATOMIC=('REPLICA_READ_ADMITTED','REPLICA_READ_CAPTURE_VALIDATED','REPLICA_READ_SETTLING','REPLICA_READ_OWNERSHIP_RELEASED')
META=('event','order','pid','generation','localNanos','node','groupId','manifestDigest')


def ownership(rows,abrupt=False,*,limit=15):
    """Replay serialized state transitions; never infer release from Future completion."""
    owned={};admitted=set();released=set();high=0
    for row in rows:
        event=row['event']
        if event not in ATOMIC:continue
        need(all(type(row.get(k)) is int and row[k]>=0 for k in
                 ('readId','owned','waiting','captured','settling','alarms','marker','highWater','cancelling')) and
             all(type(row.get(k)) is bool for k in ('preparing','completionReturned')),'read accounting field types')
        identity=row['readId']
        if event=='REPLICA_READ_ADMITTED':
            need(identity not in admitted and row['phase']=='QUEUED','duplicate or invalid read admission')
            admitted.add(identity);owned[identity]='QUEUED';high=max(high,len(owned))
        elif event=='REPLICA_READ_CAPTURE_VALIDATED':
            need(owned.get(identity)=='QUEUED' and row['phase']=='CAPTURED','capture ownership transition');owned[identity]='CAPTURED'
        elif event=='REPLICA_READ_SETTLING':
            need(owned.get(identity) in ('QUEUED','CAPTURED') and row['phase']=='SETTLING','settlement ownership transition');owned[identity]='SETTLING'
        else:
            need(owned.get(identity)=='SETTLING' and identity not in released,'missing or duplicate ownership release')
            need(row['phase']=='SETTLING' and row['completionReturned'] and row['cancelling']==0 and not row['preparing'],
                 'ownership released before actual completion')
            del owned[identity];released.add(identity)
        expected=dict(owned=len(owned),waiting=sum(p=='QUEUED' for p in owned.values()),
                      captured=sum(p=='CAPTURED' for p in owned.values()),settling=sum(p=='SETTLING' for p in owned.values()),highWater=high)
        need(all(row[k]==v for k,v in expected.items()) and row['alarms']==expected['waiting'] and
             0<=row['marker']<=1 and high<=limit and expected['captured']<=1,'read counter conservation')
    need(abrupt or not owned,'normal process leaked read ownership')
    return dict(admitted=len(admitted),released=len(released),abruptOutstanding=len(owned))


def schedule(root,name,traces,history,processes,*,details=None):
    need(name in CASES,'unknown public read lifecycle schedule')
    details=e.read(root/'lifecycle.json') if details is None else details
    need(details['scenario']==name,'lifecycle scenario binding');node=details['node'];by_id={a['opId']:a for a in history}
    for process in processes:ownership([r for r in traces[process['node']] if r['pid']==process['pid']],process['exitCode']!=0)
    def call(key):
        need(details[key] in by_id,'missing lifecycle call');return by_id[details[key]]
    def response(key):
        value=call(key);need(value['outcome']=='SUCCESS','lifecycle control call did not succeed');return value['response']
    # Every auxiliary response is bound to the real worker, including failed close.
    for value in history:
        if value['kind'] in ('read','addAll'):continue
        rows=[r for r in traces[value['node']] if r['pid']==value['pid'] and r['event'] in ('CLIENT_SUCCESS','CLIENT_FAILURE') and r['opId']==value['opId']]
        need(len(rows)==1 and value['response']=={k:v for k,v in rows[0].items() if k not in META} and
             value['outcome']==rows[0]['outcome'] and value['startNanos']<value['endNanos'],'auxiliary response binding')
        invoked=[r for r in traces[value['node']] if r['pid']==value['pid'] and r['event']=='CLIENT_INVOKE' and r['opId']==value['opId']]
        need(len(invoked)==1 and invoked[0]['kind']==value['kind'] and invoked[0].get('target')==value.get('target') and
             invoked[0]['order']<rows[0]['order'],'auxiliary invocation binding')
    kind=name.removeprefix('lifecycle-');crash=kind.endswith(('-halt','-kill'));base=kind.rsplit('-',1)[0] if crash else kind
    target=call('targetOp');action=call('actionOp');own=[r for r in traces[node] if r['pid']==target['pid']]
    need(target['node']==node and action['node']==node,'lifecycle target node')
    inv=next((r for r in own if r['event']=='CLIENT_INVOKE' and r['opId']==target['opId']),None)
    need(inv is not None,'missing lifecycle read invocation')
    runtime=next((r for r in own if r['event']=='REPLICA_READ_INVOKED' and r['order']>inv['order']),None)
    need(runtime is not None,'missing lifecycle runtime invocation');read_id=runtime['readId']
    callbacks=[r for r in own if r['event']=='REPLICA_READ_CALLBACK' and r['opId']==target['opId']]
    releases=[r for r in own if r['event']=='REPLICA_READ_OWNERSHIP_RELEASED' and r['readId']==read_id]
    retained=base in ('cancel-captured','cancel-completion','close-captured')
    expected_callbacks=1 if retained else 0
    need(len(callbacks)==expected_callbacks,'lifecycle callback count')
    baseline=response('baselineProbe')['queues'];before=response('beforeProbe')['queues'];during=response('duringProbe')['queues'];final=response('finalProbe')['queues']
    need(baseline['readsOwned']==0 and baseline['admissionAvailable']==16,'lifecycle initial resources')
    predecessor=base=='cancel-queued'
    need(before['readsOwned']==(2 if predecessor else 1) and before['admissionAvailable']==16-before['readsOwned'],'lifecycle registered resources')
    expected_owned=1 if retained or predecessor else 0
    need(during['readsOwned']==expected_owned and during['admissionAvailable']==16-expected_owned and
         during['readsCaptured']==(1 if base in ('cancel-captured','close-captured') or predecessor else 0) and
         during['readsSettling']==(1 if base=='cancel-completion' else 0),'premature lifecycle ownership release')
    need(final['readsOwned']==final['readsWaiting']==final['readsCaptured']==final['readsSettling']==final['readsAlarms']==0 and
         final['admissionAvailable']==16,'lifecycle final resources')
    if base.startswith('cancel-'):
        need(action['kind']=='cancel' and action['target']==target['opId'] and action['outcome']=='SUCCESS' and
             action['response']['cancelled']==(base!='cancel-completion'),'original future cancellation binding')
        need(target['outcome']==('SUCCESS' if base=='cancel-completion' else 'CANCELLED'),'cancelled future outcome changed')
        if base!='cancel-completion':need(target['reasonCode']=='CancellationException','cancelled future failure category')
        need(target['endNanos']<=action['endNanos'],'cancel response preceded original future handlers')
    else:
        need(action['kind']=='begin-close','close action missing')
        if base=='close-waiting':need(action['outcome']=='SUCCESS' and target['reasonCode']=='CLOSED','waiting close outcome')
        else:
            need(action['reasonCode']=='DEADLINE_EXCEEDED' and action['outcome']=='NOT_APPLICABLE','paused callback close must remain incomplete')
            need(target['outcome']==('PENDING' if crash else 'SUCCESS'),'captured close read outcome')
            if not crash:need(response('secondCloseOp')['kind']=='begin-close','later close missing')
    pause={'cancel-queued':'REPLICA_READ_CALLBACK','cancel-before-capture':'REPLICA_READ_BEFORE_DISPATCH',
           'cancel-captured':'REPLICA_READ_CALLBACK','close-captured':'REPLICA_READ_CALLBACK',
           'cancel-completion':'REPLICA_READ_COMPLETION_RETURN'}.get(base)
    if pause:
        cuts=[r for r in own if r['event']=='CUT_REACHED' and r['cut']==pause and r['mode']=='pause']
        resumed=[r for r in own if r['event']=='CUT_RELEASED' and r['cut']==pause]
        need(len(cuts)==len(resumed)==1 and cuts[0]['order']<resumed[0]['order'],'lifecycle pause witness')
        probe=next(r for r in own if r['event']=='CLIENT_SUCCESS' and r['opId']==details['duringProbe'])
        need(cuts[0]['order']<probe['order']<resumed[0]['order'],'lifecycle probe outside pause')
        if retained:
            need(crash or len(releases)==1 and resumed[0]['order']<releases[0]['order'],'ownership release before held work returned')
    need(len(releases)==(0 if crash else 1),'lifecycle exact release count')
    if crash:
        cuts=[r for r in own if r['event']=='CUT_REACHED' and r['cut']=='REPLICA_READ_RELEASED' and r['mode']==details['mode']]
        need(len(cuts)==1 and own[-1]==cuts[0] and details['pid']==target['pid'],'lifecycle abrupt release witness')
        if base=='close-captured':need(target['endNanos'] is None and target.get('disconnectNanos') is not None,'lost close read response invented')
        before_dir=root/'pre-reopen'/node
        need(details['preReopen']==bundle.members(before_dir) and details['preReopen'],'lifecycle pre-reopen inventory')
        before_store=e.physical.storage._inspect(before_dir,8<<30,8<<20,Path(e.read(root/'binding.json')['origin'])/node)
        restored=[r for r in traces[node] if r['generation']==2 and r['event']=='APPLICATION_RESTORED']
        need(len(restored)==1,'missing lifecycle retained restore')
        snapshot=e.recovery.snapshot(e.physical.raw(restored[0]['snapshot']),e.context(root,traces)[0])
        need(len(snapshot['anchors'])==before_store['provenThrough'] and all(a['entryDigest']==before_store['acceptedDigests'][i]
             for i,a in enumerate(snapshot['anchors'])),'lifecycle retained prefix changed')
        restarted=response('restartedOp');carried=details['carried']
        need(carried['opId'] in by_id and by_id[carried['opId']]['response']==carried,'unobserved lifecycle carried token')
        need(call('restartedOp')['generation']==2 and call('restartedOp')['minimum']==carried['token'] and
             token.decode(e.physical.raw(restarted['token']))['index']>=token.decode(e.physical.raw(carried['token']))['index'],
             'lifecycle carried token not preserved')
    need(all(a['outcome']=='SUCCESS' or a['opId'] in (target['opId'],action['opId']) for a in history),'undeclared unsuccessful lifecycle call')


def negatives(root,binding,queries):
    e.validate(root,binding,queries);results=e.negatives(root,binding,queries)
    original=e.traces_at(root);history=e.read(root/'history.json');processes=e.read(root/'processes.json');details=e.read(root/'lifecycle.json')
    for variant in ('missing-release','duplicate-release','premature-release','forged-counters'):
        traces=copy.deepcopy(original)
        row=next(r for rows in traces.values() for r in rows if r['event']=='REPLICA_READ_OWNERSHIP_RELEASED')
        rows=traces[row['node']]
        if variant=='missing-release':rows.remove(row);reason='counter conservation'
        elif variant=='duplicate-release':rows.insert(rows.index(row)+1,dict(row));reason='duplicate ownership release'
        elif variant=='premature-release':row['completionReturned']=False;reason='before actual completion'
        else:row['owned']+=1;reason='counter conservation'
        try:schedule(root,binding['scenario'],traces,history,processes,details=details)
        except ValueError as error:
            need(reason in str(error),'unrelated lifecycle negative failure: '+str(error))
            results.append(dict(case=variant,status='REJECTED',reason=str(error)))
        else:raise ValueError('invalid lifecycle evidence accepted: '+variant)
    return results

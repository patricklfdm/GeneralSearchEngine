"""Diagnostic-only replay of a failed node client after its last publication.

This entry point always reports FAIL, even when every retained byte, request,
force and child observation is consistent. It cannot qualify a native member.
Successful members still use node_current_evidence.validate without exceptions.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from . import node_current_evidence as current
from . import joining_history_run as history
from .node_grant_maintenance import Replay

p,n,f,e,need=current.p,current.n,current.f,current.e,current.need
REASON='original activation endpoint deadline/closed'


def failure(root):
    result=n.read(root/'process/result.json')
    need(type(result) is dict and set(result)=={'mode','cut','children','status','powerLoss','phase3Complete'}
         and result['status']=='FAIL' and result['mode'] in ('halt','kill') and result['cut'] in p.RENAME_CUTS
         and result['powerLoss'] is False and result['phase3Complete'] is False,'failed node exact producer failure')
    rows=result['children']
    need(type(rows) is list and len(rows)==2 and all(type(v) is dict and type(v.get('pid')) is int and v['pid']>0 for v in rows)
         and rows[0]['pid']!=rows[1]['pid'],'failed node fresh child identities')
    for life,row in enumerate(rows,1):
        expected=dict(life=life,pid=row['pid'],started=dict(life=life,pid=row['pid'],mode=result['mode']),
                      exit=(73 if result['mode']=='halt' else 137) if life==1 else 1)
        if life==1:expected.update(lockHeldBeforeDeath=True,lockReleasedAfterDeath=True)
        need(row==expected and f.canonical(row)==f.canonical(expected),'failed node exact death without clean drain')
    raw=(root/'process/life-2.stderr').read_bytes()
    need(0<len(raw)<=64*1024,'failed node bounded original stderr')
    text=raw.decode('utf-8')
    need('Caused by: java.lang.IllegalArgumentException: '+REASON+'\n' in text
         and 'MembershipActivationEndpoint$Scope.check(' in text and 'MembershipRoundDriver.publish(' in text,
         'failed node original post-publication exception')
    return result,rows,dict(reason=REASON,stderrSha256=e.digest(raw),stderrBytes=len(raw),rootCauseEstablished=False)


def inspect(root):
    root=Path(root);p.process.inventory(root);original=history.inventory(root)
    result,rows,error=failure(root);raw=root/'history';point=result['cut']
    need(n.read(raw/'node-result.json')==dict(status='PARTIAL',producerPassed=False,coldReopens=1,barriers=3,dataCalls=2,
        physicalReplay=False,processRestart=True,phase3Complete=False,serviceBudgetNanos=180_000_000_000),
        'failed node exact failed workload scope')
    service=current.physical(raw,point)
    events,death=p._lifecycle(raw,point,reconciled=True,closed=False)
    p.process.configuration(root)
    counts=p.process._observations(root,rows,cut=point,reconciled=True,failed=True)
    grants=Replay(getattr(service,'grant_retirements',{}))
    network=p.network(raw,events,death,point,reconciled=True,maintenance_replay=current.maintenance_network,
        background_replay=current.network.heartbeats,grant_maintenance_replay=grants)
    transitions=grants.complete()
    # The unchanged qualification boundary must continue to refuse this history.
    try:p.lifecycle(raw,point,reconciled=True)
    except ValueError as rejected:need(str(rejected)=='inflight exact lifecycle order','failed node qualification rejection')
    else:raise ValueError('failed node promoted to successful lifecycle')
    need(history.inventory(root)==original,'failed node original changed')
    return dict(status='FAIL',diagnosticReplay='PASS',scope='failed-node-post-publication',mode=result['mode'],cut=point,
        physicalReplay=True,network=network,grantMaintenance=transitions,childMessages=counts,error=error,
        originalUnchanged=True,processAdmission='REJECTED',admissionReason='inflight exact lifecycle order',
        clientSuccess=False,processDrainQualified=False,nativeQualification=False,phase3Complete=False)


CALLBACKS={
 'missing-floor-member-force':'FLOOR_MEMBER_FORCED',
 'missing-source-authority':'SOURCE_RETIREMENT_FORCED',
 'missing-journal-force':'JOURNAL_ROTATION_FORCED',
 'missing-retirement-delete':'SOURCE_RETIREMENT_FILE_DELETED',
 'missing-floor-release':'FLOOR_RELEASE_PARENT_FORCED'}

def mutate(root,name):
 raw=root/'history';events=n.read(raw/'events.json');wire=n.read(raw/'wire.json')
 if name in CALLBACKS:
  at=next(i for i,v in enumerate(events) if v['node']=='node-3' and v['event']==CALLBACKS[name]);events.pop(at)
 elif name=='early-source-retirement':
  at=next(i for i,v in enumerate(events) if v['node']=='node-3' and v['event']=='SOURCE_RETIREMENT_FORCED');row=events.pop(at)
  at=next(i for i,v in enumerate(events) if v['node']=='node-3' and v['event']=='FLOOR_BEFORE_RETURN');events.insert(at,row)
 elif name=='duplicate-retirement-delete':
  at=next(i for i,v in enumerate(events) if v['node']=='node-3' and v['event']=='SOURCE_RETIREMENT_FILE_DELETED');events.insert(at,dict(events[at]))
 elif name in ('missing-borrowed-probe','missing-complete-prefix','missing-complete-generation'):
  files=current.c.inventory(raw/'published-3/node-1');prefix,members,packet=current.c.current(files)
  refs={
   'missing-borrowed-probe':n.current_reference(packet['capsule'],'retained-current-packet'),
   'missing-complete-prefix':e.digest(f.canonical(packet['capsule']['cut'])),
   'missing-complete-generation':n.current_reference(packet['capsule'],'retained-current-generation-metadata')}
  decoded=[(v,*n.transfer.t.wire(v['request'])) for v in wire]
  traces={q['trace'] for v,k,q in decoded if q['sender']['node']=='node-3' and q['recipient']['node']=='node-1' and q['ballot']['counter']==4 and q['sequence']==1 and q['payload'].get('digest')==refs[name]}
  need(len(traces)==1,'one removed original trace')
  removed=[v for v,k,q in decoded if q['trace'] in traces]
  requests={e.digest(base64.b64decode(v['request'])) for v in removed};responses={e.digest(base64.b64decode(v['response'])) for v in removed}
  events=[v for v in events if v.get('request') not in requests and v.get('response') not in responses]
  wire=[v for v in wire if v not in removed]
  # Keep the independent child transcript consistent with this intentional
  # network omission so replay reaches its complete-source requirement.
  for life in (1,2):
   path=root/f'process/life-{life}.jsonl';rows=p.process.transcript(path);kept=[]
   for row in rows:
    value=row['value'].get('event') if row['action']=='response' else row['value'] if row['action']=='event' else None
    if isinstance(value,dict) and (value.get('request') in requests or value.get('response') in responses):continue
    kept.append(row)
   path.write_bytes(b'\n'.join(f.canonical(v) for v in kept)+b'\n')
 elif name=='invented-success-close':events.append(dict(node='node-1',incarnation=2,event='NODE_CLOSED'))
 elif name=='invented-clean-exit':
  path=root/'process/result.json';value=n.read(path);value['children'][1]['exit']=0;path.write_bytes(f.canonical(value))
 elif name=='invented-producer-pass':
  path=root/'history/node-result.json';value=n.read(path);value['producerPassed']=True;path.write_bytes(f.canonical(value))
 elif name=='missing-final-child-event':
  path=root/'process/life-2.jsonl';rows=p.process.transcript(path);rows.pop();path.write_bytes(b'\n'.join(f.canonical(v) for v in rows)+b'\n')
 else:raise ValueError(name)
 (raw/'events.json').write_bytes(f.canonical(events));(raw/'wire.json').write_bytes(f.canonical(wire))


NEGATIVES={name:'node grant maintenance complete original callbacks' for name in
    (*CALLBACKS,'early-source-retirement','duplicate-retirement-delete')}
NEGATIVES.update({name:'restart network required original source' for name in
    ('missing-borrowed-probe','missing-complete-prefix','missing-complete-generation')})
NEGATIVES.update({'invented-success-close':'inflight exact lifecycle order',
    'invented-clean-exit':'failed node exact death without clean drain',
    'invented-producer-pass':'failed node exact failed workload scope',
    'missing-final-child-event':'node process failed terminal boundary'})


def qualify(root):
    root=Path(root);original=inspect(root);before=history.inventory(root);rows=[]
    for name,expected in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-failed-node-negative-') as temp:
            changed=Path(temp)/'original';shutil.copytree(root,changed);mutate(changed,name)
            try:inspect(changed)
            except ValueError as error:reason=str(error)
            else:raise ValueError('failed node mutation accepted: '+name)
            need(reason==expected,'failed node exact negative '+name+': '+reason)
            rows.append(dict(case=name,status='REJECTED',reason=reason))
    need(history.inventory(root)==before,'failed node negative replay changed original')
    return dict(original,negatives=rows)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--output',required=True);parser.add_argument('--negatives',action='store_true');args=parser.parse_args()
    need(not Path(args.output).resolve().is_relative_to(Path(args.root).resolve()),'failed node output outside originals')
    result=(qualify if args.negatives else inspect)(args.root);history.save(Path(args.output),result)
    print(json.dumps(dict(status=result['status'],diagnosticReplay=result['diagnosticReplay'],nativeQualification=False)))
    # A successfully inspected failed experiment remains a failed experiment.
    raise SystemExit(2)


if __name__=='__main__':main()

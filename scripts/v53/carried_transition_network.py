"""Complete observed carried INTENT/FINAL attempts and durable network replies.

The independent original physical/lifecycle reduction must pass first. Complete
export capability/maintenance composition and process faults are separate gates.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile
import copy
import uuid
from . import carried_transition_evidence as physical
from . import remove_network_evidence as network
from . import required_four_network as connected

need=network.need
NEGATIVES={**network.NEGATIVES,**{k:v for k,v in connected.NEGATIVES.items() if k in (
    'missing-request','late-request','overlapping-retry','wrong-send-owner','missing-delivery',
    'partial-event-connection','partial-wire-connection','crossed-response-connection')},
    'missing-send':'joining connection old delivery shape',
    'wrong-send-kind':'connection request kind',
    'crossed-response-connection':'joining connection old response shape',
    'stripped-connections':'carried transition original connection observations absent',
    **{name:('connection invocation changed' if name.endswith('-foreign') else
             'connection duplicate boundary' if name.endswith('-duplicate') else 'connection incomplete invocation')
       for name in network.profile_network.TERMINAL_NEGATIVES}}


def observations(root):
    root=Path(root);events=network.collection.read_json(root,'events.json',network.collection.EVENT_BYTES)
    wires=network.collection.read_json(root,'wire.json',network.collection.WIRE_BYTES)
    need(connected.connections.present(events,wires),'carried transition original connection observations absent')
    return events,wires


def history(root,kind):
    first,_,_=physical.shape(kind)
    return network.History(root,'4-REMOVE',indices=tuple(range(first,8)))


def replay(root,kind):
    observations(root)
    return network.replay(root,history(root,kind))


def failed_attempts(root,kind):
    events,wires=observations(root);model=history(root,kind)
    identities={n:network.d.future.identity(network.c.inventory(Path(root)/'before-network'/n)) for n in model.old}
    root_id=network.f.decode(model.phases[0]['SELECTED'],'records','SELECTED')['root']
    return events,connected.connections.replay(events,wires,identities,root_id)


def mutate(root,kind,name):
    root=Path(root)
    if name in network.profile_network.TERMINAL_NEGATIVES:
        _,result=failed_attempts(root,kind);cases,targets=connected.terminal_plan(result)
        need(name in targets,'carried transition original terminal required')
        connected.mutate(root,name,terminal=targets[name]);return
    if name=='failed-control-over-attempts':
        events,result=failed_attempts(root,kind)
        attempt=next((v for v in result['failed'] if v['clientFailed'] is not None and v['serverFailed'] is not None
                      and not v.get('responseOffered',False)),None)
        need(attempt is not None,'carried transition original failed control required')
        digest=attempt['requestHash'];client=events[attempt['sent']]['connection']['id']
        server=events[attempt['received']]['connection']['id'];ids={client,server}
        duplicate=[v for v in events if v.get('connection',{}).get('id') in ids]
        sends=sum(v['event'] in connected.connections.SENDS and v['request']==digest for v in events)
        need(0<sends<=3,'carried transition original attempt bound')
        diagnostics=network.d.read(root/'failures.json');original=next(v for v in diagnostics if v['request']==digest)
        for _ in range(4-sends):
            replacements={old:str(uuid.uuid4()) for old in ids}
            for row in copy.deepcopy(duplicate):
                row['connection']['id']=replacements[row['connection']['id']];events.append(row)
            diagnostics.append(dict(original))
        (root/'events.json').write_bytes(network.f.canonical(events))
        (root/'failures.json').write_bytes(network.f.canonical(diagnostics));return
    if name=='stripped-connections':
        events,wires=observations(root)
        for row in events+wires:row.pop('connection',None)
        (root/'events.json').write_bytes(network.f.canonical(events));(root/'wire.json').write_bytes(network.f.canonical(wires));return
    if name not in network.NEGATIVES:connected.mutate(root,name);return
    network.mutate(root,name)


def validate(root,kind):
    physical.shape(kind);root=Path(root);before=network.collection.inventory(root)
    original=physical.validate(root,kind);result=replay(root,kind)
    need(network.collection.inventory(root)==before,'carried transition network original changed')
    return dict(status='PARTIAL',kind=kind,physical=original,network=result,
                observedAttemptsQualified=True,durableActivationAndSlotACKsQualified=True,
                completeExportAuthorityQualified=False,maintenanceCompositionQualified=False,
                processDeathQualified=False,publicReady=False,phase3Complete=False)


def negative(root,kind,before,name):
    reason=NEGATIVES[name]
    observations={'events.json','wire.json','failures.json'}
    protected={k:v for k,v in before['files'].items() if k not in observations}
    with tempfile.TemporaryDirectory(prefix='v53-carried-network-negative-') as temp:
        copied=Path(temp)/'raw';shutil.copytree(root,copied);mutate(copied,kind,name)
        after=network.collection.inventory(copied)
        need({k:v for k,v in after['files'].items() if k not in observations}==protected and
             after['directories']==before['directories'],'carried transition network negative changed physical input')
        try:replay(copied,kind)
        except ValueError as error:need(str(error)==reason,'carried transition unrelated network negative: '+name+': '+str(error))
        else:raise ValueError('carried transition network mutation accepted: '+name)
    return dict(case=name,status='REJECTED',reason=reason)


def qualify(root,kind,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'carried transition network replay workers')
    root=Path(root);original=validate(root,kind);before=network.collection.inventory(root);results={}
    def record(row):
        results[row['case']]=row
        print(json.dumps(dict(kind=kind,case=row['case'],completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    if workers==1:
        for name in NEGATIVES:record(negative(root,kind,before,name))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs=[pool.submit(negative,root,kind,before,name) for name in NEGATIVES]
            for job in as_completed(jobs):record(job.result())
    need(network.collection.inventory(root)==before,'carried transition network original changed')
    return dict(original=original,negatives=[results[name] for name in NEGATIVES])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--kind',choices=physical.KINDS,required=True)
    p.add_argument('--qualify',action='store_true');p.add_argument('--workers',type=int,default=1);a=p.parse_args()
    need(a.qualify or a.workers==1,'carried transition workers require qualification')
    print(json.dumps(qualify(a.root,a.kind,workers=a.workers) if a.qualify else validate(a.root,a.kind),sort_keys=True))

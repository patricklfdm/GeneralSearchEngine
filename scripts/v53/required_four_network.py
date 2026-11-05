"""Connection-bound network qualification of the exact required-four history.

Whole original owner/retirement derivation is mandatory. Historical traces with
no socket observations cannot enter this gate through the legacy matcher.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import required_four_physical as physical
from . import joining_network_evidence as network
from . import joining_connections as connections

need,collection=network.need,network.s.collection


def observations(root):
    events=collection.read_json(root,'events.json',collection.EVENT_BYTES)
    wires=collection.read_json(root,'wire.json',collection.WIRE_BYTES)
    need(connections.present(events,wires),'required-four original connection observations absent')
    return events,wires


def replay(root):
    observations(root)
    return network.network(root,size=5,kind='REPLACE',required_four=True)


def validate(directory):
    root=Path(directory);before=collection.inventory(root)
    original=physical.validate(root);result=replay(root)
    need(result['slots']==11 and result['ownedSlotTransactions']==34,
         'required-four complete network slots')
    need(collection.inventory(root)==before,'required-four network original changed')
    return dict(status='PASS',scope='required-four-original-connections-and-durable-ACKs',profile=physical.semantic.PROFILE,
                physical=original,network=result,observedNetworkQualified=True,durableACKsQualified=True,
                completeControlExportQualified=False,maintenanceAndPeerCompositionQualified=False,
                completePhysicalQualified=False,forceAndNetworkQualified=False,processDeathQualified=False,
                finalSourceCohortQualified=False,phase3Complete=False)


# The same mutations now reach the connection reader first. Durable/transfer
# gates retain their exact original rejection reasons; none is dropped.
NEGATIVES={**network.NEGATIVES,
    'missing-send':'connection boundary without start',
    'missing-request':'connection boundary without start',
    'late-request':'connection boundary without start',
    'overlapping-retry':'connection duplicate boundary',
    'wrong-send-owner':'connection invocation changed',
    'wrong-send-kind':'connection invocation changed',
    'wrong-server-lifetime':'connection invocation changed',
    'wrong-client-lifetime':'connection invocation changed',
    'missing-delivery':'connection incomplete invocation',
    'stripped-connections':'required-four original connection observations absent',
    'partial-event-connection':'joining connection complete event metadata',
    'partial-wire-connection':'joining connection complete wire metadata',
    'crossed-response-connection':'connection invocation changed',
}


def terminal_targets(root):
    events,wires=observations(root)
    model=network.s.Replay(root,size=5,kind='REPLACE',required_four=True)
    for index in range(1,12):model.step(index)
    identities=network.s.catalog.identities(model.states[-1]['identities'])
    result=connections.replay(events,wires,identities,model.root)
    return terminal_plan(result)


def terminal_plan(result):
    """Choose original connection-bound failures before mutating anything."""
    targets={};cases={}
    for side,field in (('caller','clientFailed'),('receiver','serverFailed')):
        failed=next((v for v in result['failed'] if v[field] is not None),None)
        if failed is None:continue
        for mode in ('missing','foreign','duplicate'):
            name='terminal-'+side+'-'+mode;targets[name]=failed[field]
            reason='connection invocation changed' if mode=='foreign' else 'connection duplicate boundary' if mode=='duplicate' else (
                'connection missing receiver terminal' if side=='receiver' and failed['responseOffered'] else 'connection incomplete invocation')
            cases[name]=reason
    return cases,targets


def mutate(root,name,*,terminal=None):
    if terminal is not None:
        events,wires=observations(root);row=events[terminal]
        need(row.get('event')==connections.t.FAIL and row.get('direction')==('OUTBOUND' if name.startswith('terminal-caller-') else 'INBOUND'),
             'required-four original terminal target')
        if name.endswith('-missing'):events.pop(terminal)
        elif name.endswith('-foreign'):row['node']='foreign-owner'
        elif name.endswith('-duplicate'):events.insert(terminal,dict(row))
        else:raise ValueError('required-four declared terminal mutation')
        (root/'events.json').write_bytes(network.f.canonical(events));return
    if name in network.NEGATIVES:network.mutate(root,name);return
    need(name in NEGATIVES,'required-four declared network mutation')
    events,wires=observations(root)
    if name=='stripped-connections':
        for row in events+wires:row.pop('connection',None)
    elif name=='partial-event-connection':
        next(row for row in events if row.get('event') in connections.SENDS).pop('connection')
    elif name=='partial-wire-connection':wires[0].pop('connection')
    else:
        offered=next(row for row in events if row.get('event') in connections.OFFERS)
        sent=next(row for row in events if row.get('event') in connections.SENDS)
        offered['connection']=sent['connection']
    (root/'events.json').write_bytes(network.f.canonical(events));(root/'wire.json').write_bytes(network.f.canonical(wires))


def qualify(directory,progress=None):
    root=Path(directory);before=collection.inventory(root);original=validate(root);results=[]
    terminal_cases,targets=terminal_targets(root);cases={**NEGATIVES,**terminal_cases}
    if progress:progress(dict(stage='original',status='PASS'))
    files={k:v for k,v in before['files'].items() if k not in ('events.json','wire.json')}
    for name,reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-required-four-network-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name,terminal=targets.get(name))
            after=collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k not in ('events.json','wire.json')}==files and
                 after['directories']==before['directories'],'required-four network negative changed physical inputs')
            try:replay(changed)
            except ValueError as error:need(str(error)==reason,'required-four unrelated network negative: '+name+': '+str(error))
            else:raise ValueError('required-four network mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        if progress:progress(dict(case=name,status='REJECTED',completed=len(results),total=len(cases)))
    need(collection.inventory(root)==before,'required-four network qualification changed original')
    return dict(original=original,negatives=results,terminalNegativeCases=len(terminal_cases))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    progress=lambda row:print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    print(json.dumps(qualify(a.root,progress) if a.qualify else validate(a.root),sort_keys=True))

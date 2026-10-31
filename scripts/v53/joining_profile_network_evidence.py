"""Profile-bound complete attempted transport and original durable ACK replay.

Original physical continuation is mandatory. This does not qualify every export
capability, maintenance lifetime, peer-ledger write, or whole-history process cut.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_profile_continuation_evidence as continuation
from . import joining_network_evidence as network
from . import joining_attempts as attempts
from .joining_profile_evidence import PROFILES, topology

need, collection, f = network.need, network.s.collection, network.f
TERMINAL_NEGATIVES = {
    'terminal-caller-missing':'joining failure missing caller terminal',
    'terminal-receiver-missing':'joining failure missing receiver terminal',
    'terminal-caller-foreign':'joining failure sender lifetime',
    'terminal-receiver-foreign':'joining failure receiver lifetime',
    'terminal-caller-duplicate':'joining duplicate outbound terminal',
    'terminal-receiver-duplicate':'joining duplicate inbound terminal',
}


def validate(root, profile):
    size,kind,_,_=topology(profile);root=Path(root);before=collection.inventory(root)
    physical=continuation.validate(root,profile)
    result=network.network(root,size=size,kind=kind)
    need(collection.inventory(root)==before,'joining profile network original changed')
    return dict(status='PARTIAL',scope='profile-original-transport-and-durable-ACKs',profile=profile,
        physicalContinuation=physical,network=result,observedNetworkQualified=True,durableACKsQualified=True,
        completeControlExportQualified=False,maintenanceAndPeerCompositionQualified=False,
        completePhysicalQualified=False,forceAndNetworkQualified=False,processDeathQualified=False,phase3Complete=False)


def terminal_pair(root):
    events=collection.read_json(Path(root),'events.json',collection.EVENT_BYTES)
    for i,row in enumerate(events):
        if row.get('event')!=attempts.EVENT or row.get('direction')!='OUTBOUND':continue
        sends=[j for j,v in enumerate(events) if v.get('event') in attempts.SENDS and v.get('request')==row['request']]
        earlier=[j for j in sends if j<i]
        if not earlier:continue
        lower=earlier[-1];upper=next((j for j in sends if j>lower),len(events))
        inbound=[j for j,v in enumerate(events) if lower<j<upper and v.get('event')==attempts.EVENT and
                 v.get('direction')=='INBOUND' and v.get('request')==row['request']]
        if len(inbound)==1:return events,i,inbound[0]
    return None


def mutate(root,name):
    if name not in TERMINAL_NEGATIVES:network.mutate(root,name);return
    pair=terminal_pair(root);need(pair is not None,'joining profile negative requires original paired terminal')
    events,caller,receiver=pair;index=caller if 'caller' in name else receiver
    if name.endswith('-missing'):events.pop(index)
    elif name.endswith('-foreign'):events[index]['node']='foreign-node'
    else:events.insert(index,dict(events[index]))
    (Path(root)/'events.json').write_bytes(f.canonical(events))


def qualify(root,profile):
    size,kind,_,_=topology(profile);root=Path(root);original=validate(root,profile)
    before=collection.inventory(root);results=[];cases=dict(network.NEGATIVES)
    if terminal_pair(root) is not None:cases.update(TERMINAL_NEGATIVES)
    # Reuse the original storage derivation only while every non-observation
    # member remains unchanged. Each disposable network mutation is replayed.
    files={k:v for k,v in before['files'].items() if k not in ('events.json','wire.json')}
    for name,reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-profile-network-negative-') as temp:
            copied=Path(temp)/'raw';shutil.copytree(root,copied);mutate(copied,name)
            after=collection.inventory(copied)
            need({k:v for k,v in after['files'].items() if k not in ('events.json','wire.json')}==files and
                 after['directories']==before['directories'],'joining profile network negative changed physical inputs')
            try:network.network(copied,size=size,kind=kind)
            except ValueError as error:
                need(str(error)==reason,'joining profile unrelated network negative: '+name+': '+str(error))
            else:raise ValueError('joining profile network accepted mutation: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(profile=profile,case=name,status='REJECTED',completed=len(results),total=len(cases))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'joining profile network qualification changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--profile',required=True,choices=PROFILES)
    p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps((qualify if a.qualify else validate)(a.root,a.profile),sort_keys=True))

"""Profile-bound temporal generation/source/record exports, original first.

All five ADD/REPLACE profiles use actual owners, selected sets and proof voters.
Control/retention authorization and full profile cohorts remain separate gates.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace

from . import bootstrap_replay_contract as source_policy
from . import joining_profile_network_evidence as network
from . import joining_export_evidence as exports
from .joining_control_evidence import owner_lifetime
from .joining_profile_evidence import PROFILES, topology

e=exports
need, collection = e.need, network.collection
NEGATIVES=e.NEGATIVES
PENDING_ABSENT='no committed pending checkpoint export in original'


def context(root,profile,*,old_owner_lifetimes=None,required_four=False, bootstrap_source='EMPTY'):
    source_args = source_policy.options(bootstrap_source)
    size,kind,old,new=topology(profile);root=Path(root)
    need(type(required_four) is bool and (not required_four or profile=='5-REPLACE'),
         'joining export required-four profile')
    # This explicit development topology removes node-3, not the ordinary
    # profile's last voter. Its caller must use the required-four precondition.
    if required_four:new=e.n.s.target_nodes(size,kind,True)
    model=e.n.s.Replay(root,size=size,kind=kind,**({'required_four':True} if required_four else {}),**source_args)
    for index in range(1,12):model.step(index)
    need(model.joining==new[-1] and tuple(model.old)==tuple(old),'joining profile export topology')
    if required_four:need(model.targets==new,'joining export required-four target')
    events=collection.read_json(root,'events.json',collection.EVENT_BYTES)
    wires=collection.read_json(root,'wire.json',collection.WIRE_BYTES)
    rows=e.n.causal(events,wires,e.n.s.catalog.identities(model.states[-1]['identities']),model.root)
    contents=[];e.n.transfers(rows,contents=contents)
    # Include inactive original voters: lack of installation is not lack of an
    # original generation, and cannot justify borrowing another owner's bytes.
    nodes=(*old,model.joining)
    windows=e.generation_windows(root,events,model,nodes=nodes,final_adoption=True)
    sources=e.source_windows(root,events)
    records=e.record_windows(root,events,model,windows,sources,nodes=nodes,old_owner_lifetimes=old_owner_lifetimes)
    return SimpleNamespace(model=model,events=events,rows=rows,contents=contents,
                           groups=e.sessions(contents),windows=windows,sources=sources,records=records)


def replay(root,profile,*,required_four=False, bootstrap_source='EMPTY'):
    source_args = source_policy.options(bootstrap_source)
    need(type(required_four) is bool,'joining export required-four profile')
    reader=context(root,profile,**({'required_four':True} if required_four else {}),**source_args)
    result=e.authorize_contents(reader.model,reader.events,reader.contents,reader.windows,reader.sources,reader.records)
    bound=0
    for values in reader.groups:
        first,last=values[0]['offer'],values[-1]['commit'];node=first['request']['recipient']['node']
        if node!=reader.model.joining or values[0]['raw']==e.pending_ack(reader.model):continue
        scope={'initial-endpoint':'initial-owner','continuation-endpoint':'continuation-owner'}.get(reader.events[first['received']].get('scope'))
        need(scope is not None,'joining profile export owner scope')
        owner_lifetime(reader.events,node,scope,first['received'],last['offered']);bound+=1
    result['joiningExportLifetimes']=bound
    return result


def validate(root,profile):
    topology(profile);root=Path(root);before=collection.inventory(root)
    original=network.validate(root,profile);result=replay(root,profile)
    counts=original['network']
    need(sum(result['boundTransfers'].values())+result['unqualifiedTransfers']==counts['committedTransfers'] and
         sum(result['boundSessions'].values())+result['unqualifiedSessionCount']==
         counts['transferSessions']-counts['rejectedTransferAttempts'],
         'joining profile export complete session accounting')
    need(collection.inventory(root)==before,'joining profile export original changed')
    return dict(status='PARTIAL',scope='profile-temporal-original-export-capabilities',profile=profile,
                precondition=original,exports=result,temporalContentExportsQualified=True,
                completeControlExportQualified=False,maintenanceAndPeerCompositionQualified=False,
                allMembershipProfilesQualified=False,processDeathQualified=False,phase3Complete=False)


def negative_plan(original):
    cases=dict(NEGATIVES);absent=[]
    if original['exports']['boundSessions'].get('pending-joining-checkpoint',0)==0:
        cases.pop('pending-after-retain')
        absent.append(dict(case='pending-after-retain',status='NOT_APPLICABLE',reason=PENDING_ABSENT))
    return cases,absent


def qualify(root,profile,progress=None):
    root=Path(root);original=validate(root,profile);before=collection.inventory(root);results=[]
    cases,absent=negative_plan(original)
    protected={k:v for k,v in before['files'].items() if k not in ('events.json','wire.json')}
    size,kind,_,_=topology(profile)
    for name,reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-profile-export-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed)
            try:e.mutate(changed,name,reader=context(changed,profile))
            except StopIteration as error:raise ValueError('joining profile export missing negative target: '+name) from error
            after=collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k not in ('events.json','wire.json')}==protected and
                 after['directories']==before['directories'],'joining profile export negative changed physical inputs')
            # Only an authority failure on a complete valid transcript counts.
            e.n.network(changed,size=size,kind=kind)
            try:replay(changed,profile)
            except ValueError as error:
                need(str(error)==reason,'joining profile unrelated export negative: '+name+': '+str(error))
            else:raise ValueError('joining profile export mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',networkPrecondition='PASS',reason=reason))
        if progress:progress(dict(profile=profile,case=name,completed=len(results),total=len(cases)))
    need(collection.inventory(root)==before,'joining profile export qualification changed original')
    return dict(original=original,negatives=results,notApplicable=absent)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root')
    parser.add_argument('--profile',required=True,choices=PROFILES);parser.add_argument('--qualify',action='store_true')
    args=parser.parse_args()
    def progress(row):print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    result=qualify(args.root,args.profile,progress) if args.qualify else validate(args.root,args.profile)
    print(json.dumps(result,sort_keys=True))

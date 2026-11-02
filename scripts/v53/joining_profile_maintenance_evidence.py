"""Actual profile floor majorities, original copies and maintenance lifetimes.

Complete physical/network/export/control replay precedes this layer. STATUS
remains a discovery hint; only complete original copies supply retention proof.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_profile_control_evidence as control
from . import joining_maintenance_evidence as maintenance
from .joining_same_view_physical import covering_floor
from .joining_profile_evidence import PROFILES, topology

m=maintenance
c,e,n,f,disk,need=m.c,m.e,m.n,m.f,m.disk,m.need
collection=control.collection
NEGATIVES=dict(m.NEGATIVES,**{'missing-floor-transaction':'joining profile maintenance unbound retirement event'})


def retirement_coverage(events):
    active=set();count=0
    for row in events:
        node=row.get('node');point=row['event']
        if point=='FLOOR_RESERVED':
            need(node not in active,'joining profile maintenance overlapping floor');active.add(node)
        elif point=='FLOOR_RELEASE_BEFORE_RETURN':
            need(node in active,'joining profile maintenance floor release without reservation');active.remove(node)
        elif point.startswith(('RETIREMENT_','SOURCE_RETIREMENT_')):
            need(node in active,'joining profile maintenance unbound retirement event');count+=1
    need(not active,'joining profile maintenance incomplete floor')
    return count


class Replay(m.Replay):
    # Old ADD fixture totals are not protocol limits. Every observed STATUS and
    # FLOOR transaction is still checked, including complete release coverage.
    expected_status_count=None
    expected_floor_counts=None

    def __init__(self,root,profile):
        self.__dict__.update(vars(control.Replay(root,profile)))
        self.direct_nodes=set();self.floor_inputs=[]

    def governing(self,copies,own):
        # Shared physical derivation verifies both majorities, actual identities,
        # exact local bytes and each remote's covering ancestry. A joiner is not
        # an additional voter requirement when the old voters satisfy both sides.
        local=disk.inventory(self.root/own['path'])
        covering_floor(local,{node:disk.inventory(self.root/v['path']) for node,v in copies.items()},own['node'])

    def acquired(self,own,lower,start):
        copies,used=super().acquired(own,lower,start)
        self.floor_inputs.append(dict(start=start,own=own,copies=copies,order=list(copies)))
        return copies,used

    def direct(self,own,start):
        """The native fixture gives every old proof voter a complete live set."""
        node=own['node'];joining=self.model.joining
        need(node in self.expected_confirmations and node not in self.direct_nodes and
             own['packet']['capsule']['cut']==self.model.states[9]['cut'],
             'joining maintenance direct fixture boundary')
        initialized=[i for i,v in enumerate(self.events) if v.get('node')==joining and v.get('scope')=='initial-owner' and
                     v['event']=='CURRENT_DIRECTORY_FORCED']
        need(len(initialized)==1,'joining maintenance direct joining owner')
        copies={}
        for peer in sorted(self.expected_confirmations|{joining}):
            points=[i for i,v in enumerate(self.events) if initialized[0]<i<start and v.get('node')==peer and
                    v['event']=='FLOOR_COPY_BEFORE_RETURN']
            need(points,'joining maintenance direct original copy missing')
            at=points[-1];copy=self.current(peer,at,start)
            if peer==joining:c.owner_lifetime(self.events,peer,'initial-owner',at,start)
            copies[peer]=copy
        self.direct_nodes.add(node)
        self.floor_inputs.append(dict(start=start,own=own,copies=copies,order=list(copies)))
        return copies

    def floors(self):
        result=super().floors()
        need(self.direct_nodes==self.expected_confirmations and
             result['directFixtureFloors']==len(self.expected_confirmations),
             'joining profile maintenance complete direct cohort')
        result['boundRetirementEvents']=retirement_coverage(self.events)
        return result


def replay(root,profile):return Replay(root,profile).run()


def validate(root,profile):
    topology(profile);root=Path(root);before=collection.inventory(root)
    original=control.validate(root,profile);result=replay(root,profile)
    need(collection.inventory(root)==before,'joining profile maintenance original changed')
    return dict(status='PARTIAL',scope='profile-original-maintenance-authority',profile=profile,
                precondition=original,maintenance=result,maintenanceForceQualified=True,
                peerLedgerCompositionQualified=False,allMembershipProfilesQualified=False,
                processDeathQualified=False,phase3Complete=False)


def mutate(root,name,reader):
    if name!='missing-floor-transaction':return m.mutate(root,name,reader=reader)
    # Remove the last network floor's entire transaction, leaving its physical
    # retirement observations and bytes intact. Counting only surviving FLOOR
    # rows would miss these now-orphaned cleanup events.
    events=reader.events;candidates=[]
    for start,row in enumerate(events):
        if row['event']!='FLOOR_RESERVED':continue
        node=row['node'];end=next(i for i in range(start+1,len(events)) if events[i].get('node')==node and
                               events[i]['event']=='FLOOR_RELEASE_BEFORE_RETURN')
        own=[v['event'] for v in events[start:end+1] if v.get('node')==node]
        if 'FLOOR_COPY_HANDED_OFF' in own and any(v.startswith(('RETIREMENT_','SOURCE_RETIREMENT_')) for v in own):
            candidates.append((start,end,node))
    need(candidates,'joining profile maintenance missing negative target: '+name)
    start,end,node=candidates[-1]
    events[:]=[v for i,v in enumerate(events) if not (start<=i<=end and v.get('node')==node and v['event'].startswith('FLOOR_'))]
    (Path(root)/'events.json').write_bytes(f.canonical(events))


def qualify(root,profile,progress=None):
    root=Path(root);original=validate(root,profile);before=collection.inventory(root);results=[]
    protected={k:v for k,v in before['files'].items() if k not in ('events.json','wire.json')}
    size,kind,_,_=topology(profile)
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-profile-maintenance-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed)
            try:mutate(changed,name,Replay(changed,profile))
            except StopIteration as error:raise ValueError('joining profile maintenance missing negative target: '+name) from error
            after=collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k not in ('events.json','wire.json')}==protected and
                 after['directories']==before['directories'],'joining profile maintenance negative changed physical inputs')
            n.network(changed,size=size,kind=kind)
            prior=control.exports.replay(changed,profile);control.replay(changed,profile,prior)
            try:replay(changed,profile)
            except ValueError as error:need(str(error)==reason,'joining profile unrelated maintenance negative: '+name+': '+str(error))
            else:raise ValueError('joining profile maintenance mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',networkExportControlPrecondition='PASS',reason=reason))
        if progress:progress(dict(profile=profile,case=name,completed=len(results),total=len(NEGATIVES)))
    need(collection.inventory(root)==before,'joining profile maintenance qualification changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root')
    parser.add_argument('--profile',required=True,choices=PROFILES);parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    def progress(row):print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    result=qualify(args.root,args.profile,progress) if args.qualify else validate(args.root,args.profile)
    print(json.dumps(result,sort_keys=True))

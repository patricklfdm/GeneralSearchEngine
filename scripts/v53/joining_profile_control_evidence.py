"""Profile-bound original control exports and delivered retention majorities.

One whole physical/network/content history must pass first. A single remote ACK
never substitutes for a four/five-voter majority; unused replies remain evidence.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_profile_export_evidence as exports
from . import joining_control_evidence as control
from .joining_profile_evidence import PROFILES, topology

c=control
need,collection,f,e=c.need,exports.collection,c.f,c.e
NEGATIVES=c.NEGATIVES


def quorum_time(view,owner,rows,end):
    """Earliest delivered original majority, without counting duplicates/fences."""
    voters=set(view['old'])|set(view['new']);seen=set();delivered=[]
    need(owner in voters,'joining profile control recording owner')
    for row in rows:
        peer=row['request']['recipient']['node']
        need(peer in voters and peer!=owner and peer not in seen,'joining profile control distinct retention voters')
        seen.add(peer);at=row['delivered']
        if at is not None:
            need(type(at) is int and at>=0,'joining profile control retention delivery')
            if at<end:delivered.append((at,peer))
    acknowledged={owner}
    for at,peer in sorted(delivered):
        acknowledged.add(peer)
        if all(len(acknowledged & set(view[side]))>len(view[side])//2 for side in ('old','new')):
            c.n.s.catalog.majority(view,sorted(acknowledged));return at
    raise ValueError('joining profile control original retention quorum')


class Replay(c.Replay):
    def __init__(self,root,profile,*,old_owner_lifetimes=None,required_four=False):
        self.root=Path(root);self.profile=profile
        need(type(required_four) is bool,'joining export required-four profile')
        self.__dict__.update(vars(exports.context(root,profile,old_owner_lifetimes=old_owner_lifetimes,
            **({'required_four':True} if required_four else {}))));self.kind=self.model.kind
        self.phases=c.n.phase.blocks(self.events,self.model,old_owner_lifetimes=old_owner_lifetimes);self.recordings=[];self.confirmations={}
        proofs=f.decode(self.model.phases[8]['CERTIFICATE'],'records','CERTIFICATE')['proofs']
        self.expected_confirmations={v['voter'] for v in proofs}
        need(self.expected_confirmations<=set(self.model.old),'joining profile control original INTENT voters')
        self.expected_controls=dict(c.Replay.expected_controls,retention=len(self.expected_confirmations))

    def quorum(self):
        groups=defaultdict(list)
        for row in self.rows:
            if row['kind']=='LEARNER_RETENTION_INTENT':groups[row['request']['sender']['node'],row['request']['trace']].append(row)
        actual=set()
        for rows in groups.values():
            record=None;binding=None
            for row in rows:
                derived=self.retention_exchange(row);q=row['request']
                context=f.canonical(dict(view=q['view'],ballot=q['ballot'],payload=q['payload']))
                if record is None:record=derived;binding=context
                need(derived==record and context==binding,'joining profile control mixed retention round')
            own=record.pop('own');self.local_recording(own,min(v['sent'] for v in rows))
            start=quorum_time(record['cut']['view'],record['node'],rows,record['end'])
            key=(record['node'],e.sha(f.canonical(c.disk.anchor(own['packet']['capsule']))))
            need(key not in actual,'joining profile control duplicate recording');actual.add(key)
            self.recordings.append(dict(record,start=start))
        required=set()
        for values in self.groups:
            q=values[0]['offer']['request'];first=values[0]['offer'];last=values[-1]['commit']['offered']
            if q['sender']['node']!=self.model.joining:continue
            # A verified frozen BASIS is not a learner alias. Its initial offer
            # can itself span a same-authority selector replacement, so use its
            # original source authorization before consulting mutable current.
            if e.record_kind(values[0]['raw'])=='BASIS':
                e.authorize_source(values,self.windows,self.sources);continue
            # Learner aliases require the current generation's permit through
            # the complete session, not merely through the initial offer.
            own=self.current(q['recipient']['node'],first['received'],first['offered']);cap=own['packet']['capsule']
            if cap['cut']['view']['operation'] is None and e.learner_alias(own,q):
                self.current(q['recipient']['node'],first['received'],last)
                required.add((own['node'],e.sha(f.canonical(c.disk.anchor(cap)))))
        need(actual==required and len(actual)==2,'joining profile control complete recording endpoints')


def replay(root,profile,prior):return Replay(root,profile).run(prior)


def validate(root,profile):
    topology(profile);root=Path(root);before=collection.inventory(root)
    prior=exports.validate(root,profile);result=replay(root,profile,prior['exports'])
    counts=prior['precondition']['network']
    need(result['observedCommittedContents']==counts['committedTransfers'] and
         result['observedContentSessions']==counts['transferSessions']-counts['rejectedTransferAttempts'],
         'joining profile control complete transfer coverage')
    need(collection.inventory(root)==before,'joining profile control original changed')
    return dict(status='PARTIAL',scope='profile-original-control-exports-and-retention-quorums',profile=profile,
                precondition=prior,controls=result,observedControlExportsQualified=True,
                observedLearnerRetentionQualified=True,maintenanceAndPeerCompositionQualified=False,
                allMembershipProfilesQualified=False,processDeathQualified=False,phase3Complete=False)


def qualify(root,profile,progress=None):
    root=Path(root);original=validate(root,profile);before=collection.inventory(root);results=[]
    protected={k:v for k,v in before['files'].items() if k not in ('events.json','wire.json')}
    size,kind,_,_=topology(profile)
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-profile-control-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed)
            try:c.mutate(changed,name,reader=Replay(changed,profile))
            except StopIteration as error:raise ValueError('joining profile control missing negative target: '+name) from error
            after=collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k not in ('events.json','wire.json')}==protected and
                 after['directories']==before['directories'],'joining profile control negative changed physical inputs')
            c.n.network(changed,size=size,kind=kind)
            # The content gate also owns generic joining endpoint lifetimes.
            # This mutation specifically targets that shared owner boundary.
            if name=='completion-closed-owner':
                try:exports.replay(changed,profile)
                except ValueError as error:need(str(error)==reason,'joining profile unrelated control negative: '+name+': '+str(error))
                else:raise ValueError('joining profile control mutation accepted: '+name)
            else:
                prior=exports.replay(changed,profile)
                try:replay(changed,profile,prior)
                except ValueError as error:need(str(error)==reason,'joining profile unrelated control negative: '+name+': '+str(error))
                else:raise ValueError('joining profile control mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',networkPrecondition='PASS',reason=reason,
                            rejectionStage='owner-lifetime' if name=='completion-closed-owner' else 'control'))
        if progress:progress(dict(profile=profile,case=name,completed=len(results),total=len(NEGATIVES)))
    need(collection.inventory(root)==before,'joining profile control qualification changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root')
    parser.add_argument('--profile',required=True,choices=PROFILES);parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    def progress(row):print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    result=qualify(args.root,args.profile,progress) if args.qualify else validate(args.root,args.profile)
    print(json.dumps(result,sort_keys=True))

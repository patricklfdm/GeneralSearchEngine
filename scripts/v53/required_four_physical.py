"""Original-file replay of the explicit four-required-voter development topology.

The original native history supplies identities/UUIDs, never expected snapshots.
This entry is separate from the frozen five-profile joining catalogue.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import bootstrap_replay_contract as source_policy
from . import required_four_evidence as semantic
from . import joining_profile_continuation_evidence as profile
from . import joining_same_view_physical as covering
from . import joining_retirement_replay as retirement

p,c,init,s,f,disk,need=profile.p,profile.c,profile.init,profile.s,profile.f,profile.disk,profile.need


def pin_required(files,voters):
    prefix,_,_=disk.current(files)
    manifest=f.decode(files[prefix+'generation.gsr'],'records','GENERATION')
    inactive=any(n.startswith('generations/') and n.count('/')==1 and n!=prefix[:-1] for n in files)
    sources={n.split('/')[1] for n in files if n.startswith('sources/') and n.endswith('/source.gscp')}
    return inactive and manifest['selection'] is not None and len(voters)>=4 and len(sources)>=2


def governing(files,copies,node,*,pinned=False):
    result=covering.covering_floor(files,copies,node)
    if pinned:
        prefix,_,_=disk.current(files);digest=c.sha(files[prefix+'generation.gsr']);path='floor-copies/'+digest
        need(path in result,'required-four pinned original copy absent')
        result={n:v for n,v in result.items() if n!=path and not n.startswith(path+'/')}
        result['floor-copies/local.gsr']=files['selector.gsr']
    return result


class Retirements(retirement.Retirements):
    def compare(self,node,files,copies,identifiers,*,pinned=False):
        files=governing(files,copies,node,pinned=pinned)
        for identifier in sorted(identifiers):
            position=self.positions.get(node,0)
            need(position<len(self.by_node[node]),'joining retirement original transaction absent')
            row=self.by_node[node][position];authority,compact=retirement.decision(files,node,identifier)
            self.floors.add((node,retirement.floor_order(self.events,node,row['steps'][0]['event'])))
            initial={n:dict(directory=True) if raw is None else retirement.observed.release.r.entry(raw) for n,raw in files.items() if n!='.'}
            self.prefixes+=retirement.observed.compare(row,initial,authority,compact,identifier)
            self.positions[node]=position+1;self.transactions+=1
            files={n:raw for n,raw in files.items() if n!='sources/'+identifier and not n.startswith('sources/'+identifier+'/')}
            files['grants.gsr']=compact


deferred=profile.deferred

class Continuation(profile.Continuation):
    preparation_label="required-four"
    def __init__(self,root,initialized,captures,retirements):
        super().__init__(root,initialized,captures);self.retirements=retirements;self.pinned_floors=0

    def maintenance(self,group,node):
        view=disk.current(group[node])[2]['capsule']['cut']['view'];eligible=set(view['old'])|set(view['new'])
        # FINAL leaves the departing owner's published bytes intact; it cannot
        # acquire a successor quorum or perform another governing campaign.
        if node not in eligible:return group[node]
        voters=tuple(n for n in self.voters if n in eligible);pinned=pin_required(group[node],voters)
        if pinned:self.pinned_floors+=1
        def compare(owner,files,copies,identifiers):self.retirements.compare(owner,files,copies,identifiers,pinned=pinned)
        return c.maintenance(group,node,compare,voters=voters)

    def preparation(self):
        ballot=init.next_ballot(self.group['node-1'])
        need(ballot['counter']==self.captures.counter,'joining profile preparation next ballot')
        sources={node:self.prepare(node,ballot) for node in self.initialization.voters}
        boundary=profile.prepared_exchanges(self.root,self.group,ballot,sources,self.initialization.voters,replay=self.replay)
        for node in self.initialization.voters:self.group[node]=self.maintenance(self.group,node)
        return boundary



def replay(root, *, bootstrap_source='EMPTY', wire_layout='JSON'):
    source_args = source_policy.options(bootstrap_source,wire_layout)
    root=Path(root);events=s.collection.read_json(root,'events.json',s.collection.EVENT_BYTES)
    captures=p.Captures(root,events,voters=semantic.OLD_LIVE,**source_args)
    retirements=Retirements(root,events,voters=(*semantic.OLD,'node-6'),**source_args)
    model=s.Replay(root,size=5,kind='REPLACE',required_four=True,**source_args)
    for index in range(1,12):model.step(index)
    model.publication_receipts=c.t.publication.CheckpointReceipts(root,model)
    history=covering.History(root,model,captures,retirements);before=history.run()
    owner=init.placement.Placement(root,history);placed=owner.run()
    handoff=init.retirement.Retirement(root,owner);retired=handoff.run()
    initialized=covering.Initialization(root,handoff,captures,retirements);joining=initialized.run()
    continuation=Continuation(root,initialized,captures,retirements);continued=continuation.run();retirements.complete()
    # Shared ordinary-profile helpers describe the topology supplied by Replay.
    for result in (before,placed,retired,joining,continued):result['profile']=semantic.PROFILE
    return dict(history=before,placement=placed,retirement=retired,initialization=joining,continuation=continued,
                sourceRetirementTransactions=retirements.transactions,sourceRetirementPrefixes=retirements.prefixes,
                governingFloorForceWindows=len(retirements.floors),pinnedMaintenanceFloors=continuation.pinned_floors)


def validate(root, *, publication_observer=None, bootstrap_source='EMPTY', wire_layout='JSON'):
    source_args = source_policy.options(bootstrap_source,wire_layout)
    root=Path(root);before=source_policy.inventory(root, bootstrap_source=bootstrap_source, wire_layout=wire_layout)
    original=semantic.validate(root,**source_args) if publication_observer is None else semantic.validate(root,publication_observer=publication_observer,**source_args)
    result=replay(root,**source_args)
    need(source_policy.inventory(root, bootstrap_source=bootstrap_source, wire_layout=wire_layout)==before,'required-four physical original changed')
    return source_policy.receipt(dict(status='PASS',scope='required-four-derived-owner-files',profile=semantic.PROFILE,semantic=original,physical=result,
                ownerFilesQualified=True,sourceRetirementPhysicalQualified=True,completePhysicalQualified=False,
                forceAndNetworkQualified=False,processDeathQualified=False,finalSourceCohortQualified=False,phase3Complete=False),bootstrap_source,wire_layout)


NEGATIVES={
    'extra-prepared-file':'joining initialization exact old prepared inventory: node-1',
    'extra-installed-file':'joining continuation exact inventory: continuation-installed-9: node-1',
    'departing-predecessor-deleted':'joining continuation exact inventory: after-close: node-3',
    'missing-pinned-original':'retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN',
}


def mutate(root,name):
    root=Path(root);need(name in NEGATIVES,'required-four declared physical mutation')
    if name in ('extra-prepared-file','extra-installed-file'):
        where='before-joint-continuation' if name=='extra-prepared-file' else 'continuation-installed-9'
        (root/where/'node-1'/'unexpected').write_bytes(b'underived file')
    elif name=='departing-predecessor-deleted':
        path=root/'after-close/node-3'
        selector=f.decode((path/'selector.gsr').read_bytes(),'records','SELECTOR')
        inactive=[v for v in (path/'generations').iterdir() if v.name!=selector['generation']]
        need(len(inactive)==1 and inactive[0].is_dir(),'required-four original departing predecessor absent')
        shutil.rmtree(inactive[0])
    else:
        events=s.collection.read_json(root,'events.json',s.collection.EVENT_BYTES)
        for event in events:
            if event.get('event')!=retirement.observed.EVENT or event['point']!='SOURCE_RETIREMENT_WRITTEN':continue
            path=root/event['capture'];meta=json.loads(path.read_bytes())
            if not any(v['name']=='floor-copies/local.gsr' for v in meta['files']):continue
            meta['files']=[v for v in meta['files'] if v['name']!='floor-copies/local.gsr']
            encoded=f.canonical(meta);path.write_bytes(encoded);event['sha256']=c.sha(encoded)
            (root/'events.json').write_bytes(f.canonical(events));return
        raise ValueError('required-four original pin capture absent')


def qualify(root,progress=None):
    root=Path(root);inventory=s.collection.inventory(root);original=validate(root);results=[]
    if progress:progress(dict(stage='original',status='PASS'))
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-required-four-physical-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name)
            # Metadata/checksum or semantic failure cannot stand in for deriving
            # the exact physical inventory. These prerequisite gates must pass.
            semantic.validate(changed);retirement.observed.validate(changed)
            try:validate(changed)
            except ValueError as error:need(str(error)==reason,'required-four unrelated physical negative: '+name+': '+str(error))
            else:raise ValueError('required-four physical mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason,semanticAndCaptureCollection='PASS'))
        if progress:progress(results[-1])
    need(s.collection.inventory(root)==inventory,'required-four physical original changed')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root,lambda row:print(json.dumps(row),file=sys.stderr,flush=True)) if args.qualify else validate(args.root),sort_keys=True))

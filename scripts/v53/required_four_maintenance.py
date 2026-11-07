"""Required-four maintenance with original local-pin custody and exact release.

Complete physical/network/export validation precedes this temporal layer. A
pin is bound to original captured selector and generation bytes, never inferred
from the presence of a PIN callback. The logical quorum still includes local.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import bootstrap_replay_contract as source_policy
from . import required_four_exports as exports
from . import joining_profile_maintenance_evidence as profile
from . import joining_source_retirement as captures

m,need,collection=profile.m,profile.need,profile.collection
PIN_POINTS=('FLOOR_LOCAL_ORIGINAL_FORCED','FLOOR_LOCAL_SELECTOR_WRITTEN',
            'FLOOR_LOCAL_SELECTOR_FORCED','FLOOR_LOCAL_PARENT_FORCED','FLOOR_RELEASE_LOCAL_CLEARED')
NEGATIVES={**profile.NEGATIVES,**{'pin/'+point:'joining maintenance exact copy force/release order' for point in PIN_POINTS}}


def captured_pin(transactions,own,start,end,selector):
    """Bind already physically derived capture bytes to this exact live window.

    Captures alone are not deletion authority. The entry's preceding physical
    replay derives their complete inventories, pin policy and both majorities.
    """
    rows=[row for row in transactions if row['node']==own['node'] and
          any(start<step['event']<end for step in row['steps'])]
    for row in rows:
        need(all(start<step['event']<end for step in row['steps']),
             'required-four pin capture outside floor')
    files=[step['files'] for row in rows for step in row['steps']]
    pins=[value.get('floor-copies/local.gsr') for value in files]
    if not any(pin is not None for pin in pins):return False
    chosen=m.f.decode(selector,'records','SELECTOR')
    need(chosen['node']==own['node'] and chosen['digest']==m.sha(own['manifest']) and
         all(pin==selector for pin in pins),'required-four original pin selector binding')
    prefix='generations/'+chosen['generation']+'/'
    members=dict(own['members'],**{'generation.gsr':own['manifest']})
    for value in files:
        need(value.get('selector.gsr')==selector and
             {name[len(prefix):]:raw for name,raw in value.items() if name.startswith(prefix)}==members,
             'required-four original pinned generation binding')
        copied='floor-copies/'+chosen['digest']
        need(not any(name==copied or name.startswith(copied+'/') for name in value),
             'required-four pinned original also copied')
    return True


class Replay(profile.Replay):
    def __init__(self,root, *, bootstrap_source='EMPTY', wire_layout='JSON'):
        source_args = source_policy.options(bootstrap_source,wire_layout)
        self.__dict__.update(vars(exports.control_reader(root,**source_args)))
        self.direct_nodes=set();self.floor_inputs=[];self.pinned_floors=set()
        self.capture_transactions=captures.collect(self.root,self.events)

    def expected_events(self,copies,own,network,start,end):
        selector=(self.root/own['path']/'selector.gsr').read_bytes()
        pinned=captured_pin(self.capture_transactions,own,start,end,selector)
        if pinned:self.pinned_floors.add((own['node'],start))
        return m.floor_events(copies,own['node'],network,pinned=pinned)

    def floors(self):
        result=super().floors()
        return dict(result,pinnedMaintenanceFloors=len(self.pinned_floors))


def replay(root, *, bootstrap_source='EMPTY', wire_layout='JSON'):
    source_args = source_policy.options(bootstrap_source,wire_layout)
    return Replay(root,**source_args).run()


def validate(directory, *, bootstrap_source='EMPTY', wire_layout='JSON'):
    source_args = source_policy.options(bootstrap_source,wire_layout)
    root=Path(directory);before=source_policy.inventory(root, bootstrap_source=bootstrap_source, wire_layout=wire_layout)
    original=exports.validate(root,**source_args);result=replay(root,**source_args)
    physical=original['precondition']['physical']['physical']
    need(result['pinnedMaintenanceFloors']==physical['pinnedMaintenanceFloors'],
         'required-four complete physical pin coverage')
    need(source_policy.inventory(root, bootstrap_source=bootstrap_source, wire_layout=wire_layout)==before,'required-four maintenance original changed')
    return source_policy.receipt(dict(status='PASS',scope='required-four-original-maintenance-and-pinned-local-custody',
                profile=exports.PROFILE,precondition=original,maintenance=result,maintenanceForceQualified=True,
                peerLedgerCompositionQualified=False,wholeRuntimeResourcesQualified=False,
                completePhysicalQualified=False,processDeathQualified=False,finalSourceCohortQualified=False,phase3Complete=False),bootstrap_source,wire_layout)


def mutate(root,case):
    need(case in NEGATIVES,'required-four declared maintenance mutation')
    reader=Replay(root)
    if not case.startswith('pin/'):return profile.mutate(root,case,reader)
    point=case.split('/',1)[1]
    next(row for row in reader.events if row['event']==point)['event']='REMOVED_'+point
    (Path(root)/'events.json').write_bytes(m.f.canonical(reader.events))


def rejection_stage(root):
    exports.network.replay(root)
    contents=exports.content(root);exports.controls(root,contents)
    return lambda:replay(root)


def qualify(directory,progress=None):
    root=Path(directory);before=collection.inventory(root);original=validate(root);results=[]
    if progress:progress(dict(stage='original',status='PASS'))
    protected={k:v for k,v in before['files'].items() if k not in ('events.json','wire.json')}
    for case,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-required-four-maintenance-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed)
            try:mutate(changed,case)
            except StopIteration as error:raise ValueError('required-four missing maintenance mutation target: '+case) from error
            after=collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k not in ('events.json','wire.json')}==protected and
                 after['directories']==before['directories'],'required-four maintenance negative changed physical inputs')
            check=rejection_stage(changed)
            try:check()
            except ValueError as error:need(str(error)==reason,'required-four unrelated maintenance negative: '+case+': '+str(error))
            else:raise ValueError('required-four maintenance mutation accepted: '+case)
        results.append(dict(case=case,status='REJECTED',reason=reason,networkExportControlPrecondition='PASS'))
        if progress:progress(dict(case=case,completed=len(results),total=len(NEGATIVES)))
    need(collection.inventory(root)==before,'required-four maintenance qualification changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    progress=lambda row:print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    print(json.dumps(qualify(a.root,progress) if a.qualify else validate(a.root),sort_keys=True))

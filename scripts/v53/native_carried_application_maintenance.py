"""Original complete-copy floors around application death and staged retirement."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_application_exports as exports
from . import native_carried_transition_maintenance as maintenance

protocol=exports.protocol;p=protocol.p;need=p.need


def stage_projector(before,current,eligible,stage,voters,point):
    need(point==protocol.application.CUT,'application maintenance original cut')
    if stage['kind']=='campaign':eligible=[node for node in eligible if 'applied-end' not in before[node]]
    else:
        if stage['kind']=='interrupted':eligible=voters
        for node in eligible:
            if 'applied-end' not in before[node]:continue
            frames,_=p.data.pending(before[node]);protocol.application.retire(before[node],frames['ENTRY'],frames['PAYLOAD'])
            current[node]=protocol.retirement.staging.without_staging(current[node])
    return current,eligible,{node:dict(pinned=protocol.pin_current(current,node,campaign=stage['kind']=='campaign')) for node in eligible}


def expected_floors(root,history):
    return maintenance.expected_floors(root,history,stage_projector=stage_projector)


class Replay(maintenance.Replay):
    slot_projection=staticmethod(protocol.slot_projection)
    recovery_phases=('ACCEPT','PROOF','CERTIFICATE')
    def __init__(self,root,kind):
        super().__init__(root,kind,export_options=dict(slot_projection=protocol.slot_projection,
            interrupted_projector=exports.interrupted_records,retirement_boundaries=exports.retirement_boundaries),
            floor_projector=expected_floors)

    def expected_events(self,copies,own,network,start,end):
        ordinal,_=self.stage(start)
        return maintenance.maintenance.floor_events(copies,own['node'],network,
            pinned=self.expected[ordinal,own['node']]['pinned'])


def replay(root,kind):
    reader=Replay(root,kind);result=reader.run()
    return dict(result,pinnedLocalOriginals=sum(v['pinned'] for v in reader.expected.values()))


def validate(root):
    root=Path(root);before=p.process.collection.inventory(root);original=exports.validate(root)
    result=replay(root,original['exports']['kind'])
    need(p.process.collection.inventory(root)==before,'application maintenance original changed')
    return dict(original=original,maintenance=result,status='PARTIAL',phase3Complete=False)


NEGATIVES=dict(maintenance.NEGATIVES)


def qualify(root):
    root=Path(root);before=p.process.collection.inventory(root);original=validate(root);kind=original['maintenance']['kind'];results=[]
    observations={'events.json','wire.json','process/life-1.jsonl','process/life-2.jsonl'}
    protected=lambda inventory:{k:v for k,v in inventory['files'].items() if k not in observations}
    with tempfile.TemporaryDirectory(prefix='v53-application-maintenance-') as temp:
        for name,reason in NEGATIVES.items():
            copied=Path(temp)/name;shutil.copytree(root,copied)
            maintenance.mutate(copied,kind,name,reader_factory=Replay)
            after=p.process.collection.inventory(copied)
            need(protected(before)==protected(after) and before['directories']==after['directories'],
                 'application maintenance negative changed original storage')
            p.process.validate_application(copied);protocol.replay(copied,kind);exports.replay(copied,kind)
            try:replay(copied,kind)
            except ValueError as error:need(str(error)==reason,'application maintenance wrong negative '+name+': '+str(error))
            else:raise ValueError('application maintenance accepted negative '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason,physicalAndNetworkPrecondition='PASS'))
            shutil.rmtree(copied)
            print(json.dumps(dict(stage='application-maintenance-negative',completed=len(results),total=len(NEGATIVES),case=name)),file=sys.stderr,flush=True)
    need(p.process.collection.inventory(root)==before,'application maintenance qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))

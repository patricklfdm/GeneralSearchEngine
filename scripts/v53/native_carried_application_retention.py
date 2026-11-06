"""Continuous peer/future ledgers through original carried application death."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_application_maintenance as maintenance
from . import native_carried_transition_retention as retention

p=maintenance.p;protocol=maintenance.protocol;exports=maintenance.exports;need=p.need


class PeerReplay(retention.PeerReplay):
    slot_projection=staticmethod(protocol.slot_projection)
    recovery_phases=maintenance.Replay.recovery_phases
    expected_events=maintenance.Replay.expected_events

    def __init__(self,root,kind):
        super().__init__(root,kind,base_options=dict(export_options=dict(slot_projection=protocol.slot_projection,
            interrupted_projector=exports.interrupted_records,retirement_boundaries=exports.retirement_boundaries),
            floor_projector=maintenance.expected_floors))


class FutureReplay(retention.FutureReplay):
    def __init__(self,root,kind):super().__init__(root,kind,base_factory=maintenance.Replay)


READERS=dict(peers=PeerReplay,future=FutureReplay)
NEGATIVES=retention.NEGATIVES


def replay(root,kind):
    return dict(status='PARTIAL',kind=kind,**{name:reader(root,kind).run() for name,reader in READERS.items()},
        retentionRevisionCompositionQualified=True,transientBytesCaptured=False,wholeRuntimeResourcesQualified=False,
        cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=p.process.collection.inventory(root);original=maintenance.validate(root)
    result=replay(root,original['maintenance']['kind'])
    need(p.process.collection.inventory(root)==before,'application retention original changed')
    return dict(original=original,retention=result,status='PARTIAL',phase3Complete=False)


def qualify(root):
    root=Path(root);before=p.process.collection.inventory(root);original=validate(root);kind=original['retention']['kind'];results=[]
    observations={'events.json','process/life-1.jsonl','process/life-2.jsonl'}
    protected=lambda inv:{k:v for k,v in inv['files'].items() if k not in observations}
    with tempfile.TemporaryDirectory(prefix='v53-application-retention-') as temp:
        for stage,cases in NEGATIVES.items():
            for name,reason in cases.items():
                changed=Path(temp)/(stage+'-'+name);shutil.copytree(root,changed)
                retention.mutate(changed,kind,stage,name,readers=READERS)
                after=p.process.collection.inventory(changed)
                need(protected(before)==protected(after) and before['directories']==after['directories'],
                     'application retention negative changed physical or wire inputs')
                need(retention.non_target(root,stage)==retention.non_target(changed,stage) and
                     retention.h.unrelated(p.process.read(root/'events.json'),stage)==
                     retention.h.unrelated(p.process.read(changed/'events.json'),stage),
                     'application retention negative changed other observations')
                try:READERS[stage](changed,kind).run()
                except ValueError as error:need(str(error)==reason,'application retention wrong negative '+stage+': '+name+': '+str(error))
                else:raise ValueError('application retention accepted negative '+stage+': '+name)
                results.append(dict(stage=stage,case=name,status='REJECTED',reason=reason,physicalWireAndOtherObservationsUnchanged=True))
                shutil.rmtree(changed)
                print(json.dumps(dict(stage='application-retention-negative',ledger=stage,completed=len(results),
                    total=sum(map(len,NEGATIVES.values())),case=name)),file=sys.stderr,flush=True)
    need(p.process.collection.inventory(root)==before,'application retention qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='full-original-physical-callback-network-export-floor; unchanged files, wire and non-target child observations')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))

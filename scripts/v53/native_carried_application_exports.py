"""Process-local export authority for carried application-ACK crash originals."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_application_protocol as protocol
from . import native_carried_transition_exports as exports

p,c,d,e,f,need=protocol.p,protocol.c,protocol.d,exports.e,protocol.f,protocol.need
sha=exports.sha


def interrupted_records(root,events,history,windows,model):
    result=exports.interrupted_records(root,events,history,windows,model)
    stage=next(v for v in history.ranges if v['kind']=='interrupted')
    selected=f.decode((root/(stage['before']+'.gsr')).read_bytes(),'records','SELECTED')
    original,_=p.data.pending(c.inventory(root/'at-cut/node-1'))
    need(original['ENTRY']==model.phases[0]['ENTRY'] and 'PROOF' in original and 'CERTIFICATE' in original,
         'application export original interrupted certificate')
    for source in selected['sources']:
        node=source['voter'];frames,_=p.data.pending(c.inventory(root/'at-cut'/node))
        for phase in ('PROOF','CERTIFICATE'):
            points=[at for at,v in enumerate(events) if stage['start']<at<stage['stop'] and
                    v.get('node')==node and v['event']==phase+'_BEFORE_RETURN']
            expected=phase=='PROOF' or node=='node-1'
            need(len(points)==int(expected),'application export interrupted completion boundary')
            if not points:continue
            at=points[0];own=e.current(windows,node,at,at);end=min(own['end'],stage['stop'])
            need(frames.get(phase)==original[phase],'application export exact original '+phase)
            result.append(dict(node=node,start=at,end=end,raw=original[phase],reference=sha(original[phase]),
                               ballot=None,view=None,family='pending-record'))
            if phase=='PROOF':
                receipt=f.canonical(dict(root=selected['root'],voter=node,incarnation=own['identity']['storage'],
                                        phase=phase,record=sha(original[phase])))
                reference=sha(f.canonical(dict(schema='gse-v53-vote-observation/1.3',receipt=sha(receipt))))
                result.append(dict(node=node,start=at,end=e.next_promise(events,node,at,end),raw=receipt,reference=reference,
                    ballot=selected['ballot'],view=selected['view'],family='native-vote-receipt'))
    return result


def retirement_boundaries(events,node,before,current,lower,upper,starts):
    """One sorted source per completed native transaction, never one shared end."""
    removed=sorted(before.keys()-current.keys())
    need(len(starts)==len(removed) and starts==sorted(set(starts)),'application export exact source retirement count')
    ends={}
    for index,(identifier,start) in enumerate(zip(removed,starts)):
        stop=starts[index+1] if index+1<len(starts) else upper
        rows=[v['event'] for at,v in enumerate(events) if start<=at<stop and v.get('node')==node and
              v['event'].startswith('SOURCE_RETIREMENT_')]
        expected=['SOURCE_RETIREMENT_CREATED','SOURCE_RETIREMENT_WRITTEN','SOURCE_RETIREMENT_FORCED',
            'SOURCE_RETIREMENT_PARENT_FORCED','SOURCE_RETIREMENT_JOURNAL_PRUNED']
        expected+=['SOURCE_RETIREMENT_FILE_DELETED']*len(before[identifier]['members'])
        expected+=['SOURCE_RETIREMENT_DIRECTORY_DELETED','SOURCE_RETIREMENT_CLEARED','SOURCE_RETIREMENT_BEFORE_RETURN']
        need(lower<start<stop and rows==expected,'application export complete per-source retirement')
        ends[identifier]=start
    return ends


class Replay(exports.Replay):
    def __init__(self,root,kind):
        super().__init__(root,kind,slot_projection=protocol.slot_projection,interrupted_projector=interrupted_records,
                         retirement_boundaries=retirement_boundaries)


def replay(root,kind):return Replay(root,kind).run()


def validate(root):
    root=Path(root);before=p.process.collection.inventory(root);original=protocol.validate(root)
    result=replay(root,original['original']['physical']['kind'])
    need(p.process.collection.inventory(root)==before,'application export original changed')
    return dict(original=original,exports=result,status='PARTIAL',phase3Complete=False)


NEGATIVES=dict(exports.NEGATIVES)
NEGATIVES.update({'proof-'+name:reason for name,reason in exports.NEGATIVES.items() if name.startswith('receipt-')})


def qualify(root):
    root=Path(root);before=p.process.collection.inventory(root);original=validate(root);kind=original['exports']['kind'];results=[]
    observations={'events.json','wire.json','process/life-1.jsonl','process/life-2.jsonl'}
    protected=lambda inventory:{k:v for k,v in inventory['files'].items() if k not in observations}
    with tempfile.TemporaryDirectory(prefix='v53-application-export-') as temp:
        for name,reason in NEGATIVES.items():
            copied=Path(temp)/name;shutil.copytree(root,copied)
            exports.mutate(copied,kind,name.removeprefix('proof-'),reader_factory=Replay,
                           receipt_phase='PROOF' if name.startswith('proof-') else None)
            after=p.process.collection.inventory(copied)
            need(protected(before)==protected(after) and before['directories']==after['directories'],
                 'application export negative changed original storage')
            p.process.validate_application(copied);protocol.replay(copied,kind)
            try:replay(copied,kind)
            except ValueError as error:need(str(error)==reason,'application export wrong negative '+name+': '+str(error))
            else:raise ValueError('application export accepted negative '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason,physicalAndNetworkPrecondition='PASS'))
            shutil.rmtree(copied)
            print(json.dumps(dict(stage='application-export-negative',completed=len(results),total=len(NEGATIVES),case=name)),file=sys.stderr,flush=True)
    need(p.process.collection.inventory(root)==before,'application export qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))

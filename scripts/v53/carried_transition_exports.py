"""Temporal export and complete-copy floor replay of carried INTENT/FINAL.

Require the complete original physical/attempted-network reduction first. The
same immutable history supplies every grant, selected generation and retirement.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
from . import carried_transition_network as network
from . import remove_export_evidence as shared
from . import remove_process_exports as process

n=network.network;e=shared.e;c=n.c;f=n.f;need=n.need;sha=n.sha
NEGATIVES=shared.NEGATIVES


def snapshots(events,history):
    result=[(-1,'before-network')]
    for ordinal,parts in enumerate(history.phases,1):
        index=f.decode(parts['ENTRY'],'records','ENTRY')['index']
        for point,path,key,value in (
            ('ROUND_INSTALLED',f'installed-{ordinal}','record',sha(parts['SELECTED'])),
            ('DRIVER_APPLIED',f'applied-{index}','index',index),
            ('DRIVER_PUBLISHED',f'published-{index}','index',index)):
            positions=[i for i,v in enumerate(events) if v['event']==point and v.get(key)==value]
            need(len(positions)==1 and result[-1][0]<positions[0],'carried export original snapshot timeline')
            result.append((positions[0],path))
    return result+[(len(events),'after-close')]


class Replay(shared.Replay):
    def __init__(self,root,kind):
        first,_,_=network.physical.shape(kind);self.root=Path(root);self.kind=kind
        self.history=network.history(self.root,kind)
        self.events=n.collection.read_json(self.root,'events.json',n.collection.EVENT_BYTES)
        wires=n.collection.read_json(self.root,'wire.json',n.collection.WIRE_BYTES)
        ids={node:n.d.future.identity(c.inventory(self.root/'before-network'/node)) for node in self.history.old}
        root_id=f.decode(self.history.phases[0]['SELECTED'],'records','SELECTED')['root']
        self.rows=n.transcript.causal(self.events,wires,ids,root_id);contents=[];n.transcript.transfers(self.rows,contents=contents)
        self.groups=e.sessions(contents)
        self.windows=shared.generation_windows(self.root,self.events,self.history,indices=tuple(range(first,8)))
        self.sources=process.source_windows(self.root,self.events,self.history,self.history,snapshots=snapshots(self.events,self.history))
        phases=[dict(v,PAYLOAD=(self.root/f'native-payload-{index}.bin').read_bytes())
                for index,v in zip(range(first,8),self.history.phases)]
        self.model=SimpleNamespace(root=root_id,phases=phases,old=self.history.old,joining=None,owner=self.history.owner)
        self.records=e.record_windows(self.root,self.events,self.model,self.windows,self.sources,nodes=self.history.old)
        sizes=[len(f.decode(v['SELECTED'],'records','SELECTED')['sources']) for v in self.history.phases]
        floors=sizes+sizes[1:]
        self.expected_floor_counts=(sum(floors),0,sum(v*v for v in floors),sum(v*(v-1) for v in floors))
        self.expected_status_count=self.expected_floor_counts[3]

    def run(self):
        result=self.exports();self.statuses();result.update(self.floors())
        # The mandatory original physical gate derives first-slot maintenance
        # after reaccept and later pre-grant source retirement separately.
        return dict(status='PARTIAL',kind=self.kind,**result,discoveryHints=len(self.status_rows),
            observedExportAuthorityQualified=True,completeCopyFloorLifetimesQualified=True,
            retentionRevisionCompositionQualified=False,processDeathQualified=False,
            publicReady=False,phase3Complete=False)


def replay(root,kind):return Replay(root,kind).run()


def validate(root,kind):
    network.physical.shape(kind);root=Path(root);before=n.collection.inventory(root)
    original=network.validate(root,kind);result=replay(root,kind)
    need(n.collection.inventory(root)==before,'carried export original changed')
    return dict(result,precondition=original)


def mutate(root,kind,name):
    reader=Replay(root,kind)
    if name in e.NEGATIVES:e.mutate(Path(root),name,reader=reader)
    elif name in shared.maintenance.NEGATIVES:shared.maintenance.mutate(Path(root),name,reader=reader)
    elif name=='all-floors-missing':
        (Path(root)/'events.json').write_bytes(f.canonical([v for v in reader.events if not v['event'].startswith('FLOOR_')]))
    else:raise ValueError('carried export unknown mutation: '+name)


def negative(root,kind,before,name):
    reason=NEGATIVES[name];observations={'events.json','wire.json'}
    protected={k:v for k,v in before['files'].items() if k not in observations}
    with tempfile.TemporaryDirectory(prefix='v53-carried-export-negative-') as temp:
        copied=Path(temp)/'raw';shutil.copytree(root,copied);mutate(copied,kind,name);after=n.collection.inventory(copied)
        need({k:v for k,v in after['files'].items() if k not in observations}==protected and
             after['directories']==before['directories'],'carried export negative changed physical input')
        network.replay(copied,kind)
        try:replay(copied,kind)
        except ValueError as error:need(str(error)==reason,'carried export unrelated negative: '+name+': '+str(error))
        else:raise ValueError('carried export mutation accepted: '+name)
    return dict(case=name,status='REJECTED',networkPrecondition='PASS',reason=reason)


def qualify(root,kind,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'carried export replay workers')
    root=Path(root);original=validate(root,kind);before=n.collection.inventory(root);results={}
    def record(row):
        results[row['case']]=row
        print(json.dumps(dict(kind=kind,case=row['case'],completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    if workers==1:
        for name in NEGATIVES:record(negative(root,kind,before,name))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs=[pool.submit(negative,root,kind,before,name) for name in NEGATIVES]
            for job in as_completed(jobs):record(job.result())
    need(n.collection.inventory(root)==before,'carried export original changed')
    return dict(original=original,negatives=[results[name] for name in NEGATIVES])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--kind',choices=network.physical.KINDS,required=True)
    p.add_argument('--qualify',action='store_true');p.add_argument('--workers',type=int,default=1);a=p.parse_args()
    need(a.qualify or a.workers==1,'carried export workers require qualification')
    print(json.dumps(qualify(a.root,a.kind,workers=a.workers) if a.qualify else validate(a.root,a.kind),sort_keys=True))

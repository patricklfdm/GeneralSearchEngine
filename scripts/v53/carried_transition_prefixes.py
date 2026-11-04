"""Compare writer-held carried INTENT/FINAL retirement bytes to derived states.

The common capture-row format is shared with REMOVE. The collection has its own
schema and binds only the carried result; callbacks alone cannot replace bytes.
This is component qualification, not source-cohort or process-death admission.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import carried_transition_retirement as r
from . import remove_retirement_prefixes as p

need=r.need;f=r.f;n=r.n;sha=r.sha
SCHEMA='gse-v53-carried-retirement-capture-v1'
NEGATIVES=dict(p.NEGATIVES,**{
    'result-binding':'REMOVE prefix original history binding',
    'kind-binding':'REMOVE prefix collection header',
    'pending-cleared':'REMOVE prefix exact original state: RETIREMENT_OLD_FILES_FORCED',
})


def collect(root,sidecar,kind):
    r.r.e.network.physical.shape(kind)
    return p.collect_bound(root,sidecar,kind,SCHEMA,'carried-transition-result.json',4)


class Replay(p.Replay,r.Replay):
    """Shared exact prefix comparison over carried plans and ledger origins."""


def replay(root,sidecar,kind):
    copies,before=collect(root,sidecar,kind);result=Replay(root,kind,copies).run()
    need(n.collection.inventory(Path(sidecar),maximum=p.g.MAXIMUM_BYTES+4096)==before,'carried prefix sidecar changed')
    return dict(result,kind=kind,publicReady=False,sourceCohortQualified=False)


def validate(root,sidecar,kind):
    r.r.e.network.physical.shape(kind);root=Path(root);before=n.collection.inventory(root)
    original=r.validate(root,kind);result=replay(root,sidecar,kind)
    need(n.collection.inventory(root)==before,'carried prefix original changed')
    return dict(result,precondition=original)


def mutate(sidecar,name):
    if name in p.NEGATIVES:return p.mutate(sidecar,name)
    sidecar=Path(sidecar);header_path=sidecar/'collection.json';_,header=p.g.json_file(header_path)
    if name=='result-binding':header['resultSha256']='0'*64
    elif name=='kind-binding':header['profile']='FINAL' if header['profile']=='INTENT' else 'INTENT'
    elif name=='pending-cleared':
        objects=sidecar/'objects';found=False
        for path in sorted(sidecar.glob('capture-*.json')):
            _,value=p.g.json_file(path)
            if value['point']!='RETIREMENT_OLD_FILES_FORCED':continue
            entry=next(v for v in value['files'] if v['name']=='pending.accept')
            if (objects/entry['identity']['sha256']).read_bytes()==r.c.EMPTY:continue
            digest=sha(r.c.EMPTY);(objects/digest).write_bytes(r.c.EMPTY)
            entry['identity']=dict(size=len(r.c.EMPTY),sha256=digest);path.write_bytes(f.canonical(value));found=True;break
        need(found,'carried prefix negative requires actual pending vote')
        used={v['identity']['sha256'] for path in sidecar.glob('capture-*.json')
              for v in p.g.json_file(path)[1]['files'] if 'sha256' in v['identity']}
        for path in objects.iterdir():
            if path.name not in used:path.unlink()
    else:raise ValueError('carried prefix unknown negative')
    header['storedBytes']=sum(path.stat().st_size for path in sidecar.rglob('*') if path.is_file() and path!=header_path)
    header_path.write_bytes(f.canonical(header))


def qualify(root,sidecar,kind):
    original=validate(root,sidecar,kind);before=n.collection.inventory(Path(root))
    captured=n.collection.inventory(Path(sidecar),maximum=p.g.MAXIMUM_BYTES+4096);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-carried-prefix-negative-') as temp:
            changed=Path(temp)/'captures';shutil.copytree(sidecar,changed);mutate(changed,name)
            try:replay(root,changed,kind)
            except ValueError as error:need(str(error)==reason,'carried unrelated prefix negative: '+name+': '+str(error))
            else:raise ValueError('carried prefix mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(kind=kind,case=name,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(n.collection.inventory(Path(root))==before and
         n.collection.inventory(Path(sidecar),maximum=p.g.MAXIMUM_BYTES+4096)==captured,'carried prefix qualification changed original')
    return dict(original=original,negatives=results,originalHistoryReexecuted=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('sidecar')
    parser.add_argument('--kind',required=True,choices=r.r.e.network.physical.KINDS);parser.add_argument('--qualify',action='store_true')
    args=parser.parse_args();print(json.dumps((qualify if args.qualify else validate)(args.root,args.sidecar,args.kind),sort_keys=True))

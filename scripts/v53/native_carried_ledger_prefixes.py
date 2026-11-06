"""Original peer/future ledger file prefixes through carried group death and reopening."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_completion_prefixes as prerequisite
from . import native_carried_retirement_prefixes as r
from . import native_ledger_files as model

need=r.need;f=r.f;collection=r.collection;shared=r.shared
SCHEMA='gse-v53-carried-process-ledger-capture-v1'
CAPTURE_SCHEMA='gse-v53-carried-ledger-capture-v1'
KINDS=model.KINDS


def plans(root):
    history=Path(root)/'history';result=r.forces.process.read(history/'process/result.json')
    return model.plans(history,result['carriedKind'],result['cut'])[0]


def replay(root,ledgers,expected=None):
    ledgers=Path(ledgers);need({v.name for v in ledgers.iterdir()}=={'life-1','life-2'},'carried ledger exact two lifetimes')
    expected=plans(root) if expected is None else expected
    lives=[r.lifetime(root,ledgers/f'life-{life}',life,expected,schema=SCHEMA,capture_schema=CAPTURE_SCHEMA,kinds=KINDS) for life in (1,2)]
    return dict(status='PARTIAL',lifetimes=lives,capturedPrefixes=sum(v['capturedPrefixes'] for v in lives),
        transientLedgerBytesQualified=True,postCutTailObserved=False,fullTransientBytesQualified=False,
        coreScratchInventoryReplay=False,wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=collection.inventory(root)
    need({v.name for v in root.iterdir()}=={'previous','ledgers'},'carried ledger wrapper inventory')
    original=prerequisite.validate(root/'previous')
    result=replay(root/'previous/previous/previous/maintenance/prefixes/observed',root/'ledgers')
    need(collection.inventory(root)==before,'carried ledger original changed')
    return dict(status='PARTIAL',original=original,ledgers=result,phase3Complete=False)


NEGATIVES={name:r.NEGATIVES[name] for name in ('missing-copy','duplicate-index','wrong-callback','missing-object',
    'altered-object','extra-object','boolean-size','wrong-owner','process-pid','process-life','process-root',
    'process-terminal','process-events','boolean-pid','missing-callback')}
NEGATIVES['missing-lifetime']='carried ledger exact two lifetimes'
MUTATIONS={'complete-prefix':'PREFIX_WRITTEN','early-rename':'WRITTEN','leftover-candidate':'RENAMED',
           'changed-active':'PARENT_FORCED','outside-ledger':'BEFORE_WRITE','changed-reseal':'RECOVERY_PARENT_FORCED'}
PHYSICAL={kind+'-'+name:((('RETENTION_' if kind=='peer' else 'FUTURE_RETENTION_')+suffix),kind,name)
          for kind in model.KINDS for name,suffix in MUTATIONS.items()}
NEGATIVES.update({name:'carried prefix exact original state: '+point for name,(point,_,_) in PHYSICAL.items()})


def mutate(root,name):
    need(name in NEGATIVES,'carried ledger unknown negative')
    if name not in PHYSICAL:return r.mutate(root,name)
    directory=Path(root)/'life-2';objects=directory/'objects';header_path=directory/'collection.json'
    copies=[(p,shared.g.json_file(p)[1]) for p in sorted(directory.glob('capture-*.json'))]
    point,kind,change=PHYSICAL[name];path,value=next((p,v) for p,v in copies if v['point']==point)
    values={v['name']:v['identity'] for v in value['files']}
    def put(key,raw):
        digest=shared.sha(raw);(objects/digest).write_bytes(raw);values[key]=dict(size=len(raw),sha256=digest)
    active,candidate=model.FILES[kind]
    if change=='complete-prefix':
        later=next(v for _,v in copies if v['node']==value['node'] and v['eventIndex']>value['eventIndex'] and v['point']==point.replace('PREFIX_WRITTEN','WRITTEN'))
        values[candidate]=next(v['identity'] for v in later['files'] if v['name']==candidate)
    elif change=='early-rename':values[active]=values.pop(candidate)
    elif change=='leftover-candidate':values[candidate]=values[active]
    elif change in ('changed-active','changed-reseal'):put(active,b'foreign revision')
    elif change=='outside-ledger':put('grants.gsr',b'foreign journal')
    value['files']=[dict(name=k,identity=v) for k,v in sorted(values.items())];path.write_bytes(f.canonical(value))
    used={entry['identity']['sha256'] for p in directory.glob('capture-*.json')
          for entry in shared.g.json_file(p)[1]['files'] if 'sha256' in entry['identity']}
    for p in objects.iterdir():
        if p.name not in used:p.unlink()
    _,header=shared.g.json_file(header_path)
    header['storedBytes']=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file() and p!=header_path)
    header_path.write_bytes(f.canonical(header))


def qualify(root):
    root=Path(root);original=validate(root);before=collection.inventory(root)
    observed=root/'previous/previous/previous/maintenance/prefixes/observed';expected=plans(observed);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-carried-ledger-negative-') as temp:
            changed=Path(temp)/'ledgers';shutil.copytree(root/'ledgers',changed);mutate(changed,name)
            try:replay(observed,changed,expected)
            except ValueError as error:need(str(error)==reason,'carried ledger unrelated negative: '+name+': '+str(error))
            else:raise ValueError('carried ledger mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(case=name,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'carried ledger qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='complete original completion/vote/campaign/maintenance/resource/process chain; independent continuous ledger revisions and file anchors')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))

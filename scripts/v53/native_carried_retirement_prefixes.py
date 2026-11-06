"""Writer-held retirement bytes across the original two process lifetimes.

The complete original process/storage/resource chain is a prerequisite. Expected
inventories come from original transaction replay, never from captured objects.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_resource_evidence as observed
from . import native_carried_transition_forces as forces
from . import remove_retirement_prefixes as shared

f=shared.f;need=shared.need;collection=observed.collection
SCHEMA='gse-v53-carried-process-retirement-capture-v1'


def plans(root):
    history=Path(root)/'history';result=forces.process.read(history/'process/result.json');expected=[]
    forces.replay(history,result['carriedKind'],result['cut'],prefixes=expected)
    return expected


def lifetime(root,directory,life,expected):
    resource=Path(root)/'resources'/f'life-{life}'
    index=observed.read(resource,'index.json',16384)
    inventory=collection.inventory(directory,maximum=shared.g.MAXIMUM_BYTES+4096)
    _,header=shared.g.json_file(directory/'collection.json')
    fields={'schema','root','life','pid','terminal','eventsSha256','captures','storedBytes'}
    need(type(header) is dict and set(header)==fields and header['schema']==SCHEMA and
         type(header['life']) is int and type(header['pid']) is int and
         all(f.canonical(header[k])==f.canonical(index[k]) for k in ('root','life','pid','terminal','eventsSha256')),
         'carried prefix original lifetime binding')
    events=observed.linked(resource,index,'events.json','eventsSha256',32*shared.g.MIB)
    # The mandatory original validator checks incarnation and complete child
    # transcript equality. This decoder compares only callback owner/name.
    events=[{k:v for k,v in row.items() if k!='incarnation'} for row in events]
    copies,_=shared.collect_contents(directory,events,header,4,
        lambda node:{key:collection.snapshot.s.regular(Path(root)/'history/before-network'/node/key,16384)
                     for key in ('root.gsr','node.gsr')},inventory)
    rows=[v for v in expected if v['life']==life]
    need(len({v['eventIndex'] for v in rows})==len(rows) and
         copies.keys()=={v['eventIndex'] for v in rows},'carried prefix exact original callback coverage')
    kinds=dict(generation=0,source=0)
    for row in rows:
        copy=copies[row['eventIndex']]
        need(all(copy[k]==row[k] for k in ('node','kind','point')),'carried prefix original transaction binding')
        need(shared.r.physical(copy['files'])==row['files'],'carried prefix exact original state: '+row['point'])
        kinds[row['kind']]+=1
    need(collection.inventory(directory,maximum=shared.g.MAXIMUM_BYTES+4096)==inventory,'carried prefix sidecar changed')
    return dict(life=life,pid=header['pid'],terminal=header['terminal'],capturedPrefixes=len(rows),
                byKind=kinds,storedBytes=header['storedBytes'])


def replay(root,retirement,expected=None):
    retirement=Path(retirement)
    need({v.name for v in retirement.iterdir()}=={'life-1','life-2'},'carried prefix exact two lifetimes')
    expected=plans(root) if expected is None else expected
    lives=[lifetime(root,retirement/f'life-{life}',life,expected) for life in (1,2)]
    return dict(status='PARTIAL',lifetimes=lives,capturedPrefixes=sum(v['capturedPrefixes'] for v in lives),
        transientRetirementBytesQualified=True,postCutTailObserved=False,fullTransientBytesQualified=False,
        coreScratchInventoryReplay=False,wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=collection.inventory(root)
    need({v.name for v in root.iterdir()}=={'observed','retirement'},'carried prefix wrapper inventory')
    original=observed.validate(root/'observed');result=replay(root/'observed',root/'retirement')
    need(collection.inventory(root)==before,'carried prefix original changed')
    return dict(status='PARTIAL',original=original,prefixes=result,phase3Complete=False)


NEGATIVES={name:reason.replace('REMOVE prefix exact original state:','carried prefix exact original state:')
           for name,reason in shared.NEGATIVES.items() if name not in ('history-binding','profile-binding')}
NEGATIVES.update({name:'carried prefix original lifetime binding' for name in
    ('process-pid','process-life','process-root','process-terminal','process-events','boolean-pid')})
NEGATIVES['missing-lifetime']='carried prefix exact two lifetimes'
NEGATIVES['missing-callback']='carried prefix exact original callback coverage'


def mutate(root,name):
    need(name in NEGATIVES,'carried prefix unknown negative')
    directory=Path(root)/'life-2'
    if name=='missing-lifetime':shutil.rmtree(Path(root)/'life-1');return
    if name=='missing-callback':
        path=directory/'collection.json';_,header=shared.g.json_file(path)
        (directory/f'capture-{header["captures"]:04d}.json').unlink();header['captures']-=1
        used={entry['identity']['sha256'] for p in directory.glob('capture-*.json')
              for entry in shared.g.json_file(p)[1]['files'] if 'sha256' in entry['identity']}
        for p in (directory/'objects').iterdir():
            if p.name not in used:p.unlink()
        header['storedBytes']=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file() and p!=path)
        path.write_bytes(f.canonical(header));return
    if name.startswith('process-') or name=='boolean-pid':
        path=directory/'collection.json';_,header=shared.g.json_file(path)
        key={'process-pid':'pid','process-life':'life','process-root':'root','process-terminal':'terminal',
             'process-events':'eventsSha256','boolean-pid':'pid'}[name]
        header[key]=True if name=='boolean-pid' else header[key]+1 if key in ('pid','life') else 'CUT_PREFIX' if key=='terminal' else '0'*64
        path.write_bytes(f.canonical(header));return
    shared.mutate(directory,name)


def qualify(root):
    root=Path(root);original=validate(root);before=collection.inventory(root)
    expected=plans(root/'observed');results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-carried-prefix-negative-') as temp:
            changed=Path(temp)/'retirement';shutil.copytree(root/'retirement',changed);mutate(changed,name)
            try:replay(root/'observed',changed,expected)
            except ValueError as error:need(str(error)==reason,'carried prefix unrelated negative: '+name+': '+str(error))
            else:raise ValueError('carried prefix mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(case=name,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'carried prefix qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='full original process/storage/network/retention/resource replay; expected prefixes derived from unchanged originals')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))

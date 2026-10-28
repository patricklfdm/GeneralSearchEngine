"""Fresh-process sequential FLOOR copying; original authority still comes last.

This tests real floor files and process death. Receiving network pulls are covered
separately; the worker's handoff callback deliberately deletes no remote data.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from . import floor_qualification as q
from . import floor_evidence as e
from . import floor_negatives as n

POINTS = ('FLOOR_COPY_DIRECTORY_FORCED', 'FLOOR_COPY_HANDED_OFF', 'FLOOR_AUTHORITY_FORCED')
NEGATIVES = n.CASES + (('early-handoff','floor force order'),
                       ('missing-handoff','floor force order'),('handoff-mode','floor handoff mode'))


class Probe(q.Probe):
    handoff = True


def cases():
    return [dict(name=f'4-{through}-{mode}-{cut.lower()}',size=4,through=through,mode=mode,cut=cut)
            for through in (0,6) for mode,cut in [('clean','none')]+[(m,c) for m in ('halt','kill') for c in POINTS]]


def validate(root):
    root=Path(root)
    e.need({p.name for p in root.iterdir()}=={c['name'] for c in cases()},'handoff complete process inventory')
    return [e.validate_case(root/c['name'],c,handoff=True) for c in cases()]


def qualify(root):
    original=validate(root);results=[];case=cases()[0]
    for name,reason in NEGATIVES:
        with tempfile.TemporaryDirectory(prefix='v53-handoff-negative-') as temp:
            path=Path(temp)/'case';shutil.copytree(Path(root)/case['name'],path)
            if name=='handoff-mode':
                value=json.loads((path/'case.json').read_text());value['handoff']=False;q.save(path/'case.json',value)
            elif name in ('early-handoff','missing-handoff'):
                output=path/'first.stdout';rows=[json.loads(line) for line in output.read_text().splitlines()]
                at=next(i for i,row in enumerate(rows) if row.get('event')=='FLOOR_COPY_HANDED_OFF')
                row=rows.pop(at)
                if name=='early-handoff':rows.insert(at-1,row)
                output.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            else:n.mutate(path,name)
            try:e.validate_case(path,case,handoff=True)
            except ValueError as error:e.need(str(error)==reason,'handoff unrelated negative: '+name+': '+str(error))
            else:raise ValueError('handoff mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


def classpath_binding(cp):
    rows={}
    e.need(bool(cp) and all(cp.split(os.pathsep)),'handoff explicit classpath entries')
    for item in cp.split(os.pathsep):
        path=Path(item);e.need(path.is_absolute() and path.exists() and not path.is_symlink(),'handoff original classpath')
        for file in sorted(path.rglob('*.class')) if path.is_dir() else [path]:
            e.need(file.is_file() and not file.is_symlink(),'handoff original classpath file')
            rows[str(file.resolve())]=hashlib.sha256(file.read_bytes()).hexdigest()
    e.need(bool(rows),'handoff empty classpath');return rows


def run(output,cp):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False);physical=output/'physical';physical.mkdir()
    receipt=dict(status='RUNNING',scope='sequential-floor-files-processes',networkReceivingQualified=False,phase3Complete=False)
    try:
        receipt['classpath']=classpath_binding(cp)
        for case in cases():
            path=physical/case['name'];path.mkdir();print(json.dumps(Probe(path,case,cp).run(),sort_keys=True),flush=True)
        result=qualify(physical);q.save(output/'validation.json',result)
        with tempfile.TemporaryDirectory(prefix='v53-handoff-portable-') as temp:
            relocated=Path(temp)/'physical';shutil.copytree(physical,relocated)
            e.need(validate(relocated)==result['original'],'handoff portable original replay')
        e.need(classpath_binding(cp)==receipt['classpath'],'handoff build changed during execution')
        receipt.update(status='PASS',cases=len(result['original']),negativeCases=len(result['negatives']),portableReplay='PASS')
    except BaseException as error:
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:q.save(output/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');parser.add_argument('--classpath');parser.add_argument('--replay',action='store_true')
    args=parser.parse_args()
    if args.replay:print(json.dumps(qualify(args.output),sort_keys=True))
    else:
        if not args.classpath:parser.error('--classpath required for execution')
        result=run(args.output,args.classpath);print(json.dumps({k:v for k,v in result.items() if k!='classpath'},sort_keys=True))

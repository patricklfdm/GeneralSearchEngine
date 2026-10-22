"""Retain and independently replay the complete 112-case deterministic composition."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from . import composition_model as model
from . import composition_oracle as oracle
from . import composition_scenarios as scenarios
from . import composition_negatives as negatives
from .membership_model import need

ROOT=Path(__file__).resolve().parents[2]
SCHEMA='gse-v53-composition-qualification-v1'
FAMILIES=('transition','heterogeneous','staged','accepted','partial-proof','proof','prefix')+tuple(
    f'{control}-{cut}' for control in ('seal','intent','final') for cut in ('accepted','proof','prefix'))
MAX_TRACE=32*1024*1024


def sha(raw):return hashlib.sha256(raw).hexdigest()
def save(path,value):path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
def cases():
    return [dict(name=f'{size}-{kind.lower()}-{family}',size=size,kind=kind,family=family)
            for size,kind in scenarios.PROFILES for family in FAMILIES]


def binding():
    files=sorted((ROOT/'scripts/v53').glob('*.py'))+[ROOT/'docs/v5x/v5.3/acceptance-plan.json']
    return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                worktreeDirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT)),
                files={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in files})


def trace(path):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=MAX_TRACE,'missing/oversized/linked model trace')
    with gzip.open(path,'rb') as stream:raw=stream.read(MAX_TRACE+1)
    need(len(raw)<=MAX_TRACE,'decoded model trace bound')
    result=json.loads(raw);need(model.encoded(result).encode()==raw,'noncanonical model trace');return result


def coverage(record,case):
    """Derive scenario coverage from original events; labels alone are insufficient."""
    initial=record['initial'];need(len(initial['members'])==case['size'],'profile initial size')
    events=record['events'];published=[e for e in events if e['event']=='published']
    commands=[oracle.read(e['certificate']['entry'])['command'] for e in published]
    reservations=[c for c in commands if c['kind']=='RESERVE']
    need(len(reservations)==1 and reservations[0]['request']['kind']==case['kind'],'profile transition kind')
    proven={e['certificate']['entry'] for e in events if e['event']=='certificate'}
    need(sum(oracle.read(raw)['command']['kind']=='INTENT' for raw in proven)==
         sum(oracle.read(raw)['command']['kind']=='FINAL' for raw in proven)==1,'missing membership boundary')
    expected={'transition':14,'heterogeneous':17,'staged':15,'accepted':16,'partial-proof':16,'proof':16,'prefix':15}
    expected.update({f'{control}-{cut}':(15 if control=='seal' else 14)-(cut=='prefix')
                     for control in ('seal','intent','final') for cut in ('accepted','proof','prefix')})
    need(len(published)==expected[case['family']] and published[-1]['ready'],'incomplete final publication')
    if case['family']=='heterogeneous':
        selected=[e['selected'] for e in events if e['event']=='selection-force'][-1]
        sources=[oracle.read(b)['packet'] for b in selected['bases']]
        need(len({p['cut']['index'] for p in sources})>1 and all(not p['journal'] for p in sources),'not heterogeneous compacted sources')
        need(any(e['event']=='basis-reply' for e in events),'missing duplicate original basis')
    elif case['family']!='transition':
        position=next(i for i,e in enumerate(events) if e['event']=='crash')
        proposals=[i for i,e in enumerate(events[:position]) if e['event']=='propose'];start=proposals[-1]
        request=events[start];command=oracle.read(request['entry'])['command'];family=case['family'];control=family.split('-')[0]
        if control in ('seal','intent','final'):
            need(command['kind']==control.upper() and command['number']==1,'wrong interrupted control');boundary=family.split('-')[1]
        else:need(command==dict(kind='DATA',value='interrupted-tail'),'wrong interrupted operation');boundary=family
        selected=next(e['selected'] for e in reversed(events[:start]) if e['event']=='selection-force')
        owners=len(selected['owners']);cut=events[start+1:position]
        observed=tuple(sum(e['event']==event and (phase is None or e['body']['kind']==phase) for e in cut)
                       for event,phase in (('vote-stage','ACCEPT'),('vote-force','ACCEPT'),('vote-force','PROOF'),('certificate',None),('prefix-force',None)))
        wanted={'staged':(1,0,0,0,0),'accepted':(owners,owners,0,0,0),'partial-proof':(owners,owners,1,0,0),
                'proof':(owners,owners,owners,1,0),'prefix':(owners,owners,owners,1,1)}
        need(observed==wanted[boundary],'force cut mislabeled')
        need(sum(e['event']=='crash' for e in events)==sum(e['event']=='restart' for e in events)==1,'crash/restart inventory')


def replay(output,source):
    output=Path(output);receipt=json.loads((output/'receipt.json').read_bytes())
    need(receipt['schema']==SCHEMA and receipt['status']=='PASS' and receipt['runtimeQualified'] is False
         and receipt['execution']=='deterministic-model-only' and receipt['source']==source,'qualification scope/source')
    expected={f"traces/{c['name']}.json.gz" for c in cases()}|{'validation.json','negatives.json'}
    actual={p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
    need(not any(p.is_symlink() for p in output.rglob('*')) and actual==expected|{'receipt.json'}
         and set(receipt['files'])==expected,'model evidence inventory')
    for path in expected:need(sha((output/path).read_bytes())==receipt['files'][path],'model evidence hash: '+path)
    results=[];originals={}
    for case in cases():
        record=trace(output/'traces'/(case['name']+'.json.gz'));result=oracle.check(record);coverage(record,case)
        results.append(dict(case=case,**{k:result[k] for k in ('events','publications','selections','capsules','deletions')}))
        if case['size']==3 and case['kind']=='ADD' and case['family'] in ('transition','heterogeneous','accepted'):originals[case['family']]=record
    need(results==json.loads((output/'validation.json').read_bytes()),'replayed model results differ')
    checks=negatives.run(originals);need(checks==json.loads((output/'negatives.json').read_bytes()),'model negative results differ')
    need(receipt['cases']==len(results) and receipt['negativeCases']==len(checks),'model coverage receipt')
    return dict(status='PASS',cases=len(results),negativeCases=len(checks),events=sum(r['events'] for r in results),runtimeQualified=False)


def run(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False);(output/'traces').mkdir()
    source=binding();receipt=dict(schema=SCHEMA,status='RUNNING',source=source,execution='deterministic-model-only',runtimeQualified=False)
    results=[];originals={}
    try:
        for case in cases():
            size,kind,family=case['size'],case['kind'],case['family']
            if family.split('-')[0] in ('seal','intent','final'):
                control,cut=family.split('-');group=scenarios.control_recovery(size,kind,control.upper(),cut)[0]
            else:
                group=(scenarios.transition(size,kind) if family=='transition' else scenarios.heterogeneous(size,kind)
                       if family=='heterogeneous' else scenarios.recover_tail(size,kind,family))[0]
            record=group.evidence();raw=model.encoded(record).encode();need(len(raw)<=MAX_TRACE,'generated model trace bound')
            path=output/'traces'/(case['name']+'.json.gz');path.write_bytes(gzip.compress(raw,mtime=0))
            retained=trace(path);result=oracle.check(retained);coverage(retained,case)
            results.append(dict(case=case,**{k:result[k] for k in ('events','publications','selections','capsules','deletions')}))
            if size==3 and kind=='ADD' and family in ('transition','heterogeneous','accepted'):originals[family]=retained
            print(json.dumps(dict(case=case['name'],status='PASS',completed=len(results),total=len(cases()))),flush=True)
        checks=negatives.run(originals);save(output/'validation.json',results);save(output/'negatives.json',checks)
        need(binding()==source,'model source changed during qualification')
        receipt.update(status='PASS',cases=len(results),negativeCases=len(checks),events=sum(r['events'] for r in results),
                       files={p.relative_to(output).as_posix():sha(p.read_bytes()) for p in sorted(output.rglob('*')) if p.is_file()})
        save(output/'receipt.json',receipt)
        with tempfile.TemporaryDirectory(prefix='gse-v53-composition-') as temp:
            relocated=Path(temp)/'evidence';shutil.copytree(output,relocated);replay(relocated,source)
        receipt['relocatedReplay']='PASS'
    except BaseException as error:
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)),completed=len(results));raise
    finally:save(output/'receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('source','files')},sort_keys=True));return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output');args=parser.parse_args();run(args.output)

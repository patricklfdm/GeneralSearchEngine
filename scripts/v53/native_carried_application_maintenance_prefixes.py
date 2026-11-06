"""Same-history application crash/recovery and three maintenance capture families."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_application_retirement_prefixes as prerequisite
from . import native_carried_application_maintenance_plans as model
from . import native_carried_retirement_prefixes as retirement
from . import native_carried_floor_prefixes as floor
from . import native_carried_campaign_prefixes as campaign

need=retirement.need;collection=retirement.collection;shared=retirement.shared;f=retirement.f
FAMILIES={'retirement':retirement,'floors':floor,'campaigns':campaign}
PLAN_KEYS={'retirement':'retirement','floors':'floor','campaigns':'campaign'}
PIN_POINTS={
    'pin-selector-substitution':'FLOOR_LOCAL_SELECTOR_WRITTEN',
    'pin-original-missing':'FLOOR_LOCAL_ORIGINAL_FORCED',
    'pin-cleared-before-authority':'FLOOR_AUTHORITY_WRITTEN',
    'pin-retained-after-release':'FLOOR_RELEASE_LOCAL_CLEARED',
    'pin-original-deleted-on-release':'FLOOR_RELEASE_LOCAL_CLEARED',
}
NEGATIVES={family+':'+name:reason for family,module in FAMILIES.items() for name,reason in module.NEGATIVES.items()}
NEGATIVES.update({'floors:'+name:'carried prefix exact original state: '+point for name,point in PIN_POINTS.items()})


def plans(observed):
    projected=model.plans(observed)
    return {family:projected[key] for family,key in PLAN_KEYS.items()}


def replay(observed,sidecar,expected=None):
    sidecar=Path(sidecar)
    need({p.name for p in sidecar.iterdir()}==set(FAMILIES),'application maintenance exact family inventory')
    expected=plans(observed) if expected is None else expected
    need(set(expected)==set(FAMILIES),'application maintenance complete expected families')
    result={family:module.replay(observed,sidecar/family,expected[family]) for family,module in FAMILIES.items()}
    return dict(status='PARTIAL',families=result,capturedPrefixes=sum(v['capturedPrefixes'] for v in result.values()),
        maintenanceTransientBytesQualified=True,postCutTailObserved=False,fullTransientBytesQualified=False,
        wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=collection.inventory(root)
    need({p.name for p in root.iterdir()}=={'previous','maintenance'},'application maintenance capture wrapper inventory')
    original=prerequisite.validate(root/'previous')
    result=replay(root/'previous/previous/observed',root/'maintenance')
    need(collection.inventory(root)==before,'application maintenance capture original changed')
    return dict(status='PARTIAL',original=original,maintenance=result,phase3Complete=False)


def mutate_pin(root,name):
    directory=Path(root)/'life-2';objects=directory/'objects';header_path=directory/'collection.json'
    copies=[(p,shared.g.json_file(p)[1]) for p in sorted(directory.glob('capture-*.json'))]
    key='floor-copies/local.gsr';point=PIN_POINTS[name]
    def contents(value):return {v['name']:v['identity'] for v in value['files']}
    path,value=next((p,v) for p,v in copies if v['point']==point and
        (name!='pin-cleared-before-authority' or key in contents(v)))
    values=contents(value)
    if name=='pin-selector-substitution':
        raw=b'foreign pinned selector';digest=shared.sha(raw);(objects/digest).write_bytes(raw)
        values[key]=dict(size=len(raw),sha256=digest)
    elif name in ('pin-original-missing','pin-original-deleted-on-release'):
        selected=f.decode((objects/values['selector.gsr']['sha256']).read_bytes(),'records','SELECTOR')
        generation='generations/'+selected['generation']+'/'
        del values[next(k for k in values if k.startswith(generation) and k.endswith('.image'))]
    elif name=='pin-cleared-before-authority':del values[key]
    elif name=='pin-retained-after-release':
        previous=next(v for _,v in reversed(copies) if v['node']==value['node'] and
            v['eventIndex']<value['eventIndex'] and key in contents(v))
        values[key]=contents(previous)[key]
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
    observed=root/'previous/previous/observed';expected=plans(observed);results=[]
    for label,reason in NEGATIVES.items():
        family,name=label.split(':',1);module=FAMILIES[family]
        with tempfile.TemporaryDirectory(prefix='v53-application-maintenance-negative-') as temporary:
            changed=Path(temporary)/family;shutil.copytree(root/'maintenance'/family,changed)
            if family=='floors' and name in PIN_POINTS:mutate_pin(changed,name)
            else:module.mutate(changed,name)
            try:module.replay(observed,changed,expected[family])
            except ValueError as error:need(str(error)==reason,'application maintenance unrelated negative: '+label+': '+str(error))
            else:raise ValueError('application maintenance accepted negative: '+label)
        results.append(dict(case=label,status='REJECTED',reason=reason))
        print(json.dumps(dict(stage='application-maintenance-negative',case=label,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'application maintenance qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='complete same-history application/resource/interrupted-file/old-end-retirement chain; unchanged independent maintenance plans')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    args=parser.parse_args();print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))

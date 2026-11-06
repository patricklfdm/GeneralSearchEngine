"""Same-history carried application vote/completion/ledger/replay captures."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_application_storage_coverage as prerequisite
from . import native_carried_application_transient_plans as model
from . import native_carried_vote_prefixes as votes
from . import native_carried_completion_prefixes as completion
from . import native_carried_ledger_prefixes as ledgers
from . import native_carried_replay_prefixes as replay_files

shared=prerequisite.shared;need=shared.need;collection=prerequisite.collection
FAMILIES={'votes':votes,'completion':completion,'ledgers':ledgers,'replay':replay_files}
NEGATIVES={family+':'+name:('application completion exact recovery lifetime' if family=='completion' and name=='missing-lifetime' else reason)
           for family,module in FAMILIES.items() for name,reason in module.NEGATIVES.items()}


def replay(observed,sidecars,expected):
    sidecars=Path(sidecars)
    need({v.name for v in sidecars.iterdir()}==set(FAMILIES) and set(expected)==set(FAMILIES),'application transient exact family inventory')
    return {family:replay_family(observed,sidecars/family,family,expected[family]) for family in FAMILIES}


def replay_family(observed,directory,family,rows):
    if family!='completion':return FAMILIES[family].replay(observed,directory,rows)
    need({v.name for v in Path(directory).iterdir()}=={'life-2'},'application completion exact recovery lifetime')
    need(rows and all(v['life']==2 for v in rows),'application completion original recovery rows')
    value=completion.r.lifetime(Path(observed),Path(directory)/'life-2',2,rows,
        schema=completion.SCHEMA,capture_schema=completion.CAPTURE_SCHEMA,kinds=completion.KINDS)
    return dict(status='PARTIAL',capturedPrefixes=value['capturedPrefixes'],lifetimes=[value])


def combine(parts):
    """Only old-end/replay overlap is intentional; both captures must agree."""
    need(set(parts)==set(FAMILIES)|set(prerequisite.prerequisite.FAMILIES)|{'application','old-end'},
         'application transient complete union families')
    result={};owners={};overlaps=0
    for family,rows in parts.items():
        need(rows,'application transient nonempty union family')
        for row in rows:
            key=(row['life'],row['eventIndex'])
            if key in result:
                need(family not in owners[key] and owners[key]|{family}=={'old-end','replay'} and row['point'].startswith('REPLAY_'),
                     'application transient unexpected callback overlap')
                need(all(result[key][k]==row[k] for k in ('node','point','files')),
                     'application transient conflicting replay capture')
                overlaps+=1
                owners[key].add(family)
            else:result[key]=row;owners[key]={family}
    need(overlaps>0,'application transient missing original replay overlap')
    return [result[k] for k in sorted(result)],overlaps


def project(observed,rows):
    ordinals=shared.coverage.ordinal_plans(rows);owners=[]
    for life in (1,2):
        directory=Path(observed)/f'resources/life-{life}'
        events=shared.resource.read(directory,'events.json',32*1024*1024)
        boundaries=shared.resource.read(directory,'boundaries.json',32*1024*1024)
        for node in shared.r.forces.process.NODES:
            _,trace=shared.coverage.t.read(directory/(node+'.json'))
            owners.append(shared.coverage.bind(rows,trace,events,boundaries,node,life,closed=life==2,ordinals=ordinals))
    need(sum(v['callbacks'] for v in owners)==len(rows),'application transient complete owner assignment')
    return dict(status='PARTIAL',callbacks=len(rows),owners=owners,wholeRuntimeResourcesQualified=False)


def validate(root):
    root=Path(root);before=collection.inventory(root)
    need({v.name for v in root.iterdir()}=={'previous','transients'},'application transient wrapper inventory')
    original=prerequisite.validate(root/'previous',include_application=True)
    observed=root/'previous/previous/previous/observed'
    parts,details=model.plans(observed);captures=replay(observed,root/'transients',parts)
    existing=prerequisite.application_plans(observed)
    rows,overlaps=combine(dict(existing,**parts));coverage=project(observed,rows)
    need(collection.inventory(root)==before,'application transient original changed')
    return dict(status='PARTIAL',original=original,captures=captures,ledger=details,coverage=coverage,
        duplicateReplayCallbacks=overlaps,applicationTransientCompositionQualified=True,
        fullTransientBytesQualified=False,wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def qualify(root):
    root=Path(root);before=collection.inventory(root);original=validate(root)
    observed=root/'previous/previous/previous/observed';parts,_=model.plans(observed);results=[]
    for label,reason in NEGATIVES.items():
        family,name=label.split(':',1)
        with tempfile.TemporaryDirectory(prefix='v53-application-transient-negative-') as temporary:
            changed=Path(temporary)/family;shutil.copytree(root/'transients'/family,changed)
            if family=='completion' and name=='missing-lifetime':shutil.rmtree(changed/'life-2')
            else:FAMILIES[family].mutate(changed,name)
            try:replay_family(observed,changed,family,parts[family])
            except ValueError as error:need(str(error)==reason,'application transient unrelated negative '+label+': '+str(error))
            else:raise ValueError('application transient accepted negative '+label)
        results.append(dict(case=label,status='REJECTED',reason=reason))
        print(json.dumps(dict(stage='application-transient-negative',case=label,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'application transient qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
                negativePrecondition='complete original five-family physical/resource chain and remaining transient captures; unchanged original models')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    args=parser.parse_args();print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))

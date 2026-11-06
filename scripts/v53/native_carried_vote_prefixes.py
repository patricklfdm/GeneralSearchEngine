"""Original vote file prefixes through carried group death and reopening."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_campaign_prefixes as prerequisite
from . import native_carried_retirement_prefixes as r
from . import native_vote_files as model

need=r.need;f=r.f;collection=r.collection;shared=r.shared
SCHEMA='gse-v53-carried-process-vote-capture-v1'
CAPTURE_SCHEMA='gse-v53-carried-vote-capture-v1'
KINDS={phase.lower():(phase+'_',) for phase in model.PHASES}


def plans(root):
    history=Path(root)/'history';result=r.forces.process.read(history/'process/result.json');expected=[]
    r.forces.replay(history,result['carriedKind'],result['cut'],vote_prefixes=expected)
    return expected


def replay(root,votes,expected=None):
    votes=Path(votes);need({v.name for v in votes.iterdir()}=={'life-1','life-2'},'carried vote exact two lifetimes')
    expected=plans(root) if expected is None else expected
    lives=[r.lifetime(root,votes/f'life-{life}',life,expected,schema=SCHEMA,capture_schema=CAPTURE_SCHEMA,kinds=KINDS) for life in (1,2)]
    return dict(status='PARTIAL',lifetimes=lives,capturedPrefixes=sum(v['capturedPrefixes'] for v in lives),
        transientVoteBytesQualified=True,postCutTailObserved=False,fullTransientBytesQualified=False,
        coreScratchInventoryReplay=False,wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=collection.inventory(root)
    need({v.name for v in root.iterdir()}=={'previous','votes'},'carried vote wrapper inventory')
    original=prerequisite.validate(root/'previous')
    result=replay(root/'previous/maintenance/prefixes/observed',root/'votes')
    need(collection.inventory(root)==before,'carried vote original changed')
    return dict(status='PARTIAL',original=original,votes=result,phase3Complete=False)


NEGATIVES={name:r.NEGATIVES[name] for name in ('missing-copy','duplicate-index','wrong-callback','missing-object',
    'altered-object','extra-object','boolean-size','wrong-owner','process-pid','process-life','process-root',
    'process-terminal','process-events','boolean-pid','missing-callback')}
NEGATIVES['missing-lifetime']='carried vote exact two lifetimes'
MUTATIONS={'nonempty-create':'CANDIDATE_CREATED','complete-prefix':'PREFIX_WRITTEN','early-rename':'CANDIDATE_WRITTEN',
           'leftover-candidate':'RENAMED','changed-active':'PARENT_FORCED','outside-vote':'VALIDATED'}
PHYSICAL={phase.lower()+'-'+name:(phase+'_'+suffix,name) for phase in model.PHASES for name,suffix in MUTATIONS.items()}
NEGATIVES.update({name:'carried prefix exact original state: '+point for name,(point,_) in PHYSICAL.items()})


def mutate(root,name):
    need(name in NEGATIVES,'carried vote unknown negative')
    if name not in PHYSICAL:return r.mutate(root,name)
    directory=Path(root)/'life-2';objects=directory/'objects';header_path=directory/'collection.json'
    copies=[(p,shared.g.json_file(p)[1]) for p in sorted(directory.glob('capture-*.json'))]
    point,change=PHYSICAL[name];path,value=next((p,v) for p,v in copies if v['point']==point)
    values={v['name']:v['identity'] for v in value['files']}
    def put(key,raw):
        digest=shared.sha(raw);(objects/digest).write_bytes(raw);values[key]=dict(size=len(raw),sha256=digest)
    if change=='nonempty-create':put(model.NEXT,b'unexpected prefix')
    elif change=='complete-prefix':
        later=next(v for _,v in copies if v['node']==value['node'] and v['eventIndex']>value['eventIndex'] and
                   v['point']==point.replace('PREFIX_WRITTEN','CANDIDATE_WRITTEN'))
        values[model.NEXT]=next(v['identity'] for v in later['files'] if v['name']==model.NEXT)
    elif change=='early-rename':values[model.ACTIVE]=values.pop(model.NEXT)
    elif change=='leftover-candidate':values[model.NEXT]=values[model.ACTIVE]
    elif change=='changed-active':put(model.ACTIVE,b'foreign active vote')
    elif change=='outside-vote':put('grants.gsr',b'changed outside transaction')
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
    observed=root/'previous/maintenance/prefixes/observed';expected=plans(observed);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-carried-vote-negative-') as temp:
            changed=Path(temp)/'votes';shutil.copytree(root/'votes',changed);mutate(changed,name)
            try:replay(observed,changed,expected)
            except ValueError as error:need(str(error)==reason,'carried vote unrelated negative: '+name+': '+str(error))
            else:raise ValueError('carried vote mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(case=name,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'carried vote qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='complete original campaign/maintenance/resource/process chain; independent unchanged vote plan')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))

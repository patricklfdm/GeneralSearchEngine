"""Original application/publication file prefixes through carried group death and reopening."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_vote_prefixes as prerequisite
from . import native_carried_retirement_prefixes as r
from . import native_completion_files as model

need=r.need;f=r.f;collection=r.collection;shared=r.shared
SCHEMA='gse-v53-carried-process-completion-capture-v1'
CAPTURE_SCHEMA='gse-v53-carried-completion-capture-v1'
KINDS=model.KINDS


def plans(root):
    history=Path(root)/'history';result=r.forces.process.read(history/'process/result.json');expected=[]
    r.forces.replay(history,result['carriedKind'],result['cut'],completion_prefixes=expected)
    return expected


def replay(root,completion,expected=None):
    completion=Path(completion);need({v.name for v in completion.iterdir()}=={'life-1','life-2'},'carried completion exact two lifetimes')
    expected=plans(root) if expected is None else expected
    lives=[r.lifetime(root,completion/f'life-{life}',life,expected,schema=SCHEMA,capture_schema=CAPTURE_SCHEMA,kinds=KINDS) for life in (1,2)]
    return dict(status='PARTIAL',lifetimes=lives,capturedPrefixes=sum(v['capturedPrefixes'] for v in lives),
        applicationPublicationBytesQualified=True,postCutTailObserved=False,fullTransientBytesQualified=False,
        coreScratchInventoryReplay=False,wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=collection.inventory(root)
    need({v.name for v in root.iterdir()}=={'previous','completion'},'carried completion wrapper inventory')
    original=prerequisite.validate(root/'previous')
    result=replay(root/'previous/previous/maintenance/prefixes/observed',root/'completion')
    need(collection.inventory(root)==before,'carried completion original changed')
    return dict(status='PARTIAL',original=original,completion=result,phase3Complete=False)


NEGATIVES={name:r.NEGATIVES[name] for name in ('missing-copy','duplicate-index','wrong-callback','missing-object',
    'altered-object','extra-object','boolean-size','wrong-owner','process-pid','process-life','process-root',
    'process-terminal','process-events','boolean-pid','missing-callback')}
NEGATIVES['missing-lifetime']='carried completion exact two lifetimes'
PHYSICAL={
    'application-nonempty-create':('APPLY_PLAN_CREATED','nonempty'),
    'application-complete-prefix':('APPLY_IMAGE_PREFIX_WRITTEN','image'),
    'application-early-ack':('APPLY_END_FORCED','ack'),
    'application-outside-end':('APPLY_VALIDATED','outside'),
    'publication-early-selector':('INSTALL_SELECTOR_WRITTEN','selector'),
    'publication-missing-member':('INSTALL_GENERATION_FORCED','member'),
    'publication-early-plan-delete':('COVERED_END_FILE_DELETED','plan'),
    'publication-leftover-directory':('COVERED_END_DIRECTORY_DELETED','directory'),
    'publication-nonempty-candidate':('COVERED_VOTE_CANDIDATE_CREATED','candidate'),
    'publication-complete-empty-prefix':('COVERED_VOTE_PREFIX_WRITTEN','empty'),
    'publication-old-active':('COVERED_VOTE_RENAMED','active'),
    'publication-leftover-candidate':('COVERED_VOTE_RENAMED','leftover'),
    'publication-changed-ledger':('PUBLICATION_RETIRED','ledger'),
}
NEGATIVES.update({name:'carried prefix exact original state: '+point for name,(point,_) in PHYSICAL.items()})


def mutate(root,name):
    need(name in NEGATIVES,'carried completion unknown negative')
    if name not in PHYSICAL:return r.mutate(root,name)
    directory=Path(root)/'life-2';objects=directory/'objects';header_path=directory/'collection.json'
    copies=[(p,shared.g.json_file(p)[1]) for p in sorted(directory.glob('capture-*.json'))]
    point,change=PHYSICAL[name];path,value=next((p,v) for p,v in copies if v['point']==point)
    values={v['name']:v['identity'] for v in value['files']}
    def put(key,raw):
        digest=shared.sha(raw);(objects/digest).write_bytes(raw);values[key]=dict(size=len(raw),sha256=digest)
    def later(point,key):
        found=next(v for _,v in copies if v['node']==value['node'] and v['eventIndex']>value['eventIndex'] and v['point']==point)
        return next(v['identity'] for v in found['files'] if v['name']==key)
    if change=='nonempty':put('applied-end/plan.json',b'unexpected prefix')
    elif change=='image':values['applied-end/application.image']=later('APPLY_IMAGE_WRITTEN','applied-end/application.image')
    elif change=='ack':values['applied-end/ack.gsr']=later('APPLY_ACK_WRITTEN','applied-end/ack.gsr')
    elif change=='outside':put('grants.gsr',b'foreign journal')
    elif change=='selector':values['selector.gsr']=values['selector.pending.gsr']
    elif change=='member':del values[next(k for k in sorted(values) if k.startswith('generations/') and k.endswith('/generation.gsr'))]
    elif change=='plan':del values['applied-end/plan.json']
    elif change=='directory':values['applied-end']=dict(directory=True)
    elif change=='candidate':put('pending.accept.next',b'foreign candidate')
    elif change=='empty':put('pending.accept.next',model.EMPTY)
    elif change=='active':
        earlier=next(v for _,v in reversed(copies) if v['node']==value['node'] and v['eventIndex']<value['eventIndex'] and v['point']=='COVERED_VOTE_CANDIDATE_PARENT_FORCED')
        values['pending.accept']=next(v['identity'] for v in earlier['files'] if v['name']=='pending.accept')
    elif change=='leftover':values['pending.accept.next']=values['pending.accept']
    elif change=='ledger':put(model.LEDGERS[0],b'foreign retention')
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
    observed=root/'previous/previous/maintenance/prefixes/observed';expected=plans(observed);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-carried-completion-negative-') as temp:
            changed=Path(temp)/'completion';shutil.copytree(root/'completion',changed);mutate(changed,name)
            try:replay(observed,changed,expected)
            except ValueError as error:need(str(error)==reason,'carried completion unrelated negative: '+name+': '+str(error))
            else:raise ValueError('carried completion mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(case=name,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'carried completion qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='complete original vote/campaign/maintenance/resource/process chain; independent unchanged completion plan')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))

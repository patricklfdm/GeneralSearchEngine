"""Current-source native installation, recovery and preflight refusal evidence."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import learner_store_evidence as s
source,e,f,need=s.source,s.e,s.f,s.need
REFUSALS={'source':'learner retention directory/inventory','replica':'basis source inventory capacity'}


def refusal(value,mode):
    need(value==dict(status='REFUSED',type='IllegalArgumentException',reason=REFUSALS[mode]),
         'learner store review exact refusal')


def validate(root):
    root=Path(root);total=0
    need(root.is_dir() and not root.is_symlink(),'learner store review directory')
    for count,path in enumerate(root.rglob('*'),1):
        need(not path.is_symlink() and (path.is_file() or path.is_dir()),'learner store review regular evidence')
        if path.is_file():
            size=path.stat().st_size;need(size<=64*e.MIB,'learner store review member capacity');total+=size
        need(count<=65536 and total<=512*e.MIB,'learner store review evidence capacity')
    need({p.name for p in root.iterdir()}=={'source-history','original.gslp','admission-events.json','resume-events.json',
         'admitted','resumed','refused-source','refused-replica'},'learner store review inventory')
    history=root/'source-history';source.validate(history);original=source.c.inventory(history/'learner-source-copy')
    original_root=(history/'before-learner-source/node-1/root.gsr').read_bytes()
    request=e.parse((history/'learner-reserve-payload.bin').read_bytes())['request']
    learner=next(v for v in request['target'] if v['node']=='node-4');peer=next(v for v in request['target'] if v['node']=='node-1')
    raw=(root/'original.gslp').read_bytes();plan=s.p.plan(raw,original_root,original,request,learner,peer)
    retained=(root/'admitted/operation'/s.RETAIN).read_bytes();decision=s.retention(retained,raw,plan)
    operation={'operation.lock':b'','learner.gslp':raw,s.RETAIN:retained}
    replica={'replica.lock':b'','root.gsr':original_root,'node.gsr':f.encode('records','NODE',dict(root=request['root'],identity=learner)),s.ADMISSION:retained}
    for name in ('admitted','resumed'):s.state(root/name,operation,replica,original,decision,'retained')
    trace=list(s.p.CUTS)+['LEARNER_SOURCE_METADATA_RESERVED']
    for _ in sorted(n for n in original if n!='source.gscp' and not n.endswith('.image')):
        trace+=['LEARNER_SOURCE_MEMBER_CREATED','LEARNER_SOURCE_MEMBER_PREFIX_WRITTEN','LEARNER_SOURCE_MEMBER_WRITTEN','LEARNER_SOURCE_MEMBER_FORCED']
    trace+=['LEARNER_SOURCE_DIRECTORY_FORCED','LEARNER_ACTIVE_PLAN_FORCED','LEARNER_ACTIVE_PLAN_PARENT_FORCED','LEARNER_PLAN_BEFORE_RETURN',
            'LEARNER_RETENTION_CREATED','LEARNER_RETENTION_PREFIX_WRITTEN','LEARNER_RETENTION_WRITTEN','LEARNER_RETENTION_FORCED','LEARNER_RETENTION_PARENT_FORCED']
    trace+=s.resume_trace(None,'staging',True,replica)[3:]
    need(e.parse((root/'admission-events.json').read_bytes())==trace,'learner store review exact admission force trace')
    need(e.parse((root/'resume-events.json').read_bytes())==s.resume_trace(replica,'retained',False,replica),'learner store review exact resume force trace')
    for mode in REFUSALS:
        path=root/('refused-'+mode)
        need({p.name for p in path.iterdir()}=={'operation-before','operation-after','replica-before','replica-after','result.json'},'learner store review refusal inventory')
        op=dict(operation,**{'learner.next.gslp':raw,s.NEXT:retained})
        original_replica=dict(replica,learner=None,**{'learner/'+k:v for k,v in original.items()})
        original_replica[('learner/' if mode=='source' else '')+'foreign']=bytes((7,8,9))
        for side in ('before','after'):
            need(s.files(path/('operation-'+side))==op,'learner store review preserved operation originals')
            need(source.c.inventory(path/('replica-'+side))==original_replica,'learner store review preserved replica originals')
        # The original replica has all five allowed members, so its sixth foreign
        # member is rejected by the bounded inventory before name validation.
        refusal(e.parse((path/'result.json').read_bytes()),mode)
    return dict(status='PASS',scope='current-native-nonvoting-store',nativeHistories=1,exactPreservedRefusals=2,
                typedPreparationQualified=False,jointEligibilityQualified=False,phase3Complete=False)


NEGATIVES={
 'missing-source':'learner source exact original generation',
 'changed-received-image':'learner store exact source bytes',
 'false-local-identity':'learner store exact nonvoting replica bytes',
 'missing-admission-force':'learner store review exact admission force trace',
 'missing-resume-force':'learner store review exact resume force trace',
 'removed-redundant-decision':'learner store review preserved operation originals',
 'removed-foreign-member':'learner store review preserved replica originals',
 'false-refusal':'learner store review exact refusal',
}


def qualify(root):
    root=Path(root);original=validate(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-learner-review-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target)
            if name=='missing-source':(target/'source-history/learner-source-copy/generation.gsr').unlink()
            elif name=='changed-received-image':next((target/'resumed/source').glob('*.image')).write_bytes(b'bad')
            elif name=='false-local-identity':(target/'resumed/replica/node.gsr').write_bytes(b'bad')
            elif name in ('missing-admission-force','missing-resume-force'):
                path=target/('admission-events.json' if name=='missing-admission-force' else 'resume-events.json')
                rows=e.parse(path.read_bytes());rows.remove('LEARNER_ADMISSION_FORCED');path.write_bytes(f.canonical(rows))
            elif name=='removed-redundant-decision':(target/'refused-source/operation-after'/s.NEXT).unlink()
            elif name=='removed-foreign-member':(target/'refused-replica/replica-after/foreign').unlink()
            elif name=='false-refusal':
                path=target/'refused-source/result.json';v=e.parse(path.read_bytes());v['status']='PASS';path.write_bytes(f.canonical(v))
            else:raise ValueError('unknown learner store review mutation')
            try:validate(target)
            except ValueError as error:need(str(error)==reason,'learner store review unrelated negative: '+name+': '+str(error))
            else:raise ValueError('learner store review accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root)))

"""Original two-revision installation plus typed successor receipt/reopen.

The existing strict installation reader receives an exact projection with only
the five declared typed-extension members excluded. This reader validates every
excluded member; neither reader accepts missing original evidence.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import learner_successor_evidence as installed
from . import bootstrap_revalidation_evidence as images

t,e,f,c,d,need=installed.t,installed.e,installed.f,installed.c,installed.d,installed.need
EXTRA={'successor-typed','successor-typed-resumed','successor-typed-receipt.gsr',
       'successor-typed-events.json','successor-typed-resume-events.json'}


def check_trace(rows,resume=False):
    need(rows==t.trace(resume),'successor typed exact force order')


def typed(root):
    root=Path(root);source=c.inventory(root/'learner-refresh-copy')
    packet=installed.source_packet.decode(source['source.gscp'])
    catalog=f.decode(packet['objects'][packet['capsule']['catalog']],'records','CATALOG')
    operation=catalog['results'][0];request=operation['request']
    need(catalog['active']==1 and operation['phase']=='PREPARING' and operation['revision']==2
         and operation['receipt'] is None,'successor typed certified current revision')
    learner=next(v for v in request['target'] if v['node']=='node-4')
    receipt=f.encode('records','LEARNER',dict(root=request['root'],receipt=dict(root=request['root'],number=1,
        request=e.digest(f.canonical(request)),identity=learner,image=operation['prepared']['application'],prepared=operation['prepared'])))
    need((root/'successor-typed-receipt.gsr').read_bytes()==receipt,'successor typed exact current receipt')
    first=c.inventory(root/'successor-typed');second=c.inventory(root/'successor-typed-resumed')
    need(first==second,'successor typed exact reopened bytes')
    backup=images.image_members(source[operation['prepared']['application']+'.image'])
    need(set(first)=={'preparation.lock','preparation.json','learner.gsr','backup'}|{'backup/'+n for n in backup},'successor typed inventory')
    need(first['preparation.lock']==b'' and first['backup'] is None and first['learner.gsr']==receipt
         and all(first['backup/'+n]==v for n,v in backup.items()),'successor typed original backup and receipt')
    raw=first['preparation.json'];value=e.parse(raw);prior=e.parse((root/'typed/preparation.json').read_bytes())
    need(len(raw)<=16384 and raw==f.canonical(value)
         and set(value)=={'schema','plan','source','receipt','configuration','path','materialization','directoryKey'},'successor typed compact plan shape')
    need(value['schema']=='gse-v53-successor-typed/1.3' and value['plan']==prior['plan']
         and value['source']==e.digest(source['source.gscp']) and value['receipt']==e.digest(receipt)
         and value['configuration']==e.digest(f.canonical(prior['configuration'])),'successor typed compact plan originals')
    path=t.binding(value['path']);core=t.binding(value['materialization'])
    oldpath=t.binding(prior['path']);oldcore=t.binding(prior['materialization'])
    parent=e.parse((root/'successor/install.json').read_bytes())
    sourcepath=t.binding(parent['path']);staging=t.binding(parent['staging'])
    paths=[path,core,oldpath,sourcepath,staging]
    need(path==oldpath.parent/('.gse-v53-learner-ready-'+prior['plan']) and core==oldcore
         and value['materialization']==prior['materialization']
         and all(p!=q and p not in q.parents and q not in p.parents for i,p in enumerate(paths) for q in paths[i+1:]),'successor typed original paths')
    need(type(value['directoryKey']) is str and value['directoryKey'].strip() and len(value['directoryKey'].encode())<=4096,
         'successor typed directory identity')
    for resume,file in [(False,'successor-typed-events.json'),(True,'successor-typed-resume-events.json')]:
        check_trace(d.read(root/file),resume)
    return dict(revision=2,receipt=e.digest(receipt),source=e.digest(source['source.gscp']))


def validate(root):
    root=Path(root);need(root.is_dir() and not root.is_symlink(),'successor typed evidence directory');total=0
    for count,p in enumerate(root.rglob('*'),1):
        need(not p.is_symlink() and (p.is_file() or p.is_dir()),'successor typed regular evidence')
        if p.is_file():
            size=p.stat().st_size;need(size<=64*e.MIB,'successor typed file capacity');total+=size
        need(count<=65536 and total<=512*e.MIB,'successor typed evidence capacity')
    need(EXTRA<={p.name for p in root.iterdir()},'successor typed extension incomplete')
    with tempfile.TemporaryDirectory(prefix='v53-successor-original-') as temp:
        projection=Path(temp)/'original';projection.mkdir()
        for p in root.iterdir():
            if p.name in EXTRA:continue
            if p.is_dir():shutil.copytree(p,projection/p.name)
            else:shutil.copy2(p,projection/p.name)
        original=installed.validate(projection)
    result=typed(root)
    return dict(status='PASS',scope='native-typed-successor',original=original,typed=result,
                semanticReader='Java core',oldGenerationRetired=False,jointEligible=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES={'stale-receipt':'successor typed exact current receipt','reopened':'successor typed exact reopened bytes',
           'backup':'successor typed original backup and receipt','descriptor':'successor typed compact plan originals',
           'source':'successor typed compact plan originals','prepared':'successor typed inventory',
           'missing-force':'successor typed exact force order','early-receipt':'successor typed exact force order'}


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-successor-typed-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path)
            if name=='stale-receipt':(path/'successor-typed-receipt.gsr').write_bytes((path/'learner-receipt.gsr').read_bytes())
            elif name=='reopened':(path/'successor-typed-resumed/learner.gsr').write_bytes(b'bad')
            elif name in ('missing-force','early-receipt'):
                file=path/'successor-typed-events.json';rows=d.read(file)
                if name=='missing-force':rows.remove('LEARNER_TYPED_RECEIPT_FORCED')
                else:
                    rows.remove('LEARNER_TYPED_RECEIPT_CREATED');rows.insert(rows.index('LEARNER_TYPED_SEMANTICS_VERIFIED'),'LEARNER_TYPED_RECEIPT_CREATED')
                file.write_bytes(f.canonical(rows))
            else:
                for stage in ('successor-typed','successor-typed-resumed'):
                    target=path/stage
                    if name=='prepared':(target/'prepared.json').write_bytes(b'bad')
                    elif name=='backup':sorted((target/'backup').iterdir())[0].write_bytes(b'bad')
                    else:
                        file=target/'preparation.json';value=d.read(file);value['configuration' if name=='descriptor' else 'source']='0'*64;file.write_bytes(f.canonical(value))
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'successor typed unrelated negative: '+name+': '+str(error))
            else:raise ValueError('successor typed accepted negative: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root)))

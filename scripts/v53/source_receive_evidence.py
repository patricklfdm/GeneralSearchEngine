"""Original public bootstrap -> forced source -> exact scratch bytes; no remote authority."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import source_export_evidence as x

e=x.e
c=x.c


def validate(directory):
    root=Path(directory)
    e.need(root.is_dir() and not root.is_symlink(),'source receive directory')
    e.need({p.name for p in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'source receive inventory')
    rows=[]
    for size in (3,4,5):
        member=root/f'stable-{size}'
        rows.append(x.case(member,size,additional=('received',)))
        original=c.inventory(member/'captured/node-1')
        _,_,packet=c.current(original)
        # Original capture and all authority files were already reconstructed by x.case.
        # Scratch must be precisely that source's packet and declared application bytes.
        rows_in_journal=c.journal(original['grants.gsr'],packet['capsule']['root'],'node-1')
        prefix='sources/'+rows_in_journal[-1][2]['basisId']+'/'
        source={k.removeprefix(prefix):v for k,v in original.items() if k.startswith(prefix)}
        e.need(c.inventory(member/'received')==source,'source receive exact complete scratch')
    wanted=dict(schema='gse-v53-source-receive-v1',status='PASS',cases=rows,publicRuntime=False,network=False,scope='complete-source-scratch-only')
    e.need(e.f.canonical(x.load(root/'receipt.json'))==e.f.canonical(wanted),'source receive scope/receipt')
    return wanted


def qualify(directory):
    original=validate(directory);results=[]
    variants=[('scope','source receive scope/receipt'),('missing-profile','source receive inventory'),
              ('missing-packet','source receive exact complete scratch'),('changed-packet','source receive exact complete scratch'),
              ('missing-image','source receive exact complete scratch'),('changed-image','source receive exact complete scratch'),
              ('extra-file','source receive exact complete scratch'),('changed-authority','admitted exact after'),
              ('changed-source','source export exact complete bytes'),('changed-descriptor','source export exact descriptor inventory')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-receive-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(directory,target);member=target/'stable-3';received=member/'received'
            if name=='scope':
                value=x.load(target/'receipt.json');value['publicRuntime']=True;(target/'receipt.json').write_text(json.dumps(value))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name in ('missing-packet','changed-packet','missing-image','changed-image'):
                path=received/'source.gscp' if name.endswith('packet') else next(received.glob('*.image'))
                if name.startswith('missing'):path.unlink()
                else:path.write_bytes(b'changed')
            elif name=='extra-file':(received/'extra').write_bytes(b'extra')
            elif name=='changed-authority':(member/'after/node-2/allocator.gsr').write_bytes(b'changed')
            elif name=='changed-source':next((member/'exported').iterdir()).write_bytes(b'changed')
            else:
                path=member/'contents.json';value=x.load(path);value[0]['bytes']+=1;path.write_text(json.dumps(value))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'source receive unrelated negative: '+name+': '+str(error))
            else:raise ValueError('source receive accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))

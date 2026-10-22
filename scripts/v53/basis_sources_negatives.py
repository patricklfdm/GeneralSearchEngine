"""Original-first, reason-specific mutations of retained source and force evidence."""
import json
from pathlib import Path
import shutil
import tempfile
from . import basis_sources_evidence as e
from .membership_model import need

CASES=(('missing-source','missing or unbound original source'),('missing-image','retained source file inventory'),
       ('corrupt-image','retained image integrity'),('corrupt-packet','packet checksum'),
       ('replaced-original','packet original basis binding'),('extra-file','retained source file inventory'),
       ('unknown-source','missing or unbound original source'),('torn-journal','torn grant journal body'),
       ('missing-force','source force order'),('runtime-relabel','source runtime scope'),
       ('partial-return','grant process outcome'))


def mutate(root,name):
    if name in ('missing-force','runtime-relabel','partial-return'):
        if name=='missing-force':
            path=root/'first.stdout';rows=[json.loads(line) for line in path.read_text().splitlines()]
            path.write_bytes(b''.join(e.f.canonical(r)+b'\n' for r in rows if r.get('event')!='SOURCE_DIRECTORY_FORCED'))
        else:
            path=root/'case.json';row=json.loads(path.read_text())
            if name=='runtime-relabel':row['remoteOwnershipVerified']=True
            else:row['processes']['resume']['exitCode']=0
            path.write_bytes(e.f.canonical(row))
        return
    authority=root/'final';_,rows=e.state(authority,3)
    sources=[authority/'sources'/v['basisId'] for k,_,v in rows if k=='BASIS'];first=sources[0]
    image=next(first.glob('*.image'))
    if name=='missing-source':shutil.rmtree(first)
    elif name=='missing-image':image.unlink()
    elif name=='corrupt-image':
        raw=bytearray(image.read_bytes());raw[0]^=1;image.write_bytes(raw)
    elif name=='corrupt-packet':
        path=first/'source.gscp';raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
    elif name=='replaced-original':shutil.copyfile(sources[1]/'source.gscp',first/'source.gscp')
    elif name=='extra-file':(first/'extra').write_bytes(b'x')
    elif name=='unknown-source':(authority/'sources'/'unknown').mkdir()
    elif name=='torn-journal':
        path=authority/'grants.gsr';path.write_bytes(path.read_bytes()[:-1])
    else:raise ValueError('unknown retained source mutation')


def run(original):
    original=Path(original);e.validate(original);results=[]
    with tempfile.TemporaryDirectory(prefix='v53-source-negatives-') as temp:
        for name,reason in CASES:
            case=next(c for c in e.cases() if c['size']==3 and
                      (c['mode']=='halt' and c['cut']=='SOURCE_CREATED' if name=='partial-return' else c['mode']=='clean'))
            target=Path(temp)/name;shutil.copytree(original/case['name'],target);mutate(target,name)
            try:e.validate_case(target,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated source negative rejection: '+name+': '+str(error));results.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted retained source negative: '+name)
    return results

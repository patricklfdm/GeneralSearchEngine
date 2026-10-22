"""Original-first exact-reason negative replay for retained governing floors."""
import json
from pathlib import Path
import shutil
import tempfile
from . import floor_evidence as e
from .membership_model import need

CASES=(('copy-force','floor force order'),('authority-force','floor force order'),('force-order','floor force order'),
       ('peer-identity','floor force order'),('source-image','floor peer original generation'),('copy-image','floor exact physical snapshot'),
       ('floor','floor exact physical snapshot'),('original-journal','floor exact physical snapshot'),
       ('selector','floor exact physical snapshot'),('missing-copy','floor exact physical snapshot'),
       ('extra-file','floor exact physical snapshot'),('returned-digest','floor returned binding'),('deletion','floor returned binding'),
       ('scope','floor scope'))


def mutate(root,name):
    if name=='scope':
        path=root/'case.json';row=json.loads(path.read_text());row['historicalOwnershipVerified']=True;path.write_bytes(e.g.f.canonical(row));return
    if name in ('copy-force','authority-force','force-order','peer-identity','returned-digest','deletion'):
        path=root/'first.stdout';rows=[json.loads(line) for line in path.read_text().splitlines()]
        if name=='returned-digest':rows[-1]['floor']='00'*32
        elif name=='deletion':rows[-1]['deletion']=True
        elif name=='peer-identity':next(r for r in rows if r.get('node')=='node-2')['node']='node-1'
        elif name=='force-order':
            a=next(i for i,r in enumerate(rows) if r.get('event')=='FLOOR_COPIES_FORCED');b=next(i for i,r in enumerate(rows) if r.get('event')=='FLOOR_AUTHORITY_WRITTEN');rows[a],rows[b]=rows[b],rows[a]
        else:
            point='FLOOR_COPY_DIRECTORY_FORCED' if name=='copy-force' else 'FLOOR_AUTHORITY_FORCED';rows.pop(next(i for i,r in enumerate(rows) if r.get('event')==point))
        path.write_bytes(b''.join(e.g.f.canonical(row)+b'\n' for row in rows));return
    if name=='source-image':path=next((root/'inputs/node-2/generations/a').glob('*.image'));path.write_bytes(b'wrong');return
    original=root/'original'
    if name=='copy-image':next((original/'floor-copies').rglob('*.image')).write_bytes(b'wrong')
    elif name=='floor':(original/'floor-copies/floor.gsr').write_bytes(b'wrong')
    elif name=='original-journal':(original/'grants.gsr').write_bytes(b'')
    elif name=='selector':(original/'selector.gsr').unlink()
    elif name=='missing-copy':shutil.rmtree(next(p for p in (original/'floor-copies').iterdir() if p.is_dir()))
    elif name=='extra-file':(original/'floor-copies/extra').write_bytes(b'wrong')
    else:raise ValueError('unknown floor negative')


def run(original):
    original=Path(original);e.validate(original);results=[]
    case=next(c for c in e.cases() if c['size']==3 and c['through']==7 and c['mode']=='clean')
    with tempfile.TemporaryDirectory(prefix='v53-floor-negatives-') as temp:
        for name,reason in CASES:
            root=Path(temp)/name;shutil.copytree(original/case['name'],root);mutate(root,name)
            try:e.validate_case(root,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated floor negative: '+name+': '+str(error));results.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted floor negative: '+name)
    return results

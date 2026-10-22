"""Original-first, exact-reason evidence rejection for governing retirement."""
import json
from pathlib import Path
import shutil
import tempfile
from . import retirement_evidence as e
from .membership_model import need

CASES=(('saved-force','retirement force order'),('authority-force','retirement force order'),
       ('force-delete-order','retirement force order'),('missing-delete','retirement force order'),
       ('original-image','retirement original generation inventory'),('peer-image','retirement original generation inventory'),
       ('active-image','retirement initial physical authority'),('floor-copy','retirement initial physical authority'),
       ('remaining-old','retirement exact physical snapshot'),('lost-active','retirement exact physical snapshot'),
       ('lost-floor','retirement exact physical snapshot'),('lost-source','retirement exact physical snapshot'),
       ('changed-journal','retirement exact physical snapshot'),('changed-selector','retirement exact physical snapshot'),
       ('retirement-not-cleared','retirement exact physical snapshot'),('returned-authority','retirement returned binding'),
       ('network-ack','retirement returned binding'),('scope','retirement scope'))


def mutate(root,name):
    if name=='scope':
        path=root/'case.json';row=json.loads(path.read_text());row['historicalOwnershipVerified']=True;path.write_bytes(e.g.f.canonical(row));return
    if name in ('saved-force','authority-force','force-delete-order','missing-delete','returned-authority','network-ack'):
        path=root/'first.stdout';rows=[json.loads(line) for line in path.read_text().splitlines()]
        if name=='returned-authority':rows[-1]['retirement']='00'*32
        elif name=='network-ack':rows[-1]['networkAck']=True
        elif name=='force-delete-order':
            a=next(i for i,r in enumerate(rows) if r.get('event')=='RETIREMENT_AUTHORITY_FORCED')
            b=next(i for i,r in enumerate(rows) if r.get('event')=='RETIREMENT_FILE_DELETED');rows[a],rows[b]=rows[b],rows[a]
        else:
            point={'saved-force':'RETIREMENT_SOURCE_FORCED','authority-force':'RETIREMENT_AUTHORITY_FORCED','missing-delete':'RETIREMENT_FILE_DELETED'}[name]
            rows.pop(next(i for i,r in enumerate(rows) if r.get('event')==point))
        path.write_bytes(b''.join(e.g.f.canonical(row)+b'\n' for row in rows));return
    if name in ('original-image','peer-image','active-image','floor-copy'):
        path={'original-image':root/'initial/generations/a','peer-image':root/'inputs/node-2/generations/a',
              'active-image':root/'initial/generations/b','floor-copy':root/'initial/floor-copies'}[name]
        next(path.rglob('*.image')).write_bytes(b'wrong');return
    original=root/'original'
    if name=='remaining-old':shutil.copytree(root/'initial/generations/a',original/'generations/a')
    elif name=='lost-active':shutil.rmtree(original/'generations/b')
    elif name=='lost-floor':shutil.rmtree(original/'floor-copies')
    elif name=='lost-source':shutil.rmtree(original/'sources')
    elif name=='changed-journal':(original/'grants.gsr').write_bytes(b'')
    elif name=='changed-selector':(original/'selector.gsr').write_bytes(b'wrong')
    elif name=='retirement-not-cleared':(original/'retirement').mkdir()
    else:raise ValueError('unknown retirement negative')


def run(original):
    original=Path(original);e.validate(original);results=[]
    case=next(c for c in e.cases() if c['size']==3 and c['through']==7 and c['mode']=='clean')
    with tempfile.TemporaryDirectory(prefix='v53-retirement-negatives-') as temp:
        for name,reason in CASES:
            root=Path(temp)/name;shutil.copytree(original/case['name'],root);mutate(root,name)
            try:e.validate_case(root,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated retirement negative: '+name+': '+str(error));results.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted retirement negative: '+name)
    return results

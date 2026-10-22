"""Original-first exact-reason rejection of altered floor-release evidence."""
import json
from pathlib import Path
import shutil
import tempfile
from . import floor_release_evidence as e
from .membership_model import need

CASES=(('missing-force','floor release force order'),('early-delete','floor release force order'),
       ('missing-parent-force','floor release force order'),('keep-floor','retirement exact physical snapshot'),
       ('keep-authority','retirement exact physical snapshot'),('lost-source','retirement exact physical snapshot'),
       ('lost-current','retirement exact physical snapshot'),('changed-journal','retirement exact physical snapshot'),
       ('changed-selector','retirement exact physical snapshot'),('returned-floor','floor release returned binding'),
       ('returned-journal','floor release returned binding'),('returned-selector','floor release returned binding'),
       ('network-ack','floor release returned binding'),('scope','floor release scope'))


def mutate(root,name):
    if name=='scope':
        path=root/'case.json';row=json.loads(path.read_text());row['historicalOwnershipVerified']=True;path.write_bytes(e.g.f.canonical(row));return
    if name in ('missing-force','early-delete','missing-parent-force','returned-floor','returned-journal','returned-selector','network-ack'):
        path=root/'first.stdout';rows=[json.loads(line) for line in path.read_text().splitlines()]
        if name.startswith('returned-'):rows[-1][name.removeprefix('returned-')]='00'*32
        elif name=='network-ack':rows[-1]['networkAck']=True
        elif name=='early-delete':
            a=next(i for i,r in enumerate(rows) if r.get('event')=='FLOOR_RELEASE_AUTHORITY_FORCED')
            b=next(i for i,r in enumerate(rows) if r.get('event')=='FLOOR_RELEASE_RELINQUISHED');rows[a],rows[b]=rows[b],rows[a]
        else:
            point='FLOOR_RELEASE_AUTHORITY_FORCED' if name=='missing-force' else 'FLOOR_RELEASE_PARENT_FORCED';rows.pop(next(i for i,r in enumerate(rows) if r.get('event')==point))
        path.write_bytes(b''.join(e.g.f.canonical(row)+b'\n' for row in rows));return
    original=root/'original'
    if name=='keep-floor':shutil.copytree(root/'initial/floor-copies',original/'floor-copies')
    elif name=='keep-authority':
        (original/'floor-copies').mkdir();(original/e.RELEASE).write_bytes(b'leftover')
    elif name=='lost-source':next((original/'sources').rglob('*.image')).unlink()
    elif name=='lost-current':(original/'generations/b/generation.gsr').unlink()
    elif name=='changed-journal':(original/'grants.gsr').write_bytes(b'wrong')
    elif name=='changed-selector':(original/'selector.gsr').write_bytes(b'wrong')
    else:raise ValueError('unknown floor release negative')


def run(original):
    original=Path(original);e.validate(original);results=[]
    case=next(c for c in e.cases() if c['size']==3 and c['through']==7 and c['mode']=='clean')
    with tempfile.TemporaryDirectory(prefix='v53-floor-release-negatives-') as temp:
        for name,reason in CASES:
            root=Path(temp)/name;shutil.copytree(original/case['name'],root);mutate(root,name)
            try:e.validate_case(root,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated floor release negative: '+name+': '+str(error));results.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted floor release negative: '+name)
    return results

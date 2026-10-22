"""Original-first exact-reason rejection of altered source-release evidence."""
import json
from pathlib import Path
import shutil
import tempfile
from . import captured_source_release_evidence as e
from .membership_model import need

CASES=(('missing-force','source release force order'),('early-delete','source release force order'),
       ('missing-parent-force','source release force order'),('keep-source','retirement exact physical snapshot'),
       ('keep-authority','retirement exact physical snapshot'),
       ('lost-current','retirement exact physical snapshot'),('changed-journal','retirement exact physical snapshot'),('lost-floor','retirement exact physical snapshot'),
       ('changed-selector','retirement exact physical snapshot'),('returned-floor','source release returned binding'),
       ('returned-journal','source release returned binding'),('returned-selector','source release returned binding'),
       ('network-ack','source release returned binding'),('scope','source release scope'))


def mutate(root,name):
    if name=='scope':
        path=root/'case.json';row=json.loads(path.read_text());row['historicalOwnershipVerified']=True;path.write_bytes(e.g.f.canonical(row));return
    if name in ('missing-force','early-delete','missing-parent-force','returned-floor','returned-journal','returned-selector','network-ack'):
        path=root/'first.stdout';rows=[json.loads(line) for line in path.read_text().splitlines()]
        if name.startswith('returned-'):rows[-1][name.removeprefix('returned-')]='00'*32
        elif name=='network-ack':rows[-1]['networkAck']=True
        elif name=='early-delete':
            a=next(i for i,r in enumerate(rows) if r.get('event')=='SOURCE_RETIREMENT_FORCED')
            b=next(i for i,r in enumerate(rows) if r.get('event')=='SOURCE_RETIREMENT_FILE_DELETED');rows[a],rows[b]=rows[b],rows[a]
        else:
            point='SOURCE_RETIREMENT_FORCED' if name=='missing-force' else 'SOURCE_RETIREMENT_PARENT_FORCED';rows.pop(next(i for i,r in enumerate(rows) if r.get('event')==point))
        path.write_bytes(b''.join(e.g.f.canonical(row)+b'\n' for row in rows));return
    original=root/'original'
    if name=='keep-source':
        id=json.loads((root/'fixture.json').read_text())['basisId'];shutil.copytree(root/'initial/sources'/id,original/'sources'/id)
    elif name=='keep-authority':
        (original/e.e.AUTHORITY).write_bytes(b'leftover')
    elif name=='lost-current':(original/'generations/b/generation.gsr').unlink()
    elif name=='lost-floor':(original/'floor-copies/floor.gsr').unlink()
    elif name=='changed-journal':(original/'grants.gsr').write_bytes(b'wrong')
    elif name=='changed-selector':(original/'selector.gsr').write_bytes(b'wrong')
    else:raise ValueError('unknown source release negative')


def run(original):
    original=Path(original);e.validate(original);results=[]
    case=next(c for c in e.cases() if c['size']==3 and c['through']==7 and c['tail'] is True and c['mode']=='clean')
    with tempfile.TemporaryDirectory(prefix='v53-captured-source-release-negatives-') as temp:
        for name,reason in CASES:
            root=Path(temp)/name;shutil.copytree(original/case['name'],root);mutate(root,name)
            try:e.validate_case(root,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated source release negative: '+name+': '+str(error));results.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted source release negative: '+name)
    return results

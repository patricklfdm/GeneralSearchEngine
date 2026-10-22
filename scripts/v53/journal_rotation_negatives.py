"""Original-first exact negative replay for grant-journal rotation."""
import json
from pathlib import Path
import shutil
import tempfile
from . import journal_rotation_evidence as e
from .membership_model import need

CASES=(('missing-force','rotation force order'),('early-rename','rotation force order'),
       ('missing-parent-force','rotation force order'),('initial-highest','rotation initial journal'),
       ('lost-current-promise','retirement exact physical snapshot'),('lost-basis','retirement exact physical snapshot'),
       ('lost-selection','retirement exact physical snapshot'),('lost-highest','retirement exact physical snapshot'),
       ('source','retirement exact physical snapshot'),('floor','retirement exact physical snapshot'),
       ('selector','retirement exact physical snapshot'),('pending','retirement exact physical snapshot'),
       ('returned-highest','rotation returned binding'),('network-ack','rotation returned binding'),('scope','rotation scope'))


def mutate(root,name):
    if name=='scope':
        path=root/'case.json';row=json.loads(path.read_text());row['historicalOwnershipVerified']=True;path.write_bytes(e.g.f.canonical(row));return
    if name in ('missing-force','early-rename','missing-parent-force','returned-highest','network-ack'):
        path=root/'first.stdout';rows=[json.loads(line) for line in path.read_text().splitlines()]
        if name=='returned-highest':rows[-1]['promise']='00'*32
        elif name=='network-ack':rows[-1]['networkAck']=True
        elif name=='early-rename':
            a=next(i for i,r in enumerate(rows) if r.get('event')=='JOURNAL_ROTATION_FORCED')
            b=next(i for i,r in enumerate(rows) if r.get('event')=='JOURNAL_ROTATION_RENAMED');rows[a],rows[b]=rows[b],rows[a]
        else:
            point='JOURNAL_ROTATION_FORCED' if name=='missing-force' else 'JOURNAL_ROTATION_PARENT_FORCED';rows.pop(next(i for i,r in enumerate(rows) if r.get('event')==point))
        path.write_bytes(b''.join(e.g.f.canonical(row)+b'\n' for row in rows));return
    if name in ('initial-highest','lost-current-promise','lost-basis','lost-selection','lost-highest'):
        path=root/('initial' if name=='initial-highest' else 'original')/'grants.gsr'
        rows=e.g.journal(path.read_bytes(),e.g.read(root/'initial/root.gsr',16384)[16:48].hex(),'node-1')
        index={'initial-highest':len(rows)-1,'lost-current-promise':1,'lost-basis':2,'lost-selection':3,'lost-highest':len(rows)-1}[name]
        path.write_bytes(b''.join(row[1] for i,row in enumerate(rows) if i!=index));return
    original=root/'original'
    if name=='source':next((original/'sources').rglob('*.image')).write_bytes(b'wrong')
    elif name=='floor':(original/'floor-copies/floor.gsr').unlink()
    elif name=='selector':(original/'selector.gsr').write_bytes(b'wrong')
    elif name=='pending':(original/e.PENDING).write_bytes(b'')
    else:raise ValueError('unknown rotation negative')


def run(original):
    original=Path(original);e.validate(original);results=[]
    case=next(c for c in e.cases() if c['size']==3 and c['through']==7 and c['mode']=='clean')
    with tempfile.TemporaryDirectory(prefix='v53-rotation-negatives-') as temp:
        for name,reason in CASES:
            root=Path(temp)/name;shutil.copytree(original/case['name'],root);mutate(root,name)
            try:e.validate_case(root,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated rotation negative: '+name+': '+str(error));results.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted rotation negative: '+name)
    return results

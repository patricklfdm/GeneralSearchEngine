"""Original-first, exact-reason evidence negatives for the capture transaction."""
import json
from pathlib import Path
import shutil
import tempfile
from . import capture_recovery_evidence as e
from .membership_model import need

CASES=(('missing-force','capture force order'),('early-basis','capture force order'),('missing-parent-force','capture force order'),
       ('returned-basis','capture returned binding'),('returned-tail','capture returned binding'),('network-ack','capture returned binding'),
       ('scope','capture scope'),('missing-process','capture process inventory'),('extra-file','capture case inventory'),
       ('crash-prefix','capture exact crash snapshot'),('crash-current','capture exact crash snapshot'),('missing-intent','capture exact crash snapshot'),
       ('early-basis-bytes','capture exact crash snapshot'),('lost-source','capture exact crash snapshot'))


def selected(name):
    return next(c for c in e.cases() if c['size']==3 and (c['through']==0 and c['tail'] is True and c['mode']=='clean' if not (name.startswith('crash-') or name in ('missing-intent','early-basis-bytes','lost-source')) else c['mode']=='halt' and c['cut']=='SOURCE_PACKET_PREFIX_WRITTEN'))


def mutate(root,name):
    if name in ('scope','missing-process'):
        path=root/'case.json';value=json.loads(path.read_text())
        if name=='scope':value['historicalOwnershipVerified']=True
        else:del value['processes']['inspect']
        path.write_bytes(e.f.canonical(value));return
    if name=='extra-file':(root/'unlisted').write_bytes(b'1');return
    if name in ('missing-force','early-basis','missing-parent-force','returned-basis','returned-tail','network-ack'):
        path=root/'first.stdout';rows=[json.loads(line) for line in path.read_text().splitlines()]
        if name.startswith('returned-'):rows[-1][name.removeprefix('returned-').replace('tail','accepted')]='00'*32
        elif name=='network-ack':rows[-1]['networkAck']=True
        elif name=='early-basis':
            a=next(i for i,r in enumerate(rows) if r.get('event')=='SOURCE_DIRECTORY_FORCED');b=next(i for i,r in enumerate(rows) if r.get('event')=='BASIS_BEFORE_WRITE');rows[a],rows[b]=rows[b],rows[a]
        else:
            point='SOURCE_PACKET_FORCED' if name=='missing-force' else 'CAPTURE_INTENT_PARENT_FORCED';rows.pop(next(i for i,r in enumerate(rows) if r.get('event')==point))
        path.write_bytes(b''.join(e.f.canonical(r)+b'\n' for r in rows));return
    crash=root/'crash';source=next((crash/'sources').iterdir())
    if name=='missing-intent':(crash/e.AUTHORITY).unlink()
    elif name=='early-basis-bytes':shutil.copyfile(root/'final/grants.gsr',crash/'grants.gsr')
    elif name=='lost-source':(source/'source.gscp').unlink()
    else:
        path=source/'source.gscp' if name=='crash-prefix' else crash/'generations/a/source.gscp';raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)


def run(original):
    original=Path(original);e.validate(original);result=[]
    with tempfile.TemporaryDirectory(prefix='v53-capture-negatives-') as temp:
        for name,reason in CASES:
            case=selected(name);root=Path(temp)/name;shutil.copytree(original/case['name'],root);mutate(root,name)
            try:e.validate_case(root,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated capture negative: '+name+': '+str(error));result.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted capture negative: '+name)
    return result

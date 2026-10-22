"""Original-first negatives. Reject only for each declared independent failure."""
import json
from pathlib import Path
import shutil
import tempfile
from . import generation_install_evidence as e
from .membership_model import need

CASES=(('receipt','install returned binding'),('network-ack','install returned binding'),
       ('missing-force','install force order'),('runtime-relabel','install runtime scope'),
       ('old-generation','install physical snapshot'),('selector','install physical snapshot'),
       ('tail','install physical snapshot'),('source','install physical snapshot'),
       ('original-reference','install original selection references'),('missing-input','install input inventory'),
       ('duplicate-write','install duplicate wrote'),('capture','install next returned binding'))


def mutate(root,name):
    if name=='runtime-relabel':
        path=root/'case.json';value=json.loads(path.read_text());value['remoteOwnershipVerified']=True;path.write_bytes(e.g.f.canonical(value));return
    if name in ('receipt','network-ack','missing-force','duplicate-write','capture'):
        path=root/('duplicate.stdout' if name=='duplicate-write' else 'next.stdout' if name=='capture' else 'first.stdout')
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        if name=='receipt':rows[-1]['manifest']='00'*32
        elif name=='network-ack':rows[-1]['networkAck']=True
        elif name=='missing-force':rows=[r for r in rows if r.get('event')!='INSTALL_PARENT_FORCED']
        elif name=='duplicate-write':rows.insert(0,dict(event='INSTALL_RESERVED'))
        else:rows[-1]['basis']='00'*32
        path.write_bytes(b''.join(e.g.f.canonical(row)+b'\n' for row in rows));return
    if name=='original-reference':
        path=root/'inputs/node-2.basis';value=e.g.f.decode(path.read_bytes(),'records','BASIS');value['basisId']='00000000-0000-0000-0000-000000000099'
        path.write_bytes(e.g.f.encode('records','BASIS',value));return
    if name=='missing-input':next((root/'inputs').glob('*.image')).unlink();return
    if name=='old-generation':shutil.rmtree(root/'original/generations/a');return
    if name=='selector':
        (root/'original/selector.gsr').write_bytes((root/'initial/selector.gsr').read_bytes());return
    if name=='tail':(root/'original/generations/b/owned-tail.gsr').unlink();return
    if name=='source':
        path=root/'original/generations/b/source.gscp';data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data);return
    raise ValueError('unknown install mutation')


def run(original):
    original=Path(original);e.validate(original);results=[]
    case=next(c for c in e.cases() if c['size']==3 and c['tail'] and c['mode']=='clean')
    with tempfile.TemporaryDirectory(prefix='v53-install-negatives-') as temp:
        for name,reason in CASES:
            path=Path(temp)/name;shutil.copytree(original/case['name'],path);mutate(path,name)
            try:e.validate_case(path,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated install negative: '+name+': '+str(error));results.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted install negative: '+name)
    return results

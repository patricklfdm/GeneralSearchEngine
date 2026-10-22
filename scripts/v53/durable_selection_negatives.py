"""Original-first, exact-reason negatives for the local durable selection gate."""
import json
from pathlib import Path
import shutil
import tempfile
from . import durable_selection_evidence as e
from .membership_model import need

CASES=(('returned-digest','selection returned binding'),('installation-ack','selection returned binding'),
       ('missing-force','selection force order'),('runtime-relabel','selection runtime scope'),
       ('choice','selection recovered choice'),('local-basis','selection original local basis'),
       ('quorum','selection eligible quorum'),('duplicate','duplicate persisted selection'),
       ('remote-reference','selection source references'),('missing-image','selection input inventory'),
       ('conflict-reason','selection conflict refusal'))


def mutate(root,name):
    if name=='runtime-relabel':
        path=root/'case.json';value=json.loads(path.read_text());value['installationAck']=True;path.write_bytes(e.g.f.canonical(value));return
    if name in ('returned-digest','installation-ack','missing-force','conflict-reason'):
        path=root/('conflict.stdout' if name=='conflict-reason' else 'first.stdout');rows=[json.loads(line) for line in path.read_text().splitlines()]
        if name=='returned-digest':rows[-1]['selection']='00'*32
        elif name=='installation-ack':rows[-1]['installationAck']=True
        elif name=='conflict-reason':rows[-1]['reason']='unrelated'
        else:rows=[row for row in rows if row.get('event')!='SELECTED_FORCED']
        path.write_bytes(b''.join(e.g.f.canonical(row)+b'\n' for row in rows));return
    if name=='remote-reference':
        path=root/'inputs/c20-node-2.basis';value=e.g.f.decode(path.read_bytes(),'records','BASIS');value['basisId']='00000000-0000-0000-0000-000000000099'
        path.write_bytes(e.g.f.encode('records','BASIS',value));return
    if name=='missing-image':next((root/'inputs').glob('*.image')).unlink();return
    path=root/'original/grants.gsr';raw=path.read_bytes();offset=0
    while offset<len(raw):
        size=48+int.from_bytes(raw[offset+12:offset+16],'big')
        if int.from_bytes(raw[offset+8:offset+10],'big')==5:break
        offset+=size
    body=e.g.f.decode(raw[offset:],'records','SELECTED')
    if name=='choice':body['nextEntry']='00'*32
    elif name=='local-basis':body['sources'][0]['basisDigest']='00'*32
    elif name=='quorum':body['sources'][1]['voter']='node-9'
    elif name!='duplicate':raise ValueError('unknown selection mutation')
    changed=e.g.f.encode('records','SELECTED',body);path.write_bytes(raw[:offset]+changed+(changed if name=='duplicate' else b''))


def run(original):
    original=Path(original);e.validate(original);results=[]
    case=next(c for c in e.cases() if c['size']==3 and c['tail'] and c['mode']=='clean')
    with tempfile.TemporaryDirectory(prefix='v53-selection-negatives-') as temp:
        for name,reason in CASES:
            path=Path(temp)/name;shutil.copytree(original/case['name'],path);mutate(path,name)
            try:e.validate_case(path,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated selection negative: '+name+': '+str(error));results.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted selection negative: '+name)
    return results

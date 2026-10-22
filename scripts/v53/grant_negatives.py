"""Original-first, exact-reason grant metadata evidence mutations."""
import json
from pathlib import Path
import shutil
import tempfile
from . import grant_evidence as e
from . import format_fixture as f
from .membership_model import need

CASES=(('basis-id','clean','none','grant basis binding'),
       ('promise-order','clean','none','non-increasing grant promise'),
       ('foreign-owner','clean','none','grant basis owner'),
       ('source-digest','clean','none','packet original basis binding'),
       ('missing-force','clean','none','grant return before complete forces'),
       ('wrong-cut','kill','PROMISE_FORCED','grant crash cut mismatch'),
       ('incomplete-resampled','halt','PROMISE_FORCED','grant process outcome'),
       ('runtime-relabel','clean','none','grant runtime scope'))


def mutate(root,name):
    if name in ('basis-id','promise-order','foreign-owner','source-digest'):
        path=root/'final/grants.gsr';raw=path.read_bytes();rows=[];at=0
        while at<len(raw):
            length=48+int.from_bytes(raw[at+12:at+16],'big');kind='PROMISE' if int.from_bytes(raw[at+8:at+10],'big')==3 else 'BASIS'
            rows.append((kind,f.decode(raw[at:at+length],'records',kind)));at+=length
        if name=='basis-id':rows[1][1]['basisId']='00000000-0000-0000-0000-000000000009'
        elif name=='promise-order':rows[2][1]['ballot']['counter']=20
        elif name=='foreign-owner':rows[1][1]['voter']='node-2'
        else:rows[1][1]['inventory']='00'*32
        path.write_bytes(b''.join(f.encode('records',kind,value) for kind,value in rows))
    elif name in ('missing-force','wrong-cut'):
        path=root/('first.stdout' if name=='missing-force' else 'fault.stdout');rows=[json.loads(line) for line in path.read_text().splitlines()]
        if name=='missing-force':rows=[r for r in rows if r.get('event')!='BASIS_FORCED']
        else:rows[0]['event']='BASIS_BEFORE_WRITE'
        path.write_bytes(b''.join(f.canonical(row)+b'\n' for row in rows))
    else:
        path=root/'case.json';row=json.loads(path.read_text())
        if name=='incomplete-resampled':row['processes']['resume']['exitCode']=0
        elif name=='runtime-relabel':row['runtimeEnabled']=True
        else:raise ValueError('unknown grant mutation')
        path.write_bytes(f.canonical(row))


def run(original):
    original=Path(original);e.validate(original);results=[]
    with tempfile.TemporaryDirectory(prefix='v53-grant-negatives-') as temp:
        for name,mode,cut,reason in CASES:
            case=next(c for c in e.cases() if c['size']==3 and c['mode']==mode and c['cut']==cut)
            target=Path(temp)/name;shutil.copytree(original/case['name'],target);mutate(target,name)
            try:e.validate_case(target,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated grant negative rejection: '+name+': '+str(error));results.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted grant negative: '+name)
    return results

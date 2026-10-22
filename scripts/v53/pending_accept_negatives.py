"""Validate original evidence first, then reject one exact force/byte/return mutation."""
import json
from pathlib import Path
import shutil
import tempfile
from . import pending_accept_evidence as e
from .membership_model import need

CASES=(('candidate-force','pending acceptance force order'),('candidate-parent','pending acceptance force order'),
       ('rename','pending acceptance force order'),('parent-force','pending acceptance force order'),
       ('early-return','pending process return'),('wrong-owned','pending returned original binding'),
       ('crash-prefix','pending exact crash snapshot'),('recovery-force','pending repeated recovery force order'),
       ('active-vote','pending exact final capture'),('extra-file','pending case inventory'),
       ('public-claim','pending evidence scope'),('wrong-exit','pending process outcome'))


def selected(name):
    if name=='crash-prefix':return next(c for c in e.cases() if c['mode']=='halt' and c['cut']=='ACCEPT_PREFIX_WRITTEN')
    if name=='recovery-force':return next(c for c in e.cases() if c['mode']=='repeat-halt' and c['cut']=='ACCEPT_CANDIDATE_FORCED')
    return e.cases()[0]


def mutate(root,name):
    if name in ('crash-prefix','active-vote'):
        path=root/('crash' if name=='crash-prefix' else 'final')/(e.NEXT if name=='crash-prefix' else e.ACTIVE)
        raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
    elif name=='extra-file':(root/'unlisted').write_text('x')
    elif name in ('public-claim','wrong-exit'):
        path=root/'case.json';value=json.loads(path.read_text())
        if name=='public-claim':value['runtimeEnabled']=True
        else:value['processes']['first']['exitCode']=1
        path.write_text(json.dumps(value))
    else:
        path=root/('recovery-fault.stdout' if name=='recovery-force' else 'first.stdout');rows=[json.loads(line) for line in path.read_text().splitlines()]
        points={'candidate-force':'ACCEPT_CANDIDATE_FORCED','candidate-parent':'ACCEPT_CANDIDATE_PARENT_FORCED','rename':'ACCEPT_RENAMED',
                'parent-force':'ACCEPT_PARENT_FORCED','recovery-force':'ACCEPT_CANDIDATE_FORCED'}
        if name in points:rows=[v for v in rows if v.get('event')!=points[name]]
        elif name=='early-return':rows.insert(0,dict(rows[-1]))
        elif name=='wrong-owned':rows[-1]['accepted']='f'*64
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))


def run(original):
    original=Path(original);e.validate(original);result=[]
    with tempfile.TemporaryDirectory(prefix='v53-pending-negatives-') as temp:
        for name,reason in CASES:
            case=selected(name);root=Path(temp)/name;shutil.copytree(original/case['name'],root);mutate(root,name)
            try:e.validate_case(root,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated pending negative: '+name+': '+str(error));result.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted pending negative: '+name)
    return result

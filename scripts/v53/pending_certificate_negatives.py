"""Original-first mutations for exact two-phase quorum and local certificate force."""
import json
from pathlib import Path
import shutil
import tempfile
from . import pending_certificate_evidence as e
from .membership_model import need

CASES=(('candidate-force','certificate force order'),('candidate-parent','certificate force order'),('rename','certificate force order'),
       ('parent-force','certificate force order'),('wrong-certificate','certificate returned original binding'),
       ('peer-accept-force','certificate actual ACCEPT force/return order'),('peer-proof-force','certificate actual PROOF force/return order'),
       ('peer-accept','proof actual ACCEPT files'),('peer-proof','certificate actual PROOF files'),
       ('crash-prefix','certificate exact crash snapshot'),('recovery-force','certificate recovery order'),
       ('active-certificate','certificate exact final source'),('extra-file','certificate case inventory'),('public-claim','certificate evidence scope'))

def selected(name):
    if name=='crash-prefix':return next(c for c in e.cases() if c['mode']=='halt' and c['cut']=='CERTIFICATE_PREFIX_WRITTEN')
    if name=='recovery-force':return next(c for c in e.cases() if c['mode']=='repeat-halt' and c['cut']=='CERTIFICATE_CANDIDATE_FORCED')
    return e.cases()[0]

def mutate(root,name):
    locations={'crash-prefix':'crash/node-1/'+e.NEXT,'active-certificate':'final/node-1/'+e.ACTIVE,'peer-accept':'accepted/node-2/'+e.ACTIVE,'peer-proof':'proven/node-2/'+e.ACTIVE}
    if name in locations:
        path=root/locations[name];raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
    elif name=='extra-file':(root/'unlisted').write_text('x')
    elif name=='public-claim':
        path=root/'case.json';value=json.loads(path.read_text());value['runtimeEnabled']=True;path.write_text(json.dumps(value))
    else:
        filename={'recovery-force':'recovery-fault.stdout','peer-accept-force':'accept-all.stdout','peer-proof-force':'prove-all.stdout'}.get(name,'first.stdout')
        path=root/filename;rows=[json.loads(line) for line in path.read_text().splitlines()]
        point={'candidate-force':'CERTIFICATE_CANDIDATE_FORCED','candidate-parent':'CERTIFICATE_CANDIDATE_PARENT_FORCED','rename':'CERTIFICATE_RENAMED',
               'parent-force':'CERTIFICATE_PARENT_FORCED','peer-accept-force':'ACCEPT_CANDIDATE_FORCED','peer-proof-force':'PROOF_CANDIDATE_FORCED','recovery-force':'CERTIFICATE_CANDIDATE_FORCED'}.get(name)
        if point:rows=[v for v in rows if v.get('event')!=point]
        else:rows[-1]['certificate']='f'*64
        path.write_text(''.join(json.dumps(v)+'\n' for v in rows))

def run(original):
    original=Path(original);e.validate(original);result=[]
    with tempfile.TemporaryDirectory(prefix='v53-certificate-negatives-') as temp:
        for name,reason in CASES:
            case=selected(name);root=Path(temp)/name;shutil.copytree(original/case['name'],root);mutate(root,name)
            try:e.validate_case(root,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated certificate negative: '+name+': '+str(error));result.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted certificate negative: '+name)
    return result

"""Original-first exact mutations include physical peer ACCEPTs and both force chains."""
import json
from pathlib import Path
import shutil
import tempfile
from . import pending_proof_evidence as e
from .membership_model import need

CASES=(('candidate-force','proof force order'),('candidate-parent','proof force order'),('rename','proof force order'),
       ('parent-force','proof force order'),('wrong-proof','proof returned original binding'),('peer-force','proof actual ACCEPT force/return order'),
       ('peer-vote','proof actual ACCEPT files'),('crash-prefix','proof exact crash snapshot'),('recovery-force','proof recovery order'),
       ('active-proof','proof exact final source'),('extra-file','proof case inventory'),('public-claim','proof evidence scope'))

def selected(name):
    if name=='crash-prefix':return next(c for c in e.cases() if c['mode']=='halt' and c['cut']=='PROOF_PREFIX_WRITTEN')
    if name=='recovery-force':return next(c for c in e.cases() if c['mode']=='repeat-halt' and c['cut']=='PROOF_CANDIDATE_FORCED')
    return e.cases()[0]

def mutate(root,name):
    if name in ('crash-prefix','active-proof','peer-vote'):
        path=root/('crash/node-1/'+e.NEXT if name=='crash-prefix' else 'accepted/node-2/'+e.ACTIVE if name=='peer-vote' else 'final/node-1/'+e.ACTIVE)
        raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
    elif name=='extra-file':(root/'unlisted').write_text('x')
    elif name=='public-claim':
        path=root/'case.json';value=json.loads(path.read_text());value['runtimeEnabled']=True;path.write_text(json.dumps(value))
    else:
        path=root/('recovery-fault.stdout' if name=='recovery-force' else 'accept-all.stdout' if name=='peer-force' else 'first.stdout')
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        point={'candidate-force':'PROOF_CANDIDATE_FORCED','candidate-parent':'PROOF_CANDIDATE_PARENT_FORCED','rename':'PROOF_RENAMED',
               'parent-force':'PROOF_PARENT_FORCED','peer-force':'ACCEPT_CANDIDATE_FORCED','recovery-force':'PROOF_CANDIDATE_FORCED'}.get(name)
        if point:rows=[v for v in rows if v.get('event')!=point]
        else:rows[-1]['proof']='f'*64
        path.write_text(''.join(json.dumps(v)+'\n' for v in rows))

def run(original):
    original=Path(original);e.validate(original);result=[]
    with tempfile.TemporaryDirectory(prefix='v53-proof-negatives-') as temp:
        for name,reason in CASES:
            case=selected(name);root=Path(temp)/name;shutil.copytree(original/case['name'],root);mutate(root,name)
            try:e.validate_case(root,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated proof negative: '+name+': '+str(error));result.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted proof negative: '+name)
    return result

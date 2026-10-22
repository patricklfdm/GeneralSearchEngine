"""Exact-reason rejection of corrupted original adoption installation evidence."""
import json
from pathlib import Path
import shutil
import tempfile
from . import adoption_install_evidence as e
from . import adoption_fence_negatives as a
from .membership_model import need

CASES=(('returned-digest','install returned binding'),('network-ack','install returned binding'),
       ('fence-force','adopt install force order'),('selector-force','adopt install force order'),
       ('scope','adopt install scope'),('marker','adopt install physical snapshot'),
       ('old-generation','adopt install physical snapshot'),('refusal','adopt install same-ballot refusal'),
       ('duplicate','adopt install duplicate wrote'),('next-cut','adopt install fresh capture'),
       ('selector','adopt install physical snapshot'),('source','retained promise view'),
       ('certificate-receipt','adoption phased receipt'),('image','adoption image'))


def mutate(root,name):
    if name in ('certificate-receipt','image'):return a.mutate(root,name)
    if name=='scope':
        path=root/'case.json';row=json.loads(path.read_text());row['networkAck']=True;path.write_bytes(e.g.f.canonical(row));return
    if name in ('returned-digest','network-ack','fence-force','selector-force','refusal','duplicate','next-cut'):
        path=root/('same.stdout' if name=='refusal' else 'duplicate.stdout' if name=='duplicate' else 'next.stdout' if name=='next-cut' else 'first.stdout')
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        if name=='returned-digest':rows[-1]['manifest']='00'*32
        elif name=='network-ack':rows[-1]['networkAck']=True
        elif name=='refusal':rows[-1]['reason']='unrelated'
        elif name=='duplicate':rows.insert(0,dict(event='INSTALL_SELECTOR_FORCED'))
        elif name=='next-cut':rows[-1]['cut']['index']-=1
        else:rows=[r for r in rows if r.get('event')!=('PROMISE_FORCED' if name=='fence-force' else 'INSTALL_SELECTOR_FORCED')]
        path.write_bytes(b''.join(e.g.f.canonical(row)+b'\n' for row in rows));return
    if name=='marker':(root/'original/generations/b/adopted-certificate.gsr').unlink();return
    if name=='old-generation':shutil.rmtree(root/'original/generations/a');return
    if name=='selector':(root/'original/selector.gsr').write_bytes((root/'initial/selector.gsr').read_bytes());return
    if name=='source':
        dirs=sorted((root/'final/sources').iterdir());original=(root/'initial/sources');old=next(original.iterdir())
        target=next(p for p in dirs if p.name!=old.name);(target/'source.gscp').write_bytes((old/'source.gscp').read_bytes());return
    raise ValueError('unknown adoption install negative')


def run(original):
    original=Path(original);e.validate(original);results=[]
    case=next(c for c in e.cases() if c['size']==3 and c['through']==7 and c['mode']=='clean')
    with tempfile.TemporaryDirectory(prefix='v53-adopt-install-negatives-') as temp:
        for name,reason in CASES:
            root=Path(temp)/name;shutil.copytree(original/case['name'],root);mutate(root,name)
            try:e.validate_case(root,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated adoption install negative: '+name+': '+str(error));results.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted adoption install negative: '+name)
    return results

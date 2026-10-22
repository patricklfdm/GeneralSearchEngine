"""Original-first exact-reason negatives for the physical certificate fence."""
import json
from pathlib import Path
import shutil
import tempfile
from . import adoption_fence_evidence as e
from .membership_model import need

CASES=(('returned-digest','adoption returned binding'),('grant','adoption returned binding'),
       ('installed','adoption returned binding'),('missing-force','adoption force order'),
       ('scope','adoption scope'),('selector','grant snapshot inventory'),
       ('basis','adoption changed prefix/source/history'),('refusal','adoption refusal reason'),
       ('duplicate','adoption duplicate wrote'),('image','adoption image'),
       ('certificate-receipt','adoption phased receipt'),('checkpoint-owner','adoption checkpoint endorsement'))


def mutate(root,name):
    if name in ('certificate-receipt','checkpoint-owner'):
        from .generation_install_evidence import packet_bytes
        path=root/'inputs/source.gscp';data=e.p.decode(path.read_bytes());cap=data['capsule'];objects=data['objects']
        item=next(v for v in cap['items'] if v['kind']=='MEMBERSHIP')
        if name=='certificate-receipt':
            value=e.g.f.decode(objects[item['certificate']],'records','CERTIFICATE');value['proofs'][0]['receipt']='00'*32
            raw=e.g.f.encode('records','CERTIFICATE',value);objects[e.c.sha(raw)]=raw;item['certificate']=e.c.sha(raw)
        else:
            value=e.g.f.decode(objects[item['endorsements'][0]],'records','CHECKPOINT_ACK');value['incarnation']='00000000-0000-0000-0000-000000000099'
            raw=e.g.f.encode('records','CHECKPOINT_ACK',value);objects[e.c.sha(raw)]=raw;item['endorsements'][0]=e.c.sha(raw)
        path.write_bytes(packet_bytes(cap,objects,data['images']));return
    if name=='scope':
        path=root/'case.json';value=json.loads(path.read_text());value['prefixInstalled']=True;path.write_bytes(e.g.f.canonical(value));return
    if name in ('returned-digest','grant','installed','missing-force','refusal','duplicate'):
        path=root/('same.stdout' if name=='refusal' else 'duplicate.stdout' if name=='duplicate' else 'first.stdout')
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        if name=='returned-digest':rows[-1]['promise']='00'*32
        elif name=='grant':rows[-1]['hasBasis']=True
        elif name=='installed':rows[-1]['prefixInstalled']=True
        elif name=='refusal':rows[-1]['reason']='unrelated'
        elif name=='duplicate':rows.insert(0,dict(event='PROMISE_WRITTEN'))
        else:rows=[r for r in rows if r.get('event')!='PROMISE_FORCED']
        path.write_bytes(b''.join(e.g.f.canonical(row)+b'\n' for row in rows));return
    if name=='basis':
        path=root/'original/grants.gsr';raw=path.read_bytes();offset=0
        while offset<len(raw):
            length=48+int.from_bytes(raw[offset+12:offset+16],'big')
            if offset+length==len(raw):break
            offset+=length
        value=e.g.f.decode(raw[offset:],'records','PROMISE');value['basisId']='00000000-0000-0000-0000-000000000099'
        path.write_bytes(raw[:offset]+e.g.f.encode('records','PROMISE',value));return
    if name=='selector':
        (root/'original/selector.pending.gsr').write_bytes((root/'initial/selector.gsr').read_bytes());return
    if name=='image':
        path=next((root/'inputs').glob('*.image'));raw=bytearray(path.read_bytes());raw[0]^=1;path.write_bytes(raw);return
    raise ValueError('unknown adoption mutation')


def run(original):
    original=Path(original);e.validate(original);results=[]
    case=next(c for c in e.cases() if c['size']==3 and c['through']==7 and c['mode']=='clean')
    with tempfile.TemporaryDirectory(prefix='v53-adoption-negatives-') as temp:
        for name,reason in CASES:
            path=Path(temp)/name;shutil.copytree(original/case['name'],path);mutate(path,name)
            try:e.validate_case(path,case)
            except ValueError as error:
                need(str(error)==reason,'unrelated adoption negative: '+name+': '+str(error));results.append(dict(case=name,status='REJECT',reason=reason))
            else:raise ValueError('accepted adoption negative: '+name)
    return results

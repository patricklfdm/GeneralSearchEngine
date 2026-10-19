"""Independent synthetic read-evidence contract, NOT physical/runtime qualification.

Actual V5.1 physical decoding and V4.4 result replay remain mandatory in later
process gates. These bounded fixtures exercise the new authority/read relations.
"""
import copy
import hashlib
import json
from pathlib import Path
from . import token

SCHEMA='gse-v52-read-foundation-v1'
LIMIT=1024*1024


def need(value,category):
    if not value:raise ValueError(category)


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def digest(raw):return hashlib.sha256(raw).hexdigest()


def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'N15');result[key]=value
        return result
    def constant(value):raise ValueError('N15')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)


def save(root,value,origin=None):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    (root/'history.json').write_bytes(encoded(value))
    (root/'inventory.json').write_bytes(encoded(dict(schema=SCHEMA,origin=origin or str(root.resolve()),
        files={'history.json':dict(size=(root/'history.json').stat().st_size,sha256=digest((root/'history.json').read_bytes()))})))


def read(root,expected,origin=None):
    root=Path(root)
    need(not root.is_symlink() and {p.name for p in root.iterdir()}=={'inventory.json','history.json'},'N15')
    for name in ('inventory.json','history.json'):
        path=root/name
        need(path.is_file() and not path.is_symlink() and path.stat().st_size<=LIMIT,'N15')
    try:
        inventory=strict((root/'inventory.json').read_bytes());raw=(root/'history.json').read_bytes()
        need(inventory==dict(schema=SCHEMA,origin=origin or str(root.resolve()),
             files={'history.json':dict(size=len(raw),sha256=digest(raw))}),'N15')
        value=strict(raw)
    except (KeyError,TypeError,json.JSONDecodeError):raise ValueError('N15') from None
    validate(value,expected)
    return value


def validate(v,expected):
    need(v['schema']==SCHEMA and v['execution']=='synthetic-foundation-only','N14')
    need(v['binding']==expected and v['read']['process']==expected['process'],'N14')
    identity=v['identity'];r=v['read'];a=v['authority']
    try:progress=token.decode(bytes.fromhex(r['token']))
    except (ValueError,TypeError):raise ValueError('N16') from None
    for name,category in (('groupId','N01'),('historyId','N02'),('manifestDigest','N03')):
        need(progress[name]==identity[name],category)
    need(progress['index']==r['captureIndex'],'N04')
    need(r['captureIndex'] in a['proofs'] and r['captureIndex']<=a['accepted'],'N05')
    publications={p['index']:p for p in a['publications']}
    need(r['captureIndex'] in publications and publications[r['captureIndex']]['at']<r['captureAt'],'N06')
    cut=publications[r['captureIndex']]
    need(r['sequence']==cut['sequence'] and r['value']==cut['value'],'N07')
    need(r['policy'] in ('strong','minimum','stale'),'N09')
    if r['policy']=='strong':
        b=r['barrier'];need(b is not None and r['invokeAt']<b['at']<r['captureAt'] and
            0<b['index']<=r['captureIndex'] and b['epoch']==r['captureEpoch'],'N08')
    if r['policy']=='minimum':
        minimum=token.decode(bytes.fromhex(r['minimum']))
        need(all(minimum[k]==identity[k] for k in ('groupId','historyId','manifestDigest')),'N09')
        need(r['captureIndex']>=minimum['index'],'N09')
    need(r['invokeAt']<r['captureAt']<r['releaseAt']<r['responseAt'] and
         r['captureAt']<r['deadline'] and (r['cancelAt'] is None or r['cancelAt']>r['captureAt']),'N10')
    need(r['writeResponseAt']<r['invokeAt'] and r['writeIndex']<=r['captureIndex'],'N11')
    need(r['viewUses'] and all(r['captureAt']<=u['at']<r['releaseAt'] and u['thread']=='callback' for u in r['viewUses']),'N12')
    counts={'permit':0,'timer':0,'pin':0};last=-1;allocations={k:0 for k in counts}
    for e in r['resources']:
        need(e['kind'] in counts and e['delta'] in (-1,1) and e['at']>=last,'N13');last=e['at']
        k=e['kind'];counts[k]+=e['delta'];allocations[k]+=int(e['delta']==1)
        need(0<=counts[k]<=1,'N13')
        if k=='pin' and e['delta']==1:need(e['at']==r['captureAt'],'N13')
        if k=='pin' and e['delta']==-1:need(e['at']==r['releaseAt'],'N13')
    need(all(v==0 for v in counts.values()) and all(v==1 for v in allocations.values()),'N13')
    expected=[dict(kind=k,delta=d,at=a) for k,d,a in
        [('permit',1,r['invokeAt']),('timer',1,r['invokeAt']),('timer',-1,r['captureAt']),
         ('pin',1,r['captureAt']),('pin',-1,r['releaseAt']),('permit',-1,r['responseAt'])]]
    need(r['resources']==expected,'N13')
    return dict(status='PASS',execution=v['execution'])


def fixture(binding):
    identity=dict(groupId='00112233-4455-6677-8899-aabbccddeeff',historyId='ffeeddcc-bbaa-9988-7766-554433221100',manifestDigest='ab'*32)
    t=dict(version=1,**identity,index=2)
    value=dict(documents=[dict(id=1,value='later')],ranking=[1],explanation='synthetic index 2')
    return dict(schema=SCHEMA,execution='synthetic-foundation-only',binding=copy.deepcopy(binding),identity=identity,
        authority=dict(accepted=3,proofs=[0,1,2],publications=[dict(index=2,at=4,sequence=1,value=value)]),
        read=dict(process=binding['process'],token=token.encode(t).hex(),policy='strong',minimum=token.encode(t).hex(),
            captureIndex=2,sequence=1,value=copy.deepcopy(value),invokeAt=2,captureAt=5,releaseAt=7,responseAt=8,deadline=9,
            cancelAt=None,barrier=dict(index=2,at=3,epoch=2),captureEpoch=2,writeResponseAt=1,writeIndex=1,
            viewUses=[dict(at=6,thread='callback')],resources=[dict(kind=k,delta=d,at=a) for k,d,a in
                [('permit',1,2),('timer',1,2),('timer',-1,5),('pin',1,5),('pin',-1,7),('permit',-1,8)]]))


def mutations(original):
    result=[]
    def change(code,edit):
        v=copy.deepcopy(original);edit(v);result.append((code,v))
    def token_change(v,**fields):
        t=token.decode(bytes.fromhex(v['read']['token']));t.update(fields);v['read']['token']=token.encode(t).hex()
    change('N01',lambda v:token_change(v,groupId='00000000-0000-0000-0000-000000000000'))
    change('N02',lambda v:token_change(v,historyId='00000000-0000-0000-0000-000000000000'))
    change('N03',lambda v:token_change(v,manifestDigest='cd'*32))
    change('N04',lambda v:token_change(v,index=3))
    change('N05',lambda v:v['authority'].update(proofs=[0,1]))
    change('N06',lambda v:v['authority']['publications'][0].update(at=6))
    change('N07',lambda v:v['read'].update(sequence=0))
    change('N08',lambda v:v['read']['barrier'].update(epoch=1))
    def minimum(v):
        t=token.decode(bytes.fromhex(v['read']['token']));t['index']=3
        v['read'].update(policy='minimum',minimum=token.encode(t).hex())
    change('N09',minimum)
    change('N10',lambda v:v['read'].update(cancelAt=4))
    change('N11',lambda v:v['read'].update(writeResponseAt=3))
    change('N12',lambda v:v['read']['viewUses'].append(dict(at=8,thread='callback')))
    change('N13',lambda v:v['read']['resources'].pop())
    change('N14',lambda v:v['binding'].update(attempt=v['binding']['attempt']+1))
    change('N16',lambda v:v['read'].update(token=v['read']['token']+'00'))
    return result


def negatives(root,expected,origin=None):
    original=read(root,expected,origin);results=[]
    for code,v in mutations(original):
        try:validate(v,expected)
        except ValueError as error:
            need(str(error)==code,'wrong negative rejection: '+code+': '+str(error))
            results.append(dict(case=code,status='REJECTED',reason=str(error)))
        else:raise ValueError('accepted negative '+code)
    # Inventory validation is exercised on a separate real relocated directory.
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        save(temp,original,origin or str(Path(root).resolve()));(Path(temp)/'history.json').write_bytes(b'{}')
        try:read(temp,expected,origin or str(Path(root).resolve()))
        except ValueError as error:
            need(str(error)=='N15','wrong inventory rejection');results.append(dict(case='N15',status='REJECTED',reason='N15'))
        else:raise ValueError('accepted negative N15')
    return sorted(results,key=lambda v:v['case'])

"""Compare original REMOVE retirement file prefixes to derived transactions.

The sidecar observes the same original callback indices without altering raw
histories. Its claimed bytes never supply the expected retirement authority.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile
from . import remove_retirement_evidence as r
from . import joining_grant_captures as g

need,sha,f=r.need,r.sha,r.f
SCHEMA='gse-v53-remove-retirement-capture-v1'
MAXIMUM_CAPTURES=2048


def collect(root,sidecar,profile):
    need(profile in r.n.original.PROFILES,'REMOVE prefix collection header')
    return collect_bound(root,sidecar,profile,SCHEMA,'transition-round-result.json',int(profile[0]))


def collect_bound(root,sidecar,profile,schema,result_name,node_count):
    """Internal shared decoder; callers fix the producer/result contract."""
    root,sidecar=Path(root),Path(sidecar)
    inventory=r.n.collection.inventory(sidecar,maximum=g.MAXIMUM_BYTES+4096)
    _,header=g.json_file(sidecar/'collection.json')
    need(type(header) is dict and set(header)=={'schema','profile','eventsSha256','resultSha256','captures','storedBytes'} and
         header['schema']==schema and header['profile']==profile and
         type(header['captures']) is int and 0<header['captures']<=MAXIMUM_CAPTURES and
         type(header['storedBytes']) is int and 0<header['storedBytes']<=g.MAXIMUM_BYTES,'REMOVE prefix collection header')
    events_raw=r.n.collection.snapshot.s.regular(root/'events.json',r.n.collection.EVENT_BYTES)
    result_raw=r.n.collection.snapshot.s.regular(root/result_name,4096)
    need(header['eventsSha256']==sha(events_raw) and header['resultSha256']==sha(result_raw),'REMOVE prefix original history binding')
    events=r.n.collection.read_json(root,'events.json',r.n.collection.EVENT_BYTES)
    names=[f'capture-{i:04d}.json' for i in range(1,header['captures']+1)]
    need({v.name for v in sidecar.iterdir()}=={'collection.json','objects',*names} and
         inventory['directories']==['objects'],'REMOVE prefix exact sidecar layout')
    payloads={};total=0;used=set();copies={};owners={}
    for path in (sidecar/'objects').iterdir():
        need(re.fullmatch('[0-9a-f]{64}',path.name) is not None and len(payloads)<8192,'REMOVE prefix object name/count')
        raw=g.snapshot.s.regular(path,64*g.MIB)
        need(sha(raw)==path.name,'REMOVE prefix object identity');payloads[path.name]=raw;total+=len(raw)
    for name in names:
        encoded,value=g.json_file(sidecar/name);total+=len(encoded)
        need(type(value) is dict and set(value)=={'schema','node','kind','point','eventIndex','files'} and
             value['schema']==SCHEMA and value['kind'] in ('generation','source') and type(value['eventIndex']) is int and
             0<=value['eventIndex']<len(events) and value['eventIndex'] not in copies,'REMOVE prefix metadata shape/index')
        at=value['eventIndex'];node=value['node'];point=value['point']
        need(events[at]==dict(node=node,event=point) and type(point) is str and
             (point.startswith('RETIREMENT_') if value['kind']=='generation' else point.startswith(('SOURCE_RETIREMENT_','JOURNAL_ROTATION_'))),
             'REMOVE prefix original callback')
        entries=value['files'];need(type(entries) is list and 0<len(entries)<=g.MAXIMUM_FILES,'REMOVE prefix file count')
        files={};previous=None
        for entry in entries:
            need(type(entry) is dict and set(entry)=={'name','identity'},'REMOVE prefix member shape')
            path=entry['name'];g.snapshot.relative(path)
            need(previous is None or previous<path,'REMOVE prefix ordered unique member');previous=path
            identity=entry['identity'];need(type(identity) is dict,'REMOVE prefix member identity')
            if set(identity)=={'directory'}:
                need(identity['directory'] is True,'REMOVE prefix directory type');files[path]=None
            else:
                need(set(identity)=={'size','sha256'} and type(identity['size']) is int and identity['size']>=0 and
                     type(identity['sha256']) is str and identity['sha256'] in payloads,'REMOVE prefix missing object/size')
                digest=identity['sha256'];raw=payloads[digest]
                need(len(raw)==identity['size'],'REMOVE prefix file size');files[path]=raw;used.add(digest)
            parent=Path(path).parent.as_posix();need(parent=='.' or parent in files and files[parent] is None,'REMOVE prefix parent directory')
        need(type(node) is str and node in {'node-'+str(i+1) for i in range(node_count)},'REMOVE prefix original node')
        if node not in owners:
            owners[node]={key:g.snapshot.s.regular(root/'before-network'/node/key,16384) for key in ('root.gsr','node.gsr')}
        need(all(files.get(k)==v for k,v in owners[node].items()),'REMOVE prefix original owner records')
        copies[at]=dict(node=node,kind=value['kind'],point=point,files=files)
    need(total==header['storedBytes'],'REMOVE prefix stored byte count')
    need(used==payloads.keys(),'REMOVE prefix unobserved object')
    return copies,inventory


class Replay(r.Replay):
    def __init__(self,root,profile,copies):
        super().__init__(root,profile);self.copies=copies;self.captured_used=set()

    def transaction(self,node,kind,actual,expected):
        need(len(actual)==len(expected),'REMOVE prefix transaction length')
        for (at,event),(point,state) in zip(actual,expected):
            need(at in self.copies and at not in self.captured_used,'REMOVE prefix missing or reused callback')
            copy=self.copies[at]
            need(copy['node']==node and copy['kind']==kind and copy['point']==point==event['event'],'REMOVE prefix transaction binding')
            need(r.physical(copy['files'])==state,'REMOVE prefix exact original state: '+point);self.captured_used.add(at)

    def run(self):
        result=super().run();need(self.captured_used==self.copies.keys(),'REMOVE prefix unbound observation')
        return dict(result,transientRetirementBytesQualified=True,capturedPrefixes=len(self.captured_used),
                    processDeathQualified=False,phase3Complete=False)


def replay(root,sidecar,profile):
    copies,before=collect(root,sidecar,profile);result=Replay(root,profile,copies).run()
    need(r.n.collection.inventory(Path(sidecar),maximum=g.MAXIMUM_BYTES+4096)==before,'REMOVE prefix sidecar changed')
    return result


def validate(root,sidecar,profile):
    original=r.validate(root,profile);before=r.n.collection.inventory(Path(root))
    result=replay(root,sidecar,profile)
    need(r.n.collection.inventory(Path(root))==before,'REMOVE prefix original changed')
    return dict(result,precondition=original)


NEGATIVES={
    'missing-copy':'REMOVE prefix exact sidecar layout',
    'history-binding':'REMOVE prefix original history binding',
    'profile-binding':'REMOVE prefix collection header',
    'duplicate-index':'REMOVE prefix metadata shape/index',
    'wrong-callback':'REMOVE prefix original callback',
    'missing-object':'REMOVE prefix missing object/size',
    'altered-object':'REMOVE prefix object identity',
    'extra-object':'REMOVE prefix unobserved object',
    'boolean-size':'REMOVE prefix missing object/size',
    'wrong-owner':'REMOVE prefix original owner records',
    'borrowed-prefix':'REMOVE prefix exact original state: RETIREMENT_BORROW_PREFIX_WRITTEN',
    'wrong-floor':'REMOVE prefix exact original state: RETIREMENT_PROPOSAL_WRITTEN',
    'early-generation-delete':'REMOVE prefix exact original state: RETIREMENT_DELETE_VALIDATED',
    'late-generation-delete':'REMOVE prefix exact original state: RETIREMENT_FILE_DELETED',
    'early-journal-rotation':'REMOVE prefix exact original state: SOURCE_RETIREMENT_WRITTEN',
    'leftover-saved-file':'REMOVE prefix exact original state: RETIREMENT_BEFORE_RETURN',
}


def mutate(sidecar,name):
    sidecar=Path(sidecar);header_path=sidecar/'collection.json';_,header=g.json_file(header_path)
    copies=[(p,g.json_file(p)[1]) for p in sorted(sidecar.glob('capture-*.json'))]
    objects=sidecar/'objects'
    def at(point):return next((p,v) for p,v in copies if v['point']==point)
    def files(value):return {v['name']:v['identity'] for v in value['files']}
    def put(values,key,raw):
        digest=sha(raw);(objects/digest).write_bytes(raw);values[key]=dict(size=len(raw),sha256=digest)
    if name=='missing-copy':copies[0][0].unlink()
    elif name=='history-binding':header['eventsSha256']='0'*64
    elif name=='profile-binding':header['profile']='4-REMOVE' if header['profile']=='5-REMOVE' else '5-REMOVE'
    elif name in ('duplicate-index','wrong-callback'):
        path,value=copies[1]
        if name=='duplicate-index':value['eventIndex']=copies[0][1]['eventIndex']
        else:value['point']='RETIREMENT_NOT_OBSERVED'
        path.write_bytes(f.canonical(value))
    elif name in ('missing-object','altered-object'):
        digest=files(copies[0][1])['root.gsr']['sha256'];path=objects/digest
        if name=='missing-object':path.unlink()
        else:path.write_bytes(b'changed')
    elif name=='extra-object':(objects/sha(b'extra')).write_bytes(b'extra')
    else:
        point={'borrowed-prefix':'RETIREMENT_BORROW_PREFIX_WRITTEN','wrong-floor':'RETIREMENT_PROPOSAL_WRITTEN',
               'early-generation-delete':'RETIREMENT_DELETE_VALIDATED','late-generation-delete':'RETIREMENT_FILE_DELETED',
               'early-journal-rotation':'SOURCE_RETIREMENT_WRITTEN','leftover-saved-file':'RETIREMENT_BEFORE_RETURN'}.get(name)
        path,value=at(point) if point else copies[0];values=files(value)
        if name=='boolean-size':values['root.gsr']['size']=False
        elif name=='wrong-owner':put(values,'node.gsr',b'foreign owner')
        elif name=='borrowed-prefix':
            key='retirement/images.json';raw=(objects/values[key]['sha256']).read_bytes();put(values,key,raw[:-1]+bytes([raw[-1]^1]))
        elif name=='wrong-floor':
            key='retirement/proposal.gsr';record=f.decode((objects/values[key]['sha256']).read_bytes(),'records','RETIREMENT')
            record['floor']='0'*64;put(values,key,f.encode('records','RETIREMENT',record))
        elif name=='early-generation-delete':
            record=f.decode((objects/values['retirement/proposal.gsr']['sha256']).read_bytes(),'records','RETIREMENT');values.pop(record['files'][0]['path'])
        elif name=='late-generation-delete':
            prior=next(v for _,v in reversed(copies) if v['node']==value['node'] and v['point']=='RETIREMENT_DELETE_VALIDATED' and v['eventIndex']<value['eventIndex'])
            old=files(prior);key=next(k for k in old if k.startswith('generations/') and k not in values);values[key]=old[key]
        elif name=='early-journal-rotation':
            later=next(v for _,v in copies if v['node']==value['node'] and v['point']=='JOURNAL_ROTATION_RENAMED' and v['eventIndex']>value['eventIndex'])
            values['grants.gsr']=files(later)['grants.gsr']
        elif name=='leftover-saved-file':put(values,'unexpected-retirement-member',b'not deleted')
        else:raise ValueError('REMOVE prefix unknown negative')
        value['files']=[dict(name=k,identity=v) for k,v in sorted(values.items())];path.write_bytes(f.canonical(value))
        used={entry['identity']['sha256'] for p in sidecar.glob('capture-*.json') for entry in g.json_file(p)[1]['files'] if 'sha256' in entry['identity']}
        for p in objects.iterdir():
            if p.name not in used:p.unlink()
    header['storedBytes']=sum(p.stat().st_size for p in sidecar.rglob('*') if p.is_file() and p!=header_path)
    header_path.write_bytes(f.canonical(header))


def qualify(root,sidecar,profile):
    original=validate(root,sidecar,profile);before=r.n.collection.inventory(Path(root));captured=r.n.collection.inventory(Path(sidecar));results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-remove-prefix-negative-') as temp:
            changed=Path(temp)/'captures';shutil.copytree(sidecar,changed);mutate(changed,name)
            try:replay(root,changed,profile)
            except ValueError as error:need(str(error)==reason,'REMOVE prefix unrelated negative: '+name+': '+str(error))
            else:raise ValueError('REMOVE prefix mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(results[-1],profile=profile,completed=len(results),total=len(NEGATIVES))),flush=True)
    need(r.n.collection.inventory(Path(root))==before and r.n.collection.inventory(Path(sidecar))==captured,'REMOVE prefix qualification changed original')
    return dict(original=original,negatives=results,originalHistoryReexecuted=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('sidecar')
    p.add_argument('--profile',required=True,choices=r.n.original.PROFILES);p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps((qualify if a.qualify else validate)(a.root,a.sidecar,a.profile),sort_keys=True))

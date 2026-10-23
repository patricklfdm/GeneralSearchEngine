"""Replay private all-voter bootstrap transactions from original plan/image bytes.

This predicts file prefixes, four decisions and force order. It does not claim
public admission, typed-codec verification, process deaths or power-loss safety.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import tempfile
from . import bootstrap_plan_evidence as plans
from . import pending_context_evidence as e
from .journal_context_evidence import read_snapshot

STATES=('PREPARING','PREPARED','COMMITTING','COMMITTED')
PREPARED='bootstrap-prepared.gsbp';SEAL='bootstrap-seal.gsbp';SEAL_PENDING='bootstrap-seal.next.gsbp'
RECEIPT='receipt.gsbp';PENDING='receipt.next.gsbp';JOURNAL='bootstrap.gsr'


def container(kind,value):
    body=e.f.canonical(value);prefix=struct.pack('>4sHHHHI',b'GSBP',1,3,kind,0,len(body))
    e.need(len(body)+48<=65536,'bootstrap transaction metadata bound')
    return prefix+bytes.fromhex(e.digest(prefix+body))+body


def derived(raw,image,*,size=3,source="EMPTY"):
    decoded=plans.decode(raw,image,details=True,size=size,source=source);p=decoded['plan'];paths=[PurePosixPath(v['path']) for v in p['descriptor']['paths']]
    if source!='EMPTY':paths.pop(1) # original source is not a transaction target
    root=decoded['rootHash'];digest=e.digest(raw);payloads=decoded['payloads'];ids=decoded['root']['initial'];preps=[];targets=[]
    anchor=paths[0].parent
    for path in paths[1:]:
        while not path.is_relative_to(anchor):anchor=anchor.parent
    for i,payload in enumerate(payloads):
        authority=paths[1+2*i];core=paths[2+2*i]
        preps.append(container(2,dict(plan=digest,root=root,identity=ids[i],authority=str(authority),materialization=str(core),
            inventory=[dict(path=k,**e.info(v)) for k,v in sorted(payload.items())])))
        targets.append(dict(identity=ids[i],authorityPath=str(authority.relative_to(anchor)),materializationPath=str(core.relative_to(anchor))))
    rows=[e.f.encode('records','BOOTSTRAP',dict(decision=state,inventory=digest,root=root,source=source,sourceDigest=decoded['genesis']['sourceDigest'],targets=targets)) for state in STATES]
    receipt=container(3,dict(plan=digest,root=root,operation=str(paths[0]),preparations=list(map(e.digest,preps)),committing=e.digest(rows[2]),committed=e.digest(rows[3])))
    seals=[container(4,dict(plan=digest,root=root,identity=ids[i],authority=str(paths[1+2*i]),materialization=str(paths[2+2*i]),
                         prepared=e.digest(preps[i]),receipt=e.digest(receipt))) for i in range(size)]
    total=2*len(raw)+len(image)+2*len(receipt)+sum(map(len,rows))+sum(map(len,preps))+2*sum(map(len,seals))+sum(sum(map(len,v.values())) for v in payloads)
    e.need(total<=p['maximumOperation'],'bootstrap full transaction capacity')
    return dict(payloads=payloads,preps=preps,rows=rows,receipt=receipt,seals=seals,completionBytes=total)


class Interrupted(Exception):pass


class Model:
    def __init__(self,raw,image,*,admission=None,size=3,source="EMPTY",progress=False,typed=False):
        self.admission=admission;self.progress=progress;self.typed=typed
        self.data=derived(raw,image,size=size,source=source);self.files={'operation/operation.lock':b'','operation/plan.gsbp':raw,'operation/application.image':image};self.dirs={'operation'}
    def emit(self,event):
        self.events.append(event)
        if event==self.stop:raise Interrupted()
    def directory(self,path,event):
        if path not in self.dirs:self.dirs.add(path);self.emit(event+'_CREATED')
        self.emit(event+'_FORCED');self.emit(event+'_PARENT_FORCED')
    def file(self,path,wanted,event):
        if path not in self.files:self.files[path]=b'';self.emit(event+'_CREATED')
        before=self.files[path];e.need(wanted.startswith(before),'bootstrap model changed original prefix')
        if len(before)<len(wanted):
            self.files[path]=wanted[:len(before)+(len(wanted)-len(before))//2];self.emit(event+'_PREFIX_WRITTEN')
            self.files[path]=wanted;self.emit(event+'_WRITTEN')
        self.emit(event+'_FORCED');self.emit(event+'_PARENT_FORCED')
    def publish(self,path,pending,wanted,event):
        if path not in self.files:
            self.file(pending,wanted,event+'_CANDIDATE');self.files[path]=self.files.pop(pending);self.emit(event+'_RENAMED')
        self.file(path,wanted,event+'_ACTIVE')
    def phase(self):
        actual=self.files.get('operation/'+JOURNAL,b'');offset=0;phase=0
        for i,row in enumerate(self.data['rows'],1):
            if len(actual)-offset<len(row):
                e.need(row.startswith(actual[offset:]),'bootstrap model decision prefix');return phase
            e.need(actual[offset:offset+len(row)]==row,'bootstrap model decision');offset+=len(row);phase=i
        e.need(offset==len(actual),'bootstrap model decision trailer');return phase
    def advance(self,phase):
        self.file('operation/'+JOURNAL,b''.join(self.data['rows'][:phase]),'BOOTSTRAP_'+STATES[phase-1]);self.emit('BOOTSTRAP_'+STATES[phase-1]+'_DURABLE')
    def execute(self,stop=None):
        self.stop=stop;self.events=[]
        try:self._execute()
        except Interrupted:pass
        else:e.need(stop is None,'bootstrap model cut missing')
        return self.events
    def _execute(self):
        phase=self.phase();d=self.data
        indices=[i for i in range(len(d['payloads'])) if not (self.progress and phase==4 and f'target-{2*i}/'+SEAL in self.files)]
        if phase==0:
            if self.typed:self.emit('BOOTSTRAP_TYPED_RECHECKED')
            self.advance(1);phase=1
        self.file('operation/'+JOURNAL,self.files['operation/'+JOURNAL],'BOOTSTRAP_RECOVERY_JOURNAL')
        for i in indices:
            t=f'target-{2*i}';self.directory(t,f'BOOTSTRAP_TARGET_{i}')
            if t+'/replica.lock' not in self.files:self.file(t+'/replica.lock',b'',f'BOOTSTRAP_LOCK_{i}')
            self.emit(f'BOOTSTRAP_OWNED_{i}')
        for i in indices:
            for name in ('generations','generations/a','sources'):self.directory(f'target-{2*i}/'+name,f'BOOTSTRAP_DIRECTORY_{i}_{name}')
        if phase==1:
            for i in indices:
                t=f'target-{2*i}'
                if t+'/'+PREPARED not in self.files:
                    for name,raw in sorted(d['payloads'][i].items()):self.file(t+'/'+name,raw,f'BOOTSTRAP_PAYLOAD_{i}_{name}')
                for name,raw in sorted(d['payloads'][i].items()):self.file(t+'/'+name,raw,f'BOOTSTRAP_RESEAL_{i}_{name}')
                self.file(t+'/'+PREPARED,d['preps'][i],f'BOOTSTRAP_PREPARATION_{i}')
            self.advance(2);phase=2
        if phase>=2:
            for i in indices:
                for name,raw in sorted(d['payloads'][i].items()):self.file(f'target-{2*i}/'+name,raw,f'BOOTSTRAP_RESEAL_{i}_{name}')
                self.file(f'target-{2*i}/'+PREPARED,d['preps'][i],f'BOOTSTRAP_PREPARATION_RESEAL_{i}')
        if phase==2:
            if self.typed:self.emit('BOOTSTRAP_TYPED_RECHECKED')
            self.advance(3);phase=3
        if phase==3:self.publish('operation/'+RECEIPT,'operation/'+PENDING,d['receipt'],'BOOTSTRAP_RECEIPT');self.advance(4)
        if self.admission is not None:
            for i in indices:self.file(f'target-{2*i}/bootstrap-admission.gsbp',self.admission,f'BOOTSTRAP_ADMISSION_{i}')
        for i in indices:self.publish(f'target-{2*i}/'+SEAL,f'target-{2*i}/'+SEAL_PENDING,d['seals'][i],f'BOOTSTRAP_SEAL_{i}')
        self.emit('BOOTSTRAP_COMMITTED_BEFORE_RETURN')


def cuts(events):
    return list(dict.fromkeys(v for v in events if v.endswith(('_DURABLE','_BEFORE_RETURN')) or v.startswith(('BOOTSTRAP_TARGET_','BOOTSTRAP_DIRECTORY_0_')) or
            v.startswith('BOOTSTRAP_PAYLOAD_0_') and v.endswith(('_PREFIX_WRITTEN','_CREATED')) or v.startswith('BOOTSTRAP_PREPARATION_0_') or
            v=='BOOTSTRAP_PREPARATION_2_PARENT_FORCED' or any(v.startswith('BOOTSTRAP_'+s+'_') and not v.endswith('BEFORE_RETURN') for s in STATES) or
            v.startswith(('BOOTSTRAP_RECEIPT_','BOOTSTRAP_SEAL_0_'))))


def validate(root):
    root=Path(root);e.need(root.is_dir() and not root.is_symlink(),'bootstrap transaction evidence root')
    first=root/'case-000';raw=plans.read(first/'original-plan.gsbp',2*e.MIB);image=plans.read(first/'original-application.image',64*e.MIB)
    points=cuts(Model(raw,image).execute());e.need({p.name for p in root.iterdir()}=={f'case-{i:03d}' for i in range(len(points))}|{'receipt.json'},'bootstrap transaction case inventory')
    rows=[]
    for i,stop in enumerate(points):
        name=f'case-{i:03d}';path=root/name;e.need(path.is_dir() and not path.is_symlink() and {p.name for p in path.iterdir()}=={'original-plan.gsbp','original-application.image','events.json','crash','second-crash','final'},'bootstrap transaction case members')
        raw=plans.read(path/'original-plan.gsbp',2*e.MIB);image=plans.read(path/'original-application.image',64*e.MIB);model=Model(raw,image)
        actual=e.parse(plans.read(path/'events.json',e.MIB));e.exact(actual,'first second resumed')
        for key,stage,cut in [('first','crash',stop),('second','second-crash','BOOTSTRAP_RESEAL_0_root.gsr_FORCED'),('resumed','final',None)]:
            expected=model.execute(cut);e.need(actual[key]==expected,'bootstrap transaction '+key+' force order')
            e.need(read_snapshot(path/stage)==(model.files,model.dirs),'bootstrap transaction exact '+stage+' bytes')
        rows.append(dict(case=name,cut=stop,plan=e.digest(raw),status='PASS'))
    expected=dict(schema='gse-v53-bootstrap-transaction-v1',status='PASS',cases=rows,freshProcesses=False,publicBootstrap=False)
    e.need(e.f.canonical(e.parse(plans.read(root/'receipt.json',65536)))==e.f.canonical(expected),'bootstrap transaction receipt scope')
    return dict(status='PASS',cases=len(points),originalFirst=True,privateCommittedTargets=3*len(points),freshProcesses=False,publicBootstrap=False,typedCodecIndependentlyVerified=False)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'missing-case':'bootstrap transaction case inventory','original-plan':'bootstrap original plan checksum','original-image':'bootstrap original image binding',
        'crash':'bootstrap transaction exact crash bytes','second-crash':'bootstrap transaction exact second-crash bytes','final':'bootstrap transaction exact final bytes',
        'first-order':'bootstrap transaction first force order','second-order':'bootstrap transaction second force order','resumed-order':'bootstrap transaction resumed force order',
        'scope':'bootstrap transaction receipt scope','scope-type':'bootstrap transaction receipt scope','target-type':'bootstrap plan derived target inventories','extra-target':'bootstrap transaction exact final bytes','linked-file':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-bootstrap-transaction-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/'case-001'
            if name=='missing-case':shutil.rmtree(case)
            elif name=='original-plan':
                p=case/'original-plan.gsbp';raw=p.read_bytes();p.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name=='original-image':(case/'original-application.image').write_bytes(b'changed')
            elif name in ('crash','second-crash','final'):(case/name/'operation/plan.gsbp').write_bytes(b'changed')
            elif name.endswith('-order'):
                p=case/'events.json';value=e.parse(p.read_bytes());value[name[:-6]]=[];p.write_bytes(e.f.canonical(value))
            elif name in ('scope','scope-type'):
                p=moved/'receipt.json';value=e.parse(p.read_bytes());value['publicBootstrap']=True if name=='scope' else 0;p.write_bytes(e.f.canonical(value))
            elif name=='target-type':
                p=case/'original-plan.gsbp';raw=p.read_bytes();value=e.parse(raw[48:])
                next(row for row in value['targets'][0]['files'] if row['path']=='replica.lock')['bytes']=False
                body=e.f.canonical(value);prefix=struct.pack('>4sHHHHI',b'GSBP',1,3,1,0,len(body));p.write_bytes(prefix+bytes.fromhex(e.digest(prefix+body))+body)
            elif name=='extra-target':(case/'final/target-1').mkdir()
            elif name=='linked-file':
                p=case/'final/operation/plan.gsbp';p.unlink();p.symlink_to(case/'original-plan.gsbp')
            try:validate(moved)
            except ValueError as error:e.need(str(error)==reason,'bootstrap transaction unexpected negative: '+name+': '+str(error))
            else:raise ValueError('bootstrap transaction negative accepted: '+name)
            negatives.append(dict(case=name,reason=reason))
    with tempfile.TemporaryDirectory(prefix='v53-bootstrap-transaction-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'bootstrap transaction portable mismatch')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('evidence');a=p.parse_args();print(json.dumps(qualify(a.evidence),sort_keys=True))

"""Bind a public backup to its exact capture and a new group's independently restored genesis."""
import copy
import struct
import uuid
from pathlib import Path
from scripts.v43 import derived_format_v12 as b
from scripts.v51 import performance_bundle as bundle
from . import public_reads_evidence as e,public_read_lifecycle_evidence as lifecycle,token
from .evidence import need,digest

CASES=('backup-export','backup-import')
IDENTITY=['v52-read-store','v52-read-schema','v52-read-codec']
INDEX=[dict(kind='text',field='value',analyzer='gse-simple-v1')]


def backup_report(directory):
    directory=Path(directory);members=bundle.members(directory)
    names=['gse-backup-checkpoint','gse-backup-metadata','gse-backup-manifest']
    need(set(members)==set(names),'read backup member set')
    payloads={name:(directory/name).read_bytes() for name in names}
    need(sum(map(len,payloads.values()))<=1<<20,'read backup byte bound')
    c=b.uncheck(payloads[names[1]],64,'read backup metadata');magic,major,minor,most,least=c.unpack('>QhhQQ')
    need((magic,major,minor,c.string(128))==(b.METADATA_MAGIC,1,2,'gse-durable'),'read backup metadata format')
    size=c.unpack('>I')[0];profile=c.take(size);profile_digest=c.take(32)
    need(profile==b.profile_bytes() and profile_digest==b.profile_digest(),'read backup profile')
    need([c.string(128) for _ in range(3)]==IDENTITY,'read backup codec identity')
    need(c.unpack('>iiiiiqqqi')==(1,1048576,65536,100,1000,268435456,8589934592,2147483648,1),'read backup configured bounds')
    need((c.unpack('>B')[0],c.string(1024),c.string(128,True))==(4,'value','gse-simple-v1'),'read backup index');c.finish()
    c=b.uncheck(payloads[names[0]],88,'read backup checkpoint')
    need(c.unpack('>QhhQQ')==(b.CHECKPOINT_MAGIC,1,2,most,least) and c.take(32)==profile_digest,'read backup checkpoint identity')
    sequence,next_doc,live,count=c.unpack('>qiii');need(sequence>=0 and count==1,'read backup checkpoint counts')
    need((c.unpack('>B')[0],c.string(1024),c.string(128,True))==(4,'value','gse-simple-v1'),'read backup checkpoint index')
    slots=c.unpack('>i')[0];need(0<=slots<=1000 and slots==next_doc,'read backup slot count');documents=[];keys=set()
    for _ in range(slots):
        state=c.unpack('>B')[0];need(state in (0,1),'read backup slot state')
        if state==0:continue
        need(c.unpack('>i')[0]==4,'read backup key size');key=c.unpack('>i')[0]
        size=c.unpack('>i')[0];need(4<=size<=65536,'read backup document size');doc=c.take(size)
        need(key not in keys and struct.unpack('>i',doc[:4])[0]==key,'read backup document identity');keys.add(key)
        documents.append(dict(id=key,value=doc[4:].decode('utf-8')))
    need(live==len(documents),'read backup live count');c.finish()
    c=b.uncheck(payloads[names[2]],160,'read backup manifest')
    need(c.unpack('>Qhh')==(b.BACKUP_MAGIC,1,2) and [c.string(128) for _ in range(2)]==['gse-backup','gse-durable'] and
         c.unpack('>hh')==(1,2) and c.take(32)==profile_digest,'read backup manifest format')
    need(c.unpack('>QQq')==(most,least,sequence),'read backup manifest sequence/history')
    need([c.string(128) for _ in range(3)]==IDENTITY and c.unpack('>iI')==(1,2),'read backup manifest identity')
    for name in names[:2]:
        need(c.string(128)==name and c.unpack('>Q')[0]==len(payloads[name]) and c.take(32).hex()==digest(payloads[name]),'read backup member hash')
    content=c.take(32).hex()
    need(content==digest(b._backup_preimage({name:payloads[name] for name in names[:2]},profile_digest,(most,least),sequence,*IDENTITY,1)),
         'read backup content identity')
    need(c.unpack('>q')[0]>=0,'read backup creation time');c.string(256,True);c.finish()
    return dict(sequence=sequence,sourceHistory=str(uuid.UUID(int=(most<<64)|least)),contentIdentity='gse-backup-v3-'+content,
                memberCount=3,totalBytes=sum(map(len,payloads.values())),documents=documents)


def schedule(root,traces,history,processes):
    details=e.read(root/'read-import.json');name=details['scenario'];need(name in CASES,'read import scenario')
    attempts={a['opId']:a for a in history};carried=attempts[details['carriedOp']]['response'];manifest,_,entries=e.context(root,traces)
    for process in processes:lifecycle.ownership([r for r in traces[process['node']] if r['pid']==process['pid']],False)
    if name=='backup-export':
        attempt=attempts[details['backupOp']];rows=traces[attempt['node']]
        def single(event):
            found=[r for r in rows if r['event']==event and (event.startswith('READ_') or r.get('opId')==attempt['opId'])]
            need(len(found)==1,'backup capture event missing/duplicate: '+event);return found[0]
        invoke=single('CLIENT_INVOKE');validated=single('READ_CAPTURE_VALIDATED');capture=single('READ_CAPTURED');released=single('READ_RELEASED');response=single('CLIENT_SUCCESS')
        need(invoke['order']<validated['order']<capture['order']<released['order']<response['order'] and
             all(capture[k]==validated[k]==released[k] for k in ('epoch','index','sequence')),'backup capture lifetime')
        published=next((r for r in rows if r['event']=='PUBLISHED' and r['order']<validated['order'] and
                        len(e.recovery.snapshot(e.physical.raw(r['snapshot']),manifest)['anchors'])==capture['index']),None)
        need(published is not None,'backup lacks exact publication');snapshot=e.recovery.snapshot(e.physical.raw(published['snapshot']),manifest)
        terminal=snapshot['anchors'][-1]['entryDigest'];proof=e.physical.frame(snapshot['terminalProof'],'PROOF',manifest)
        need(entries[terminal]['operation']==9 and proof['epoch']==capture['epoch'] and any(r['event']=='FORCE' and r['kind']=='ACCEPT' and
             e.physical.frame(r['record'],'ACCEPT',manifest)['entryDigest']==terminal and invoke['order']<r['order']<validated['order'] for r in rows),
             'backup lacks own fresh barrier')
        promises=[e.physical.frame(r['record'],'PROMISE',manifest)['epoch'] for r in rows if r['event']=='FORCE' and r['kind']=='PROMISE' and r['order']<validated['order']]
        need(promises and promises[-1]==capture['epoch'],'backup capture after higher promise')
        need(attempt['response']=={k:v for k,v in response.items() if k not in lifecycle.META},'backup worker response binding')
        report=backup_report(root/'backup');need(all(attempt['response'][k]==v for k,v in report.items() if k!='documents'),'backup result differs from bytes')
        prefix=e.prefix(snapshot,manifest,e.context(root,traces)[1],entries)
        need(report['sequence']==prefix['sequence']==carried['sequence'] and report['documents']==prefix['documents']==carried['documents'],
             'backup application differs from captured prefix')
        need(all(a['outcome']=='SUCCESS' for a in history),'export unsuccessful call')
    else:
        denied=attempts[details['deniedOp']];rows=traces[denied['node']]
        need(denied['outcome']=='REJECTED' and denied.get('reasonCode')=='INCOMPATIBLE_HISTORY' and
             denied['minimum']==details['oldToken'],'old group token not rejected')
        invoke=next(r for r in rows if r['event']=='CLIENT_INVOKE' and r['opId']==denied['opId'])
        response=next(r for r in rows if r['event']=='CLIENT_FAILURE' and r['opId']==denied['opId'])
        need(not any(r['event'] in lifecycle.ATOMIC and invoke['order']<r['order']<response['order'] for r in rows),
             'old imported token allocated ownership')
        new=attempts[details['freshOp']];need(new['outcome']=='SUCCESS' and new['minimum']==carried['token'],'new imported token failed')
        need(all(a['outcome']=='SUCCESS' or a['opId']==denied['opId'] for a in history),'undeclared imported failure')
        backup_report(root/'control/seed')


def pair(source,imported):
    source=Path(source);imported=Path(imported)
    sb=e.read(source/'binding.json');ib=e.read(imported/'binding.json')
    need(all(sb[k]==ib[k] for k in ('source','checkoutSha256','java','artifacts','classes','run','attempt','codec','seed')),'import source/build/run binding')
    source_history=e.read(source/'history.json');import_history=e.read(imported/'history.json')
    sd=e.read(source/'read-import.json');id=e.read(imported/'read-import.json')
    old=next(a['response'] for a in source_history if a['opId']==sd['carriedOp'])
    first=import_history[0]['response'];a=token.decode(e.physical.raw(old['token']));n=token.decode(e.physical.raw(first['token']))
    need(all(a[k]!=n[k] for k in ('groupId','historyId','manifestDigest')) and n['index']==0,'import retained old replication identity')
    need(first['sequence']==old['sequence'] and first['documents']==old['documents'],'import lost application sequence/data')
    need(id['oldToken']==old['token'],'import borrowed old token')
    need(bundle.members(source/'backup')==bundle.members(imported/'control/seed')==ib['importedBackup'],'imported backup differs from public export')
    report=backup_report(source/'backup');need(report==backup_report(imported/'control/seed'),'copied backup changed')
    missing=e.read(imported/'token-only.json');need(missing==e.read(imported/'token-only.stdout') and
                                                set(missing)=={'status','reasonCode'} and missing['status']=='REJECTED' and
                                                missing['reasonCode'] in ('STORAGE_FAILURE','INTEGRITY_FAILURE'),
                                                'token recovered missing authority')
    need(not list((imported/'token-only').rglob('manifest.gsr')) and not list((imported/'token-only').rglob('genesis.gsr')),'token created missing authority')
    return dict(status='PASS',exportSequence=old['sequence'],importGenesisIndex=n['index'],distinctGroup=True,distinctHistory=True,tokenOnly=missing)


def negatives(root,binding,queries):
    cases=e.negatives(root,binding,queries)
    if binding['scenario']=='backup-export':
        traces=copy.deepcopy(e.traces_at(root));history=copy.deepcopy(e.read(root/'history.json'))
        attempt=next(a for a in history if a['kind']=='backup');attempt['response']['contentIdentity']='gse-backup-v3-'+'00'*32
        next(r for rows in traces.values() for r in rows if r['event']=='CLIENT_SUCCESS' and r['kind']=='backup')['contentIdentity']=attempt['response']['contentIdentity']
        try:e.validate(root,binding,queries,traces=traces,history=history)
        except ValueError as error:
            need(str(error)=='backup result differs from bytes','unexpected backup negative: '+str(error));cases.append(dict(case='forged-backup-identity',status='REJECTED',reason=str(error)))
        else:raise ValueError('forged backup identity accepted')
    return cases

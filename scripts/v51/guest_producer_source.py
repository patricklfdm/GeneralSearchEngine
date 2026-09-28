"""Prepare once over SSH; download only immutable, digest-bound source bytes."""
import hashlib
import os
from pathlib import Path
import re
import time
from . import guest_source_producer as producer, guest_source_transfer as wire
from . import performance_model as m, remote_command as c

MAX_CALLS=1024
READ_ATTEMPTS=3
MAX_READ_FAILURES=400


class RemoteSource:
    offline=True
    scope='authenticated-producer-download'
    def __init__(self,*,clock=time.monotonic,sleep=time.sleep):
        self.clock,self.sleep=clock,sleep;self.root=None

    def prepare(self,configs,deadline,*,endpoint,output):
        request=dict(schema=producer.SCHEMA,configs=configs);producer.validate(request)
        m.need(self.root is None and endpoint.offline is True and endpoint.value['binding']==configs[0]['binding'] and
               endpoint.value['manifestSha256']==configs[0]['packageManifestSha256'],'producer controller binding/scope/consumed')
        self.root=Path(output);self.root.mkdir(mode=0o700);c.sync_directory(self.root.parent)
        c.write_once(self.root/'plan.json',request)
        record=dict(status='FAIL',sourcePreparation=self.scope,paidCloud=False,calls=[],readFailures=0,exports=[])
        def call(action,node=None,index=None):
            m.need(self.clock()<deadline and len(record['calls'])<MAX_CALLS,'producer original deadline/call bound')
            record['calls'].append(dict(action=action,node=node,index=index))
            result=endpoint.producer(action,request,deadline,node=node,index=index)
            m.need(self.clock()<deadline,'producer late controller result');return result
        def receipt(answer):
            m.need(type(answer) is dict and answer.get('state') in ('NOT_FOUND','UNCERTAIN','SUCCEEDED','FAILED') and
                   all(answer.get(k)==v for k,v in producer.envelope(request,answer['state']).items()),'producer receipt identity')
            return answer['state']
        def failed_read(error,node,index):
            number=record['readFailures'];m.need(number<MAX_READ_FAILURES,'producer failed-read bound');record['readFailures']+=1
            folder=self.root/'failures';folder.mkdir(mode=0o700,exist_ok=True)
            raw=getattr(error,'partial_output',b'')
            m.need(type(raw) is bytes and len(raw)<=wire.CHUNK_BYTES,'producer failed-read byte bound')
            c.write_once(folder/f'read-{number:04d}.json',dict(node=node,index=index,type=type(error).__name__,message=str(error)[:2000],
                bytes=len(raw),sha256=m.sha(raw)),maximum=4096)
            with (folder/f'read-{number:04d}.bin').open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            c.sync_directory(folder)
        def download(action,node,index=None):
            for attempt in range(READ_ATTEMPTS):
                try:return call(action,node,index)
                except (ConnectionError,TimeoutError) as error:
                    failed_read(error,node,index)
                    if attempt==READ_ATTEMPTS-1:raise
                    self.sleep(min(.05,max(0,deadline-self.clock())))
        try:
            m.need(call('query')==producer.envelope(request,'NOT_FOUND'),'producer destination consumed')
            c.write_once(self.root/'prepare-intent.json',dict(requestSha256=m.sha(m.canonical(request))))
            try:answer=call('prepare')
            except (ConnectionError,TimeoutError):answer=None
            while True:
                m.need(self.clock()<deadline,'producer unresolved; no prepare replay')
                if answer is not None:
                    state=receipt(answer)
                    if state in ('SUCCEEDED','FAILED'):
                        m.need(state=='SUCCEEDED','producer preparation failed: '+str(answer));break
                self.sleep(min(.05,max(0,deadline-self.clock())))
                try:answer=call('query')
                except (ConnectionError,TimeoutError):answer=None
            summaries=answer.get('exports')
            m.need(type(summaries) is list and len(summaries)==3,'producer export count')
            for i,row in enumerate(summaries):
                m.need(set(row)=={'node','descriptorSha256','transferSha256'} and row['node']=='node-'+str(i+1) and
                       all(isinstance(row[k],str) and re.fullmatch('[0-9a-f]{64}',row[k]) for k in ('descriptorSha256','transferSha256')),
                       'producer export summary identity')
                cfg=configs[i];node=row['node'];value=download('manifest',node);wire.validate(value)
                m.need(value['config']==cfg and m.sha(m.canonical(value))==row['transferSha256'] and
                       m.sha(m.canonical(value['bootstrap']))==row['descriptorSha256'],'producer downloaded descriptor identity')
                c.write_once(self.root/(node+'-descriptor.json'),value,maximum=wire.METADATA_BYTES)
                folder=self.root/node;folder.mkdir(mode=0o700);parts=folder/'parts';parts.mkdir(mode=0o700)
                for part in value['parts']['parts']:
                    digest=hashlib.sha256();temporary=parts/(part['name']+'.partial')
                    with temporary.open('xb') as stream:
                        for chunk in (v for v in value['chunks'] if v['part']==part['name']):
                            raw=download('chunk',node,chunk['index'])
                            if not (type(raw) is bytes and len(raw)==chunk['bytes'] and m.sha(raw)==chunk['sha256']):
                                error=ValueError('producer downloaded chunk digest/size');error.partial_output=raw
                                failed_read(error,node,chunk['index']);raise error
                            stream.write(raw);digest.update(raw)
                        stream.flush();os.fsync(stream.fileno())
                    m.need(temporary.stat().st_size==part['bytes'] and digest.hexdigest()==part['sha256'],'producer downloaded part identity')
                    os.rename(temporary,parts/part['name']);c.sync_directory(parts)
                c.write_once(parts/'parts.json',value['parts']);c.write_once(folder/'bootstrap.json',value['bootstrap'])
                m.need(wire.describe(folder,row['descriptorSha256'],cfg)==value,'producer downloaded archive identity')
                wire.check_archive(folder,value)
                m.need(self.clock()<deadline,'producer download deadline')
                record['exports'].append(dict(node=node,folder=str(folder),descriptorSha256=row['descriptorSha256']))
            inventories=[c.read(self.root/(v['node']+'-descriptor.json'))['bootstrap']['files'] for v in summaries]
            m.need(all(v==inventories[0] for v in inventories),'producer downloaded source disagreement')
            record.update(status='PASS',producerReceipt=answer);return record['exports']
        except (Exception,KeyboardInterrupt) as error:
            record['failure']=dict(type=type(error).__name__,message=str(error)[:2000]);raise
        finally:c.write_once(self.root/'receipt.json',record,maximum=262144)

    def retention_files(self):
        if self.root is None:return
        c.directory(self.root)
        metadata={'plan.json','prepare-intent.json','receipt.json',*(f'node-{i}-descriptor.json' for i in (1,2,3))}
        for path in sorted(self.root.iterdir()):
            if path.name in metadata:
                m.need(path.is_file() and not path.is_symlink() and path.stat().st_size<=262144,'producer retention metadata')
                yield path.name,path.read_bytes()
            elif path.name=='failures':
                c.directory(path)
                for child in sorted(path.iterdir()):
                    match=re.fullmatch(r'read-([0-9]{4})\.(json|bin)',child.name)
                    m.need(match and int(match[1])<MAX_READ_FAILURES and child.is_file() and not child.is_symlink() and
                           child.stat().st_size<=(4096 if match[2]=='json' else wire.CHUNK_BYTES),'producer retention failure inventory')
                    if match[2]=='json':yield path.name+'/'+child.name,child.read_bytes()
            else:
                m.need(path.name in ('node-1','node-2','node-3'),'producer retention inventory');c.directory(path)
                for child in path.iterdir():
                    if child.name=='parts':
                        c.directory(child)
                        for part in child.iterdir():
                            valid=part.name=='parts.json' or re.fullmatch(r'part-000[0-8]\.bin(?:\.partial)?',part.name)
                            m.need(valid and part.is_file() and not part.is_symlink() and part.stat().st_size<=wire.parts.LIMITS['partBytes'],
                                   'producer cached part inventory')
                    else:m.need(child.name=='bootstrap.json' and child.is_file() and not child.is_symlink() and
                                child.stat().st_size<=wire.METADATA_BYTES,'producer cached metadata inventory')

"""Controller-to-receiver immutable source transfer; native cloud stays disabled."""
from pathlib import Path
import time
from . import guest_source_transfer as wire, performance_model as m, remote_command as c


class Delivery:
    offline=True
    scope='authenticated-source-chunks'
    def __init__(self, *, clock=time.monotonic, sleep=time.sleep): self.clock,self.sleep=clock,sleep

    def deliver(self, folder, digest, config, endpoint, deadline, output):
        m.need(endpoint.offline is True,'native source delivery disabled')
        return self._deliver(folder,digest,config,endpoint,deadline,output)

    def _deliver(self, folder, digest, config, endpoint, deadline, output):
        root=Path(output);root.mkdir(mode=0o700);c.sync_directory(root.parent)
        record=dict(status='FAIL',calls=[],sourceTransport=self.scope,paidCloud=not self.offline)
        try:
            value=wire.describe(folder,digest,config)
            m.need(endpoint.value['binding']==config['binding'] and endpoint.value['manifestSha256']==config['packageManifestSha256'],
                   'source endpoint package binding')
            c.write_once(root/'descriptor.json',value,maximum=wire.METADATA_BYTES)
            def exchange(action,data=b'',index=None):
                m.need(self.clock()<deadline and len(record['calls'])<4096,'source original deadline/call bound')
                record['calls'].append(dict(action=action,index=index))
                return endpoint.source(action,value,data,deadline,index)
            def once(action,data=b'',index=None):
                c.write_once(root/('intent-'+action+('-'+str(index) if index is not None else '')+'.json'),
                    dict(requestSha256=m.sha(m.canonical(value)),action=action,index=index))
                try:answer=exchange(action,data,index)
                except (ConnectionError,TimeoutError):answer=None
                while True:
                    m.need(self.clock()<deadline,'source unresolved; no replay')
                    if answer is not None:
                        count=answer.get('completedChunks');state=answer.get('state')
                        m.need(type(count) is int and 0<=count<=len(value['chunks']) and state in
                            ('NOT_FOUND','RECEIVING','READY','SUCCEEDED','FAILED','UNCERTAIN') and
                            all(answer.get(k)==v for k,v in wire.envelope(value,state,count).items()),'source receipt identity')
                        if state not in ('NOT_FOUND','UNCERTAIN'):return answer
                    self.sleep(min(.05,max(0,deadline-self.clock())))
                    try:answer=exchange('query')
                    except (ConnectionError,TimeoutError):answer=None
            m.need(exchange('query')==wire.envelope(value,'NOT_FOUND'),'source destination consumed')
            answer=once('begin');m.need(answer['state']=='RECEIVING' and answer['completedChunks']==0,'source destination consumed')
            for chunk in value['chunks']:
                path=Path(folder)/'parts'/chunk['part']
                m.need(path.is_file() and not path.is_symlink(),'source sender part type')
                with path.open('rb') as stream:stream.seek(chunk['offset']);raw=stream.read(chunk['bytes'])
                m.need(len(raw)==chunk['bytes'] and m.sha(raw)==chunk['sha256'],'source sender bytes changed')
                answer=once('chunk',raw,chunk['index'])
                m.need(answer['state'] in ('RECEIVING','READY') and answer['completedChunks']==chunk['index']+1,'source chunk failed: '+str(answer))
            answer=once('finish')
            m.need(answer['state']=='SUCCEEDED' and answer['completedChunks']==len(value['chunks']) and
                   answer['descriptorSha256']==digest,'source finished identity')
            record.update(status='PASS',receipt=answer)
            return dict(config=config,descriptorSha256=digest,sourceTransferSha256=m.sha(m.canonical(value)))
        except (Exception,KeyboardInterrupt) as error:
            record['failure']=dict(type=type(error).__name__,message=str(error)[:2000]);raise
        finally:c.write_once(root/'receipt.json',record,maximum=262144)

    @staticmethod
    def retention_files(root):
        root=c.directory(root)
        allowed={'descriptor.json','receipt.json','intent-begin.json','intent-finish.json',*(f'intent-chunk-{i}.json' for i in range(65))}
        for path in sorted(root.iterdir()):
            m.need(path.name in allowed and path.is_file() and not path.is_symlink() and path.stat().st_size<=262144,'source transfer retention inventory')
            yield path.name,path.read_bytes()

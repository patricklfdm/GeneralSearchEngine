"""Real SSH binary source import/public seal without a privileged mount namespace.

One receiver, shared host, synthetic cloud identity. The producer's original path
is removed before transfer, its retained export path before import. The separate
owned qualification covers three exact-path independent mounts and cleanup.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import signal
import sys
import tempfile
import time
import uuid
from scripts import ci_v51_bundle as build
from . import cloud_package as package, cloud_guest as guest, guest_transport as transport
from . import guest_package_qualification as packaged, guest_source_delivery as binary, guest_bootstrap as boot
from . import performance_model as m, remote_command as c
from .guest_ssh_qualification import Server, ROOT


def run(output,bundle,source,*,producer_source=False):
    root=Path(output).resolve();root.mkdir(parents=True,mode=0o700,exist_ok=False)
    bundle=Path(bundle).resolve();manifest=package.verify(bundle/'package',source)
    m.need(manifest['buildBinding']==build.binding(ROOT,source),'source qualification checkout/build mismatch')
    receipt=dict(schema='gse-v51-source-qualification-v1',status='FAIL',source=source,buildBinding=manifest['buildBinding'],
        execution='loopback-ssh-source-import',realSshExecuted=True,publicBootstrapVerified=False,engineWorkloadExecuted=False,
        providerIdentity='modeled-fixtures',filesystem='shared-local-single-receiver',paidCloud=False,fullRemoteQualification=False)
    try:
        with tempfile.TemporaryDirectory(prefix='gse-v51-source-keys-',dir=ROOT/'target') as private,Server(private,root) as server:
            deadline=time.monotonic()+600;attempt=uuid.uuid4().hex;mode=package.MODES[2]
            cell=root/'packages'/(attempt+'-node-1')/mode
            cfg=dict(schema='gse-v51-guest-service-v1',execution=guest.EXECUTION,
                binding=c.binding(source,m.sha((bundle/'guest.tar.gz').read_bytes()),attempt,'node-1'),
                packageManifestSha256=m.sha((bundle/'package/manifest.json').read_bytes()),root=str(cell),mode=mode,
                hosts=['127.0.0.2','127.0.0.3','127.0.0.4'],ports=[23001,23002,23003],groupId=str(uuid.uuid4()))
            p=packaged.Delivery(root/'packages',bundle,server);p.install(cfg,deadline);ep=p.endpoints[attempt+'-node-1'][0]
            if producer_source:
                from .guest_producer_source import RemoteSource
                configs=[deepcopy(cfg) for _ in range(3)]
                for n,value in enumerate(configs,1):value['binding']['node']='node-'+str(n)
                producer=ep.producer;lost_chunks=set()
                def lose_producer(action,request,end,*,node=None,index=None):
                    answer=producer(action,request,end,node=node,index=index)
                    if action=='prepare':raise ConnectionError('discarded preparation reply')
                    if action=='chunk' and index==0 and node not in lost_chunks:
                        lost_chunks.add(node);error=ConnectionError('interrupted producer chunk');error.partial_output=answer[:len(answer)//2];raise error
                    return answer
                ep.producer=lose_producer
                exports=RemoteSource().prepare(configs,deadline,endpoint=ep,output=root/'producer-download')
                folder=Path(exports[0]['folder']);digest=exports[0]['descriptorSha256']
                producer_root=Path(ep.parent)/(attempt+'-node-1')/'source-producer'
                (producer_root/'exports').rename(producer_root/'hidden-exports')
                receipt['sourcePreparation']='authenticated-producer-download'
            else:
                raw=transport.process([sys.executable,'-I',str(bundle/'package/guest.py'),'bootstrap','prepare','--deadline',str(deadline)],
                    m.canonical(cfg),deadline,maximum=65536)
                answer=m.strict_json(raw);m.need(answer['state']=='SUCCEEDED','source public preparation')
                cell.rename(root/'producer');folder=root/'producer/agents/node-1/bootstrap/node-1';digest=answer['result']['bootstrap'][0]['descriptorSha256']
            original=ep.source
            def lost(action,value,data,end,index=None):
                result=original(action,value,data,end,index)
                if action in ('begin','chunk','finish'):raise ConnectionError('discarded original source receipt')
                return result
            ep.source=lost
            request=binary.Delivery().deliver(folder,digest,cfg,ep,deadline,root/'controller')
            folder.rename(folder.with_name('hidden-node-1-export'))
            m.need(not folder.exists() and 'folder' not in request,'source path not removed from admission')
            for phase in ('install','seal'):
                m.need(ep.bootstrap('query-'+phase,request,deadline)==dict(state='NOT_FOUND'),'bootstrap destination consumed')
                result=ep.bootstrap(phase,request,deadline)
                m.need(result['state']=='SUCCEEDED' and ep.bootstrap('query-'+phase,request,deadline)==result,'bootstrap original receipt')
            ready=boot.check_ready(cell,cfg,sealed=True)
            m.need(ready['files']==c.read(root/'controller/descriptor.json')['bootstrap']['files'],'source imported inventory')
            chunks=len(c.read(root/'controller/descriptor.json')['chunks'])
            counts={k:sum(v['action']=='source-'+k for v in ep.calls) for k in ('begin','chunk','finish','query')}
            m.need(counts==dict(begin=1,chunk=chunks,finish=1,query=chunks+3),'source lost-reply writes/queries')
            receipt.update(status='PASS',tools=server.versions,sourceCalls=counts,producerPathsHidden=True,
                publicBootstrapVerified=True,identity=result['result']['identity'],packageTransfers=p.receipts)
            if producer_source:
                record=c.read(root/'producer-download/receipt.json')
                expected=sum(len(c.read(root/f'producer-download/node-{n}-descriptor.json')['chunks']) for n in (1,2,3))
                counts={k:sum(v['action']=='producer-'+k for v in ep.calls) for k in ('prepare','query','manifest','chunk')}
                m.need(counts==dict(prepare=1,query=2,manifest=3,chunk=expected+3) and record['readFailures']==3,'producer qualification read/write cardinality')
                receipt['producerCalls']=counts
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error)[:3000]);raise
    finally:c.write_once(root/'receipt.json',receipt)
    print(m.canonical(receipt).decode(),flush=True);return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--bundle',required=True);p.add_argument('--source',required=True)
    p.add_argument('--producer-source',action='store_true');args=p.parse_args()
    def terminate(*_):raise TimeoutError('source qualification terminated')
    signal.signal(signal.SIGTERM,terminate);run(args.output,args.bundle,args.source,producer_source=args.producer_source)

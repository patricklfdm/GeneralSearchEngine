"""Full package transfer and persistent services over real loopback SSH, no GCP."""
import argparse
from pathlib import Path
import signal
import tempfile
from . import guest_package_delivery as d, guest_qualification as q
from . import cloud_package as package, performance_model as m, remote_command as c
from .guest_ssh_qualification import Server


class Delivery:
    def __init__(self, root, bundle, server):
        self.root,self.bundle,self.server=Path(root),Path(bundle),server
        self.root.mkdir(mode=0o700); self.endpoints={}; self.receipts=[]
        self.manifest=package.verify(self.bundle/'package')
    def install(self, config, deadline):
        binding=config['binding']; key=binding['attempt']+'-'+binding['node']
        parent=self.root/key; parent.mkdir(mode=0o700); route=self.server.endpoint(parent)
        value=d.describe(self.bundle/'guest.tar.gz',self.manifest,binding,
                         dict(instanceId='123',diskId='456',attempt=binding['attempt'],node=int(binding['node'][-1])),
                         m.sha(m.canonical(self.server.access)))
        class Loopback(d.Endpoint):
            offline=True
            def argv(self,remote): return route.argv(remote)
        endpoint=Loopback(route.target,parent,value)
        c.write_once(parent/'descriptor.json',value)
        # Each transfer loses its first completed chunk response and its final
        # install response. Queries must observe those writes, never repeat them.
        original=endpoint.exchange; lost=set()
        def exchange(action,data,end,index=None):
            result=original(action,data,end,index)
            if (action=='part' and index==0 or action=='finish') and action not in lost:
                lost.add(action); raise ConnectionError('discarded authenticated package response')
            return result
        endpoint.exchange=exchange
        try:
            answer=d.deliver(endpoint,self.bundle/'guest.tar.gz',deadline)
            counts={action:sum(row['action']==action for row in endpoint.calls) for action in ('begin','part','finish','query')}
            m.need(counts==dict(begin=1,part=len(value['parts']),finish=1,query=2),'package transfer replay/count')
            row=dict(node=binding['node'],mode=config['mode'],state=answer['state'],parts=len(value['parts']),
                     archiveBytes=value['archiveBytes'],calls=counts,installed=answer['installed'])
            self.receipts.append(row); self.endpoints[key]=(endpoint,route)
            return Path(answer['installed']['package'])
        finally:
            c.write_once(parent/'transport.json',dict(calls=endpoint.calls,failures=endpoint.failures,deadline=endpoint.budget))
    def client(self,config):
        endpoint,route=self.endpoints[config['binding']['attempt']+'-'+config['binding']['node']]
        return endpoint.client(config)


def run(output,bundle,source,*,healthy=False):
    root=Path(output).resolve(); root.mkdir(parents=True,mode=0o700)
    receipt=dict(schema='gse-v51-package-service-qualification-v1',status='FAIL',source=source,
        execution='loopback-openssh-package-services',realSshExecuted=True,engineWorkloadExecuted=True,
        providerIdentity='modeled-fixtures',filesystem='shared-local',realBlockDeviceWritten=False,paidCloud=False,fullRemoteQualification=False)
    try:
        # sshd StrictModes rejects even a sticky /tmp ancestor for authorized_keys.
        # Use the existing private-key location outside the uploaded evidence tree.
        with tempfile.TemporaryDirectory(prefix='gse-v51-package-keys-',dir=Path(__file__).resolve().parents[2]/'target') as private, Server(private,root) as server:
            delivery=Delivery(root/'deliveries',bundle,server); receipt['tools']=server.versions; receipt['deliveries']=delivery.receipts
            result=q.run(root/'services',bundle,source,delivery=delivery,healthy=healthy)
            m.need(result['status']=='PASS' and len(delivery.receipts)==7,'delivered service member set')
            receipt.update(status='PASS',healthyWindows=healthy,calls=sum(v['calls'] for v in result['cases']),modes=len(result['cases']),warmupCalls=sum(v['warmupCalls'] for v in result['cases']),cleanupErrors=result['cleanupErrors'])
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error)[:3000]); raise
    finally: c.write_once(root/'receipt.json',receipt)
    print(m.canonical(receipt).decode(),flush=True); return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--source',required=True);p.add_argument('--healthy',action='store_true')
    a=p.parse_args()
    def terminate(*_): raise TimeoutError('package qualification terminated')
    signal.signal(signal.SIGTERM,terminate)
    run(a.output,a.bundle,a.source,healthy=a.healthy)

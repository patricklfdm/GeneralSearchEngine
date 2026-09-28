"""Owned startup with modeled volumes and actual SSH-delivered idle services.

Cloud facts/accounts/block operations remain explicit fixtures. No JVM workload,
IAP, privileged disk write or paid resource is exercised by this gate.
"""
import argparse
import ctypes
import os
from pathlib import Path
import signal
import tempfile
import time
from copy import deepcopy
from scripts import ci_v51_bundle as build
from . import cloud_authority as a, cloud_fake, cloud_gcp, cloud_package as package, cloud_runner
from . import guest_startup, guest_startup_fake, guest_owned_services as owned, guest_package_delivery as delivery
from . import performance_model as m, remote_command as c
from . import cloud_guest as guest
from .guest_ssh_qualification import Server, ROOT
from .guest_transport import ssh_args


class Clock:
    def nanos(self): return time.monotonic_ns()
    def seconds(self): return time.monotonic()
    def wall(self): return 10001  # Explicit offline approval fixture, not current cloud admission.
    def sleep(self, seconds): time.sleep(seconds)


def run(output, bundle, source):
    root=Path(output).resolve(); root.mkdir(parents=True,mode=0o700,exist_ok=False)
    bundle=Path(bundle).resolve(); manifest=package.verify(bundle/'package',source)
    m.need(manifest['buildBinding']==build.binding(ROOT,source),'owned qualification checkout/build mismatch')
    packed=package.read(bundle/'receipt.json')
    m.need(packed['status']=='PASS' and packed['source']==source and
           m.sha((bundle/'guest.tar.gz').read_bytes())==packed['archiveSha256'],'owned qualified package receipt')
    m.need(ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0,'owned qualification subreaper')
    receipt=dict(schema='gse-v51-owned-service-qualification-v1',status='FAIL',source=source,
        execution='owned-model-loopback-ssh-idle-services',realSshExecuted=True,engineWorkloadExecuted=False,
        providerIdentity='modeled-fixtures',volumeObservations='offline-block-model',filesystem='shared-local',
        realBlockDeviceWritten=False,paidCloud=False,fullRemoteQualification=False)
    services=None; endpoints=[]
    try:
        with tempfile.TemporaryDirectory(prefix='gse-v51-owned-keys-',dir=ROOT/'target') as private, Server(private,root) as server:
            req,pre,approval,_,http,store,old,_=guest_startup_fake.fixture(Path(private)/'owner')
            req.update(source=source,bundleSha256=m.sha((bundle/'guest.tar.gz').read_bytes()))
            sha=a.validate_request(req); pre.update(requestSha256=sha); pre['cleanup']['source']=source
            approval.update(requestSha256=sha,preflightSha256=m.sha(m.canonical(pre)))
            clock=Clock(); old.api.clock=clock.seconds
            provider=cloud_gcp.Compute(old.config,req,old.api,guest_access=old.guest_access,sleep=clock.sleep)
            transport=guest_startup_fake.Transport(clock)
            server.authorized.write_text('restrict '+provider.guest_access['publicKey']+'\n')
            original=http.hook
            def hook(method,path,query,body):
                if method=='GET' and path.path.endswith('/getGuestAttributes'):
                    return http.reply(dict(queryPath='hostkeys/',queryValue=dict(items=[dict(namespace='hostkeys',key='ssh-ed25519',value=server.host['publicKey'].split()[1])])))
                return original(method,path,query,body)
            http.hook=hook
            mounts={n:str(root/f'mount-{n}') for n in (1,2,3)}
            for path in mounts.values(): Path(path).mkdir(mode=0o700)
            class Loopback(delivery.Endpoint):
                offline=True
                def argv(self,remote):
                    # Keep the provider/access descriptor; only route the offline
                    # transport to this ephemeral daemon and existing local account.
                    target=deepcopy(self.target); target['user']=server.user
                    argv=ssh_args(target,remote)
                    argv=[v if not v.startswith('ProxyCommand=') else 'ProxyCommand=none' for v in argv]
                    return [*argv[:-2],'-o','Hostname=127.0.0.1','-p',str(server.port),*argv[-2:]]
            def endpoint(target,parent,value):
                ep=Loopback(target,parent,value); endpoints.append(ep)
                exchange=ep.exchange; lost=set()
                def lose_reply(action,data,end,index=None):
                    answer=exchange(action,data,end,index)
                    if (action=='part' and index==0 or action=='finish') and action not in lost:
                        lost.add(action); raise ConnectionError('discarded completed package reply')
                    return answer
                ep.exchange=lose_reply; original_client=ep.client
                def client(config):
                    cl=original_client(config); start=cl.start; shutdown=cl.shutdown
                    def lost_start(end): start(end); raise ConnectionError('discarded launch reply')
                    def lost_stop(end): shutdown(end); raise ConnectionError('discarded shutdown reply')
                    cl.start=lost_start; cl.shutdown=lost_stop; return cl
                ep.client=client; return ep
            services=owned.Services(provider,bundle/'guest.tar.gz',endpoint,qualification_mounts=mounts)
            startup=guest_startup.Prepare(provider,transport,Path(private)/'owner/identity',root/'startup',services=services)
            probe=cloud_fake.Probe(root/'probe',clock)
            result=cloud_runner.Runner(store,provider,probe,root/'controller',clock=clock.nanos,wall=clock.wall,startup=startup).run(req,pre,approval)
            m.need(result['status']=='PASS' and result['leaseReleased'] and not http.resources,'owned controller completion: '+str(result['errors']))
            m.need(len(services.clients)==3 and all(b.formats==1 for b in transport.blocks),'owned service/format cardinality')
            rows=[]
            for ep in endpoints:
                counts={key:sum(v['action']==key for v in ep.calls) for key in ('clock','begin','part','finish','query')}
                m.need(counts==dict(clock=1,begin=1,part=len(ep.value['parts']),finish=1,query=2),'owned package write/query cardinality')
                rows.append(dict(node=ep.value['binding']['node'],archiveBytes=ep.value['archiveBytes'],calls=counts))
            receipt.update(status='PASS',tools=server.versions,packages=rows,services=len(services.clients),
                modeledControlCells=result['evidence']['cells'],retainedObjects=len(http.objects),
                reservedCostMicrousd=a.inspect_ledger(store.get(a.LEDGER)[1])[0],leaseReleased=result['leaseReleased'])
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error)[:3000]); raise
    finally:
        errors=[]
        if services is not None:
            # Runner already issued at most one shutdown per attempted launch.
            # Reap exact observed PIDs; never send another service mutation here.
            for node,client,cfg in services.clients:
                try:
                    path=guest.validate(cfg)/'ready.json'
                    if not path.exists(): raise ValueError('no observed PID for attempted service; inspect startup evidence')
                    state=c.read(path)
                    m.need(state['configSha256']==m.sha(m.canonical(cfg)),'owned reap identity')
                    pid=state['pid']; until=time.monotonic()+10
                    while True:
                        waited,status=os.waitpid(pid,os.WNOHANG)
                        if waited: break
                        m.need(time.monotonic()<until,'owned service reap deadline'); time.sleep(.05)
                    m.need(os.waitstatus_to_exitcode(status)==0,'owned service exit status')
                except BaseException as error: errors.append(str(error))
        receipt['cleanupErrors']=errors
        if errors: receipt['status']='FAIL'
        c.write_once(root/'receipt.json',receipt)
    m.need(receipt['status']=='PASS','owned service qualification failed')
    print(m.canonical(receipt).decode(),flush=True); return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--source',required=True)
    args=p.parse_args()
    def terminate(*_): raise TimeoutError('owned qualification terminated')
    signal.signal(signal.SIGTERM,terminate)
    run(args.output,args.bundle,args.source)

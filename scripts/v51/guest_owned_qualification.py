"""Owned startup with modeled volumes and actual SSH-delivered idle services.

Cloud facts/accounts/block operations remain explicit fixtures. --workload adds
one automatic healthy tape; IAP, physical disks and paid resources remain closed.
"""
import argparse
import ctypes
import os
from pathlib import Path
import signal
import sys
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


def run(output, bundle, source, *, bootstrap=False, allow_sudo=False, source_transfer=False, producer_source=False, workload=False):
    m.need(not source_transfer or bootstrap,'source transfer requires bootstrap qualification')
    m.need(not producer_source or source_transfer,'producer requires source transfer qualification')
    m.need(not workload or producer_source,'owned workload requires authenticated source preparation')
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
    services=None; endpoints=[]; views=None; workload_submits=[]; lost_windows=[]
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
            if bootstrap:
                from .guest_isolation import Views
                from .guest_bootstrap_source import ViewSource
                from .guest_owned_bootstrap import Bootstrap
                mount=root/'guest-mount'; mount.mkdir(mode=0o700)
                # The package receiver authenticates ancestor ownership. Keep
                # native UIDs; a user namespace would map root-owned ancestors away.
                views=Views(root/'mount-views',mount,allow_sudo,preserve_uid=True)
                mounts={n:str(mount) for n in (1,2,3)}
                from .guest_producer_source import RemoteSource
                source_adapter=RemoteSource() if producer_source else ViewSource(views,bundle/'package')
                from .guest_source_delivery import Delivery
                admitted_bootstrap=Bootstrap(source_adapter,delivery=Delivery() if source_transfer else None)
                receipt.update(execution='owned-model-loopback-ssh-local-bootstrap',filesystem='independent-mount-views',
                    sourcePreparation=source_adapter.scope,sourceTransport=admitted_bootstrap.delivery.scope if source_transfer else source_adapter.scope,
                    sudoNamespace=views.sudo,producerPathsHidden=False)
            else:
                mounts={n:str(root/f'mount-{n}') for n in (1,2,3)}
                for path in mounts.values(): Path(path).mkdir(mode=0o700)
                admitted_bootstrap=None
            class Loopback(delivery.Endpoint):
                offline=True
                def argv(self,remote):
                    # Keep the provider/access descriptor; only route the offline
                    # transport to this ephemeral daemon and existing local account.
                    target=deepcopy(self.target); target['user']=server.user
                    if views is not None:
                        remote=views.args(self.value['binding']['node'],[sys.executable,*remote[1:]])
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
                    cl.start=lost_start; cl.shutdown=lost_stop
                    if workload:
                        submit=cl.submit
                        def lose_window(value,end):
                            workload_submits.append(dict(node=config['binding']['node'],request=value))
                            answer=submit(value,end)
                            if value['command']=='window':
                                lost_windows.append(value['commandId'])
                                raise ConnectionError('discarded original workload submission reply')
                            return answer
                        cl.submit=lose_window
                    return cl
                ep.client=client
                original_bootstrap=ep.bootstrap
                def lost_bootstrap(action,request,end):
                    if source_transfer and not producer_source and not receipt['producerPathsHidden']:
                        # All three deliveries must finish before the first import.
                        for n in (1,2,3):
                            record=c.read(root/f'startup/services/bootstrap/node-{n}-transfer/receipt.json')
                            m.need(record['status']=='PASS','source transfer barrier')
                        producer=views.root/'producer'/guest.validate(request['config']).relative_to(views.cell)
                        (producer/'bootstrap').rename(producer/'hidden-bootstrap-exports')
                        m.need(not (producer/'bootstrap').exists(),'producer export path remained visible')
                        receipt['producerPathsHidden']=True
                    answer=original_bootstrap(action,request,end)
                    if action in ('install','seal'): raise ConnectionError('discarded completed bootstrap reply')
                    return answer
                ep.bootstrap=lost_bootstrap
                original_source=ep.source; source_lost=set()
                def lose_source(action,request,data,end,index=None):
                    if producer_source and not receipt['producerPathsHidden']:
                        record=c.read(root/'startup/services/bootstrap/producer/receipt.json')
                        m.need(record['status']=='PASS' and len(record['exports'])==3,'producer download barrier')
                        first=endpoints[0].value
                        producer=views.root/'node-1'/(first['binding']['attempt']+'-node-1')/'source-producer'
                        (producer/'exports').rename(producer/'hidden-exports')
                        receipt['producerPathsHidden']=True
                    answer=original_source(action,request,data,end,index)
                    if (action in ('begin','finish') or action=='chunk' and index==0) and action not in source_lost:
                        source_lost.add(action);raise ConnectionError('discarded completed source reply')
                    return answer
                ep.source=lose_source
                original_producer=ep.producer;read_lost=set()
                def lose_producer(action,request,end,*,node=None,index=None):
                    answer=original_producer(action,request,end,node=node,index=index)
                    if action=='prepare':raise ConnectionError('discarded completed source preparation reply')
                    if action=='chunk' and index==0 and node not in read_lost:
                        read_lost.add(node);error=ConnectionError('interrupted immutable source download')
                        error.partial_output=answer[:len(answer)//2];raise error
                    return answer
                ep.producer=lose_producer;return ep
            services=owned.Services(provider,bundle/'guest.tar.gz',endpoint,qualification_mounts=mounts,bootstrap=admitted_bootstrap,
                qualification_hosts=['127.0.0.2','127.0.0.3','127.0.0.4'] if workload else None)
            startup=guest_startup.Prepare(provider,transport,Path(private)/'owner/identity',root/'startup',services=services)
            from .guest_owned_workload import Probe, SCOPE
            probe=Probe(services,root/'probe') if workload else cloud_fake.Probe(root/'probe',clock)
            result=cloud_runner.Runner(store,provider,probe,root/'controller',clock=clock.nanos,wall=clock.wall,startup=startup,
                qualification=SCOPE if workload else None).run(req,pre,approval)
            if workload:
                receipt.update(execution=SCOPE,engineWorkloadExecuted=result['engineWorkloadExecuted'],
                    physicalHistoryQualified=False,networkMapping='qualification-loopback',workload=result.get('evidence'))
            m.need(result['status']=='PASS' and result['leaseReleased'] and not http.resources,'owned controller completion: '+str(result['errors']))
            if workload:
                requests=[v['request'] for v in workload_submits]
                m.need(len(lost_windows)==5 and len({q['commandId'] for q in requests})==len(requests),
                       'owned workload submission replay/cardinality')
                c.write_once(root/'workload-submissions.json',workload_submits)
                receipt['workloadSubmitReplyLosses']=len(lost_windows)
            m.need(len(services.clients)==3 and all(b.formats==1 for b in transport.blocks),'owned service/format cardinality')
            rows=[]
            for ep in endpoints:
                counts={key:sum(v['action']==key for v in ep.calls) for key in ('clock','begin','part','finish','query')}
                m.need(counts==dict(clock=1,begin=1,part=len(ep.value['parts']),finish=1,query=2),'owned package write/query cardinality')
                rows.append(dict(node=ep.value['binding']['node'],archiveBytes=ep.value['archiveBytes'],calls=counts))
                if bootstrap:
                    for phase in ('install','seal'):
                        m.need(sum(v['action']=='bootstrap-'+phase for v in ep.calls)==1 and
                               sum(v['action']=='bootstrap-query-'+phase for v in ep.calls)==2,'owned bootstrap write/query cardinality')
                if source_transfer:
                    n=ep.value['binding']['node'];record=c.read(root/f'startup/services/bootstrap/{n}-transfer/descriptor.json')
                    counts={k:sum(v['action']=='source-'+k for v in ep.calls) for k in ('begin','chunk','finish','query')}
                    m.need(counts==dict(begin=1,chunk=len(record['chunks']),finish=1,query=4),'owned source write/query cardinality')
                    rows[-1]['sourceCalls']=counts
            if bootstrap:
                from . import guest_bootstrap as boot
                completed=c.read(root/'startup/services/bootstrap/receipt.json')
                m.need(completed['status']=='PASS' and len(completed['members'])==3,'owned local bootstrap completion')
                for node,_,cfg in services.clients:
                    cell=views.root/('node-'+str(node))/Path(cfg['root']).relative_to(views.cell)
                    m.need((cell/boot.LOCAL_READY).is_file() and all(not (cell/('node-'+str(other))).exists() for other in (1,2,3) if other!=node),
                           'owned bootstrap live neighbour storage')
                receipt['bootstrap']=completed
            if producer_source:
                record=c.read(root/'startup/services/bootstrap/producer/receipt.json')
                expected=sum(len(c.read(root/f'startup/services/bootstrap/producer/node-{n}-descriptor.json')['chunks']) for n in (1,2,3))
                counts={k:sum(v['action']=='producer-'+k for v in endpoints[0].calls) for k in ('prepare','query','manifest','chunk')}
                m.need(counts==dict(prepare=1,query=2,manifest=3,chunk=expected+3) and record['readFailures']==3,'producer original operation/read cardinality')
                receipt['producerCalls']=counts
            receipt.update(status='PASS',tools=server.versions,packages=rows,services=len(services.clients),
                qualifiedCells=result['evidence']['cells'] if workload else [],
                modeledControlCells=[] if workload else result['evidence']['cells'],retainedObjects=len(http.objects),
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
                    if views is not None: path=views.root/('node-'+str(node))/path.relative_to(views.cell)
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
    p.add_argument('--bootstrap',action='store_true');p.add_argument('--allow-sudo-namespace',action='store_true')
    p.add_argument('--source-transfer',action='store_true')
    p.add_argument('--producer-source',action='store_true')
    p.add_argument('--workload',action='store_true')
    args=p.parse_args()
    def terminate(*_): raise TimeoutError('owned qualification terminated')
    signal.signal(signal.SIGTERM,terminate)
    run(args.output,args.bundle,args.source,bootstrap=args.bootstrap,allow_sudo=args.allow_sudo_namespace,
        source_transfer=args.source_transfer,producer_source=args.producer_source,workload=args.workload)

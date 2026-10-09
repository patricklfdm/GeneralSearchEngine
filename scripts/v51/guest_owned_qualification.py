"""Owned startup with modeled volumes and actual SSH-delivered idle services.

Cloud facts/accounts/block operations remain explicit fixtures. --workload adds
one selected healthy tape; IAP, physical disks and paid resources remain closed.
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


def require_completion(result, resources):
    m.need(result['status']=='PASS' and result['leaseReleased'] and not resources,
           'owned controller completion: '+str(dict(errors=result['errors'],
               workloadErrors=(result.get('evidence') or {}).get('errors',[]))))


def run(output, bundle, source, *, bootstrap=False, allow_sudo=False, source_transfer=False, producer_source=False, workload=False, physical=False, backup=False, mode=package.MODES[2], three_mode=False, faults=False, fault_local=False, experiment=False, maintenance=False, network=False, failure_drill=False, canonical_cell=None):
    if canonical_cell is not None:
        from . import guest_workload_spec as rich
        m.need((mode,canonical_cell) in rich.CASES and not any((bootstrap,source_transfer,producer_source,workload,physical,backup,
            three_mode,faults,fault_local,experiment,maintenance,network,failure_drill)), 'canonical tape has its own offline scope')
        bootstrap=source_transfer=producer_source=workload=True
        physical=backup=mode in package.MODES[1:]
    m.need(not failure_drill or not any((experiment,maintenance,network,faults,three_mode,bootstrap,source_transfer,producer_source,workload,physical,backup)), 'failure drill has its own scope')
    m.need(not network or not any((experiment,maintenance,faults,three_mode,bootstrap,source_transfer,producer_source,workload,physical,backup)), 'network faults have their own scope')
    m.need(not (experiment or maintenance) or not any((faults,three_mode,bootstrap,source_transfer,producer_source,workload,physical,backup)) and not (experiment and maintenance), 'complete experiment/maintenance has its own scope')
    if maintenance or network or failure_drill:faults=True
    if experiment:three_mode=bootstrap=source_transfer=producer_source=workload=physical=backup=True
    m.need(not fault_local or faults, 'shared local fault scope')
    m.need(not faults or not any((three_mode,bootstrap,source_transfer,producer_source,workload,physical,backup)) and mode==package.MODES[2], 'fault qualification has its own scope')
    m.need(not three_mode or bootstrap and source_transfer and producer_source and workload and physical and backup,
           'three-mode qualification requires complete bootstrap/history/backup')
    m.need(mode in package.MODES and (mode==package.MODES[2] or workload),'owned qualification mode/scope')
    m.need(not physical or mode in package.MODES[1:],'owned physical evidence requires replicated mode')
    m.need(not backup or physical,'backup requires physical evidence')
    m.need(not physical or workload,'physical evidence requires owned workload')
    m.need(not source_transfer or bootstrap,'source transfer requires bootstrap qualification')
    m.need(not producer_source or source_transfer,'producer requires source transfer qualification')
    m.need(not workload or producer_source,'owned workload requires authenticated source preparation')
    nodes=package.experiment_nodes(mode)
    root=Path(output).resolve(); root.mkdir(parents=True,mode=0o700,exist_ok=False)
    bundle=Path(bundle).resolve(); manifest=package.verify(bundle/'package',source)
    m.need(manifest['buildBinding']==build.binding(ROOT,source),'owned qualification checkout/build mismatch')
    packed=package.read(bundle/'receipt.json')
    m.need(packed['status']=='PASS' and packed['source']==source and
           m.sha((bundle/'guest.tar.gz').read_bytes())==packed['archiveSha256'],'owned qualified package receipt')
    m.need(ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0,'owned qualification subreaper')
    receipt=dict(schema='gse-v51-owned-service-qualification-v1',status='FAIL',source=source,mode=mode,
        execution='owned-model-loopback-ssh-idle-services',realSshExecuted=True,engineWorkloadExecuted=False,
        providerIdentity='modeled-fixtures',volumeObservations='offline-block-model',filesystem='shared-local',
        realBlockDeviceWritten=False,paidCloud=False,fullRemoteQualification=False)
    if producer_source:receipt['producerPathsHidden']=False
    services=None; endpoints=[]; views=None; workload_submits=[]; lost_submissions=[]
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
            if bootstrap or faults and not fault_local:
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
                    if workload or faults:
                        submit=cl.submit
                        def lose_workload_reply(value,end):
                            workload_submits.append(dict(mode=config['mode'],node=config['binding']['node'],request=value,**({'faultCell':config['faultCell']} if 'faultCell' in config else {})))
                            answer=submit(value,end)
                            activate=(config['mode']==package.MODES[1] and value['command']=='fault' and value['payload']==dict(action='activate'))
                            if faults or 'faultCell' in config or value['command']=='window' or activate or backup and value['command'] in ('backup','restore-backup'):
                                lost_submissions.append(value['commandId'])
                                raise ConnectionError('discarded original workload submission reply')
                            return answer
                        cl.submit=lose_workload_reply
                    return cl
                ep.client=client
                original_bootstrap=ep.bootstrap
                def lost_bootstrap(action,request,end):
                    if source_transfer and not producer_source and not receipt['producerPathsHidden']:
                        # Every selected delivery must finish before the first import.
                        for n in nodes:
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
                        producer_root=(root/'startup/services'/package.MODES[0]/'bootstrap/producer/original') if three_mode else root/'startup/services/bootstrap/producer'
                        record=c.read(producer_root/'receipt.json')
                        m.need(record['status']=='PASS' and len(record['exports'])==(1 if three_mode else len(nodes)),'producer download barrier')
                        first=endpoints[0].value
                        producer=views.root/'node-1'/(first['binding']['attempt']+'-node-1')/'source-producer'
                        (producer/'exports').rename(producer/'hidden-exports')
                        receipt['producerPathsHidden']=True
                    answer=original_source(action,request,data,end,index)
                    key=(request['config']['mode'],action)
                    if (action in ('begin','finish') or action=='chunk' and index==0) and key not in source_lost:
                        source_lost.add(key);raise ConnectionError('discarded completed source reply')
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
            from . import guest_owned_three_mode as batch
            from . import guest_owned_faults as fault_batch
            from . import guest_owned_experiment as experiment_batch
            from . import guest_owned_network as network_batch
            from . import guest_owned_drill as drill_batch
            if failure_drill:service_type=drill_batch.Services
            elif experiment:service_type=experiment_batch.Services
            elif network:service_type=network_batch.Services
            elif maintenance:service_type=fault_batch.MaintenanceServices
            elif faults:service_type=fault_batch.Services
            elif three_mode:service_type=batch.Services
            else:service_type=owned.Services
            options={} if three_mode or faults else dict(mode=mode,bootstrap=admitted_bootstrap)
            if canonical_cell is not None:options['canonical_cell']=canonical_cell
            services=service_type(provider,bundle/'guest.tar.gz',endpoint,qualification_mounts=mounts,
                qualification_hosts=['127.0.0.2','127.0.0.3','127.0.0.4'] if workload or faults else None,**options)
            if faults:receipt.update(mode=service_type.mode,sourcePreparation='per-guest-public-empty-bootstrap')
            if three_mode:receipt.update(mode=batch.MODE,sourcePreparation='authenticated-shared-source')
            if experiment:receipt.update(mode=experiment_batch.MODE)
            startup=guest_startup.Prepare(provider,transport,Path(private)/'owner/identity',root/'startup',services=services)
            from .guest_owned_workload import Probe
            if failure_drill:probe=drill_batch.Probe(services,root/'probe')
            elif experiment:probe=experiment_batch.Probe(services,root/'probe')
            elif network:probe=network_batch.Probe(services,root/'probe')
            elif maintenance:probe=fault_batch.MaintenanceProbe(services,root/'probe')
            elif faults:probe=fault_batch.Probe(services,root/'probe')
            elif three_mode:probe=batch.Probe(services,root/'probe')
            elif workload:probe=Probe(services,root/'probe',physical=physical,backup=backup)
            else:probe=cloud_fake.Probe(root/'probe',clock)
            result=cloud_runner.Runner(store,provider,probe,root/'controller',clock=clock.nanos,wall=clock.wall,startup=startup,
                qualification=probe.scope if workload or faults else None).run(req,pre,approval)
            if workload or faults:
                receipt.update(execution=probe.scope,engineWorkloadExecuted=result['engineWorkloadExecuted'],
                    backupRestoreQualified=result.get('evidence',{}).get('backupRestoreQualified',False),
                    physicalHistoryQualified=result.get('evidence',{}).get('physicalHistoryQualified',False),networkMapping='qualification-loopback',workload=result.get('evidence'))
            require_completion(result, http.resources)
            if faults:
                requests=[v['request'] for v in workload_submits]
                m.need(len(requests)==len(lost_submissions)==len({r['commandId'] for r in requests}), 'fault command replay/lost reply coverage')
                c.write_once(root/'workload-submissions.json',workload_submits)
                receipt['workloadSubmitReplyLosses']=len(lost_submissions)
            if workload:
                healthy_submits=[v for v in workload_submits if 'faultCell' not in v]
                requests=[v['request'] for v in healthy_submits]
                fault_submits=[v['request'] for v in workload_submits if 'faultCell' in v]
                from . import remote_schedule
                windows=len(remote_schedule.windows(canonical_cell or 'healthy','canonical' if canonical_cell else 'experiment'))
                m.need(len(lost_submissions)-len(fault_submits)==(20 if three_mode else windows+2*int(backup)+int(mode==package.MODES[1])) and len({q['commandId'] for q in requests})==len(requests),
                       'owned workload submission replay/cardinality')
                activations=[v for v in workload_submits if v['request']['command']=='fault' and v['request']['payload']==dict(action='activate')]
                m.need(len(activations)==(1 if three_mode else int(mode==package.MODES[1])) and
                       (not activations or activations[0]['node']=='node-1'), 'owned configured activation owner/cardinality')
                for command in ('backup','restore-backup'):
                    submitted=[v for v in healthy_submits if v['request']['command']==command]
                    m.need(len(submitted)==(2 if three_mode else int(backup)) and
                           all(v['node']=='node-'+str(((probe.healthy if experiment else probe).probes[v['mode']] if three_mode else probe).active[0]) for v in submitted),
                           'owned backup/restore submission owner/cardinality')
                c.write_once(root/'workload-submissions.json',workload_submits)
                receipt['workloadSubmitReplyLosses']=len(lost_submissions)
                if mode==package.MODES[0] or three_mode:
                    local=[v for v in workload_submits if v['mode']==package.MODES[0]]
                    m.need(all(v['node']=='node-1' and v['request']['command']!='fault' for v in local),
                           'owned local single issuer/no replication control')
            if experiment:
                all_ids=[v['request']['commandId'] for v in workload_submits]
                m.need(len(set(all_ids))==len(all_ids) and all(v['commandId'] in lost_submissions for v in fault_submits), 'experiment replay/fault lost-reply coverage')
            m.need([n for n,_,_ in services.clients]==([1,2,3]*12 if failure_drill else [1,2,3]*4 if network else [1,1,2,3,1,2,3]+[1,2,3]*3 if experiment else [1,2,3] if maintenance else [1,2,3,1,2,3] if faults else [1,1,2,3,1,2,3] if three_mode else list(nodes)) and len(endpoints)==len(nodes) and
                   all(b.formats==1 for b in transport.blocks),'owned service/format cardinality')
            rows=[]
            for ep in endpoints:
                counts={key:sum(v['action']==key for v in ep.calls) for key in ('clock','begin','part','finish','query')}
                m.need(counts==dict(clock=1,begin=1,part=len(ep.value['parts']),finish=1,query=2),'owned package write/query cardinality')
                rows.append(dict(node=ep.value['binding']['node'],archiveBytes=ep.value['archiveBytes'],calls=counts))
                uses=(3 if ep.value['binding']['node']=='node-1' else 2) if three_mode else 1
                if bootstrap:
                    for phase in ('install','seal'):
                        m.need(sum(v['action']=='bootstrap-'+phase for v in ep.calls)==uses and
                               sum(v['action']=='bootstrap-query-'+phase for v in ep.calls)==2*uses,'owned bootstrap write/query cardinality')
                if source_transfer:
                    n=ep.value['binding']['node']
                    folders=[g.root/'bootstrap' for g in (services.healthy.groups if experiment else services.groups).values() if n in ['node-'+str(i) for i,_,_ in g.clients]] if three_mode else [root/'startup/services/bootstrap']
                    chunks=sum(len(c.read(f/(n+'-transfer/descriptor.json'))['chunks']) for f in folders)
                    counts={k:sum(v['action']=='source-'+k for v in ep.calls) for k in ('begin','chunk','finish','query')}
                    m.need(counts==dict(begin=uses,chunk=chunks,finish=uses,query=4*uses),'owned source write/query cardinality')
                    rows[-1]['sourceCalls']=counts
            if bootstrap:
                from . import guest_bootstrap as boot
                groups=list((services.healthy.groups if experiment else services.groups).values()) if three_mode else [services]
                completed=[c.read(g.root/'bootstrap/receipt.json') for g in groups]
                m.need(all(v['status']=='PASS' and len(v['members'])==len(g.clients) for v,g in zip(completed,groups)),'owned local bootstrap completion')
                for node,_,cfg in (services.healthy.clients if experiment else services.clients):
                    cell=views.root/('node-'+str(node))/Path(cfg['root']).relative_to(views.cell)
                    m.need((cell/boot.LOCAL_READY).is_file() and all(not (cell/('node-'+str(other))).exists() for other in (1,2,3) if other!=node),
                           'owned bootstrap live neighbour storage')
                    if cfg['mode']==package.MODES[0]:
                        m.need(not any((cell/('node-'+str(n))).exists() for n in (1,2,3)), 'owned local replication storage')
                if mode==package.MODES[0] or three_mode:
                    m.need(all(not (views.root/('node-'+str(n))/package.MODES[0]).exists() for n in (2,3)), 'owned local idle neighbours')
                receipt['bootstrap']=completed
            if faults or experiment:
                for node,_,cfg in services.clients:
                    if 'faultCell' not in cfg:continue
                    cell=Path(cfg['root'])
                    if views is not None:cell=views.root/('node-'+str(node))/cell.relative_to(views.cell)
                    m.need((cell/('node-'+str(node))/'bootstrap-seal.gsr').is_file() and
                           all(not (cell/('node-'+str(other))).exists() for other in (1,2,3) if other!=node),
                           'owned fault live neighbour storage')
            if producer_source:
                producer_root=(root/'startup/services'/package.MODES[0]/'bootstrap/producer/original') if three_mode else root/'startup/services/bootstrap/producer'
                record=c.read(producer_root/'receipt.json');producer_nodes=(1,) if three_mode else nodes
                expected=sum(len(c.read(producer_root/f'node-{n}-descriptor.json')['chunks']) for n in producer_nodes)
                counts={k:sum(v['action']=='producer-'+k for v in endpoints[0].calls) for k in ('prepare','query','manifest','chunk')}
                m.need(counts==dict(prepare=1,query=2,manifest=len(producer_nodes),chunk=expected+len(producer_nodes)) and
                       record['readFailures']==len(producer_nodes),'producer original operation/read cardinality')
                receipt['producerCalls']=counts
            receipt.update(status='PASS',tools=server.versions,packages=rows,services=len(services.clients),
                qualifiedCells=result['evidence']['cells'] if workload or faults else [],
                modeledControlCells=[] if workload or faults else result['evidence']['cells'],retainedObjects=len(http.objects),
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
    p.add_argument('--physical',action='store_true');p.add_argument('--backup',action='store_true')
    p.add_argument('--experiment',action='store_true');p.add_argument('--maintenance',action='store_true')
    p.add_argument('--network-faults',action='store_true');p.add_argument('--failure-drill',action='store_true')
    p.add_argument('--three-mode',action='store_true');p.add_argument('--faults',action='store_true');p.add_argument('--fault-local',action='store_true',help='Fault JVM/SSH qualification in separate local paths; no mount-isolation claim')
    p.add_argument('--mode',choices=package.MODES,default=package.MODES[2])
    p.add_argument('--canonical-cell',choices=('healthy','read-heavy','sustained'),help='One full offline canonical tape; not a complete preset')
    args=p.parse_args()
    def terminate(*_): raise TimeoutError('owned qualification terminated')
    signal.signal(signal.SIGTERM,terminate)
    run(args.output,args.bundle,args.source,bootstrap=args.bootstrap,allow_sudo=args.allow_sudo_namespace,
        source_transfer=args.source_transfer,producer_source=args.producer_source,workload=args.workload,physical=args.physical,backup=args.backup,mode=args.mode,three_mode=args.three_mode,faults=args.faults,fault_local=args.fault_local,experiment=args.experiment,maintenance=args.maintenance,network=args.network_faults,failure_drill=args.failure_drill,canonical_cell=args.canonical_cell)

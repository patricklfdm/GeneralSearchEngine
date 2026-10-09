"""Owned preparation -> mount recheck -> package -> idle service, offline only.

The volume observations still come from the qualified block model. Optional local
mount mappings are explicitly recorded for loopback SSH qualification, not disks.
"""
from copy import deepcopy
from pathlib import Path
import time
import uuid
from . import cloud_authority as a, cloud_package as package, cloud_guest as guest
from . import guest_package_delivery as delivery, guest_volume as volume, performance_model as m, remote_command as c

PHASES = ('initial', 'delivery', 'delivered', 'launch', 'ready', 'final')
FILES = {'plan.json', 'receipt.json', 'stop.json', 'stop-claim.json'} | {
    f'node-{n}-{kind}.json' for n in (1,2,3) for kind in ('package','launch','ready',*('check-'+p for p in PHASES))}
BOOTSTRAP_FILES = {f'node-{n}-check-{phase}.json' for n in (1,2,3) for phase in ('bootstrap','install','seeded','seal','sealed')}
SOURCE_FILES = {f'node-{n}-check-{phase}.json' for n in (1,2,3) for phase in ('transfer','transferred')}


class Services:
    offline = True
    authority = a
    service_execution = guest.EXECUTION
    def __init__(self, provider, archive, endpoint_factory=delivery.Endpoint, *, mode=package.MODES[2],
                 qualification_mounts=None, qualification_hosts=None, clock=time.monotonic, sleep=time.sleep, bootstrap=None, deliver=delivery.deliver, fault_cell=None, canonical_cell=None):
        m.need(provider.api.offline is True and mode in package.MODES, 'live owned services disabled')
        from . import guest_workload_spec as workload
        m.need(canonical_cell is None or fault_cell is None and bootstrap is not None and
               (mode,canonical_cell) in workload.CASES, 'owned canonical service scope')
        self.canonical_cell=canonical_cell
        self._initialize(provider,archive,endpoint_factory,mode=mode,qualification_mounts=qualification_mounts,
            qualification_hosts=qualification_hosts,clock=clock,sleep=sleep,bootstrap=bootstrap,deliver=deliver,fault_cell=fault_cell)

    def _initialize(self, provider, archive, endpoint_factory, *, mode=package.MODES[2], qualification_mounts=None,
                    qualification_hosts=None, clock=time.monotonic, sleep=time.sleep, bootstrap=None, deliver=delivery.deliver, fault_cell=None):
        self.provider, self.archive, self.factory = provider, Path(archive).resolve(), endpoint_factory
        from .guest_fault_network import CASES as network_cases
        from .guest_fault_recovery import CASES as recovery_cases
        allowed=('leader-loss','maintenance','no-quorum')+(network_cases+recovery_cases if self.offline else ())
        m.need(fault_cell is None or fault_cell in allowed and mode==package.MODES[2] and bootstrap is None, 'owned fault service scope')
        self.fault_cell=fault_cell
        self.mode, self.clock, self.sleep = mode, clock, sleep
        self.mounts = deepcopy(qualification_mounts) if qualification_mounts is not None else {n:volume.MOUNT for n in (1,2,3)}
        m.need(set(self.mounts) == {1,2,3} and all(isinstance(p,str) and Path(p).is_absolute() and
               str(Path(p)) == p and '..' not in Path(p).parts for p in self.mounts.values()), 'owned service mount paths')
        self.mapping = 'qualification-local-paths' if qualification_mounts is not None else 'guest-mount-paths'
        m.need(qualification_hosts is None or qualification_hosts==['127.0.0.2','127.0.0.3','127.0.0.4'], 'owned qualification host mapping')
        self.hosts=deepcopy(qualification_hosts)
        m.need(bootstrap is None or bootstrap.offline is self.offline, 'owned bootstrap domain')
        self.deliver=deliver
        self.bootstrap=bootstrap; self.clients = []; self.root = None

    def descriptor(self, manifest, binding, provider, access_sha):
        return delivery.describe(self.archive,manifest,binding,provider,access_sha)

    def mounted_readiness(self, node, recheck, readiness):
        recheck(node)
        observed = readiness(node)
        recheck(node)
        return observed

    def prepare(self, req, facts, targets, startup, output, deadline, *, recheck, readiness):
        m.need(req == self.provider.req and len(facts) == len(targets) == len(startup) == 3 and
               [v['provider']['node'] for v in facts] == [1,2,3], 'owned service topology')
        m.need(self.root is None, 'owned service preparation consumed')
        self.root = Path(output); self.root.mkdir(mode=0o700); c.sync_directory(self.root.parent)
        sha = self.authority.validate_request(req)
        result = dict(schema='gse-v51-owned-services-v1', status='FAIL', requestSha256=sha,
            execution=self.authority.EXECUTION, paidCloud=self.authority.PAID_CLOUD, engineWorkloadExecuted=False, fullRemoteQualification=False,
            mountMapping=self.mapping, volumeObservations='offline-block-model' if self.offline else 'native-linux-observations', members=[])
        try:
            manifest = package.verify(self.archive.parent/'package', req['source'])
            m.need(req['guestAccessSha256'] == m.sha(m.canonical(self.provider.guest_access)), 'owned service access binding')
            configs, descriptors, endpoints = [], [], []
            canonical_cell=getattr(self,'canonical_cell',None)
            selection=dict(mode=self.mode,execution=self.service_execution)
            if canonical_cell:selection['workload']=dict(cell=canonical_cell,preset='canonical')
            label=self.fault_cell or package.bootstrap_directory_name(selection)
            group = str(uuid.uuid5(uuid.NAMESPACE_URL, sha+':'+label))
            nodes=package.experiment_nodes(self.mode)
            for node in nodes:
                item,target=facts[node-1],targets[node-1]
                node = item['provider']['node']; binding = c.binding(req['source'],req['bundleSha256'],req['attempt'],'node-'+str(node))
                desc = self.descriptor(manifest,binding,item['provider'],req['guestAccessSha256'])
                m.need(target['instanceId'] == desc['instanceId'] and target['user'] == self.provider.guest_access['user'], 'owned service SSH target')
                cfg = dict(schema='gse-v51-guest-service-v1', execution=self.service_execution, binding=binding,
                    packageManifestSha256=desc['manifestSha256'], root=self.mounts[node]+'/'+label, mode=self.mode,
                    hosts=self.hosts or [v['privateIp'] for v in facts], ports=[self.provider.config['port']]*3, groupId=group)
                if self.fault_cell:cfg['faultCell']=self.fault_cell
                if canonical_cell:cfg['workload']=dict(cell=canonical_cell,preset='canonical')
                guest.validate(cfg)
                endpoint = self.factory(target,self.mounts[node],desc)
                m.need(endpoint.offline is self.offline and endpoint.value == desc and endpoint.target == target and
                       endpoint.parent == self.mounts[node], 'owned service endpoint binding/scope')
                configs.append(cfg); descriptors.append(desc); endpoints.append(endpoint)
            c.write_once(self.root/'plan.json',dict(requestSha256=sha,mountMapping=self.mapping,
                networkMapping='qualification-loopback' if self.hosts else 'provider-private-addresses',
                configs=configs,descriptors=descriptors,startupSha256=[m.sha(m.canonical(v)) for v in startup]))
            def check(index, phase):
                m.need(self.clock() < deadline, 'owned service original deadline')
                observed = self.mounted_readiness(index+1,recheck,readiness)
                m.need(observed['schema'] == ('gse-v51-volume-readiness-v1' if self.offline else 'gse-v51-native-volume-readiness-v1') and observed['provider'] == facts[index]['provider'] and
                       observed['volume'] == startup[index]['volume'] and
                       observed['startupSha256'] == m.sha(m.canonical(startup[index])), 'owned service mounted readiness')
                m.need(self.clock() < deadline, 'owned service original deadline')
                c.write_once(self.root/f'node-{index+1}-check-{phase}.json',observed,maximum=262144)
            for i in range(len(configs)): check(i,'initial')
            for i, endpoint in enumerate(endpoints):
                check(i,'delivery'); record = dict(descriptor=descriptors[i], status='FAIL')
                try:
                    record['receipt'] = self.deliver(endpoint,self.archive,deadline); record['status']='PASS'
                finally:
                    record.update(deadline=endpoint.budget,calls=endpoint.calls,failures=endpoint.failures)
                    c.write_once(self.root/f'node-{i+1}-package.json',record,maximum=262144)
            for i in range(len(configs)): check(i,'delivered')
            if self.bootstrap is not None:
                result['bootstrap']=self.bootstrap.prepare(req,configs,endpoints,self.root/'bootstrap',deadline,recheck=check)
                m.need(result['bootstrap']['status']=='PASS' and result['bootstrap']['publicBootstrapVerified'] is True,
                       'owned bootstrap group not verified')
            for i, (endpoint,cfg) in enumerate(zip(endpoints,configs)):
                check(i,'launch'); client=endpoint.client(cfg)
                m.need(client.config == cfg, 'owned service client binding')
                intent = dict(configSha256=m.sha(m.canonical(cfg)),requestSha256=sha)
                c.write_once(self.root/f'node-{i+1}-launch.json',intent)
                self.clients.append((i+1,client,cfg))  # Includes an uncertain start.
                from . import native_experiment_timing as timing
                native=timing.selected(req);failures=0
                ready_end=min(deadline,self.clock()+timing.control(req,'activation',3600)) if native else deadline
                def failed(error):
                    nonlocal failures
                    if getattr(error,'retryable',True) is False:raise error
                    failures+=1
                    m.need(not native or failures<timing.MAX_TRANSIENT_FAILURES,'owned service observation failures exhausted')
                try:
                    launched=client.start(ready_end)
                    m.need(launched['state']=='LAUNCHED' and launched['configSha256']==intent['configSha256'], 'owned service launch receipt')
                except (ConnectionError,TimeoutError) as error: failed(error);launched=None
                while True:
                    m.need(self.clock()<ready_end,'owned service readiness deadline')
                    try: answer=client.ready(ready_end);failures=0
                    except (ConnectionError,TimeoutError) as error: failed(error);answer=None
                    if answer is not None:
                        m.need(self.clock()<ready_end,'owned service readiness deadline')
                        m.need(answer['closed'] is None, 'owned service closed during startup')
                        ready=answer['ready']
                        if ready is not None:
                            m.need(ready['configSha256']==intent['configSha256'] and type(ready['pid']) is int and ready['pid']>0 and
                                   (launched is None or ready['pid']==launched['pid']), 'owned service readiness identity')
                            break
                    self.sleep(min(1 if native else .05,max(0,ready_end-self.clock())))
                check(i,'ready'); c.write_once(self.root/f'node-{i+1}-ready.json',answer)
                result['members'].append(dict(node=i+1,configSha256=intent['configSha256'],pid=ready['pid']))
            for i in range(len(configs)): check(i,'final')
            result['status']='PASS'
        except (Exception,KeyboardInterrupt) as error:
            result['failure']=dict(type=type(error).__name__,message=str(error)[:2000]); raise
        finally: c.write_once(self.root/'receipt.json',result,maximum=262144)
        return result

    def stop(self, deadline):
        if self.root is None: return None
        path=self.root/'stop.json'
        if path.exists():
            result=c.read(path); m.need(result['status']=='PASS','owned service earlier stop failed'); return result
        c.write_once(self.root/'stop-claim.json',dict(nodes=[node for node,_,_ in self.clients]))
        from . import native_experiment_timing as timing
        end=min(deadline,self.clock()+timing.control(self.provider.req,'service-stop',30)); rows=[]; errors=[]
        native=timing.selected(self.provider.req)
        for node,client,cfg in self.clients:
            row=dict(node=node,status='FAIL'); rows.append(row)
            try:
                failures=0
                def failed(error):
                    nonlocal failures
                    if getattr(error,'retryable',True) is False:raise error
                    failures+=1
                    m.need(not native or failures<timing.MAX_TRANSIENT_FAILURES,'owned service observation failures exhausted')
                m.need(self.clock()<end,'owned service stop deadline')
                try: client.shutdown(end)
                except (ConnectionError,TimeoutError) as error: failed(error)  # Query only; no second shutdown write.
                while True:
                    m.need(self.clock()<end,'owned service stop deadline')
                    try: observed=client.ready(end);failures=0
                    except (ConnectionError,TimeoutError) as error: failed(error);observed=None
                    if observed is not None and observed['closed'] is not None:
                        m.need(self.clock()<end,'owned service stop deadline')
                        m.need(observed['ready'] is not None and observed['ready']['configSha256']==m.sha(m.canonical(cfg)) and
                               observed['closed']['status']=='PASS' and observed['closed']['jvmStopped'] is True,'owned service stop identity/outcome')
                        row.update(status='PASS',receipt=observed); break
                    self.sleep(min(1 if native else .05,max(0,end-self.clock())))
            except (Exception,KeyboardInterrupt) as error:
                row['failure']=dict(type=type(error).__name__,message=str(error)[:2000]); errors.append(row['failure'])
        result=dict(status='FAIL' if errors else 'PASS',members=rows,errors=errors,paidCloud=self.authority.PAID_CLOUD)
        c.write_once(path,result,maximum=262144)
        m.need(not errors,'owned service stop failed'); return result

    def retention_files(self):
        if self.root is None: return
        c.directory(self.root)
        allowed=FILES | (BOOTSTRAP_FILES if self.bootstrap is not None else set())
        if self.bootstrap is not None and getattr(self.bootstrap,'delivery',None) is not None:allowed |= SOURCE_FILES
        if self.bootstrap is not None and getattr(getattr(self.bootstrap,'source',None),'scope',None) in ('authenticated-producer-download','authenticated-shared-source'):
            allowed |= {'node-1-check-produced.json'}
        for path in sorted(self.root.iterdir()):
            if path.name=='bootstrap' and self.bootstrap is not None:
                c.directory(path)
                for name,raw in self.bootstrap.retention_files(): yield 'services/'+name,raw
                continue
            m.need(path.name in allowed and path.is_file() and not path.is_symlink() and path.stat().st_size<=262144,'owned service retention inventory')
            yield 'services/'+path.name,path.read_bytes()

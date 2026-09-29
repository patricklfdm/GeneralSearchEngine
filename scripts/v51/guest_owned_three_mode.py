"""Bounded experiment healthy coordinator: one owned lease, package and seed.

Provider facts remain modeled. This is not a full preset or native cloud admission.
"""
from copy import deepcopy
from pathlib import Path
import time
from . import cloud_authority as a, cloud_package as package, performance_model as m, remote_command as c
from . import guest_owned_services as owned, guest_owned_workload as workload, guest_package_delivery as delivery
from . import guest_owned_bootstrap as bootstrap, guest_bootstrap, guest_shared_source, guest_source_delivery
from . import remote_collection as parts

MODE='three-mode'
SCOPE='owned-three-mode-healthy-experiment'


class PackagePool:
    def __init__(self, factory):self.factory=factory;self.endpoints={};self.completed={}
    def endpoint(self, target, parent, descriptor):
        key=descriptor['binding']['node']
        if key not in self.endpoints:self.endpoints[key]=self.factory(target,parent,descriptor)
        ep=self.endpoints[key]
        m.need(ep.target==target and ep.parent==parent and ep.value==descriptor,'shared package endpoint identity')
        return ep
    def deliver(self, endpoint, archive, deadline):
        key=endpoint.value['binding']['node']
        if key not in self.completed:
            # Keep failed/uncertain installation consumed too. Never replay it.
            self.completed[key]=None
            result=delivery.deliver(endpoint,archive,deadline)
            self.completed[key]=(Path(archive),deadline,deepcopy(result))
        previous=self.completed[key]
        m.need(previous is not None and previous[:2]==(Path(archive),deadline),'shared package consumed/deadline')
        return deepcopy(previous[2])


class Services:
    offline=True
    mode=MODE
    def __init__(self, provider, archive, endpoint_factory=delivery.Endpoint, *, clock=time.monotonic, sleep=time.sleep, **options):
        self.provider=provider;self.archive=Path(archive);self.root=None;self.groups={};self.clock=clock;self.sleep=sleep
        self.pool=PackagePool(endpoint_factory);self.options=options
    @property
    def clients(self):return [member for group in self.groups.values() for member in group.clients]
    def prepare(self, req, facts, targets, startup, output, deadline, *, recheck, readiness):
        m.need(self.root is None,'three-mode services consumed')
        self.root=Path(output);self.root.mkdir(mode=0o700)
        self.source=guest_shared_source.SharedSource(self.root/'shared-source',clock=self.clock,sleep=self.sleep)
        result=dict(status='FAIL',requestSha256=a.validate_request(req),modes=[])
        try:
            for mode in package.MODES:
                seed=bootstrap.Bootstrap(guest_shared_source.Source(self.source),clock=self.clock,sleep=self.sleep,
                                         delivery=guest_source_delivery.Delivery())
                group=owned.Services(self.provider,self.archive,self.pool.endpoint,mode=mode,bootstrap=seed,
                    deliver=self.pool.deliver,clock=self.clock,sleep=self.sleep,**self.options)
                self.groups[mode]=group
                answer=group.prepare(req,facts,targets,startup,self.root/mode,deadline,recheck=recheck,readiness=readiness)
                result['modes'].append(dict(mode=mode,receipt=answer))
            identities=[row['receipt']['bootstrap']['identity']['sourceSha256'] for row in result['modes']]
            m.need(len(set(identities))==1,'three-mode shared source disagreement')
            result.update(status='PASS',sourceSha256=identities[0]);return result
        finally:c.write_once(self.root/'receipt.json',result,maximum=262144)
    def stop(self, deadline):
        errors=[]
        for mode,group in self.groups.items():
            try:group.stop(deadline)
            except (Exception,KeyboardInterrupt) as error:errors.append(dict(mode=mode,message=str(error)))
        m.need(not errors,'three-mode service shutdown: '+str(errors))
    def retention_files(self):
        if self.root is None:return
        for mode,group in self.groups.items():
            for name,raw in group.retention_files():yield mode+'/'+name,raw
        if (self.root/'receipt.json').exists():yield 'three-mode-services.json',(self.root/'receipt.json').read_bytes()


class Probe:
    execution=a.EXECUTION
    scope=SCOPE
    mode=MODE
    require_physical=True
    require_backup=True
    def __init__(self, services, output, *, clock=time.monotonic, sleep=time.sleep):
        m.need(services.offline is True and services.mode==MODE,'three-mode services scope')
        self.services=services;self.clock=clock;self.sleep=sleep;self.root=Path(output)
        self.root.mkdir(parents=True,mode=0o700);self.raw=self.root/'raw';self.raw.mkdir(mode=0o700)
        self.probes={};self.started=[];self.cells=[];self.prepared=False;self.attempted=False;self.stopped=False
        self.binding=m.sha(m.canonical(dict(scope=SCOPE,requestSha256=a.validate_request(services.provider.req))))
    @property
    def engineWorkloadExecuted(self):return any(p.engineWorkloadExecuted for p in self.probes.values())
    def prepare(self, req, deadline):
        m.need(not self.prepared and list(self.services.groups)==list(package.MODES),'three-mode preparation/order')
        complete=c.read(self.services.root/'receipt.json')
        m.need(complete['status']=='PASS' and complete['requestSha256']==a.validate_request(req),'three-mode service admission')
        c.write_once(self.raw/'plan.json',dict(scope=SCOPE,request=req,services=complete))
        # The common source is retained independently of receiver paths.
        seed=self.services.source.root/'seed/source';(self.raw/'source').mkdir(mode=0o700)
        for name in guest_bootstrap.SOURCE:(self.raw/'source'/name).write_bytes((seed/name).read_bytes())
        for mode,group in self.services.groups.items():
            probe=workload.Probe(group,self.root/mode,physical=mode in package.MODES[1:],backup=mode in package.MODES[1:],clock=self.clock,sleep=self.sleep)
            self.probes[mode]=probe;probe.prepare(req,deadline)
        self.prepared=True
    def cell(self, name, deadline):
        m.need(self.prepared and not self.attempted and name=='healthy','three-mode healthy consumed/scope')
        self.attempted=True;end=min(deadline/10**9,self.clock()+900)
        record=dict(status='FAIL',startNanos=int(self.clock()*10**9),modes=[])
        try:
            for mode,probe in self.probes.items():
                until=min(end,self.clock()+300)
                row=dict(mode=mode,status='FAIL',startNanos=int(self.clock()*10**9));record['modes'].append(row);self.started.append(mode)
                try:
                    probe.cell(name,int(until*10**9))
                    errors=probe.close_voters(until)
                    m.need(not errors,'three-mode previous voters not closed: '+str(errors))
                    m.need(self.clock()<=until,'three-mode healthy mode ceiling including close')
                    row['status']='PASS'
                finally:row['endNanos']=int(self.clock()*10**9)
            m.need(self.clock()<=end,'three-mode healthy category ceiling');self.cells=['healthy'];record['status']='PASS'
        finally:
            record['endNanos']=int(self.clock()*10**9);c.write_once(self.raw/'timeline.json',record)
    def stop(self):
        self.stopped=True
        for probe in self.probes.values():probe.stop()
    def collect_validate(self, output, deadline):
        m.need(self.stopped,'three-mode collection before stop');errors=[];reports=[]
        for mode in self.started:
            probe=self.probes[mode]
            try:
                result=probe.collect_validate(output,deadline);reports.append(dict(mode=mode,result=result))
            except (Exception,KeyboardInterrupt) as error:errors.append(dict(mode=mode,message=str(error)[:2000]))
            finally:
                # Keep original raw collections and partial failures; replay scratch
                # stays outside the aggregate archive and cannot stand in for input.
                destination=self.raw/mode
                m.need(not destination.exists(),'three-mode raw consumed')
                probe.raw.rename(destination);probe.raw=destination
        result=dict(status='FAIL',execution=a.EXECUTION,scope=SCOPE,mode=MODE,paidCloud=False,fullRemoteQualification=False,
            engineWorkloadExecuted=self.engineWorkloadExecuted,physicalHistoryQualified=False,backupRestoreQualified=False,
            cells=list(self.cells),modes=reports,errors=errors)
        try:
            m.need(self.clock()<deadline/10**9,'three-mode validation deadline')
            from .guest_three_mode_evidence import validate
            result['aggregate']=validate(self.raw,self.root/'aggregate-replay')
            m.need(not errors and len(reports)==3 and all(v['result']['status']=='PASS' for v in reports),'three-mode collected failures')
            m.need(self.clock()<deadline/10**9,'three-mode validation deadline')
            result.update(status='PASS',physicalHistoryQualified=True,backupRestoreQualified=True)
        except (Exception,KeyboardInterrupt) as error:errors.append(dict(phase='aggregate',message=str(error)[:2000]))
        c.write_once(self.raw/'validation.json',result,maximum=262144);return result
    def retention_files(self):
        parts.pack(self.raw,self.root/'retained',self.binding)
        for path in sorted((self.root/'retained').iterdir()):yield path.name,path.read_bytes()

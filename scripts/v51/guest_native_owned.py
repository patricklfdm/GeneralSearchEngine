"""Internal native experiment bridge; no standalone live transport/CLI override.

Reuses the qualified workload, source and evidence algorithms. Only the original
admitted creation API may construct this bridge; each connection keeps its pinned
identity and scoped credential environment, and every daemon inherits that lease.
"""
import base64
from copy import deepcopy
import math
from pathlib import Path
from . import cloud_native_authority as n, cloud_runner_guest_setup as setup, cloud_runner_iap as iap
from . import guest_native_session as session, guest_package_delivery as delivery, guest_owned_services as owned
from . import guest_owned_bootstrap as bootstrap, guest_shared_source as shared, guest_source_delivery as transfer
from . import guest_producer_source as producer, guest_owned_workload as workload, guest_owned_three_mode as healthy
from . import guest_owned_experiment as experiment, performance_model as m, remote_command as c
from . import guest_session_recovery as recovery
from . import native_experiment_timing as timing


def creation(api):
    from .cloud_runner_resources import _Api
    m.need(type(api) is _Api and not api.offline and api.gate_open and not api.failed and
           api.state=='done' and not api.failure_claimed and not api.owner_claimed, 'native owned creation authority')


class Endpoint(delivery.Endpoint):
    def __init__(self, api, prepared, hosts):
        creation(api);original=prepared['endpoint']
        m.need(type(original) is setup._PackageEndpoint and original.api is api and original.budget is not None,
               'native session original delivery')
        super().__init__(original.target,original.parent,original.value)
        self.api=api;self.recheck=prepared['recheck'];self.deadline=original.deadline;self.budget=deepcopy(original.budget)
        self.calls=deepcopy(original.calls);self.failures=deepcopy(original.failures)
        self.session=session.validate(dict(schema=session.SCHEMA,packageSha256=m.sha(m.canonical(self.value)),
            preparation=self.budget,leaseExpiresNanos=self.budget['expiresNanos']+math.floor((api.owner_deadline-self.deadline)*1e9),
            hosts=list(hosts),port=api.cfg['port']),self.value)
        self.started=False

    def remote(self, action, token, *tail):
        if action=='service':tail=(token,*tail)
        else:m.need(token==base64.b64encode(m.canonical(self.budget)).decode(),'native original preparation token')
        return ['/usr/bin/python3','-I','-c',setup.trusted_source('session'),action,
            base64.b64encode(m.canonical(self.value)).decode(),base64.b64encode(m.canonical(self.session)).decode(),*tail]

    def process(self, remote, data, deadline, **options):
        m.need(len(self.calls)<4096 and self.api.clock()<deadline<=self.api.deadline,'native session connection budget')
        deadline=min(deadline,self.api.clock()+timing.EXCHANGE_SECONDS)
        self.api.guest_operation = dict(node=self.value['binding']['node'],kind='session',action=remote[4])
        # Provider guards share the command's deadline during preparation AND
        # runtime; a short exchange must not inherit the whole cell allowance.
        def check():self.recheck(deadline=deadline)
        check();self.calls.append(dict(action=remote[4],index=None))
        try:
            raw=iap._network_exchange(self.api,self.target,remote,data,deadline,**options)
            check();return raw
        except (Exception,KeyboardInterrupt) as error:
            if len(self.failures)<8:self.failures.append(dict(type=type(error).__name__))
            raise

    def begin(self):
        m.need(not self.started,'native session already submitted');self.started=True
        token=base64.b64encode(m.canonical(self.budget)).decode()
        if not hasattr(self.api,'session_recoveries'): self.api.session_recoveries=[]
        report=dict(node=self.value['binding']['node']);self.api.session_recoveries.append(report)
        expected=dict(state='SUCCEEDED',sessionSha256=m.sha(m.canonical(self.session)))
        return recovery.initialize(lambda action,until:m.strict_json(self.process(
            self.remote(action,token),b'',until,maximum=4096)),expected,self.deadline,report,clock=self.api.clock)

    def client(self, config):
        m.need(self.started,'native session not started');session.check_config(config,self.value,self.session)
        return self._client(config)
    def bootstrap(self,*args,**kwargs):return self._bootstrap(*args,**kwargs)
    def source(self,*args,**kwargs):return self._source(*args,**kwargs)
    def producer(self,*args,**kwargs):return self._producer(*args,**kwargs)


class Delivery(transfer.Delivery):
    offline=False
    def deliver(self,folder,descriptor_sha,config,endpoint,deadline,output):
        m.need(type(endpoint) is Endpoint,'native source endpoint')
        return self._deliver(folder,descriptor_sha,config,endpoint,deadline,output)


class RemoteSource(producer.RemoteSource):
    offline=False
    def prepare(self,configs,deadline,*,endpoint,output):
        m.need(type(endpoint) is Endpoint,'native producer endpoint')
        return self._prepare(configs,deadline,endpoint=endpoint,output=output)


class SharedSource(shared.SharedSource):
    def __init__(self,output,**options):
        super().__init__(output,**options);self.remote=RemoteSource(**options)


class Source(shared.Source):offline=False


class Bootstrap(bootstrap.Bootstrap):
    offline=False;authority=n
    def __init__(self,source,**options):
        m.need(type(source) is Source and type(options.get('delivery')) is Delivery,'native bootstrap dependencies')
        self._initialize(source,**options)


class Group(owned.Services):
    offline=False;authority=n;service_execution=session.EXECUTION
    def __init__(self,provider,archive,pool,**options):
        creation(provider.api);self.pool=pool
        self._initialize(provider,archive,pool.endpoint,deliver=pool.deliver,**options)
    def descriptor(self,manifest,binding,provider,access_sha):
        expected=super().descriptor(manifest,binding,provider,access_sha)
        actual=self.pool.endpoints[binding['node']].value
        m.need(all(actual[k]==v for k,v in expected.items() if k!='schema'),'native package descriptor drift')
        return deepcopy(actual)

    def mounted_readiness(self,node,recheck,readiness):
        # The native volume exchange already checks current durable authority,
        # exact provider IDs and the pinned host key before AND after the remote
        # mount check. Do not wrap it in a second identical pair of checks.
        disk=self.pool.disks['node-'+str(node)]
        m.need(type(disk) is setup._VolumeEndpoint and disk.api is self.provider.api and
               disk.value['binding']['node']=='node-'+str(node),
               'native readiness original endpoint')
        return disk.exchange('check')['readiness']


class Pool(healthy.PackagePool):
    def __init__(self,api,archive,prepared):
        super().__init__(None);hosts=[v['facts']['privateIp'] for v in prepared]
        self.disks={'node-'+str(row['facts']['provider']['node']):row.get('disk') for row in prepared}
        for row in prepared:
            ep=Endpoint(api,row,hosts);key=ep.value['binding']['node']
            self.endpoints[key]=ep;self.completed[key]=(Path(archive),api.deadline,deepcopy(row['installed']))
        self.started=False
    def begin(self,root):
        m.need(not self.started,'native pool consumed');self.started=True
        for node,ep in self.endpoints.items():
            c.write_once(root/(node+'-session-request.json'),ep.session)
            c.write_once(root/(node+'-session.json'),ep.begin())
    def promote(self,api,rechecks):
        m.need(self.started,'native pool not prepared')
        for node,ep in self.endpoints.items():
            m.need(ep.api is api.source,'native pool original owner')
            ep.api=api;ep.recheck=rechecks[node]


class Services(experiment.Services):
    offline=False;authority=n
    def __init__(self,provider,archive,prepared):
        creation(provider.api);super().__init__(provider,archive)
        self.pool=Pool(provider.api,self.archive,prepared)
    def shared_source(self):return SharedSource(self.root/'shared-source',clock=self.clock,sleep=self.sleep)
    def seed(self):return Bootstrap(Source(self.source),clock=self.clock,sleep=self.sleep,delivery=Delivery())
    def group(self,**options):return Group(self.provider,self.archive,self.pool,clock=self.clock,sleep=self.sleep,**options)


class SingleProbe(workload.Probe):
    authority=n;execution=n.EXECUTION
    def __init__(self,services,output,**options):
        m.need(type(services) is Group and services.bootstrap is not None,'native workload group/bootstrap')
        self._initialize(services,output,**options)


class HealthyProbe(healthy.Probe):
    authority=n;execution=n.EXECUTION;workload_probe=SingleProbe
    def __init__(self,services,output,**options):
        m.need(not services.offline and services.mode==healthy.MODE and
               all(type(v) is Group for v in services.groups.values()),'native healthy group scope')
        self._initialize(services,output,**options)


class Probe(experiment.Probe):
    authority=n;execution=n.EXECUTION;healthy_probe=HealthyProbe
    def __init__(self,services,output,**options):
        m.need(type(services) is Services,'native complete experiment scope')
        self._initialize(services,output,**options)

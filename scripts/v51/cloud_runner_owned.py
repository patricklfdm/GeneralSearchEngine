"""Fixed native experiment lifecycle, selected only by the exact approved entry.

A live entry always repeats fresh admission; copied receipts and fake adapters
cannot enter it. Shared cleanup still needs the original retained CAS authority.
"""
from copy import deepcopy
from pathlib import Path
from contextlib import contextmanager
import json
import threading
import time as walltime
import re
import time
from urllib.parse import urlsplit, parse_qsl
from . import cloud_runner_failure as failure, cloud_native_cleanup as cleanup, cloud_native_authority as n
from . import cloud_runner_resources as resources, cloud_runner_guest_setup as setup, cloud_runner as runner
from . import cloud_gcp as g, guest_native_owned as native, guest_owned_experiment as experiment
from . import remote_collection as parts, performance_model as m, remote_command as c
from .remote_budget import Budget
from . import cloud_runner_timing as timing
from . import cloud_runner_diagnostics as diagnostics
from . import cloud_runner_iap as iap


class _Api(failure._Api):
    execution='native-v51-owned-experiment'

    def __init__(self, source):
        native.creation(source)
        m.need(source.last_lease_write is not None,'owned original lease write')
        source.owner_claimed=True;self._initialize(source)
        self.phase='admission';self.deadline=min(source.deadline,source.owner_deadline)
        self.seen=set();self.retention_sealed=False

    def stage(self, name, deadline):
        m.need(name in (*experiment.CELLS,'validation-retention','cleanup','completion') and name not in self.seen and
               self.clock()<deadline<=self.source.owner_deadline,'owned stage deadline/consumed')
        limits=dict(timing.allocation()['limitsSeconds']);limits['completion']=limits['control']
        if name in experiment.CELLS:
            m.need(self.phase==('admission' if name=='healthy' else experiment.CELLS[experiment.CELLS.index(name)-1]),'owned cell order')
        elif name=='completion':m.need(self.phase=='cleanup','owned completion before cleanup')
        elif name=='validation-retention':m.need(self.phase in ('admission',*experiment.CELLS),'owned validation after close')
        m.need(deadline<=self.clock()+limits[name],'owned frozen stage ceiling')
        self.seen.add(name);self.phase=name;self.deadline=deadline

    def check(self, method, url, body):
        m.need(self.clock()<self.deadline<=self.source.owner_deadline,'owned original stage/lease deadline')
        parsed=urlsplit(url);base=parsed._replace(query='').geturl()
        m.need(parsed.scheme=='https' and parsed.netloc in ('compute.googleapis.com','storage.googleapis.com') and
               not parsed.fragment and not parsed.username,'owned endpoint')
        if method=='GET' and parsed.netloc=='compute.googleapis.com' and self.phase!='cleanup':
            m.need(self.phase in (*experiment.CELLS,'validation-retention') and self.provider is not None and
                   self.lease is not None and body is None,'owned runtime compute read scope')
            for row in self.lease['resources']:
                spec=row['spec']
                if not row['attempted'] or row['id'] is None or spec['kind'] not in ('disk','instance'):continue
                # Runtime reads bind retained IDs directly. They never populate
                # cleanup's resolved map or authorize deletion without reconciling
                # the original insert operation in the cleanup stage.
                if not parsed.query and base==self.provider.url(spec,row['id']):return ('resource',spec,row['id'])
                if spec['kind']=='instance' and base==self.provider.url(spec)+'/getGuestAttributes':
                    m.need(parse_qsl(parsed.query,keep_blank_values=True,strict_parsing=True)==[('queryPath','hostkeys/')],
                           'owned host key read scope')
                    return ('host-key',None,None)
            raise ValueError('owned runtime compute read scope')
        if method=='POST' and base==self.upload:
            pairs=parse_qsl(parsed.query,strict_parsing=True);query=dict(pairs);key=query.get('name')
            m.need(len(pairs)==len(query),'owned duplicate query')
            if key in self.retained:
                m.need(self.phase=='validation-retention' and not self.retention_sealed and
                       query==dict(uploadType='media',name=key,ifGenerationMatch='0') and
                       self.fingerprint(body)==self.retained[key],'owned immutable evidence changed/stage')
                return ('object',key,'upload')
            if self.lease is not None and key==self.attempt+'completion.json':
                m.need(self.phase=='completion' and self.expected_completion is not None and body==self.expected_completion and
                       query==dict(uploadType='media',name=key,ifGenerationMatch='0') and self.retention_sealed and
                       set(self.retained)==self.verified,'owned completion before sealed read-back')
                self.completion_value(body);return ('object',key,'upload')
            m.need((self.phase=='cleanup' and key==n.LEASE) or (self.phase=='completion' and key==n.LEDGER),
                   'owned control write outside stage')
        if method=='DELETE':
            if parsed.netloc=='storage.googleapis.com':
                m.need(self.phase=='completion' and self.expected_completion is not None and self.completion==self.expected_completion and
                       self.retention_sealed and set(self.retained)==self.verified,'owned release before retention')
            else:m.need(self.phase=='cleanup','owned compute mutation outside cleanup')
        elif method!='GET':m.need(method=='POST' and parsed.netloc=='storage.googleapis.com','owned cannot allocate resources')
        return cleanup._Policy.check(self,method,url,body)

    @staticmethod
    def fingerprint(data):
        raw=data if type(data) is bytes else m.canonical(data)
        return dict(bytes=len(raw),sha256=m.sha(raw))

    def observe(self,checked,value):
        kind,key,detail=checked
        if kind=='host-key':return
        if kind=='object' and key in self.retained and detail.startswith('media:'):
            m.need(self.fingerprint(value)==self.retained[key],'owned evidence read-back differs')
            self.verified.add(key);return
        cleanup._Policy.observe(self,checked,value)

    def retain(self, store, name, data):
        m.need(self.phase=='validation-retention' and not self.retention_sealed and isinstance(name,str) and
               re.fullmatch(r'[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)*',name) and
               all(p not in ('.','..') for p in name.split('/')),'owned retention inventory/path')
        key=self.attempt+'owned-experiment/'+name
        m.need(key not in self.retained,'owned evidence duplicate')
        self.retained[key]=self.fingerprint(data)
        m.need(len(self.retained)<=10000 and self.retained[key]['bytes']<=parts.LIMITS['partBytes'] and
               sum(v['bytes'] for v in self.retained.values())<=parts.LIMITS['compressedBytes'],'owned retention byte/file bound')
        return runner.retain(store,key,data)

    def seal(self):
        m.need(self.phase=='validation-retention' and self.retained and set(self.retained)==self.verified and
               not self.retention_sealed,'owned incomplete retention')
        self.retention_sealed=True


def _runtime_rechecks(api, store, prepared, lease, generation):
    """Freeze preparation identities; each command brackets fresh bounded reads."""
    lease=deepcopy(lease);checks={}
    for node,row in enumerate(prepared,1):
        old=row['endpoint'];facts=deepcopy(row['facts'])
        pin=Path(old.target['knownHosts']);pin_raw=pin.read_bytes();identity=old.value['instanceId']
        def check(*,deadline=None,node=node,facts=facts,pin=pin,pin_raw=pin_raw,identity=identity):
            until=min(api.deadline,api.source.owner_deadline,deadline if deadline is not None else api.deadline)
            m.need(api.clock()<until,'owned runtime identity deadline')
            current=store.get(n.LEASE,deadline=until);ledger=store.get(n.LEDGER,deadline=until)
            m.need(current==(generation,lease) and ledger is not None and ledger[1]==api.source.reserved,
                   'owned runtime durable authority changed')
            observed=api.provider.guest_identity(lease,node,deadline=until)
            m.need(observed['facts']==facts and not pin.is_symlink() and pin.read_bytes()==pin_raw==
                   ('gse-v51-'+identity+' '+observed['publicKey']+'\n').encode(),'owned provider/pinned host changed')
        checks['node-'+str(node)]=check
    return checks


def _execute(output, prepare):
    """Private composition seam; the public entry below fixes native dependencies."""
    # All later controller paths (source exports, restore and retained evidence)
    # derive from this root. Keep guest/session paths separate and unchanged.
    root=Path(output).absolute();root.mkdir(parents=True,exist_ok=False);c.directory(root)
    budget=Budget(profile=timing.PROFILE);held={};api=None;store=None
    @contextmanager
    def stage(name):
        # No provider data, paths or exception strings in the live heartbeat.
        started=walltime.monotonic();done=threading.Event()
        def emit(state):
            print(json.dumps(dict(stage=name,status=state,elapsedSeconds=round(walltime.monotonic()-started,1),
                                  limitSeconds=budget.limits[name]//10**9)),flush=True)
        def beat():
            while not done.wait(30):emit('RUNNING')
        emit('START');worker=threading.Thread(target=beat,daemon=True);worker.start()
        try:
            with budget.stage(name) as deadline:yield deadline
        except BaseException:
            emit('FAIL');raise
        else:emit('DONE')
        finally:done.set();worker.join()
    result=dict(schema=n.COMPLETION_SCHEMA,execution=n.EXECUTION,paidCloud=False,engineWorkloadExecuted=False,
        fullRemoteQualification=False,qualificationScope=experiment.SCOPE,status='FAIL',errors=[],cleanup=None,
        retention='INCOMPLETE',leaseReleased=False)

    def continuation(source,archive,prepared):
        native.creation(source);held['source']=source
        services=native.Services(source.provider(),archive,prepared);held['services']=services
        session_root=root/'sessions';session_root.mkdir()
        services.pool.begin(session_root)
        services.prepare(source.req,[v['facts'] for v in prepared],[v['endpoint'].target for v in prepared],
            [v['startup'] for v in prepared],root/'services',source.deadline,
            recheck=lambda node:prepared[node-1]['recheck'](),readiness=lambda node:prepared[node-1]['disk'].exchange('check')['readiness'])
        probe=native.Probe(services,root/'workload');held['probe']=probe
        probe.prepare(source.req,int(source.deadline*1e9))
        held['prepared']=prepared

    def report(phase,error):
        record=diagnostics.runtime_failure(phase,error)
        if api is not None and api.phase in experiment.CELLS:record['cell']=api.phase
        result['errors'].append(record)
    try:
        with stage('preparation') as deadline:
            prepared=prepare(root/'preparation',continuation)
            result['preparation']=prepared;result['paidCloud']=prepared['paidCloud']
            m.need(prepared['status']=='PARTIAL' and 'probe' in held,'owned preparation failed')
            api=_Api(held['source']);store=api.admit()
            result['requestSha256']=api.sha;result['paidCloud']=True
            lease=deepcopy(api.lease);generation=api.lease_generation
            held['services'].pool.promote(api,_runtime_rechecks(api,store,held['prepared'],lease,generation))
            m.need(time.monotonic_ns()<deadline,'owned preparation total deadline')
        for cell in experiment.CELLS:
            with stage(cell) as deadline:
                api.stage(cell,min(deadline/1e9,api.source.owner_deadline))
                with iap.runtime_connections(api,root/('connections-'+cell+'.json')):
                    held['probe'].cell(cell,int(api.deadline*1e9))
    except (Exception,KeyboardInterrupt) as error:report('execution',error)
    finally:
        if api is not None and store is not None:
            probe=held['probe'];result['engineWorkloadExecuted']=probe.engineWorkloadExecuted
            try:probe.stop()
            except (Exception,KeyboardInterrupt) as error:report('stop',error)
            try:
                with stage('validation-retention') as deadline:
                    api.stage('validation-retention',min(deadline/1e9,api.source.owner_deadline))
                    with iap.runtime_connections(api,root/'connections-validation-retention.json'):
                        try:result['evidence']=probe.collect_validate(root,int(api.deadline*1e9))
                        except (Exception,KeyboardInterrupt) as error:report('collection',error)
                        finally:
                            try:held['services'].stop(api.deadline)
                            except (Exception,KeyboardInterrupt) as error:report('service-stop',error)
                    for path in sorted(root.glob('connections-*.json')):api.retain(store,path.name,path.read_bytes())
                    for name,data in held['services'].retention_files():api.retain(store,'startup/'+name,data)
                    for name,data in probe.retention_files():api.retain(store,'parts/'+name,data)
                    for name,data in failure.evidence(root/'preparation',status='PARTIAL').items():api.retain(store,'preparation/'+name,data)
                    for path in sorted((root/'sessions').iterdir()):api.retain(store,'sessions/'+path.name,path.read_bytes())
                    evidence=result.get('evidence',dict(status='FAIL',reason='collection incomplete'))
                    result['evidenceSha256']=api.retain(store,'evidence.json',m.canonical(evidence))
                    manifest=dict(schema='gse-v51-native-owned-evidence-v1',requestSha256=api.sha,files=deepcopy(api.retained))
                    result['inventorySha256']=api.retain(store,'manifest.json',m.canonical(manifest));api.seal()
                    m.need(evidence['status']=='PASS' and evidence['scope']==experiment.SCOPE and evidence['execution']==n.EXECUTION and
                           evidence['paidCloud'] is True and evidence['fullRemoteQualification'] is False and
                           evidence['engineWorkloadExecuted'] is True and evidence['physicalHistoryQualified'] is True and
                           evidence['backupRestoreQualified'] is True and evidence['cells']==list(experiment.CELLS),
                           'owned independent qualification failed')
            except (Exception,KeyboardInterrupt) as error:report('validation-retention',error)
            try:
                with stage('cleanup') as deadline:
                    api.stage('cleanup',min(deadline/1e9,api.source.owner_deadline))
                    def persist():
                        nonlocal generation
                        generation=store.put(n.LEASE,lease,generation)
                    result['cleanup']=runner.cleanup(api.provider,lease,persist,authority=n,redact=True)
            except (Exception,KeyboardInterrupt) as error:report('cleanup',error)
            result['budgetBeforeCompletion']=budget.finish()
            result['status']=('PASS' if not result['errors'] and result['cleanup'] and result['cleanup']['status']=='PASS' and
                              result['budgetBeforeCompletion']['status']=='PASS' else 'FAIL')
            try:
                # Final control calls use the remaining control allowance and the
                # original lease; no fresh finalization/retention deadline.
                left=budget.limits['control']-budget.spent['control']
                api.stage('completion',min(api.source.owner_deadline,(budget.cursor+left)/1e9))
                completion={k:deepcopy(v) for k,v in result.items() if k not in ('retention','leaseReleased')}
                api.expected_completion=completion
                runner.finalize(store,lease,completion,authority=n);result['retention']='VERIFIED'
                if result['cleanup'] and result['cleanup']['status']=='PASS':
                    store.delete(n.LEASE,generation);result['leaseReleased']=True
            except (Exception,KeyboardInterrupt) as error:report('completion',error);result['status']='FAIL'
        # Resource/preparation failures use the existing immediate-owner recovery;
        # no second cleanup authority is created for the same invocation.
        result['budget']=budget.finish()
        if result['budget']['status']!='PASS':result['status']='FAIL'
        c.write_once(root/'receipt.json',result,maximum=1<<20)
    return result


def run_native(cfg,env,source,checkout,preflight,precheck_root,value,approved,artifacts,key,output):
    """Fresh native admission and fixed complete experiment; no injectable backend."""
    proof=deepcopy(value['artifacts'])
    transports=[]
    def prepare(root,continuation):
        def stage(api,key,root,guests):
            transports.append(api.transport)
            return setup._stage(api,key,root,guests,artifacts,proof,continuation=continuation)
        return resources._prepare_native(cfg,env,source,checkout,preflight,precheck_root,value,approved,artifacts,key,root,
            guest_stage=stage)
    try:return _execute(output,prepare)
    finally:
        for transport in transports:
            close=getattr(transport,'close',None)
            if close is not None:close()

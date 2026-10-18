"""Owned native Runner admission and resource lifetime, not a workload PASS.

Only the factory collects original CI/build/cleanup and current provider facts.
No copied receipt, injected client/token/clock or OfflineOwner opens this entry.
The returned session must be closed; its context manager owns renewal and cleanup.
"""
from copy import deepcopy
import math
import os
from pathlib import Path
import sys
import threading
import time
from scripts.v51 import cloud_http as h
from . import cloud_authority as a, cloud_control as c, cloud_provider as p, cloud_wire_policy as w
from . import cloud_preflight as f, cloud_preflight_read as reads, cloud_credentials as credentials
from . import cloud_inputs as inputs, cloud_prepared as prepared, cloud_ci as ci, cloud_artifacts as artifacts
from . import cloud_recent_cleanup as recent, cloud_native_cleanup as cleanup
from .evidence import need, encoded, digest, strict

_CAPABILITY = object()
FRESH_SECONDS = 900


def diagnostic(path,value):
    """A failed diagnostic write must not bypass cleanup or mask the cause."""
    try:artifacts.save(path,value)
    except Exception:
        try:print('v52RunnerDiagnosticRetention=FAIL',file=sys.stderr,flush=True)
        except Exception:pass


def ledger_baseline(snapshot):
    return None if snapshot is None else dict(generation=snapshot['generation'],ledger=deepcopy(snapshot['value']))


class _Admission:
    def __init__(self, source, cfg, plan, approval, confirmation, proof, observations, build, clean, started, ticket):
        need(ticket is _CAPABILITY,'V5.2 native Runner admission factory required')
        self.source=source;self.cfg=deepcopy(cfg);self.plan=deepcopy(plan);self.approval=deepcopy(approval)
        self.confirmation=confirmation;self.proof=deepcopy(proof);self.observations=deepcopy(observations)
        self.build=deepcopy(build);self.clean=deepcopy(clean);self.started=started
        self.request=deepcopy(plan['request']);self.request_sha=a.validate_request(self.request,domain='native')
        self.control=deepcopy(observations['controlAfter']);self.state='ADMITTED'
        self.check()

    def check(self):
        now=int(time.time());a.integer(now,self.started,self.started+FRESH_SECONDS-1)
        need(now<self.clean['expiresAt'],'V5.2 Runner cleanup observation expired')
        need(f.evaluate(self.cfg,self.source,'runner',self.observations,now=now)['status']=='PREFLIGHT_OBSERVED_NOT_ADMITTED',
             'V5.2 Runner provider preflight rejected')
        need(self.build['status']=='BUILD_PROVENANCE_VERIFIED_NOT_ADMITTED' and self.build['source']==self.source and
             self.build['buildBinding']==self.proof['source'] and self.build['buildManifestSha256']==self.proof['buildManifestSha256'],
             'V5.2 Runner original build binding')
        need(self.clean['status']=='RECENT_CLEANUP_VERIFIED_NOT_ADMITTED' and self.clean['source']==self.source and
             self.clean['configurationSha256']==f.configuration(self.cfg),'V5.2 Runner cleanup source/configuration')
        need(self.request['layout']==self.cfg['layout'] and self.request['policy']==self.cfg['policy'],
             'V5.2 Runner source-controlled layout/policy')
        return prepared.review(self.plan,self.approval,self.confirmation,current_inputs=self.proof,
            current_configuration=self.cfg['provider'],project_number=self.cfg['projectNumber'],
            current_ledger=ledger_baseline(self.control['ledger']),active_lease=self.control['lease'],now=now)

    def baseline(self,store,*,empty_lease):
        expected=self.control['ledger'];actual=store.get(a.LEDGER)
        need(actual==(None if expected is None else (expected['generation'],expected['value'])),
             'V5.2 Runner original ledger generation changed')
        if empty_lease:need(store.get(a.LEASE) is None,'V5.2 Runner lease appeared before acquisition')

    def before_write(self,api,route,body):
        # Called by the native transport AFTER token refresh and wire-policy
        # observations, immediately before the original mutation is submitted.
        if route['operation']!='put':return
        kind=route['kind']
        if kind==a.LEASE and body['phase']=='CLEANING':self.state='CLEANING';return
        if self.state in ('ACTIVE','CLEANING'):
            need(kind!='context' and not (kind==a.LEASE and route['expected']==0),'V5.2 Runner acquisition already consumed')
            return
        if kind=='context' or kind==a.LEASE and body['phase']=='ACQUIRING':
            need(self.state=='ADMITTED','V5.2 Runner acquisition already consumed');self.check()
            self.baseline(api.policy.store,empty_lease=True)
            if kind==a.LEASE:self.state='ACQUIRING'  # A lost reply cannot resubmit this CAS.
        elif kind==a.LEDGER:
            need(self.state=='ACQUIRING','V5.2 Runner reservation already consumed');self.check()
            self.baseline(api.policy.store,empty_lease=False);self.state='RESERVED'
        elif kind==a.LEASE and body['phase']=='ACTIVE':
            need(self.state=='RESERVED','V5.2 Runner activation without original charge');self.check();self.state='ACTIVE'
        else:raise ValueError('V5.2 Runner write before admission/activation')


class _RunnerGate(cleanup._NativeGate):
    def exchange(self,method,endpoint,headers,body,timeout,maximum):
        if method!='GET':
            value=strict(body) if body is not None else None;route=self.api.policy.route(method,endpoint,value)
            self.api.admission.before_write(self.api,route,value)
            timeout=min(timeout,self.api.deadline-self.api.clock())
            need(timeout>0,'V5.2 Runner original exchange deadline')
        return super().exchange(method,endpoint,headers,body,timeout,maximum)


class NativeRunnerApi(w._ScopedApi):
    def __init__(self,reader,admission,log,ticket):
        need(ticket is _CAPABILITY and type(reader) is reads.NetworkReader and reader.role=='runner' and
             type(admission) is _Admission,'V5.2 native Runner factory required')
        reader.guard();need(reader.source==admission.source and reader.configuration==admission.cfg,'V5.2 Runner reader binding')
        need(reader.tokens.binding['runId']!=admission.clean['runId'],'V5.2 Runner cannot be its own completed cleanup')
        self.reader=reader;self.admission=admission;self.closed=False;self.retained=None
        reservation=admission.plan['reservation']
        self.policy=w.Policy(admission.cfg['provider'],admission.request,role='runner',
            previous_cost=reservation['previousCostMicrousd'],cost=reservation['costMicrousd'],wall=time.time)
        self.lock=threading.RLock();self.deadline=math.inf;self.calls=self.writes=self.deletes=0;self.log=log
        super().__init__(transport=_RunnerGate(self,reader.transport),tokens=reader.tokens,clock=time.monotonic)

    def validate_adapter(self):
        need(not self.closed and type(self.reader) is reads.NetworkReader,'V5.2 native Runner closed/reader');self.reader.guard()
        need(type(self.transport) is _RunnerGate and self.transport.api is self and
             type(self.transport.server) is h.Network and self.transport.server is self.reader.transport and
             type(self.tokens) is credentials.NetworkCredentials and self.tokens is self.reader.tokens and
             self.clock is time.monotonic and self.reader.role=='runner' and self.policy.role=='runner' and self.policy.domain=='native' and
             self.reader.source==self.admission.source and self.reader.configuration==self.admission.cfg and
             self.policy.cfg==self.admission.cfg['provider'] and self.policy.req==self.admission.request and
             digest(encoded(self.policy.req))==self.admission.request_sha,'V5.2 native Runner adapter changed')

    def close(self):self.closed=True;self.token=None;self.expires=0


class NativeOwner(c._OwnedLifecycle):
    def __init__(self,store,provider,request,ticket):
        need(ticket is _CAPABILITY and type(store) is p.Store and type(store.api) is NativeRunnerApi,
             'V5.2 native owner factory required')
        super().__init__(store,provider,request,wall=lambda:int(time.time()));self.heartbeat=None

    def checkpoint(self):
        if self.heartbeat is not None:need(self.heartbeat.failure is None,'V5.2 Runner renewal failed')
        return super().checkpoint()


class _Heartbeat:
    def __init__(self,owner):
        self.owner=owner;self.stop=threading.Event();self.failure=None
        self.interval=min(30,owner.request['policy']['leaseSeconds']/3)
        self.thread=threading.Thread(target=self.run,name='v52-native-lease',daemon=True)

    def run(self):
        while not self.stop.wait(self.interval):
            try:self.owner.renew()
            except BaseException as error:self.failure=type(error).__name__;self.stop.set();return

    def start(self):self.thread.start()
    def close(self):
        self.stop.set()
        if self.thread.ident is not None:self.thread.join()  # Each in-flight original exchange is bounded.


class Session:
    """One admitted member; completion requires retained evidence and cleanup."""
    def __init__(self,reader,api,owner,log,output,package,ticket):
        need(ticket is _CAPABILITY and type(api) is NativeRunnerApi and type(owner) is NativeOwner,'V5.2 Runner session factory required')
        self.reader=reader;self.api=api;self.owner=owner;self.log=log;self.output=output;self.package=package
        self.closed=False;self.result=None;self.guests=None;self.guest_identity=None;self.storage=None
        self.staged=None;self.java=None;self.member_started=False;self.member_lock=threading.Lock();self.member_capture=None;self.retention_started=False
        self.heartbeat=_Heartbeat(owner);owner.heartbeat=self.heartbeat

    def start(self):
        cost=self.api.admission.plan['reservation']
        warning=self.owner.acquire(previous_cost=cost['previousCostMicrousd'],cost=cost['costMicrousd'])
        self.heartbeat.start();self.owner.provision();claim=self.owner.resource_claim()
        self.result=dict(schema='gse-v52-native-resources-v1',status='RESOURCES_PREPARED_NOT_QUALIFIED',
            source=self.reader.source,requestSha256=self.api.admission.request_sha,claim=claim,warning=warning,
            paidCloud=True,resourceAdmission=True,engineWorkloadExecuted=False,fullRemoteQualification=False)
        artifacts.save(self.output/'resources.json',self.result);return self

    def checkpoint(self):
        need(not self.closed,'V5.2 Runner session closed');return self.owner.resource_claim()

    def open_guests(self,key,output):
        from . import cloud_iap
        self.checkpoint();return cloud_iap.open_native(self,key,output)

    def retain_member(self,output):
        from . import cloud_retention
        return cloud_retention.publish(self,output)

    def run_member(self,key,output):
        from . import cloud_member
        return cloud_member.run(self,key,output)

    def close(self):
        if self.closed:return
        self.closed=True;guest_error=None
        try:
            if self.guests is not None:self.guests.close()
        except BaseException as error:guest_error=error
        self.heartbeat.close()
        try:
            result=self.owner.close()
            artifacts.save(self.output/'cleanup.json',dict(status='NOT_ACQUIRED' if result is None else result['status'],
                result=result,renewalFailure=self.heartbeat.failure,providerWrites=self.api.writes,
                resourceDeletesSubmitted=self.api.deletes,guestCloseFailure=None if guest_error is None else type(guest_error).__name__,
                fullRemoteQualification=False))
            need(result is None or result['status']=='PASS','V5.2 Runner resource cleanup incomplete')
            if guest_error is not None:raise guest_error
        finally:
            try:self.api.close()
            finally:
                try:self.reader.close()
                finally:
                    self.log.close()
                    if self.staged is not None:self.staged.close()

    def close_after_error(self):
        try:self.close()
        except BaseException as error:
            diagnostic(self.output/'cleanup-failure.json',dict(status='FAIL',errorType=type(error).__name__))

    def __enter__(self):
        try:self.checkpoint();return self
        except BaseException:
            self.close_after_error();raise

    def __exit__(self,kind,value,trace):
        if kind is None:self.close()
        else:self.close_after_error()
        return False


def open_native(source,plan_path,approval_path,confirmation,package_path,output,*,prepare_workload=False):
    """Own all observations and resources. Caller must close or use `with`.

    There is deliberately no provisioning-only CLI. The whole-member entry uses
    this scope; exiting records FAIL unless its original evidence was retained
    and the same scope completes exact-ID cleanup. Full-set replay is separate.
    """
    output=Path(output);need(not any(p.is_symlink() for p in (output,*output.parents)),'V5.2 Runner output symlink')
    output.mkdir(parents=True,exist_ok=False);phase='source';reader=api=session=log=staged=None;java=None
    try:
        started=int(time.time());cfg=reads.source_configuration(source)
        plan=strict(inputs.regular(plan_path,8<<20));approval=strict(inputs.regular(approval_path,65536))
        prepared.validate(plan,started);need(plan['request']['selection']['binding']['source']==source,'V5.2 Runner prepared source')
        a.validate_request(plan['request'],domain='native')
        expected=prepared.approval_template(plan);expected['confirmed']=True
        need(encoded(approval)==encoded(expected) and confirmation==expected['planSha256'],'V5.2 exact operator approval missing/changed')
        phase='original-build';artifacts.collect_native(source,output/'build-provenance')
        bound=inputs.checkout(ci.ROOT,source);shape=ci.contract()
        build=artifacts.replay(output/'build-provenance',source,shape,bound,now=int(time.time()))
        phase='package';package=output/'inputs.tar.gz'
        with package.open('xb') as stream:stream.write(inputs.regular(package_path,inputs.MAX_BYTES))
        proof=inputs.inspect(ci.ROOT,source,output/'build-provenance'/'build',package)
        if prepare_workload:
            from . import cloud_staging,remote_java_package
            phase='original-staging'
            staged=cloud_staging.stage(ci.ROOT,source,output/'build-provenance'/'build',package,output/'staging',expected=proof)
            phase='java-package'
            java=dict(descriptor=remote_java_package.create(ci.ROOT,bound,output/'java-package'),
                      archive=str(output/'java-package'/'runtime.tar.gz'))
            staged.check()
        phase='recent-cleanup';recent.collect_native(source,output/'recent-cleanup')
        clean=recent.validate(artifacts.read(output/'recent-cleanup'/'observation.json'),cfg,source,
            output/'recent-cleanup'/'cleanup.zip',int(time.time()))
        phase='provider';reader=reads.NetworkReader(cfg,source,'runner',dict(os.environ),output/'provider-reads',reads._NATIVE)
        observations=reads.collect(reader,wall=time.time);artifacts.save(output/'observations.json',observations)
        phase='approval';admission=_Admission(source,cfg,plan,approval,confirmation,proof,observations,build,clean,started,_CAPABILITY)
        review=admission.check();artifacts.save(output/'admission.json',dict(review=review,build=build,cleanup=clean,
            preflight=f.evaluate(cfg,source,'runner',observations,now=int(time.time())),resourceAdmission=False))
        phase='final-source';need(reads.source_configuration(source)==cfg and inputs.checkout(ci.ROOT,source)==bound and
            ci.contract()==shape,'V5.2 Runner source changed')
        reader.tokens.recheck(time.monotonic()+30)
        if staged is not None:staged.check()
        phase='resources';log=(output/'exchanges.jsonl').open('xb');api=NativeRunnerApi(reader,admission,log,_CAPABILITY)
        store=p.Store(cfg['provider'],api);provider=p.Provider(store,admission.request,wall=lambda:int(time.time()),sleep=time.sleep)
        owner=NativeOwner(store,provider,admission.request,_CAPABILITY)
        session=Session(reader,api,owner,log,output,package,_CAPABILITY)
        session.staged=staged;session.java=java
        return session.start()
    except BaseException as error:
        failure=dict(status='FAIL',phase=phase,code='V52_RUNNER_'+phase.upper().replace('-','_')+'_REJECTED',
            errorType=type(error).__name__,fullRemoteQualification=False)
        if type(error) is h.ApiError:failure['httpStatus']=error.status
        diagnostic(output/'failure.json',failure)
        if session is not None:
            try:session.close()
            except BaseException as cleanup_error:
                diagnostic(output/'cleanup-failure.json',dict(status='FAIL',errorType=type(cleanup_error).__name__))
        else:
            try:
                if api is not None:api.close()
            finally:
                try:
                    if reader is not None:reader.close()
                finally:
                    if log is not None:log.close()
                    if staged is not None:staged.close()
        raise

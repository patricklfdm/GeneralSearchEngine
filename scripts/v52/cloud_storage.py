"""Factory-owned native data volumes, installed capsule and whole-history placement.

No operator CLI, caller-supplied mount receipt or client can create this scope.
Source, lease and exact provider IDs bracket each guest action. Initialization
and installation are submitted once; only original-result queries may reconnect.
"""
import base64
from copy import deepcopy
from functools import wraps
import math
from pathlib import Path
import secrets
import shlex
import time
import uuid
import zlib
from . import cloud_iap as iap, cloud_native_runner as runner, cloud_inputs as inputs
from . import cloud_guest_identity as guest, cloud_volume_guest as volume, cloud_volume_paths as paths
from . import remote_python_package as package,remote_python_receiver as python,remote_python_ssh as install
from . import remote_bound_receivers as bound,remote_host as host
from . import cloud_storage_diagnostics as diagnostic
from .evidence import need,encoded,digest,strict

_TICKET=object()
ROOT=Path(__file__).resolve().parents[2]
CHECK_SECONDS=300
CHECK_ATTEMPTS=3


def recorded(method):
    @wraps(method)
    def run(self,*args,**kwargs):
        try:return method(self,*args,**kwargs)
        except BaseException as error:
            try:self.retain_failure(error)
            except Exception:pass  # Diagnostics must never replace the original failure.
            raise
    return run


def trusted_source(kind):
    need(kind in ('volume','paths'),'V5.2 storage receiver kind')
    modules=[guest,volume]+([paths] if kind=='paths' else [])
    sources={m.__name__.rsplit('.',1)[1]:Path(m.__file__).read_text() for m in modules}
    names=list(sources);packed=base64.b64encode(zlib.compress(encoded(sources))).decode()
    source=("import sys,types,json,zlib,base64\n"
        "p=types.ModuleType('trusted_v52');p.__path__=[];sys.modules['trusted_v52']=p\n"
        "sources=json.loads(zlib.decompress(base64.b64decode("+repr(packed)+")))\n"
        "for name in "+repr(names)+":\n"
        " q=types.ModuleType('trusted_v52.'+name);q.__package__='trusted_v52';sys.modules[q.__name__]=q\n"
        " exec(compile(sources[name],'<trusted-v52-'+name+'>','exec'),q.__dict__)\n"
        "raise SystemExit(sys.modules['trusted_v52."+names[-1]+"'].main())\n")
    need(len(source.encode())<=65536,'V5.2 storage trusted source bound');return source


def request(guests,node):
    guests.checkpoint();row=guests.observations[node];facts=row['facts'];claim=guests.claim
    return volume.validate(dict(schema=volume.SCHEMA,source=deepcopy(claim['source']),requestSha256=claim['requestSha256'],
        resourceClaimSha256=digest(encoded(claim)),resourceIdentitySha256=row['resourceIdentitySha256'],attempt=claim['attempt'],
        node=int(node[-1]),instanceId=facts['instanceId'],diskId=facts['dataDiskId'],bootDiskId=facts['bootDiskId'],
        sizeGiB=facts['dataDiskGiB'],bootSizeGiB=guests.session.owner.request['layout']['bootDiskGiB'],
        guest=deepcopy(guests.guests[node]),publicKey=guests.session.owner.request['guestAccess']['publicKey']))


def transient(error):return isinstance(error,(ConnectionError,TimeoutError)) and getattr(error,'retryable',True) is True


def readonly(call,deadline):
    for attempt in range(3):
        need(time.monotonic()<deadline,'V5.2 storage original query deadline')
        try:
            result=call()
            need(time.monotonic()<deadline,'V5.2 storage late query')
            return result
        except (ConnectionError,TimeoutError) as error:
            if not transient(error) or attempt==2:raise
            time.sleep(min(.2,max(0,deadline-time.monotonic())))


class VolumeEndpoint:
    def __init__(self,storage,guests,node):
        self.storage=storage;self.guests=guests;self.node=node;self.value=request(guests,node);self.calls=[]
        self.started=False;self.original=None;self.end=None;self.trace=[];self.received_at=None

    def checkpoint(self):
        self.storage.checkpoint(self.guests)
        self.guests.observe(self.node,time.monotonic()+30)
        need(request(self.guests,self.node)==self.value,'V5.2 storage guest binding changed')

    def call(self,action,token,end):
        self.storage.note(self.node,'volume',action,'precheck')
        self.checkpoint();need(time.monotonic()<end,'V5.2 storage original exchange deadline')
        self.calls.append(action);need(len(self.calls)<=256,'V5.2 storage connection bound')
        try:value=self.storage.exchange(self.guests,self.node,'volume',action,dict(request=self.value,token=token),end)
        except BaseException as error:
            self.trace.append(dict(action=action,errorType=type(error).__name__))
            raise
        # Capture response arrival before the potentially slow provider postcheck.
        self.received_at=getattr(self.storage,'reply_received_at',None)
        if self.received_at is None:self.received_at=time.monotonic()
        self.trace.append(dict(action=action,answer=deepcopy(value)))
        self.storage.note(self.node,'volume',action,'postcheck')
        self.checkpoint();need(time.monotonic()<end,'V5.2 storage late exchange')
        self.storage.note(self.node,'volume',action,'reply');return value

    def clock(self,seconds,deadline=None):
        # This is the original operation's grant, not a whole-experiment cap.
        # It fits the current lease+grace; lost replies cannot renew this grant.
        lease=self.guests.session.owner.checkpoint();remaining=lease['expiresAt']+lease['graceSeconds']-time.time()-5
        seconds=min(seconds,remaining);need(seconds>0,'V5.2 storage ownership grant expired')
        end=time.monotonic()+seconds
        if deadline is not None:end=min(end,deadline)
        nonce=secrets.token_hex(16)
        sample=readonly(lambda:self.call('clock',nonce,end),end)
        need(type(sample) is dict and set(sample)=={'schema','requestSha256','bootId','nonce','sampledNanos'} and
             sample['schema']=='gse-v52-volume-clock-v1' and sample['requestSha256']==volume.digest(self.value) and
             sample['bootId']==self.value['guest']['bootId'] and sample['nonce']==nonce,'V5.2 storage clock identity')
        volume.integer(sample['sampledNanos'],1,(1<<63)-1)
        # The remote sample predates receipt. This conservative translation can
        # never extend local authority; subtracting the later postcheck again
        # needlessly shortened the guest grant and caused early remote expiry.
        left=math.floor((end-self.received_at)*1e9);need(0<left<=volume.MAX_SECONDS*10**9,'V5.2 storage clock grant')
        return dict(sample=sample,expiresNanos=sample['sampledNanos']+left),end

    def exchange(self,action,token,end):
        result=self.call(action,token,end)
        need(type(result) is dict and set(result)=={'schema','requestSha256','budgetSha256','action','state','startup','readiness','process'} and
             result['schema']=='gse-v52-volume-answer-v1' and result['requestSha256']==volume.digest(self.value) and
             result['budgetSha256']==volume.digest(token) and result['action']==action and
             result['state'] in ('NOT_FOUND','UNCERTAIN','RUNNING','SUCCEEDED','FAILED'),'V5.2 storage reply identity')
        return result

    def prepare(self):
        need(not self.started,'V5.2 volume initialization already submitted');self.started=True
        token,end=self.clock(volume.MAX_SECONDS);self.original,self.end=deepcopy(token),end;answer=None
        try:answer=self.exchange('prepare',token,end)
        except (ConnectionError,TimeoutError) as error:
            if not transient(error):raise
        failures=0
        while answer is None or answer['state']=='RUNNING':
            need(time.monotonic()<end,'V5.2 volume original initialization deadline')
            if answer is not None:time.sleep(min(.2,max(0,end-time.monotonic())))
            try:answer=self.exchange('query',token,end);failures=0
            except (ConnectionError,TimeoutError) as error:
                if not transient(error):raise
                failures+=1;need(failures<3,'V5.2 volume query failures exhausted');answer=None
        need(answer['state']=='SUCCEEDED','V5.2 volume initialization unresolved/failed; no reformat')
        volume.replay(answer['startup'],self.value)
        need(answer['startup']['budgetSha256']==volume.digest(token),'V5.2 volume startup original grant')
        return self.check(answer['startup'])

    def check(self,startup):
        deadline=time.monotonic()+CHECK_SECONDS;attempts=[]
        for attempt in range(1,CHECK_ATTEMPTS+1):
            phase='clock';started=time.monotonic();error=None
            try:
                if started>=deadline:raise TimeoutError('V5.2 storage check original deadline')
                # A new clock is safe only for a fresh read. All attempts retain
                # this check's one deadline and each grant fits current ownership.
                token,end=self.clock(CHECK_SECONDS,deadline);deadline=min(deadline,end)
                phase='check';answer=self.exchange('check',token,end)
                need(answer['state']=='SUCCEEDED' and answer['startup']==startup and answer['process'] is None,'V5.2 original mount startup changed')
                checked=volume.replay(startup,self.value);ready=answer['readiness']
                need(type(ready) is dict and set(ready)=={'startupSha256','volume','observation'} and
                     ready['startupSha256']==volume.digest(startup) and ready['volume']==checked and
                     volume.mounted(ready['observation'],startup['before'],self.value)==checked,'V5.2 current mount evidence changed')
                if time.monotonic()>=deadline:raise TimeoutError('V5.2 storage late check')
                phase='complete';return answer
            except BaseException as failure:
                error=failure
                if not transient(failure) or attempt==CHECK_ATTEMPTS or time.monotonic()>=deadline:raise
            finally:
                now=time.monotonic()
                attempts.append(dict(attempt=attempt,phase=phase,elapsedMillis=max(0,int((now-started)*1000)),
                    remainingMillis=max(0,int((deadline-now)*1000)),reasonCode=None if error is None else diagnostic.reason(error)))
                self.storage.record_check(self.node,dict(limitSeconds=CHECK_SECONDS,attempts=deepcopy(attempts)))
            time.sleep(min(.2,max(0,deadline-time.monotonic())))


class Storage:
    def __init__(self,guests,output,ticket):
        need(ticket is _TICKET and type(guests) is iap.Guests and type(guests.session) is runner.Session and
             type(guests.session.api) is runner.NativeRunnerApi,'V5.2 native storage factory required')
        self.session=guests.session;self.claim=guests.checkpoint();self.output=host.path(str(output))
        need(not any(p.is_symlink() for p in (self.output,*self.output.parents)),'V5.2 storage output symlink')
        self.output.mkdir(parents=True,mode=0o700,exist_ok=False)
        self.source=deepcopy(self.session.api.admission.proof['source']);self.proof=deepcopy(self.session.api.admission.proof)
        self.volume_source=trusted_source('volume');self.paths_source=trusted_source('paths')
        self.records={};self.endpoints={};self.installations={};self.claimed=set();self.ready=False
        self.descriptor=self.payload=None
        self.java=None;self.java_started=False
        self.context=dict(node=None,operation='source',stage='begin',kind=None,action=None)
        self.failure=None;self.java_installations={};self.last_check=None;self.check_records=0

    def stage(self,node,operation):
        need(node in (None,*iap.topology.NODES) and operation in diagnostic.OPERATIONS,'V5.2 storage diagnostic context')
        self.context=dict(node=node,operation=operation,stage='begin',kind=None,action=None)
        self.last_check=None
        # Short explicit milestones complement the member's minute heartbeat.
        print(encoded(dict(stage='storage-progress',node=node,operation=operation)).decode(),flush=True)

    def note(self,node,kind,action,stage):
        self.context.update(node=node,kind=kind,action=action,stage=stage)

    def record_check(self,node,value):
        self.last_check=deepcopy(value)
        # Diagnostics cannot mask the original outcome or authorize success.
        self.check_records+=1
        try:runner.diagnostic(self.output/(node+f'-check-{self.check_records:04d}.json'),
            dict(node=node,operation=self.context['operation'],readCheck=value))
        except Exception:pass

    def retain_failure(self,error):
        if self.failure is not None:return
        self.failure=dict(schema=diagnostic.SCHEMA,status='FAIL',**self.context,
            reasonCode=diagnostic.reason(error),errorType=diagnostic.error_type(error),origin=diagnostic.origin(error),
            initializedNodes=list(self.records),pythonInstalledNodes=list(self.installations),javaInstalledNodes=list(self.java_installations))
        if self.last_check is not None:self.failure['readCheck']=deepcopy(self.last_check)
        runner.diagnostic(self.output/'diagnostic.json',self.failure)

    def checkpoint(self,guests):
        need(type(guests) is iap.Guests and guests.session is self.session and self.session.guests is guests and
             self.session.storage is self,'V5.2 storage route/session changed')
        need(guests.checkpoint()==self.claim and self.session.api.admission.proof==self.proof,'V5.2 storage original authority changed')
        need(all(self.source[k]==v for k,v in self.claim['source'].items()),'V5.2 storage original source changed')
        need(trusted_source('volume')==self.volume_source and trusted_source('paths')==self.paths_source,'V5.2 storage receiver source changed')

    def exchange(self,guests,node,kind,action,data,end):
        self.note(node,kind,action,'precheck')
        self.checkpoint(guests);args=iap.ssh.ssh.ssh_args(guests.targets[node])
        command=['/usr/bin/python3','-I','-S','-c',self.volume_source if kind=='volume' else self.paths_source,action]
        if kind=='volume':command=['sudo','-n','-u','root','-g','root','--',*command]
        args[-1]=shlex.join(command)
        self.note(node,kind,action,'transport');self.reply_received_at=None
        try:
            raw=iap.transport.process(args,encoded(data),end,maximum=volume.MAX_BYTES,retain_partial=True,
                env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'})
        except iap.transport.ProcessError as error:
            raise diagnostic.remote_error(error,action,data) from None
        self.reply_received_at=time.monotonic()
        self.note(node,kind,action,'postcheck');self.checkpoint(guests)
        self.note(node,kind,action,'reply');return strict(raw)

    @recorded
    def start(self,guests):
        self.stage(None,'source')
        self.checkpoint(guests)
        need(inputs.checkout(ROOT,self.source['source'])==self.source,'V5.2 storage checkout/toolchain changed')
        raw=inputs.regular(self.session.package,inputs.MAX_BYTES)
        need(len(raw)==self.proof['packageBytes'] and digest(raw)==self.proof['packageSha256'],'V5.2 storage original input package changed')
        self.payload,self.descriptor,_=package.compose(ROOT,self.source)
        need(inputs.checkout(ROOT,self.source['source'])==self.source,'V5.2 storage packaging source changed')
        runner.artifacts.save(self.output/'python-descriptor.json',self.descriptor)
        for node in iap.topology.NODES:
            self.stage(node,'volume-initialize')
            endpoint=VolumeEndpoint(self,guests,node);self.endpoints[node]=endpoint
            runner.artifacts.save(self.output/(node+'-request.json'),endpoint.value)
            mounted=endpoint.prepare();self.records[node]=mounted
            runner.artifacts.save(self.output/(node+'-volume.json'),mounted)
            self.stage(node,'python-install');endpoint.checkpoint();installer=install.Installer(guests.targets[node],self.descriptor)
            try:receipt=installer.install(volume.MOUNT,self.payload)
            finally:installer.close()
            host.validate_pin(receipt['host'])
            need(all(receipt['host'][k]==endpoint.value['guest'][k] for k in ('bootId','uid')),'V5.2 installed guest changed')
            self.installations[node]=receipt
            runner.artifacts.save(self.output/(node+'-python.json'),receipt)
            self.stage(node,'volume-ready')
            final=endpoint.check(mounted['startup']);runner.artifacts.save(self.output/(node+'-ready.json'),final)
        self.stage(None,'storage-receipt')
        self.checkpoint(guests)
        runner.artifacts.save(self.output/'receipt.json',dict(schema='gse-v52-native-storage-v1',status='STORAGE_READY_NOT_QUALIFIED',
            source=self.source,resourceClaimSha256=digest(encoded(self.claim)),pythonDescriptorSha256=digest(encoded(self.descriptor)),
            nodes={n:dict(volume=self.records[n]['startup']['volume'],installation=self.installations[n]) for n in iap.topology.NODES},
            mountedStorageVerified=True,engineWorkloadExecuted=False,fullRemoteQualification=False))
        self.ready=True
        return self

    @recorded
    def install_java(self,guests,descriptor,archive):
        from . import remote_java_receiver as j,remote_java_ssh as js
        self.stage(None,'java-image')
        self.checkpoint(guests);need(self.ready and not self.java_started,'V5.2 Java installation not ready/already consumed')
        descriptor=deepcopy(j.descriptor(descriptor));need(descriptor['source']==self.source,'V5.2 Java original input source changed')
        j.verify_archive(archive,descriptor);self.java_started=True
        retained=self.output/'java-runtime.tar.gz'
        # Retain the exact originally built image before any guest submission.
        with Path(archive).open('rb') as source,retained.open('xb') as out:
            while raw:=source.read(j.PIECE):out.write(raw)
        j.verify_archive(retained,descriptor);runner.artifacts.save(self.output/'java-image.json',descriptor)
        installations=self.java_installations
        try:
            for node in iap.topology.NODES:
                self.stage(node,'java-volume-before')
                endpoint=VolumeEndpoint(self,guests,node);endpoint.check(self.records[node]['startup'])
                self.stage(node,'java-install')
                installer=js.Installer(guests.targets[node],descriptor)
                try:receipt=installer.install(volume.MOUNT,retained)
                finally:installer.close()
                self.checkpoint(guests);host.validate_pin(receipt['host'])
                need(receipt['host']==self.installations[node]['host'],'V5.2 Java original installation host/directory changed')
                installations[node]=receipt;runner.artifacts.save(self.output/(node+'-java.json'),receipt)
                self.stage(node,'java-volume-after')
                endpoint.check(self.records[node]['startup'])
            self.stage(None,'java-receipt')
            self.checkpoint(guests)
            runner.artifacts.save(self.output/'java-receipt.json',dict(status='JAVA_READY_NOT_QUALIFIED',source=self.source,
                descriptorSha256=digest(encoded(descriptor)),nodes=installations,engineWorkloadExecuted=False,fullRemoteQualification=False))
            self.java=dict(descriptor=descriptor,archive=str(retained),installations=installations)
        except BaseException as error:
            runner.diagnostic(self.output/'java-failure.json',dict(status='FAIL',errorType=type(error).__name__,installedNodes=list(installations)))
            raise
        return self

    @recorded
    def placement(self,guests,name):
        self.stage(None,'placement-source')
        self.checkpoint(guests);need(self.ready,'V5.2 storage not ready')
        need(not self.java_started or self.java is not None,'V5.2 original Java installation incomplete')
        need(name in self.session.owner.request['selection']['member']['histories'] and name not in self.claimed,
             'V5.2 original whole history already claimed/undeclared');self.claimed.add(name)
        history=digest(encoded([self.claim['requestSha256'],name]));roots={}
        for node in iap.topology.NODES:
            self.stage(node,'placement-volume')
            endpoint=VolumeEndpoint(self,guests,node)
            need(endpoint.value==self.endpoints[node].value,'V5.2 history changed original volume')
            startup=self.records[node]['startup'];endpoint.check(startup)
            self.stage(node,'placement-python')
            installer=install.Installer(guests.targets[node],self.descriptor)
            try:current=readonly(lambda:installer.exchange('verify',volume.MOUNT,None),time.monotonic()+90)
            finally:installer.close()
            need(current==self.installations[node],'V5.2 history installed capsule changed')
            if self.java is not None:
                from . import remote_java_ssh as js
                self.stage(node,'placement-java')
                installer=js.Installer(guests.targets[node],self.java['descriptor'])
                try:current_java=readonly(lambda:installer.exchange('verify',volume.MOUNT),time.monotonic()+90)
                finally:installer.close()
                need(current_java==self.java['installations'][node],'V5.2 history installed Java changed')
            self.stage(node,'placement-parent')
            data=dict(request=endpoint.value,volume=startup['volume'],history=history);end=time.monotonic()+60
            answer=None
            try:answer=self.exchange(guests,node,'paths','prepare',data,end)
            except (ConnectionError,TimeoutError) as error:
                if not transient(error):raise
            if answer is None:answer=readonly(lambda:self.exchange(guests,node,'paths','query',data,end),end)
            claim=dict(requestSha256=volume.digest(endpoint.value),historySha256=history,volume=startup['volume'])
            expected=str(Path(volume.MOUNT)/('history-'+history)/node)
            need(type(answer) is dict and set(answer)=={'schema','claimSha256','state','root','host'} and
                 answer['schema']=='gse-v52-history-parent-v1' and answer['claimSha256']==volume.digest(claim) and
                 answer['state']=='SUCCEEDED' and answer['root']==expected,'V5.2 history parent unresolved/changed')
            host.validate_pin(answer['host']);need(all(answer['host'][k]==endpoint.value['guest'][k] for k in ('bootId','uid')) and
                answer['host']['parentDevice']==current['host']['parentDevice'],'V5.2 history parent guest/device changed')
            roots[node]=expected;endpoint.check(startup)
            runner.artifacts.save(self.output/(history+'-'+node+'.json'),dict(parent=answer,installation=current))
        self.stage(None,'placement-binding')
        binding=guests.binding(str(uuid.UUID(hex=history[:32])))
        binding.update(deepcopy(self.source));self.checkpoint(guests)
        return bound.Placement(binding,guests.targets,roots,self.installations,self.descriptor,self.payload,java=self.java)


def prepare_native(guests,output):
    need(type(guests) is iap.Guests and type(guests.session) is runner.Session and type(guests.session.api) is runner.NativeRunnerApi,
         'V5.2 native storage factory required')
    session=guests.session;guests.checkpoint();need(session.storage is None,'V5.2 storage initialization already consumed')
    storage=Storage(guests,output,_TICKET);session.storage=storage
    try:return storage.start(guests)
    except BaseException as error:
        storage.ready=False
        runner.diagnostic(storage.output/'failure.json',dict(status='FAIL',code='V52_STORAGE_FAILED',errorType=type(error).__name__,
            initializedNodes=list(storage.records),engineWorkloadExecuted=False,fullRemoteQualification=False))
        raise
    finally:
        for node,endpoint in storage.endpoints.items():
            runner.diagnostic(storage.output/(node+'-exchanges.json'),dict(request=endpoint.value,
                originalGrant=endpoint.original,exchanges=endpoint.trace))

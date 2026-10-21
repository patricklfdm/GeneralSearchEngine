"""Owned private IAP routes and read-only native guest identity.

The native Runner supplies authority. One accepted local SSH connection starts
one SDK stdin tunnel with its own current credential. Neither this transport nor
its lifetime watcher retries a business request or replays connection bytes.
"""
from copy import deepcopy
from collections import deque
import os
from pathlib import Path
import selectors
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from . import cloud_native_runner as runner, cloud_identity as identity, cloud_access as access
from . import remote_command as command, remote_host as host, remote_host_domains as domains
from . import remote_topology as topology, remote_voter_ssh as ssh, remote_voter_ssh_evidence as routes
from . import cloud_guest_identity as probe
from . import cloud_iap_diagnostics as diagnostics
from . import cloud_sdk_runtime as sdk_runtime, cloud_read_retry
from .evidence import need, encoded, digest, strict
from scripts.v51 import guest_transport as transport

_TICKET=object()
BUFFER=64<<10
MAX_RECENT=64
MAX_ACTIVE=4
CONNECT_SECONDS=60
ADMISSION_SECONDS=30
ADMISSION_ATTEMPTS=2
ADMISSION_BACKOFF=1
HALF_CLOSE_SECONDS=30


def _gcloud():
    return sdk_runtime.executable()


def _private(path,raw):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())


def _safe(error):
    if type(error) is cloud_read_retry.ReadError:return error.code
    if type(error) is sdk_runtime.SdkError:return error.code
    if type(error) in (transport.ProcessError,transport.ProcessRejected):return error.code
    if type(error) is runner.h.ApiError and type(error.status) is int and 100<=error.status<=599:
        return 'IAP_PROVIDER_HTTP_'+str(error.status)
    if type(error) is runner.credentials.ContextError:return error.reason_code
    if type(error) is runner.credentials.exchange.CredentialError:return error.reason_code
    if type(error) is runner.p.ControlReadError:return error.code
    if isinstance(error,TimeoutError):return 'IAP_ORIGINAL_CONNECT_TIMEOUT'
    if isinstance(error,ConnectionError):return 'SSH_DISCONNECTED'
    return 'IAP_IDENTITY_OR_AUTHORITY_REJECTED'


def _remaining(deadline):
    left=deadline-time.monotonic()
    if left<=0:raise TimeoutError('V5.2 IAP admission deadline')
    return left


def _retry_admission(error):
    # Before SDK spawn only. Unknown errors, denied credentials and changed
    # ownership are terminal even when they happen near a deadline.
    return type(error) in (TimeoutError,ConnectionError) or (type(error) is runner.credentials.ContextError and
                                          error.reason_code=='V52_CREDENTIAL_DEADLINE')


class _Channel:
    def __init__(self,forward,connection,ordinal):
        self.forward=forward;self.connection=connection;self.ordinal=ordinal
        self.stop=threading.Event();self.proc=None;self.lock=threading.Lock();self.killed=False
        self.record=dict(ordinal=ordinal,status='STARTING',failureCode=None,sentBytes=0,receivedBytes=0)
        self.admission=[]
        self.thread=threading.Thread(target=self.run,name='v52-iap-channel',daemon=True)

    def start(self):self.thread.start()

    def run(self):
        deadline=time.monotonic()+CONNECT_SECONDS
        temporary=None
        try:
            for attempt in range(1,ADMISSION_ATTEMPTS+1):
                if self.stop.is_set():return
                _remaining(deadline)
                temporary=tempfile.TemporaryDirectory(prefix='channel-',dir=self.forward.group.private.name)
                began=time.monotonic();phase='directory';phase_began=began;durations={}
                def progress(next_phase):
                    nonlocal phase,phase_began
                    need(next_phase in diagnostics.PHASES,'V5.2 IAP diagnostic phase')
                    now=time.monotonic()
                    durations[phase]=durations.get(phase,0)+max(0,round((now-phase_began)*1000))
                    phase,phase_began=next_phase,now
                try:
                    attempt_end=min(deadline,began+ADMISSION_SECONDS)
                    args,env=self.forward.group.authorize(self.forward.node,Path(temporary.name),
                        attempt_end,progress=progress)
                    _remaining(attempt_end)
                except BaseException as error:
                    progress(phase)
                    row=diagnostics.attempt(attempt,phase,began,durations,error,_safe(error))
                    self.admission.append(row)
                    retry=attempt<ADMISSION_ATTEMPTS and _retry_admission(error) and not self.stop.is_set() and \
                          deadline-time.monotonic()>ADMISSION_BACKOFF
                    try:print(encoded(dict(stage='iap-admission',node=self.forward.node,retry=retry,**row)).decode(),flush=True)
                    except Exception:pass  # Diagnostic output cannot replace the original error.
                    temporary.cleanup();temporary=None
                    if not retry:raise
                    if self.stop.wait(ADMISSION_BACKOFF):return
                    continue
                progress(phase)
                self.admission.append(diagnostics.attempt(attempt,phase,began,durations))
                break
            with self.lock:
                need(not self.stop.is_set(),'V5.2 IAP channel closed before spawn')
                self.proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                           start_new_session=True,env=env)
            self.record.update(status='OPEN',pid=self.proc.pid)
            self.pump(deadline)
            self.record['status']='CLOSED'
        except BaseException as error:
            self.record.update(status='CLOSED' if self.stop.is_set() else 'FAIL',
                               failureCode=None if self.stop.is_set() else _safe(error))
            if not self.stop.is_set() and not (isinstance(error,(ConnectionError,TimeoutError)) and getattr(error,'retryable',True)):
                self.forward.group.fail(self.record['failureCode'])
        finally:
            if self.stop.is_set() and self.record['status'] in ('STARTING','OPEN'):self.record['status']='CLOSED'
            self.terminate()
            try:
                proc=self.proc
                if proc is not None:
                    proc.wait(timeout=5)
                    for stream in (proc.stdin,proc.stdout,proc.stderr):stream.close()
            finally:
                self.connection.close()
                if temporary is not None:temporary.cleanup()

    def pump(self,deadline):
        proc=self.proc;sock=self.connection;sock.setblocking(False)
        for stream in (proc.stdin,proc.stdout,proc.stderr):os.set_blocking(stream.fileno(),False)
        outgoing=bytearray();incoming=bytearray();errors=bytearray()
        client_eof=server_eof=False;remote_seen=False;stderr_eof=False;stdin_closed=False;closing=None
        with selectors.DefaultSelector() as selector:
            while not self.stop.is_set():
                if not remote_seen and time.monotonic()>=deadline:raise TimeoutError('V5.2 IAP original connect deadline')
                if closing is not None and time.monotonic()>=closing:return
                wanted={}
                def watch(file,mask,kind):
                    if mask:wanted[file]=(mask,kind)
                watch(sock,(0 if client_eof or len(outgoing)>=BUFFER else selectors.EVENT_READ)|
                           (selectors.EVENT_WRITE if incoming else 0),'socket')
                if not stdin_closed:watch(proc.stdin,selectors.EVENT_WRITE if outgoing else 0,'input')
                watch(proc.stdout,selectors.EVENT_READ if not server_eof and len(incoming)<BUFFER else 0,'output')
                watch(proc.stderr,0 if stderr_eof else selectors.EVENT_READ,'error')
                for key in list(selector.get_map().values()):
                    if key.fileobj not in wanted:selector.unregister(key.fileobj)
                for file,(mask,kind) in wanted.items():
                    try:selector.modify(file,mask,kind)
                    except KeyError:selector.register(file,mask,kind)
                for key,mask in selector.select(.1):
                    if key.data=='socket':
                        if mask & selectors.EVENT_READ:
                            try:chunk=sock.recv(BUFFER-len(outgoing))
                            except BlockingIOError:continue
                            if chunk:outgoing.extend(chunk)
                            else:client_eof=True
                        if mask & selectors.EVENT_WRITE:
                            try:sent=sock.send(incoming)
                            except BlockingIOError:continue
                            del incoming[:sent];self.record['receivedBytes']+=sent
                    elif key.data=='input':
                        try:sent=os.write(proc.stdin.fileno(),outgoing)
                        except BlockingIOError:continue
                        except BrokenPipeError:outgoing.clear();stdin_closed=True;continue
                        del outgoing[:sent];self.record['sentBytes']+=sent
                    else:
                        limit=BUFFER-len(incoming) if key.data=='output' else 4096
                        try:chunk=os.read(key.fileobj.fileno(),limit)
                        except BlockingIOError:continue
                        if key.data=='output':
                            if chunk:remote_seen=True;incoming.extend(chunk)
                            else:server_eof=True
                        elif chunk:
                            errors.extend(chunk);need(len(errors)<=BUFFER,'V5.2 IAP diagnostic bound')
                        else:stderr_eof=True
                if client_eof and not outgoing and not stdin_closed:
                    # Preserve TCP half-close and drain the original response.
                    # Closing a channel never starts another SDK process.
                    try:selector.unregister(proc.stdin)
                    except KeyError:pass
                    proc.stdin.close();stdin_closed=True;closing=time.monotonic()+HALF_CLOSE_SECONDS
                if server_eof and not incoming and stderr_eof:
                    code=proc.poll()
                    if code is None:
                        proc.wait(timeout=5);code=proc.returncode
                    if code and not client_eof:raise transport.exit_error(255,bytes(errors),ssh=True)
                    return

    def terminate(self):
        self.stop.set()
        try:self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:pass
        with self.lock:
            if self.proc is not None and not self.killed:
                self.killed=True
                try:os.killpg(self.proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass

    def close(self):
        self.terminate()
        if self.thread.ident is not None and self.thread is not threading.current_thread():self.thread.join()


class _Forward:
    def __init__(self,group,node):
        self.group=group;self.node=node;self.stop=threading.Event();self.channels=[];self.lock=threading.Lock()
        self.recent=deque(maxlen=MAX_RECENT)
        self.totals=dict(accepted=0,completed=0,failed=0,peakActive=0,capacityRejections=0,
                         sentBytes=0,receivedBytes=0,lastFailureCode=None,
                         admissionRetries=0,admissionMillis=0,lastAdmission=None)
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            self.sock.bind(('127.0.0.1',0));self.sock.listen(MAX_ACTIVE);self.sock.settimeout(.1)
        except BaseException:self.sock.close();raise
        self.port=self.sock.getsockname()[1]
        self.thread=threading.Thread(target=self.run,name='v52-iap-'+node,daemon=True)

    def start(self):self.thread.start()

    def reap(self):
        # Caller holds lock. A stopped thread has finished process reaping and
        # private credential cleanup; merely closing its socket is insufficient.
        active=[]
        for channel in self.channels:
            if channel.thread.is_alive():active.append(channel);continue
            row=dict(channel.record);self.recent.append(row);self.totals['completed']+=1
            self.totals['admissionRetries']+=max(0,len(channel.admission)-1)
            self.totals['admissionMillis']+=sum(v['elapsedMillis'] for v in channel.admission)
            if channel.admission and (len(channel.admission)>1 or channel.admission[-1]['status']=='FAIL'):
                self.totals['lastAdmission']=deepcopy(channel.admission)
            for key in ('sentBytes','receivedBytes'):self.totals[key]+=row[key]
            if row['failureCode'] is not None:
                self.totals['failed']+=1;self.totals['lastFailureCode']=row['failureCode']
        self.channels=active

    def snapshot(self):
        with self.lock:
            self.reap()
            return dict(self.totals,active=len(self.channels),
                        historyDropped=self.totals['completed']-len(self.recent),
                        recent=[dict(row) for row in self.recent],
                        activeRecords=[dict(c.record) for c in self.channels])

    def run(self):
        while not self.stop.is_set():
            try:connection,_=self.sock.accept()
            except socket.timeout:continue
            except OSError:
                if not self.stop.is_set():self.group.fail('IAP_LISTENER_CLOSED')
                return
            with self.lock:
                self.reap()
                if self.stop.is_set():connection.close();continue
                if len(self.channels)>=MAX_ACTIVE:
                    self.totals['capacityRejections']+=1
                    connection.close();continue
                self.totals['accepted']+=1
                channel=_Channel(self,connection,self.totals['accepted']);self.channels.append(channel);channel.start()
                self.totals['peakActive']=max(self.totals['peakActive'],len(self.channels))

    def stop_channels(self):
        # Terminal failures can arrive on several channel threads together.
        # Signal every owner here; only the outer scope joins threads, avoiding
        # two failing channels joining each other during fail-closed shutdown.
        self.stop.set();self.sock.close()
        with self.lock:channels=list(self.channels)
        for channel in channels:channel.terminate()

    def close(self):
        self.stop_channels()
        if self.thread.ident is not None and self.thread is not threading.current_thread():self.thread.join()
        with self.lock:channels=list(self.channels)
        for channel in channels:channel.close()
        with self.lock:self.reap()


class Guests:
    """One owned guest route scope. It observes identities, not mounted storage."""
    def __init__(self,session,key,output,ticket):
        need(ticket is _TICKET and type(session) is runner.Session and type(session.api) is runner.NativeRunnerApi,
             'V5.2 native IAP factory required')
        self.session=session;self.key=host.path(str(key));self.output=host.path(str(output))
        need(not any(p.is_symlink() for p in (self.output,*self.output.parents)),'V5.2 IAP output symlink')
        self.claim=session.checkpoint();access.check_private_key(self.key,session.owner.request['guestAccess'])
        self.key_sha=digest(self.key.read_bytes());self.sdk=_gcloud();self.observations={};self.guests={};self.forwards={};self.targets={};self.original_targets={}
        self.failure=None;self.closed=False;self.output_identity=None;self.stop=threading.Event();self.lock=threading.RLock()
        self.private=tempfile.TemporaryDirectory(prefix='gse-v52-iap-')
        self.watch_thread=threading.Thread(target=self.watch,name='v52-iap-authority',daemon=True)
        self.probe_source=Path(probe.__file__).read_text()

    def cheap_check(self):
        need(not self.closed and not self.stop.is_set() and self.failure is None,'V5.2 IAP scope closed/failed')
        need(not self.session.closed and self.session.heartbeat.failure is None,'V5.2 IAP owner/renewal failed')
        self.session.api.validate_adapter()
        need(self.key.is_file() and not self.key.is_symlink() and 0<self.key.stat().st_size<=65536 and
             digest(self.key.read_bytes())==self.key_sha,
             'V5.2 IAP key changed')
        need(self.targets==self.original_targets,'V5.2 IAP routes changed')
        for target in self.targets.values():ssh.public_target(target)
        for node,target in self.targets.items():
            need(digest(Path(target['knownHosts']).read_bytes())==self.observations[node]['sshHostPinSha256'],
                 'V5.2 IAP host pin changed')

    def checkpoint(self):
        self.cheap_check();need(self.session.checkpoint()==self.claim,'V5.2 IAP allocation changed')
        return deepcopy(self.claim)

    def fail(self,code):
        with self.lock:
            if self.failure is None:self.failure=code
            self.stop.set()
        for forward in list(self.forwards.values()):
            try:forward.stop_channels()
            except BaseException:self.failure='IAP_CLOSE_INCOMPLETE'

    def watch(self):
        checked=time.monotonic()
        try:
            while not self.stop.wait(1):
                self.cheap_check()
                if time.monotonic()-checked>=30:self.checkpoint();checked=time.monotonic()
        except BaseException:
            if not self.stop.is_set():self.fail('IAP_OWNER_OR_PIN_CHANGED')

    def observe(self,node,deadline):
        self.checkpoint()
        value=identity.observe(self.session.owner.provider,self.claim,node,deadline=deadline)
        need(value['execution']=='native-v52-provider-observation' and value['paidCloud'] is True,
             'V5.2 IAP native observation required')
        if node in self.observations:need(value==self.observations[node],'V5.2 IAP provider identity changed')
        return value

    def authorize(self,node,directory,deadline,*,progress=lambda stage:None):
        need(node in self.observations,'V5.2 IAP unknown guest');_remaining(deadline)
        progress('directory')
        directory=host.path(str(directory));command.directory(directory)
        info=directory.stat()
        need(directory.parent==Path(self.private.name) and info.st_uid==os.getuid() and info.st_mode&0o077==0,
             'V5.2 IAP credential directory outside owned scope')
        owner=self.session.owner
        progress('owner-lock')
        if not owner.lock.acquire(timeout=_remaining(deadline)):raise TimeoutError('V5.2 IAP authority queue deadline')
        api=self.session.api;locked=False;original=None
        try:
            progress('api-lock')
            if not api.lock.acquire(timeout=_remaining(deadline)):raise TimeoutError('V5.2 IAP API queue deadline')
            locked=True
            original=api.deadline;api.deadline=min(original,deadline)
            progress('identity-before');_remaining(deadline)
            self.cheap_check();value=self.observe(node,deadline)
            # Match owner -> API lock order used by renewal. A later socket gets
            # a new credential epoch; no ambient SDK/ADC identity is accepted.
            progress('credentials')
            token=api.tokens(min(30,_remaining(deadline)))
            need(type(token) is runner.h.AccessToken and token.usable_until>time.monotonic()+10,
                 'V5.2 IAP credential lifetime')
            api.token,api.expires=token.value,token.usable_until
            progress('identity-after');_remaining(deadline)
            self.observe(node,deadline);_remaining(deadline)
            progress('credential-file')
            config=directory/'config';config.mkdir(mode=0o700);path=directory/'token'
            need(type(token.value) is str and 0<len(token.value)<=16384 and all(33<=ord(c)<=126 for c in token.value),
                 'V5.2 IAP token shape')
            _private(path,token.value.encode('ascii'))
            env=sdk_runtime.environment(config)
            args=[self.sdk,'compute','start-iap-tunnel',value['facts']['instance'],'22','--listen-on-stdin',
                  '--project='+value['project'],'--zone='+value['zone'],'--access-token-file='+str(path),
                  '--quiet','--verbosity=error']
            return args,env
        finally:
            if locked:
                if original is not None:api.deadline=original
                api.lock.release()
            owner.lock.release()

    def probe(self,node):
        self.observe(node,time.monotonic()+30);row=self.observations[node]
        need(Path(probe.__file__).read_text()==self.probe_source,'V5.2 IAP probe source changed')
        expected=dict(instanceId=row['facts']['instanceId'],privateAddress=row['facts']['privateAddress'],
            user=self.session.owner.request['guestAccess']['user'],publicKey=self.session.owner.request['guestAccess']['publicKey'])
        args=ssh.ssh.ssh_args(self.targets[node]);args[-1]=shlex.join(['python3','-I','-S','-c',self.probe_source])
        try:raw=transport.process(args,encoded(expected),time.monotonic()+60,maximum=4096,
                                  env=dict(PATH='/usr/bin:/bin',LANG='C',LC_ALL='C'))
        except Exception as error:raise ValueError('V5.2 IAP probe failed: '+_safe(error)) from None
        value=probe.validate(strict(raw))
        need(all(value[k]==expected[k] for k in ('instanceId','privateAddress','user')),'V5.2 IAP wrong guest')
        self.observe(node,time.monotonic()+30)
        if node in self.guests:need(value==self.guests[node],'V5.2 IAP guest boot/user changed')
        return value

    def start(self):
        self.output.mkdir(parents=True,mode=0o700,exist_ok=False);command.directory(self.output)
        info=self.output.stat();self.output_identity=(info.st_dev,info.st_ino)
        deadline=time.monotonic()+300
        for node in topology.NODES:
            pending=0
            while True:
                try:self.observations[node]=self.observe(node,min(deadline,time.monotonic()+30));break
                except access.HostKeyPending:
                    pending+=1;need(pending<30 and time.monotonic()<deadline,'V5.2 IAP host-key readiness exhausted')
                    time.sleep(min(3,max(0,deadline-time.monotonic())))
            row=self.observations[node];known=self.output/(node+'.known_hosts');access.pin(known,row['alias'],row['hostKey'])
            forward=_Forward(self,node);self.forwards[node]=forward
            self.targets[node]=dict(host='127.0.0.1',port=forward.port,connectSeconds=CONNECT_SECONDS,user=self.session.owner.request['guestAccess']['user'],
                key=str(self.key),knownHosts=str(known),alias=row['alias'])
            self.original_targets[node]=deepcopy(self.targets[node]);forward.start()
        self.watch_thread.start()
        for node in topology.NODES:self.guests[node]=self.probe(node)
        need(len({g['bootId'] for g in self.guests.values()})==3 and
             len({r['facts']['privateAddress'] for r in self.observations.values()})==3 and
             len({r['facts']['instanceId'] for r in self.observations.values()})==3 and
             len({r['hostKey'] for r in self.observations.values()})==3,'V5.2 independent native guests required')
        observed=dict(provider=self.observations,guests=self.guests)
        need(self.session.guest_identity is None or self.session.guest_identity==observed,'V5.2 same-owner guest identity changed')
        self.checkpoint();runner.artifacts.save(self.output/'identity.json',dict(schema='gse-v52-native-guest-scope-v1',
            status='GUEST_IDENTITIES_VERIFIED_NOT_QUALIFIED',execution='native-v52-iap-identity',paidCloud=True,
            claim=self.claim,provider=self.observations,guests=self.guests,
            targets={n:ssh.public_target(t) for n,t in self.targets.items()},mountedStorageVerified=False,
            engineWorkloadExecuted=False,fullRemoteQualification=False))
        self.session.guest_identity=deepcopy(observed)
        return self

    def binding(self,group_id):
        # The caller still must establish data mounts and install the exact Python
        # capsule before passing this fresh identity binding into Placement.
        for node in topology.NODES:self.probe(node)
        plan=dict(schema=topology.SCHEMA,placement='owned-private-hosts',groupId=group_id,
                  members=[dict(node=n,host=self.observations[n]['facts']['privateAddress'],
                     port=self.session.owner.provider.config['port']) for n in topology.NODES])
        value=dict(**self.claim['source'],remoteTopology=plan,
            remoteHostDomains=dict(schema=domains.SCHEMA,source=self.claim['source'],attempt=self.claim['attempt'],
                leaseSha256=digest(encoded(self.claim)),nodes={n:dict(resourceIdentitySha256=self.observations[n]['resourceIdentitySha256'],
                    privateAddress=self.observations[n]['facts']['privateAddress'],bootId=self.guests[n]['bootId'],uid=self.guests[n]['uid'],
                    sshHostPinSha256=self.observations[n]['sshHostPinSha256']) for n in topology.NODES}),
            remoteVoterTransport=dict(schema=routes.SCHEMA,execution=routes.BOUND_EXECUTION,
                nodes={n:ssh.public_target(t) for n,t in self.targets.items()}))
        domains.validate(value);domains.routes(value);self.checkpoint();return deepcopy(value)

    def prepare_storage(self,output):
        from . import cloud_storage
        self.checkpoint();return cloud_storage.prepare_native(self,output)

    def close(self):
        with self.lock:
            if self.closed:return
            self.closed=True;self.stop.set()
        error=None
        try:
            for forward in self.forwards.values():
                try:forward.close()
                except BaseException as failure:
                    if error is None:error=failure
            if self.watch_thread.ident is not None and self.watch_thread is not threading.current_thread():self.watch_thread.join()
        finally:
            self.private.cleanup()
            self.diagnostic('connections.json',dict(schema='gse-v52-iap-connections-v2',
                status='FAIL' if self.failure or error else 'CLOSED',failureCode=self.failure,
                closeFailure=None if error is None else type(error).__name__,
                nodes={n:f.snapshot() for n,f in self.forwards.items()},fullRemoteQualification=False))
        if error is not None:raise error

    def diagnostic(self,name,value):
        if self.output_identity is None:return
        try:
            need(name in ('connections.json','close-failure.json'),'V5.2 guest diagnostic name')
            command.directory(self.output);info=self.output.stat()
            need((info.st_dev,info.st_ino)==self.output_identity,'V5.2 guest output replaced')
        except Exception:
            try:print('v52GuestDiagnosticRetention=FAIL',file=sys.stderr,flush=True)
            except Exception:pass
            return
        runner.diagnostic(self.output/name,value)

    def close_after_error(self):
        try:self.close()
        except BaseException as error:self.diagnostic('close-failure.json',dict(status='FAIL',errorType=type(error).__name__))

    def __enter__(self):
        try:self.checkpoint();return self
        except BaseException:self.close_after_error();raise

    def __exit__(self,kind,value,trace):
        if kind is None:self.close()
        else:self.close_after_error()
        return False


def open_native(session,key,output):
    need(type(session) is runner.Session and type(session.api) is runner.NativeRunnerApi,
         'V5.2 native IAP session required')
    need(getattr(session,'guests',None) is None or session.guests.closed,'V5.2 IAP guest scope already active')
    group=Guests(session,key,output,_TICKET);session.guests=group
    try:return group.start()
    except BaseException:
        group.close_after_error();raise

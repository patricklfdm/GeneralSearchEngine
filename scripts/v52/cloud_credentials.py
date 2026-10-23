"""V5.2 exact-workflow credential entry; credentials alone grant no cloud work.

The native factory performs read-only source/GitHub/descriptor checks. Its fixed
OIDC -> STS -> impersonation exchange is reusable by a future scoped API; no
Compute/Storage adapter, deployment, workflow or paid admission is enabled here.
"""
from copy import deepcopy
import math
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
from scripts.v51 import cloud_cleanup_credentials as exchange, cloud_http as http
from scripts.v51.cloud_cleanup_entry import credential_file
from . import cloud_authority as a, cloud_provider as provider, cloud_read_retry
from .evidence import need, encoded, digest, strict

ROOT=Path(__file__).resolve().parents[2]
REPOSITORY='patricklfdm/GeneralSearchEngine'
REPOSITORY_ID=1341513206
OWNER_ID=147357093
SCHEMA='gse-v52-credential-context-v1'
ROLES={
    'runner':('gse-v52-runner','.github/workflows/v52-replication-evidence.yml','workflow_dispatch','v52-cloud-benchmark','runner'),
    'manual':('gse-v52-manual-cleanup','.github/workflows/v52-manual-cleanup.yml','workflow_dispatch','v52-cloud-manual-cleanup','cleanup'),
    'schedule':('gse-v52-cleanup','.github/workflows/v52-expired-cleanup.yml','schedule','v52-cloud-cleanup','cleanup'),
}
CODES=frozenset(('CONFIGURATION','ROLE','SOURCE','RUNTIME_CONTEXT','RUN_IDENTITY','RUN_OBSERVATION','CLOSED','DEADLINE','UNCLASSIFIED'))


class ContextError(ValueError):
    def __init__(self, code):
        need(code in CODES,'V5.2 unknown credential context error')
        self.reason_code='V52_CREDENTIAL_'+code
        super().__init__(self.reason_code)


def public_failure(value):
    """Project closed diagnostic fields only; never echo exchange response text."""
    if type(value) is not dict:return {}
    code=value.get('credentialCode')
    if type(code) is not str or code not in exchange.DIAGNOSTICS and code not in {'V52_CREDENTIAL_'+v for v in CODES}:return {}
    result=dict(credentialCode=code)
    kind=value.get('credentialFailureKind');status=value.get('credentialHttpStatus')
    if code in exchange.DIAGNOSTICS and type(kind) is str and kind in exchange.FAILURE_KINDS:
        result['credentialFailureKind']=kind
        if kind=='http' and type(status) is int and 100<=status<=599:result['credentialHttpStatus']=status
    result.update(cloud_read_retry.public_failure(value))
    return result


def failure(error):
    if type(error) not in (ContextError,exchange.CredentialError):return {}
    return public_failure(dict(credentialCode=getattr(error,'reason_code',None),
        credentialFailureKind=getattr(error,'failure_kind',None),credentialHttpStatus=getattr(error,'http_status',None),
        readRetry=getattr(error,'read_retry',None)))


def remaining(deadline, clock):
    left=deadline-clock()
    if not 0<left<=30 or not math.isfinite(left):raise ContextError('DEADLINE')
    return left


def selection(configuration, project_number, role):
    try:
        sha=provider.config(configuration);a.numeric(project_number)
    except (ValueError,TypeError,KeyError):raise ContextError('CONFIGURATION') from None
    if type(role) is not str or role not in ROLES:raise ContextError('ROLE')
    name,workflow,event,environment,job=ROLES[role]
    return dict(role=role,configurationSha256=sha,project=configuration['project'],projectNumber=project_number,
        serviceAccount=name+'@'+configuration['project']+'.iam.gserviceaccount.com',
        provider='projects/'+project_number+'/locations/global/workloadIdentityPools/'+name+'/providers/github',
        workflow=workflow,event=event,environment=environment,job=job)


def identity(configuration, project_number, env, *, role, source, checkout):
    selected=selection(configuration,project_number,role)
    try:a.hex_value(source,40);need(checkout==source,'source')
    except (TypeError,ValueError):raise ContextError('SOURCE') from None
    expected=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=REPOSITORY,GITHUB_REPOSITORY_ID=str(REPOSITORY_ID),
        GITHUB_REPOSITORY_OWNER_ID=str(OWNER_ID),GITHUB_EVENT_NAME=selected['event'],GITHUB_REF='refs/heads/master',
        GITHUB_WORKFLOW_REF=REPOSITORY+'/'+selected['workflow']+'@refs/heads/master',GITHUB_WORKFLOW_SHA=source,
        GITHUB_SHA=source,GITHUB_JOB=selected['job'],V52_CLOUD_ENVIRONMENT=selected['environment'])
    if type(env) is not dict or any(env.get(k)!=v for k,v in expected.items()):raise ContextError('RUNTIME_CONTEXT')
    numbers=[]
    for key in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT'):
        value=env.get(key)
        if type(value) is not str or not re.fullmatch('[1-9][0-9]{0,19}',value):raise ContextError('RUN_IDENTITY')
        numbers.append(int(value))
    # The shared exchange's immutable repository claims must remain exactly the
    # same project; this does not reuse any V5.1 workflow or IAM selection.
    from scripts.v51 import cloud_ci
    need((REPOSITORY,REPOSITORY_ID,OWNER_ID)==(cloud_ci.REPOSITORY,cloud_ci.REPOSITORY_ID,cloud_ci.OWNER_ID),
         'V5.2 shared credential repository drift')
    return dict(schema=SCHEMA,**selected,source=source,runId=numbers[0],runAttempt=numbers[1])


def check_run(binding, value):
    try:
        need(type(value) is dict,'run type')
        for key in ('repository','head_repository'):
            row=value[key]
            need(type(row['id']) is int and row['id']==REPOSITORY_ID and row['full_name']==REPOSITORY and
                 type(row['owner']['id']) is int and row['owner']['id']==OWNER_ID,'repository')
        need(type(value['id']) is int and type(value['run_attempt']) is int and value['id']==binding['runId'] and
             value['run_attempt']==binding['runAttempt'] and value['head_sha']==binding['source'] and
             value['head_branch']=='master' and value['path']==binding['workflow'] and value['event']==binding['event'] and
             value['status']=='in_progress' and value['conclusion'] is None,'run context')
    except (ValueError,TypeError,KeyError):raise ContextError('RUN_OBSERVATION') from None
    return value


def collect_run(binding, get, deadline, clock):
    """Latest -> exact attempt -> latest, one original bounded observation."""
    path='actions/runs/'+str(binding['runId']);observations=[]
    for endpoint in (path,path+'/attempts/'+str(binding['runAttempt']),path):
        remaining(deadline,clock)
        try:value=get(endpoint,deadline)
        except ContextError:raise
        except Exception:raise ContextError('RUN_OBSERVATION') from None
        remaining(deadline,clock);check_run(binding,value);observations.append(value)
    return dict(schema='gse-v52-credential-run-observation-v1',runId=binding['runId'],runAttempt=binding['runAttempt'],
        source=binding['source'],workflow=binding['workflow'],observationSha256=digest(encoded(observations)))


def checkout(deadline, clock):
    try:
        def run(args):
            result=subprocess.run(['git',*args],cwd=ROOT,capture_output=True,timeout=remaining(deadline,clock))
            need(result.returncode==0 and len(result.stdout)<=1<<20,'git source observation')
            return result.stdout.decode().strip()
        need(Path(run(['rev-parse','--show-toplevel']))==ROOT,'repository root')
        source=run(['rev-parse','HEAD']);a.hex_value(source,40)
        need(not run(['status','--porcelain=v1','--untracked-files=all']),'dirty checkout')
        remaining(deadline,clock);return source
    except ContextError:raise
    except Exception:raise ContextError('SOURCE') from None


def github(path, deadline, clock):
    need(type(path) is str and re.fullmatch(r'actions/runs/[1-9][0-9]{0,19}(/attempts/[1-9][0-9]{0,19})?',path),
         'V5.2 credential GitHub path')
    try:
        # Reuse the bounded GitHub GET implementation and its closed diagnostics.
        # This observes the same exact run/attempt; it never dispatches or reruns.
        from . import cloud_artifacts
        with tempfile.TemporaryDirectory(prefix='gse-v52-credential-run-') as directory:
            client=cloud_artifacts.Network(Path(directory)/'reads')
            client.authorize_path(path)
            target=client._read(path,16<<20,remaining(deadline,clock))
            remaining(deadline,clock);return strict(target.read_bytes())
    except ContextError:raise
    except Exception:raise ContextError('RUN_OBSERVATION') from None


class _RetryExchange(exchange._Exchange):
    """Retry only one transient token-service exchange, not the credential chain."""
    def request(self, phase, method, url, headers, body, deadline):
        original=super().request;last=None
        def classify(error):
            nonlocal last
            if type(error) is not exchange.CredentialError:return None
            last=error
            if error.failure_kind=='transport':return 'connection'
            if error.failure_kind=='timeout':return 'timeout'
            if error.failure_kind=='http' and error.http_status in cloud_read_retry.STATUSES:
                return 'http-'+str(error.http_status)
            return None
        try:
            # Leave room for another exchange inside the original 30-second
            # credential grant; a single stalled socket must not consume it all.
            return cloud_read_retry.run(lambda:original(phase,method,url,headers,body,min(deadline,self.clock()+10)),
                deadline=deadline,clock=self.clock,scope='credential-'+phase,classify=classify)
        except cloud_read_retry.ReadError as error:
            code={'oidc':'OIDC_EXCHANGE_FAILED','sts':'STS_EXCHANGE_FAILED','impersonation':'IMPERSONATION_EXCHANGE_FAILED'}[phase]
            safe=exchange.CredentialError(code,failure_kind='deadline' if last is None else last.failure_kind,
                http_status=None if last is None else last.http_status)
            safe.read_retry=error.detail
            raise safe from None


class _Credentials:
    """Serial token epochs with bounded transient retries inside each exchange."""
    def __init__(self, configuration, project_number, env, binding, *, clock, wall):
        self.configuration,self.project_number=deepcopy(configuration),project_number
        self.env,self.binding=deepcopy(env),deepcopy(binding)
        self.clock,self.wall=clock,wall;self.lock=threading.Lock();self.closed=False
        self.exchanges=0;self.attempts=0;self.latest='NOT_STARTED';self.last_reason=None;self.observation=None

    def __call__(self, timeout):
        if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<timeout<=30:raise ContextError('DEADLINE')
        end=self.clock()+timeout
        if not self.lock.acquire(timeout=timeout):raise ContextError('DEADLINE')
        try:
            self.latest='FAIL';self.last_reason=None;self.attempts+=1
            if self.closed:raise ContextError('CLOSED')
            self.observation=None
            self.recheck(end)
            delegate=self.exchange(end)
            token=delegate(remaining(end,self.clock));remaining(end,self.clock)
            need(type(token) is http.AccessToken and token.usable_until>self.clock(),'V5.2 credential lifetime')
            self.exchanges+=1;self.latest='PASS';return token
        except Exception as error:
            code=getattr(error,'reason_code',None)
            # Rebuild a known exception from its closed code. Never pass through
            # arbitrary adapter text or accept a lookalike reason_code attribute.
            if type(error) is exchange.CredentialError and type(code) is str and code in exchange.DIAGNOSTICS:
                detail=failure(error)
                safe=exchange.CredentialError(code,failure_kind=detail.get('credentialFailureKind'),
                                              http_status=detail.get('credentialHttpStatus'))
                if 'readRetry' in detail:safe.read_retry=detail['readRetry']
            elif type(error) is ContextError and type(code) is str and code in {'V52_CREDENTIAL_'+v for v in CODES}:
                safe=ContextError(code.removeprefix('V52_CREDENTIAL_'))
            else:safe=ContextError('UNCLASSIFIED')
            self.last_reason=safe.reason_code
            raise safe from None
        finally:self.lock.release()

    def receipt(self):
        with self.lock:
            return dict(schema='gse-v52-credential-exchange-v1',execution=self.execution,context=deepcopy(self.binding),
                status=self.latest,attempts=self.attempts,completedExchanges=self.exchanges,reasonCode=self.last_reason,
                runObservation=deepcopy(self.observation),paidAdmission=False,fullRemoteQualification=False)

    def close(self):
        with self.lock:
            if self.closed:return
            self.closed=True;self.env.clear()
            if hasattr(self,'transport'):self.transport.close()


class OfflineCredentials(_Credentials):
    execution='offline-v52-credential-exchange'
    def __init__(self, configuration, project_number, env, value, invocation, issuer, *, role, source, checkout_sha):
        from .cloud_credentials_offline import Invocation
        from scripts.v51.cloud_cleanup_auth_fake import Issuer
        need(type(invocation) is Invocation and type(issuer) is Issuer,'V5.2 offline credential adapters')
        need(issuer.clock is invocation.clock,'V5.2 offline credential clock changed')
        bound=identity(configuration,project_number,env,role=role,source=source,checkout=checkout_sha)
        need(issuer.binding==bound and invocation.binding==bound,'V5.2 offline credential context changed')
        super().__init__(configuration,project_number,env,bound,clock=invocation.clock.seconds,wall=invocation.clock.wall)
        self.invocation,self.issuer,self.value=invocation,issuer,deepcopy(value)
        exchange.descriptor(bound,env,self.value)  # Reject descriptor drift before any observation/exchange.

    def recheck(self, end):
        need(identity(self.configuration,self.project_number,self.env,role=self.binding['role'],source=self.binding['source'],
                      checkout=self.invocation.source)==self.binding,'V5.2 credential context changed')
        self.observation=collect_run(self.binding,self.invocation.get,end,self.clock)

    def exchange(self, end):
        return _RetryExchange(self.binding,self.env,self.value,transport=self.issuer,clock=self.clock,wall=self.wall)


_NATIVE=object()


class NetworkCredentials(_Credentials):
    """Fixed network exchange, constructed only by open_network's read-only gate.

    It is not a provider-mutation capability, effective IAM proof or paid approval.
    Python private constructors are trusted-code boundaries, not a security sandbox.
    """
    execution='native-v52-credential-exchange'
    def __init__(self, configuration, project_number, env, binding, ticket):
        need(ticket is _NATIVE,'V5.2 native credential factory required')
        super().__init__(configuration,project_number,env,binding,clock=time.monotonic,wall=time.time)
        self.transport=http.Network()

    def recheck(self, end):
        actual=identity(self.configuration,self.project_number,self.env,role=self.binding['role'],source=self.binding['source'],
                        checkout=checkout(end,self.clock))
        need(actual==self.binding,'V5.2 credential context changed')
        self.observation=collect_run(self.binding,lambda path,deadline:github(path,deadline,self.clock),end,self.clock)

    def exchange(self, end):
        remaining(end,self.clock)
        value=credential_file(self.env)
        # No ADC, gcloud account, caller-supplied transport or token provider.
        return _RetryExchange(self.binding,self.env,value,transport=self.transport,clock=self.clock,wall=self.wall)


def open_network(configuration, project_number, env, *, role, source):
    """No external credential exchange happens until the returned object is called."""
    end=time.monotonic()+30
    bound=identity(configuration,project_number,env,role=role,source=source,checkout=checkout(end,time.monotonic))
    collect_run(bound,lambda path,deadline:github(path,deadline,time.monotonic),end,time.monotonic)
    exchange.descriptor(bound,env,credential_file(env));remaining(end,time.monotonic)
    return NetworkCredentials(configuration,project_number,env,bound,_NATIVE)

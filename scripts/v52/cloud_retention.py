"""Retain an original live Session's validated member with exact read-back.

A copied receipt cannot open this entry. Its live capture is created only after
all selected histories, independent original/portable replay and guest closure.
The certificate permits one PASS completion only after retained exact-ID cleanup.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from . import cloud_authority as a,cloud_control as control,cloud_member as member
from . import cloud_native_runner as native,cloud_artifacts as artifacts,cloud_inputs as inputs,cloud_ci as ci
from . import cloud_evidence_parts as parts
from .evidence import need,encoded,digest,strict

_CERTIFICATE=object()
BUILD_FILES=('ci-before.json','ci-after.json','artifact.json','artifact-after.json','artifacts-before.json',
    'artifacts-after.json','producer-run.json','producer-job.json','producer-jobs.json','build.zip',
    'build/manifest.json','build/build.tar.gz','inspection.json','receipt.json')


def prefix(request):return control.attempt_key(request)+'evidence/'
def chunk_key(request,ordinal):return prefix(request)+f'chunk-{ordinal:05d}.json'


class Retained:
    def __init__(self,session,manifest,generations,ticket):
        need(ticket is _CERTIFICATE,'V5.2 live retained certificate required')
        self.api=session.api;self.request=deepcopy(session.owner.request)
        self.manifest=deepcopy(manifest);self.generations=deepcopy(generations)
        self.sha=digest(encoded(manifest))

    def completion(self,api,request,cleanup_sha):
        need(api is self.api and request==self.request and api.retained is self and api.policy.retained is self,
             'V5.2 retained certificate original owner changed')
        return dict(schema='gse-v52-owned-completion-v1',execution=request['execution'],
            requestSha256=a.validate_request(request,domain='native'),status='PASS',
            evidenceSha256=self.sha,cleanupSha256=a.hex_value(cleanup_sha))


def capture_files(session,output):
    """Recheck originals and select public evidence only; never credentials/keys."""
    captured=session.member_capture
    need(type(captured) is member.Captured and captured.session is session and session.guests.closed and
         session.guests.failure is None,'V5.2 retention requires original closed member capture')
    claim=session.checkpoint();request=session.owner.request;selection=request['selection']
    need(captured.receipt['selection']==selection and captured.receipt['status']=='MEMBER_EXECUTED_NOT_QUALIFIED' and
         captured.receipt['resourceClaimSha256']==digest(encoded(claim)) and
         captured.receipt==artifacts.read(captured.root/'receipt.json'),'V5.2 original member receipt changed')
    proof=session.staged.check();need(proof==session.api.admission.proof,'V5.2 retention original inputs changed')
    now=session.api.admission.observations['completedAt']
    built=artifacts.replay(session.output/'build-provenance',proof['source']['source'],ci.contract(),proof['source'],now=now)
    need(built==session.api.admission.build,'V5.2 retention original build changed')
    need(inputs.inspect(ci.ROOT,proof['source']['source'],session.output/'build-provenance/build',session.package)==proof,
         'V5.2 retention original package changed')
    files={'inputs.tar.gz':session.package,'member.json':captured.root/'receipt.json'}
    files.update({'provenance/'+name:session.output/'build-provenance'/name for name in BUILD_FILES})
    placements={};rows=[]
    need(list(captured.histories)==selection['member']['histories'],'V5.2 retention original history inventory')
    for name,value in captured.histories.items():
        root=captured.root/name;result=artifacts.read(root/'result.json')
        need(result==value['result'],'V5.2 original history replay result changed')
        row=member.correlate(root,result,name,SimpleNamespace(binding=value['placement']),proof['source'],
            session.storage.java,session.staged.files);rows.append(row)
        files['histories/'+name+'/history.tar.gz']=captured.root/row['archive']
        files['histories/'+name+'/result.json']=root/'result.json'
        placements[name]=deepcopy(value['placement'])
    need(rows==captured.receipt['histories'],'V5.2 retained member history rows changed')
    metadata=dict(schema='gse-v52-native-member-authority-v1',request=deepcopy(request),configuration=session.api.admission.cfg,
        plan=session.api.admission.plan,approval=session.api.admission.approval,inputs=proof,build=built,
        observations=session.api.admission.observations,recentCleanup=session.api.admission.clean,
        claim=claim,guestIdentity=session.guest_identity,placements=placements,
        storage=dict(records=session.storage.records,python=session.storage.installations,
                     java=session.storage.java['installations'],javaDescriptor=session.storage.java['descriptor']))
    artifacts.save(output/'authority.json',metadata);files['authority.json']=output/'authority.json'
    for name in ('observation.json','cleanup.zip','receipt.json'):
        files['recent-cleanup/'+name]=session.output/'recent-cleanup'/name
    return files


def publish(session,output):
    need(type(session) is native.Session and type(session.api) is native.NativeRunnerApi,
         'V5.2 retention requires original native session')
    session.checkpoint()
    with session.member_lock:
        need(not session.retention_started and session.api.retained is None,'V5.2 original evidence retention already consumed')
        session.retention_started=True
    output=Path(output)
    need(not any(p.is_symlink() for p in (output,*output.parents)),'V5.2 retention output symlink')
    output.mkdir(parents=True,mode=0o700,exist_ok=False)
    request=deepcopy(session.owner.request);store=session.owner.store;claim=session.checkpoint()
    progress=member.Progress(request['selection']['member']['name']);progress.thread.start();failure=None
    receipt=dict(schema='gse-v52-native-evidence-retention-v1',status='FAIL',requestSha256=a.validate_request(request,domain='native'),
        generations={},fullRemoteQualification=False)
    try:
        progress.update('retention-originals');files=capture_files(session,output)
        manifest=parts.scan(files,request);artifacts.save(output/'manifest.json',manifest)
        session.staged.check();need(session.checkpoint()==claim,'V5.2 retention resource claim changed')
        progress.update('retention-manifest');key=prefix(request)+'manifest.json'
        receipt['generations']['manifest']=control.put(store,key,manifest,0)
        receipt['manifestSha256']=digest(encoded(manifest))
        for ordinal,body in parts.chunks(files,manifest):
            need(session.checkpoint()==claim,'V5.2 retention resource claim changed')
            progress.update('retention-readback',completed=ordinal)
            receipt['generations'][str(ordinal)]=control.put(store,chunk_key(request,ordinal),body,0)
        need(store.get(key)==(receipt['generations']['manifest'],manifest),'V5.2 retained original manifest changed')
        need(parts.scan(files,request)==manifest,'V5.2 retained original inputs changed after upload')
        session.staged.check();need(session.checkpoint()==claim,'V5.2 retention resource claim changed')
        receipt.update(status='EVIDENCE_RETAINED_AWAITING_CLEANUP',parts=len(manifest['parts']),bytes=manifest['totalBytes'])
        artifacts.save(output/'receipt.json',receipt)
        # Publish the in-memory capability last. A failed local receipt or any
        # partial/uncertain immutable upload leaves cleanup's default FAIL intact.
        certificate=Retained(session,manifest,receipt['generations'],_CERTIFICATE)
        session.api.retained=certificate;session.api.policy.retained=certificate
        return deepcopy(receipt)
    except BaseException as error:
        failure=error;receipt['failure']=dict(type=type(error).__name__);raise
    finally:
        progress.close()
        if failure is not None:native.diagnostic(output/'failure.json',receipt)


def completion(api,request,cleanup_sha,outcome):
    if type(api) is not native.NativeRunnerApi or api.retained is None or outcome['status']!='PASS':return None
    need(type(api.retained) is Retained,'V5.2 retained completion capability')
    return api.retained.completion(api,request,cleanup_sha)

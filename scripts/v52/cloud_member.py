"""One admitted member's complete original histories, pending cloud retention.

This internal entry has no CLI and cannot grant qualified PASS. The caller owns
the original Session context through subsequent evidence retention and cleanup.
No member/history/workload is retried here. All actual guest faults come from the
frozen history controllers, never the transport qualification's loss injections.
"""
from copy import deepcopy
from pathlib import Path
import threading
import time
from . import cloud_native_runner as native,cloud_staging as staging,cloud_suite as suite
from . import remote_history as history,remote_host_domains as domains,measurement_bundle as bundle
from . import history_diagnostics as diagnostics
from .evidence import need,encoded,digest


_CAPTURE=object()
FAILURE_PHASES=frozenset(('guest-identity','storage','java-installation','placement','history','correlation','completion','guest-close'))


def failure_record(root,phase,error,progress):
    record=dict(status='FAIL',phase=phase,
        code='V52_MEMBER_'+phase.upper().replace('-','_')+'_REJECTED',
        errorType=type(error).__name__,fullRemoteQualification=False)
    try:
        snapshot=progress.snapshot();name=snapshot['history']
        if name in suite.load()['histories']:
            record.update(history=name,completedHistories=snapshot['completed'])
            detail=diagnostics.report(root,name)
            if detail is not None:record['historyDiagnostic']=detail
    except Exception:pass  # Diagnostic enrichment must not mask the original exception.
    native.diagnostic(root/'failure.json',record)


class Captured:
    """Created only after original replay, all histories and guest closure."""
    def __init__(self,session,root,receipt,histories,ticket):
        need(ticket is _CAPTURE,'V5.2 original member capture required')
        self.session=session;self.root=Path(root).absolute();self.receipt=deepcopy(receipt);self.histories=deepcopy(histories)


class Progress:
    def __init__(self,member,*,emit=None,interval=60):
        self.member=member;self.history=None;self.stage='starting';self.completed=0
        self.began=time.monotonic();self.stop=threading.Event();self.lock=threading.Lock()
        self.emit=emit or (lambda row:print(encoded(row).decode(),flush=True));self.interval=interval
        self.thread=threading.Thread(target=self.beat,name='v52-member-progress',daemon=True)
    def snapshot(self):
        with self.lock:
            return dict(member=self.member,history=self.history,stage=self.stage,completed=self.completed,
                     elapsedSeconds=round(time.monotonic()-self.began,1))
    def report(self):self.emit(self.snapshot())
    def update(self,stage,*,name=None,completed=None):
        with self.lock:
            self.stage=stage
            if name is not None:self.history=name
            if completed is not None:self.completed=completed
        self.report()
    def beat(self):
        while not self.stop.wait(self.interval):self.report()
    def close(self):
        self.stop.set()
        if self.thread.ident is not None:self.thread.join()


def correlate(root,result,name,placement,source,java,original_files):
    """Join independently replayed bytes to this original placement and inputs."""
    spec=history.specification(name);binding=result['binding']
    need(result['status']=='PASS' and result['history']==name and result['family']==spec['family'] and
         result['mode']==spec['mode'] and all(result[k] is False for k in
         ('paidCloud','qualifiedMeasurement','fullRemoteQualification')),'V5.2 original history result scope')
    need(all(binding.get(k)==v for k,v in source.items()),'V5.2 original history source changed')
    need(binding[domains.FIELD]==placement.binding[domains.FIELD] and
         binding['remoteTopology']==placement.binding['remoteTopology'] and
         binding['remoteVoterTransport']==placement.binding['remoteVoterTransport'],'V5.2 original history placement changed')
    domains.chain(binding)
    pins={Path(name).name:digest(raw) for name,raw in original_files.items()}
    version='5.1.0' if spec['mode'].startswith('published') else staging.inputs.VERSION
    names={f'general-search-engine-{version}.jar',f'general-search-engine-replication-{version}.jar',
           'general-search-engine-4.4.0.jar'}
    need(set(binding['artifacts'])==names and all(pins.get(name)==sha for name,sha in binding['artifacts'].items()),
         'V5.2 original history artifact changed')
    need(binding['remoteJava']['nodes']==java['installations'] and
         binding['remoteJava']['descriptorSha256']==digest(encoded(java['descriptor'])),
         'V5.2 original history installed Java changed')
    archive=root/('history.tar.gz' if spec['family']=='UNTIMED' else 'portable/history.tar.gz')
    need(bundle.sha_file(archive)==result['archiveSha256'],'V5.2 original history archive changed')
    return dict(history=name,archive=archive.relative_to(root.parent).as_posix(),archiveSha256=result['archiveSha256'],
                bindingSha256=digest(encoded(binding)),reads=result['originalReads'],updates=result['originalUpdates'])


def run(session,key,output):
    need(type(session) is native.Session and type(session.api) is native.NativeRunnerApi and
         type(session.staged) is staging.Staged and session.java is not None,
         'V5.2 member requires original native preparation')
    session.checkpoint();need(not session.member_started,'V5.2 original member already consumed')
    selection=deepcopy(session.owner.request['selection']);suite.validate_selection(selection)
    expected=deepcopy(session.api.admission.proof['source'])
    need(session.staged.check()==session.api.admission.proof,'V5.2 member staged input proof changed')
    root=Path(output)
    need(not any(p.is_symlink() for p in (root,*root.parents)),'V5.2 member output symlink')
    with session.member_lock:
        need(not session.member_started,'V5.2 original member already consumed')
        root.mkdir(parents=True,mode=0o700,exist_ok=False);session.member_started=True
    member=selection['member'];progress=Progress(member['name']);guests=None;claim=session.checkpoint()
    receipt=dict(schema='gse-v52-native-member-execution-v1',status='FAIL',selection=selection,
        source=expected,resourceClaimSha256=digest(encoded(claim)),histories=[],
        fullRemoteQualification=False,paidCloud=True)
    failure=None;captured={};phase='guest-identity';progress.thread.start()
    try:
        progress.update(phase);guests=session.open_guests(key,root/'guests')
        phase='storage';progress.update(phase);storage=guests.prepare_storage(root/'storage')
        phase='java-installation';progress.update(phase);storage.install_java(guests,session.java['descriptor'],session.java['archive'])
        need(storage.java is not None,'V5.2 member installed Java missing')
        for name in member['histories']:
            phase='placement';progress.update(phase,name=name);session.staged.check()
            need(session.checkpoint()==claim,'V5.2 member original resources changed')
            placement=storage.placement(guests,name);own=root/name
            receiver=placement.factory(name);phase='history'
            result=history.run(own,name,expected,progress=progress.update,receiver_factory=receiver)
            phase='correlation'
            # Store the original result immediately, before any further history.
            native.artifacts.save(own/'result.json',result)
            row=correlate(own,result,name,placement,expected,storage.java,session.staged.files)
            captured[name]=dict(result=deepcopy(result),placement=deepcopy(placement.binding))
            session.staged.check();guests.checkpoint()
            receipt['histories'].append(row);native.artifacts.save(root/('completed-%02d.json'%len(receipt['histories'])),receipt)
            progress.update('history-complete',completed=len(receipt['histories']))
        phase='completion'
        need([r['history'] for r in receipt['histories']]==member['histories'] and
             sum(r['reads'] for r in receipt['histories'])==member['reads'] and
             sum(r['updates'] for r in receipt['histories'])==member['updates'],
             'V5.2 member original histories/counts incomplete')
        need(session.checkpoint()==claim,'V5.2 member original resources changed');session.staged.check()
        receipt['status']='MEMBER_EXECUTED_NOT_QUALIFIED'
    except BaseException as error:
        failure=error;receipt['failure']=dict(type=type(error).__name__)
        failure_record(root,phase,error,progress)
        raise
    finally:
        try:
            progress.update('guest-close')
            if guests is not None:guests.close()
        except BaseException as error:
            receipt['status']='FAIL';receipt['guestCloseFailure']=type(error).__name__
            if failure is None:
                failure_record(root,'guest-close',error,progress)
                raise
        finally:
            progress.close();receipt['elapsedSeconds']=round(time.monotonic()-progress.began,3)
            if failure is None and 'guestCloseFailure' not in receipt:native.artifacts.save(root/'receipt.json',receipt)
            else:native.diagnostic(root/'receipt.json',receipt)
    session.member_capture=Captured(session,root,receipt,captured,_CAPTURE)
    return receipt

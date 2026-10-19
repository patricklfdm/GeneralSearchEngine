"""One original admitted member through retention, cleanup and public sealing.

Internal protected-entry operation. No client/credential/clock injection, no
workload retry, and no provisioning-only success. The operator workflow and
prepare/download entries are connected separately.
"""
from pathlib import Path
from . import cloud_native_runner as native, cloud_member as member, cloud_member_seal as seal
from .evidence import need


def run_native(source, plan, approval, confirmation, package, key, output):
    output = Path(output)
    need(not any(p.is_symlink() for p in (output, *output.parents)), 'V5.2 execution output link')
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    progress = member.Progress('original-member'); progress.thread.start(); phase = 'admission'
    try:
        progress.update(phase)
        with native.open_native(source, plan, approval, confirmation, package, output/'native', prepare_workload=True) as session:
            phase = 'whole-member'; progress.update(phase)
            session.run_member(key, output/'member')
            phase = 'retention'; progress.update(phase)
            session.retain_member(output/'retention')
            phase = 'cleanup'; progress.update(phase)
        phase = 'public-seal'; progress.update(phase)
        result = seal.publish(session, output/'public')
        native.artifacts.save(output/'receipt.json', dict(status=result['status'], source=source,
            requestSha256=result['requestSha256'], fullRemoteQualification=False))
        return result
    except BaseException as error:
        native.diagnostic(output/'failure.json', dict(status='FAIL', phase=phase,
            code='V52_ORIGINAL_MEMBER_'+phase.upper().replace('-', '_')+'_REJECTED', errorType=type(error).__name__,
            fullRemoteQualification=False))
        raise
    finally:
        progress.close()

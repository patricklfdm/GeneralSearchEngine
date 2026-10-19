"""Join protected original invocations to independently restored whole members.

This factory owns both native read-only collectors and every original replay.
Copied local receipts cannot enter it. No VM creation, measurement, workflow
dispatch, original-run substitution or business retry occurs here.
"""
from copy import deepcopy
from pathlib import Path
import time
from . import cloud_preflight_read as reads, cloud_inputs as inputs, cloud_artifacts as artifacts
from . import cloud_authority as a, cloud_suite as suite, cloud_evidence_read as objects
from . import cloud_runner_provenance as runners, cloud_member_seal as seal, cloud_set_evidence as evidence
from . import cloud_member as member
from .evidence import need, encoded, digest


def selection(chosen):
    need(type(chosen) is dict and set(chosen) == set(suite.MEMBERS), 'V5.2 five protected original selections required')
    requests = set(); invocations = set()
    for row in chosen.values():
        a.fields(row, 'requestSha256 runId runAttempt', 'original cloud set selection')
        sha = a.hex_value(row['requestSha256']); inv = (a.integer(row['runId'], 1), a.integer(row['runAttempt'], 1))
        need(sha not in requests and inv not in invocations, 'V5.2 duplicate original cloud selection')
        requests.add(sha); invocations.add(inv)
    return deepcopy(chosen)


def verify_native(source, chosen, output):
    chosen = selection(chosen); output = Path(output)
    need(not any(p.is_symlink() for p in (output, *output.parents)), 'V5.2 acceptance output link')
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    progress = member.Progress('complete-original-set'); progress.thread.start()
    receipt = dict(status='FAIL', fullRemoteQualification=False, paidCloud=False); phase = 'source'
    def update(stage, **values):
        progress.update(stage, name=values.get('name'), completed=values.get('completed'))
    try:
        cfg = reads.source_configuration(source); bound = inputs.checkout(reads.ROOT, source); workflow = runners.contract()
        phase = 'original-objects'; update(phase)
        restored = objects.restore_native(source, {name: row['requestSha256'] for name, row in chosen.items()},
                                          output/'objects', progress=update)
        need(restored['receipt']['status'] == 'ORIGINALS_RESTORED_NOT_QUALIFIED' and
             restored['receipt']['execution'] == 'native-v52-evidence-reads', 'V5.2 original native restoration required')
        ledger = artifacts.read(output/'objects/originals/ledger-after.json')
        need(ledger['value'] == restored['ledger'], 'V5.2 restored original ledger changed')
        expected = {}; provenance = {}
        phase = 'original-runners'
        for value in restored['inputs']:
            name = value['request']['selection']['member']['name']; update(phase, name=name, completed=len(expected))
            original = {key: chosen[name][key] for key in ('runId', 'runAttempt')}
            record = runners.collect_native(source, value['request'], original, output/'runners'/name)
            expected[name] = seal.match(record['seal'], cfg, bound, value, ledger, now=int(time.time()))
            need(expected[name] == dict(run=str(original['runId']), attempt=original['runAttempt']),
                 'V5.2 selected original invocation changed')
            provenance[name] = digest(encoded(record))
        phase = 'complete-replay'; update(phase)
        replayed = evidence.replay(restored['inputs'], bound, cfg, restored['ledger'], output/'replay',
                                   progress=update, expected_invocations=expected)
        need(replayed['status'] == 'COMPLETE_SET_REPLAYED_NOT_QUALIFIED' and
             set(replayed['completedMembers']) == set(suite.MEMBERS), 'V5.2 incomplete original set replay')
        phase = 'final-source'; update(phase)
        need(reads.source_configuration(source) == cfg and inputs.checkout(reads.ROOT, source) == bound and runners.contract() == workflow,
             'V5.2 acceptance source changed')
        receipt = dict(schema='gse-v52-protected-cloud-set-v1', status='PASS', execution='native-v52-complete-set-replay',
            fullRemoteQualification=True, paidCloud=False, source=bound, configurationSha256=reads.f.configuration(cfg),
            selected=chosen, originalInvocations=expected, runnerReceiptHashes=provenance,
            restorationSha256=digest(encoded(restored['receipt'])), replaySha256=digest(encoded(replayed)),
            totals=replayed['totals'], m01=replayed['m01'], selectedReservedCostMicrousd=replayed['selectedReservedCostMicrousd'],
            ledgerReservedCostMicrousd=replayed['ledgerReservedCostMicrousd'])
        return receipt
    except BaseException as error:
        receipt['failure'] = dict(phase=phase, code='V52_SET_'+phase.upper().replace('-', '_')+'_REJECTED', errorType=type(error).__name__)
        raise
    finally:
        progress.close(); artifacts.save(output/'receipt.json', receipt)

"""Original non-mutating preparation for one operator-selected whole member."""
from pathlib import Path
import time
import uuid
from . import cloud_authority as a, cloud_inputs as inputs, cloud_artifacts as artifacts, cloud_ci as ci
from . import cloud_preflight_read as reads, cloud_preflight as preflight, cloud_recent_cleanup as recent
from . import cloud_prepared as prepared, cloud_prepared_artifact as package, cloud_access as access
from . import cloud_native_runner as native, cloud_member as member, cloud_suite as suite, controls
from .evidence import need, encoded, digest


def request(value):
    a.fields(value, 'member sequence estimate', 'prepare request')
    suite.member(value['member']); a.hex_value(value['sequence'], 32)
    need(type(value['estimate']) is dict, 'V5.2 explicit dated operator estimate required')
    return value


def prepare_native(source, value, public_key, output):
    request(value); access.ed25519(public_key); output = Path(output)
    need(not any(p.is_symlink() for p in (output, *output.parents)), 'V5.2 preparation output link')
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    progress = member.Progress(value['member']); progress.thread.start(); phase = 'source'
    try:
        cfg = reads.source_configuration(source); bound = inputs.checkout(ci.ROOT, source)
        # Workflow contract is imported here to avoid circular entry imports.
        from . import cloud_runner_provenance as origin
        workflow = origin.contract()
        phase = 'original-build'; progress.update(phase)
        artifacts.collect_native(source, output/'build')
        built = artifacts.replay(output/'build', source, ci.contract(), bound, now=int(time.time()))
        phase = 'published-controls'; progress.update(phase)
        inputs.controls(ci.ROOT); controls.resolve(output/'controls')
        phase = 'input-package'; progress.update(phase)
        proof = inputs.create(ci.ROOT, source, output/'build/build', output/'controls', output/'package')
        phase = 'recent-cleanup'; progress.update(phase)
        recent.collect_native(source, output/'cleanup')
        phase = 'provider'; progress.update(phase)
        observed = reads.collect_native(source, output/'preflight', role='runner')
        now = int(time.time()); original = artifacts.read(output/'preflight/observations.json')
        need(observed == preflight.evaluate(cfg, source, 'runner', original, now=observed['checkedAt']) and
             observed['status'] == 'PREFLIGHT_OBSERVED_NOT_ADMITTED' and original['execution'] == 'native-v52-provider-observations',
             'V5.2 preparation native preflight unavailable')
        # Independently revalidate both current observations at the point the
        # prepared plan is created; neither uploaded receipt grants admission.
        need(preflight.evaluate(cfg, source, 'runner', original, now=now)['status'] == 'PREFLIGHT_OBSERVED_NOT_ADMITTED',
             'V5.2 preparation preflight changed before plan')
        cleanup = recent.validate(artifacts.read(output/'cleanup/observation.json'), cfg, source, output/'cleanup/cleanup.zip', now)
        need(original['controlAfter']['lease'] is None, 'V5.2 preparation active lease')
        phase = 'plan'; progress.update(phase)
        plan = prepared.prepare(cfg['provider'], cfg['projectNumber'], proof, access.descriptor(uuid.uuid4().hex, public_key),
            cfg['layout'], cfg['policy'], native.ledger_baseline(original['controlAfter']['ledger']), value['estimate'],
            source=source, sequence=value['sequence'], member=value['member'], now=now, domain='native')
        approval = prepared.approval_template(plan)
        record = dict(schema=package.SCHEMA, status='PREPARED_NOT_ADMITTED', configurationSha256=preflight.configuration(cfg),
            credentialContext=observed['credentialContext'], planSha256=approval['planSha256'], requestSha256=approval['requestSha256'],
            preparedAt=now, buildSha256=digest(encoded(built)), cleanupSha256=digest(encoded(cleanup)),
            preflightSha256=digest(encoded(observed)), paidAdmission=False, fullRemoteQualification=False)
        files = {'plan.json': encoded(plan), 'approval.json': encoded(approval), 'preparation.json': encoded(record),
                 'inputs.tar.gz': inputs.regular(output/'package/inputs.tar.gz', inputs.MAX_BYTES)}
        chosen = {key: record['credentialContext'][key] for key in ('runId', 'runAttempt')}
        package.validate(files, cfg, bound, chosen, now=now)
        need(reads.source_configuration(source) == cfg and inputs.checkout(ci.ROOT, source) == bound and origin.contract() == workflow,
             'V5.2 preparation source changed')
        (output/'public').mkdir()
        for name, raw in files.items():
            with (output/'public'/name).open('xb') as stream: stream.write(raw)
        artifacts.save(output/'receipt.json', record); return record
    except BaseException as error:
        native.diagnostic(output/'failure.json', dict(status='FAIL', phase=phase,
            code='V52_PREPARE_'+phase.upper().replace('-', '_')+'_REJECTED', errorType=type(error).__name__, paidAdmission=False))
        raise
    finally:
        progress.close()

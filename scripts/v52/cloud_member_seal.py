"""Compact original Runner result, published only after the owned scope closes.

The public seal is a correlation record, not an admission or replay receipt.
GitHub provenance and immutable provider objects must independently authenticate
it before the complete original histories can be accepted.
"""
from copy import deepcopy
from pathlib import Path
from . import cloud_authority as a, cloud_preflight as preflight, cloud_inputs as inputs
from . import cloud_credentials as credentials, cloud_artifacts as artifacts, cloud_control as control
from .evidence import need, encoded, digest

SCHEMA = 'gse-v52-original-member-seal-v1'
MAX_BYTES = 65536


def validate(value, cfg, source, request, *, now):
    a.fields(value, 'schema status source configurationSha256 requestSha256 selection credentialContext '
             'startedAt completedAt manifestSha256 completionSha256 cleanupSha256 ledgerGeneration '
             'ledgerEntries ledgerPrefixSha256 reservedCostMicrousd fullRemoteQualification', 'original member seal')
    inputs.identity(source); sha = a.validate_request(request, domain='native')
    need(value['schema'] == SCHEMA and value['status'] == 'ORIGINAL_MEMBER_CLOSED_NOT_QUALIFIED' and
         value['fullRemoteQualification'] is False and value['source'] == source and
         value['configurationSha256'] == preflight.configuration(cfg) and value['requestSha256'] == sha and
         value['selection'] == request['selection'] and request['configurationSha256'] == preflight.p.config(cfg['provider']) and
         all(request['selection']['binding'][k] == source[k] for k in ('source', 'checkoutSha256')),
         'V5.2 original seal source/request/scope')
    expected = dict(schema=credentials.SCHEMA, **credentials.selection(cfg['provider'], cfg['projectNumber'], 'runner'),
                    source=source['source'])
    context = value['credentialContext']; a.fields(context, ' '.join([*expected, 'runId', 'runAttempt']), 'seal credential context')
    need(all(context[k] == v for k, v in expected.items()), 'V5.2 original seal credential selection')
    a.integer(context['runId'], 1); a.integer(context['runAttempt'], 1)
    a.integer(value['startedAt'], request['createdAt'], now); a.integer(value['completedAt'], value['startedAt'], now)
    for key in ('manifestSha256', 'completionSha256', 'cleanupSha256', 'ledgerPrefixSha256'): a.hex_value(value[key])
    a.integer(value['ledgerGeneration'], 1); a.integer(value['ledgerEntries'], 2, 4096)
    a.integer(value['reservedCostMicrousd'], 1)
    need(len(encoded(value)) <= MAX_BYTES, 'V5.2 original seal bound')
    return value


def create(cfg, source, request, manifest, completed, clean, ledger, claim, plan, context, *, started, now):
    from . import cloud_member_evidence as evidence
    accounting = evidence.completion(request, manifest, completed, clean, ledger['value'], claim, plan)
    value = dict(schema=SCHEMA, status='ORIGINAL_MEMBER_CLOSED_NOT_QUALIFIED', source=deepcopy(source),
        configurationSha256=preflight.configuration(cfg), requestSha256=a.validate_request(request, domain='native'),
        selection=deepcopy(request['selection']), credentialContext=deepcopy(context), startedAt=started, completedAt=now,
        manifestSha256=digest(encoded(manifest)), completionSha256=accounting['completionSha256'],
        cleanupSha256=accounting['cleanupSha256'], ledgerGeneration=ledger['generation'],
        ledgerEntries=len(ledger['value']['entries']), ledgerPrefixSha256=digest(encoded(ledger['value']['entries'])),
        reservedCostMicrousd=accounting['reservedCostMicrousd'], fullRemoteQualification=False)
    return validate(value, cfg, source, request, now=now)


def match(value, cfg, source, restored, ledger, *, now):
    """Join to separately restored objects; later ledger entries remain intact."""
    request = restored['request']; validate(value, cfg, source, request, now=now)
    a.validate_completion(restored['completed'], request); view = a.inspect_ledger(ledger['value'], domain='native')
    sha = value['requestSha256']; count = value['ledgerEntries']
    need(view['attempts'].get(sha) == dict(request=request, status='PASS') and
         ledger['generation'] >= value['ledgerGeneration'] and len(ledger['value']['entries']) >= count and
         (ledger['generation'] != value['ledgerGeneration'] or len(ledger['value']['entries']) == count) and
         digest(encoded(ledger['value']['entries'][:count])) == value['ledgerPrefixSha256'],
         'V5.2 original seal ledger prefix changed')
    for key, field in (('manifest', 'manifestSha256'), ('completed', 'completionSha256'), ('cleanup', 'cleanupSha256')):
        need(digest(encoded(restored[key])) == value[field], 'V5.2 original seal immutable object changed')
    completed = restored['completed']
    need(completed['status'] == 'PASS' and completed['evidenceSha256'] == value['manifestSha256'] and
         completed['cleanupSha256'] == value['cleanupSha256'], 'V5.2 original seal unsuccessful completion')
    reserved = [v for v in ledger['value']['entries'][:count] if v['requestSha256'] == sha]
    need(len(reserved) == 2 and reserved[0]['kind'] == 'RESERVED' and reserved[1] == dict(kind='FINISHED',
         requestSha256=sha, status='PASS', completionSha256=value['completionSha256']) and
         reserved[0]['reservedCostMicrousd'] == value['reservedCostMicrousd'], 'V5.2 original seal terminal record changed')
    return dict(run=str(value['credentialContext']['runId']), attempt=value['credentialContext']['runAttempt'])


def capture(session, result):
    """Called inside original close, while its scoped provider reader is alive."""
    from . import cloud_native_runner as native, cloud_retention as retention
    need(type(session) is native.Session and session.closed and type(session.api) is native.NativeRunnerApi and
         type(session.api.retained) is retention.Retained and result['status'] == 'PASS' and
         result['leaseReleased'] is True and session.heartbeat.failure is None, 'V5.2 original close required')
    api = session.api; api.validate_adapter(); req = session.owner.request; store = session.owner.store
    certificate = api.retained
    need(certificate.api is api and certificate.request == req and api.policy.retained is certificate,
         'V5.2 original retained owner changed')
    completed = store.get(control.attempt_key(req)+'completion.json')
    ledger = store.get(a.LEDGER)
    need(completed is not None and ledger is not None, 'V5.2 original terminal writes missing')
    value = create(api.admission.cfg, api.admission.proof['source'], req, certificate.manifest, completed[1],
        result['cleanup'], dict(generation=ledger[0], value=ledger[1]), session.result['claim'], api.admission.plan,
        session.reader.tokens.binding, started=session.started_at, now=int(native.time.time()))
    return value


def publish(session, output):
    """No file-to-success entry: only a successfully closed original Session."""
    from . import cloud_native_runner as native
    need(type(session) is native.Session and session.closed and session.api.closed and session.original_seal is not None,
         'V5.2 original successfully closed session required')
    source = session.api.admission.proof['source']; cfg = session.api.admission.cfg
    need(native.reads.source_configuration(source['source']) == cfg and inputs.checkout(native.ci.ROOT, source['source']) == source,
         'V5.2 original seal source changed')
    value = deepcopy(session.original_seal); validate(value, cfg, source, session.owner.request, now=int(native.time.time()))
    output = Path(output)
    need(not any(p.is_symlink() for p in (output, *output.parents)), 'V5.2 original seal output link')
    output.mkdir(parents=True, exist_ok=False)
    artifacts.save(output/'member-seal.json', value)
    return value

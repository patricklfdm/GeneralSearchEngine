"""Exact-request topology preparation for cleanup qualification; no engine runner.

One closed 13-resource inventory, conditional authority writes, no mutation retry.
The existing manual/scheduled reconciler owns cleanup after expiry plus grace.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import re
import subprocess
import time
import uuid
from . import cloud_fixture_driver as single, cloud_authority as a
from . import cloud_native_authority as n, cloud_gcp as g, cloud_http as h
from . import cloud_cleanup as cleanup, cloud_cleanup_observation as observation
from . import cloud_preflight as p, cloud_ci as ci, guest_setup
from . import performance_model as m, remote_command as c
from . import cloud_topology_contract as contract
from .cloud_resource_creation import CreationPolicy

SCHEMA = 'gse-v51-topology-fixture-request-v1'
COST = contract.COST
PREPARATION_SECONDS = contract.PREPARATION_SECONDS
BOUNDARY = dict(cleanupReady=False, paidAdmission=False, fullRemoteQualification=False,
                engineWorkloadExecuted=False, topologyCleanupQualified=False)
PROVIDER_CHECKS = ('image', 'topology', 'quota', 'storagePolicy')


def price(value, now):
    m.need(type(value) is dict and set(value) == {'observedAt', 'expiresAt', 'region', 'diskType',
        'machineType', 'vmMicrousdPerHour', 'diskMicrousdPerGiBHour', 'pricedThroughSeconds',
        'otherCostsMicrousd', 'sources'}, 'topology price fields')
    a.integer(value['observedAt'], 1)
    a.integer(value['expiresAt'], value['observedAt']+1, value['observedAt']+86400)
    m.need(value['observedAt'] <= now < value['expiresAt'] and
           (value['region'], value['diskType'], value['machineType']) ==
           ('us-west4', 'pd-balanced', 'n2-standard-8'), 'topology price age/selection')
    vm = a.integer(value['vmMicrousdPerHour'], 1, COST)
    disk = a.integer(value['diskMicrousdPerGiBHour'], 1, COST)
    seconds = a.integer(value['pricedThroughSeconds'], 6480, 86400)
    extra = value['otherCostsMicrousd']
    m.need(type(extra) is dict and set(extra) == {'requests', 'retention30Days', 'actions', 'failureOverhang'},
           'topology price coverage')
    for amount in extra.values(): a.integer(amount, 1, COST)
    sources = value['sources']
    m.need(type(sources) is list and 1 <= len(sources) <= 8 and all(type(v) is str and len(v) <= 1024 and
           re.fullmatch(r'https://(?:cloud|docs\.cloud)\.google\.com/[^\s]+|https://docs\.github\.com/[^\s]+', v)
           for v in sources), 'topology price sources')
    total = ((3*vm+450*disk)*seconds+3599)//3600+sum(extra.values())
    m.need(total <= COST, 'topology estimate exceeds reservation')
    return total


def provider_checks(cfg, value, operator, now, offline):
    execution = 'offline-preflight-fixture' if offline else 'read-only-provider-observations'
    m.need(value['configurationSha256'] == p.configuration(cfg) and value['execution'] == execution and
           now-300 <= value['startedAt'] <= value['completedAt'] <= now and
           value['observations']['principal'] == operator, 'topology provider observation binding/age')
    checks = p.check_provider(cfg, value)
    m.need(all(checks[k]['status'] == 'PASS' for k in PROVIDER_CHECKS), 'topology provider readiness')
    return {k: checks[k] for k in PROVIDER_CHECKS}


def make(cfg, source, operator, public_key, prices, before, provider, *, now, attempt, sequence, offline=False):
    p.configuration(cfg); a.digest(source, 40); a.digest(attempt, 32); a.digest(sequence, 32); a.integer(now, 1)
    m.need(type(offline) is bool and type(operator) is str and
           re.fullmatch(r'[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+', operator) and
           not operator.startswith(('gse-v51-', 'gse-v50-')), 'topology separately approved operator')
    observation.envelope(cfg, before)
    m.need(before['execution'] == ('offline-cleanup-observation' if offline else 'read-only-native-cleanup-observation') and
           before['source'] == source and before['lease'] is None and before['referenceSha256'] is None and
           now-300 <= before['startedAt'] <= before['completedAt'] <= now, 'topology fresh empty control observation')
    old = observation.item(before['ledger'])
    total, attempts = n.inspect_ledger(old if old is not None else n.empty_ledger())
    m.need(not any(v['status'] == 'PENDING' for v in attempts.values()) and total+COST <= a.MAXIMUM_BUDGET_MICROUSD,
           'topology pending attempt/budget')
    provider_checks(cfg, provider, operator, now, offline)
    estimate = price(prices, now)
    manifest = contract.manifest(cfg, source, m.sha(m.canonical(prices)))
    guest = dict(attempt=attempt, user='gse-'+attempt[:24], publicKey=public_key); guest_setup.access(guest)
    req = n.request(source, m.sha(m.canonical(manifest)), g.config(cfg['provider']), sequence, attempt,
                    'experiment', now=now, guest_access_sha256=m.sha(m.canonical(guest)))
    # Store observations contain tuples in memory; freeze the same JSON types
    # that the reviewed file and immutable provider object will carry.
    return m.strict_json(m.canonical(dict(schema=SCHEMA, execution='offline-topology-request' if offline else 'operator-topology-request',
        configuration=deepcopy(cfg), request=req, guestAccess=guest, operator=operator,
        qualificationManifest=manifest, prices=deepcopy(prices), estimatedCostMicrousd=estimate,
        before=deepcopy(before), providerObservation=deepcopy(provider), previousCostMicrousd=total,
        maximumCostMicrousd=COST, expiresAt=min(now+900, prices['expiresAt']), **BOUNDARY)))


def validate(value, *, now):
    req = value['request']
    expected = make(value['configuration'], req['source'], value['operator'], value['guestAccess']['publicKey'],
        value['prices'], value['before'], value['providerObservation'], now=req['createdAt'],
        attempt=req['attempt'], sequence=req['sequence'], offline=value['execution'] == 'offline-topology-request')
    m.need(value == expected, 'topology request drift')
    m.need(req['createdAt'] <= now < value['expiresAt'], 'topology request expired/future')
    price(value['prices'], now)
    return m.sha(m.canonical(value))


def manifest_key(req):
    return n.PREFIX+'attempts/'+n.validate_request(req)+'/topology-fixture.json'


class _Policy(CreationPolicy):
    def initialize(self, value, now):
        validate(value, now=now)
        self.value = deepcopy(value)
        self.initialize_creation(value['configuration']['provider'], value['request'], value['guestAccess'],
                                 value['before']['ledger'], value, now,
                                 qualification_manifest=value['qualificationManifest'])

    def marker_key(self):
        return manifest_key(self.req)

    def marker_value(self):
        return dict(schema='gse-v51-topology-prepared-v1', fixtureRequest=self.value,
                    fixtureSha256=m.sha(m.canonical(self.value)), lease=deepcopy(self.lease),
                    leaseGeneration=self.generation)


class PreparationApi(_Policy, h.Api):
    def __init__(self, value, now, *, transport, tokens, clock):
        m.need(transport.offline is True and value['execution'] == 'offline-topology-request', 'topology offline constructor')
        h.Api.__init__(self, transport=transport, tokens=tokens, clock=clock); self.initialize(value, now)


def network_checks(value, confirmation):
    now = int(time.time()); digest = validate(value, now=now)
    m.need(value['execution'] == 'operator-topology-request' and confirmation == digest, 'topology exact approval')
    subprocess.check_output(['git', 'ls-files', '--error-unmatch', 'scripts/v51/cloud_topology_fixture.py'], cwd=ci.ROOT)
    evidence = single.protected_checks(value)
    # The operator is the preparer. This is not an observer/runner IAM qualification.
    provider = p.collect_provider(value['configuration'])
    provider_checks(value['configuration'], provider, value['operator'], int(time.time()), False)
    validate(value, now=int(time.time()))
    return dict(**evidence, provider=provider)


class NetworkPreparationApi(_Policy, h.Api):
    def __init__(self, value, *, confirmation):
        self.preparation_evidence = network_checks(value, confirmation)
        def tokens(timeout):
            single.operator_account(value['operator'])
            result = subprocess.run(['gcloud', 'auth', 'print-access-token', '--account='+value['operator']], capture_output=True, timeout=timeout)
            m.need(result.returncode == 0 and result.stdout.strip(), 'topology operator credential unavailable')
            return result.stdout.decode().strip()
        h.Api.__init__(self, transport=h.Network(), tokens=tokens); self.initialize(value, int(time.time()))


def execute(value, api, output, *, now, sleep=time.sleep):
    validate(value, now=now)
    m.need(type(api) in (PreparationApi, NetworkPreparationApi) and api.value == value and
           api.offline == (value['execution'] == 'offline-topology-request'), 'topology execution binding')
    root = Path(output); root.mkdir(parents=True, exist_ok=False); c.write_once(root/'request.json', value)
    receipt = dict(schema='gse-v51-topology-preparation-v1', status='FAIL', requestSha256=n.validate_request(api.req),
        fixtureSha256=m.sha(m.canonical(value)), execution='offline-topology-preparation' if api.offline else 'gcp-topology-preparation',
        startedAt=api.lease['startedAt'], paidCloud=not api.offline, **BOUNDARY)
    phase = 'original-state'
    try:
        m.need(api.state == 'lease' and not api.failed and api.store.get(n.LEASE) is None and
               m.canonical(api.store.get(n.LEDGER)) == m.canonical(value['before']['ledger']), 'topology state changed')
        for key in (cleanup.context_key(api.req, authority=n), manifest_key(api.req)):
            m.need(api.store.get(key) is None, 'topology object already exists')
        provider = api.provider(sleep)
        for row in api.lease['resources']:
            spec = row['spec']
            m.need(provider.describe(spec) is None and provider.operation(spec)['state'] == 'UNKNOWN', 'topology resource/operation already exists')
        while api.state != 'done':
            phase = api.state
            if phase == 'insert': api.insert(sleep)
            else: api.upload()
        receipt.update(status='PREPARED', leaseGeneration=api.generation, resources=deepcopy(api.lease['resources']),
            expiresAt=api.lease['expiresAt'], cleanupEligibleAt=api.lease['expiresAt']+api.lease['graceSeconds'],
            reservedCostMicrousd=COST, previousCostMicrousd=value['previousCostMicrousd'])
    except (Exception, KeyboardInterrupt) as error:
        api.failed = True
        receipt['failure'] = dict(phase=phase, type=type(error).__name__)
        if isinstance(error, h.ApiError): receipt['failure']['httpStatus'] = error.status
    finally:
        c.write_once(root/'http.json', api.requests); c.write_once(root/'receipt.json', receipt)
    return receipt


def review_prepared(value, receipt, observed):
    """Compare the preparer's claim with a separate read-only authority snapshot."""
    req = value['request']; cfg = value['configuration']; sha = n.validate_request(req)
    digest = validate(value, now=req['createdAt'])
    lease = observation.envelope(cfg, observed)
    offline = value['execution'] == 'offline-topology-request'
    m.need(receipt['schema'] == 'gse-v51-topology-preparation-v1' and receipt['status'] == 'PREPARED' and
           receipt['fixtureSha256'] == digest and receipt['requestSha256'] == sha and
           receipt['execution'] == ('offline-topology-preparation' if offline else 'gcp-topology-preparation') and
           receipt['paidCloud'] is (not offline) and all(receipt[k] is False for k in BOUNDARY), 'topology preparation receipt')
    expected = n.lease(req, receipt['startedAt']); expected['resources'] = receipt['resources']; n.validate_lease(expected)
    m.need(lease == expected and all(r['attempted'] and r['id'] is not None for r in lease['resources']) and
           observed['lease'][0] == receipt['leaseGeneration'] and observed['source'] == req['source'] and
           observed['referenceSha256'] is None and receipt['startedAt'] <= observed['startedAt'] < lease['expiresAt'] and
           observed['execution'] == ('offline-cleanup-observation' if offline else 'read-only-native-cleanup-observation'),
           'topology prepared lease observation')
    m.need(receipt['expiresAt'] == lease['expiresAt'] and receipt['cleanupEligibleAt'] == lease['expiresAt']+lease['graceSeconds'] and
           receipt['reservedCostMicrousd'] == COST and receipt['previousCostMicrousd'] == value['previousCostMicrousd'], 'topology preparation accounting/time')
    old = observation.item(value['before']['ledger'])
    m.need(observation.item(observed['ledger']) == n.reserve(old if old is not None else n.empty_ledger(), req, value) and
           observed['completion'] is None, 'topology reservation changed')
    context = cleanup.context(cfg['provider'], req, value['guestAccess'], authority=n,
                              qualification_manifest=value['qualificationManifest'])
    m.need(observation.item(observed['context']) == context, 'topology retained context changed')
    rows = observed['resources']; m.need(len(rows) == 13, 'topology observation inventory')
    for retained, row in zip(lease['resources'], rows):
        spec = retained['spec']; identity = retained['id']
        m.need(row == dict(spec=spec, operation=dict(spec=spec, state='DONE', id=identity), queriedId=identity,
                          byName=dict(spec=spec, id=identity), byId=dict(spec=spec, id=identity)), 'topology independent resource/operation mismatch')
    return dict(status='PREPARATION_STATE_MATCH', execution='topology-preparation-review',
        requestSha256=sha, fixtureSha256=digest, observationSha256=m.sha(m.canonical(observed)),
        resourceCount=13, retainedCostMicrousd=value['previousCostMicrousd']+COST,
        artifactProvenanceVerified=False, **BOUNDARY)


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    review = sub.add_parser('review'); review.add_argument('--operator', required=True)
    review.add_argument('--public-key', type=Path, required=True); review.add_argument('--prices', type=Path, required=True)
    review.add_argument('--output', type=Path, required=True)
    run = sub.add_parser('prepare'); run.add_argument('--request', type=Path, required=True)
    run.add_argument('--confirm', required=True); run.add_argument('--output', type=Path, required=True)
    verify = sub.add_parser('review-prepared'); verify.add_argument('--request', type=Path, required=True)
    verify.add_argument('--preparation', type=Path, required=True); verify.add_argument('--observation', type=Path, required=True)
    verify.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'review':
        source = single.checkout(); cfg = c.read(p.CONFIG); single.operator_account(args.operator)
        before = observation.capture(cfg, source); provider = p.collect_provider(cfg)
        m.need(args.public_key.is_file() and not args.public_key.is_symlink() and args.public_key.stat().st_size <= 4096, 'public key file')
        value = make(cfg, source, args.operator, args.public_key.read_text().strip(), c.read(args.prices), before, provider,
                     now=int(time.time()), attempt=uuid.uuid4().hex, sequence=uuid.uuid4().hex)
        args.output.mkdir(parents=True, exist_ok=False); c.write_once(args.output/'request.json', value)
        result = dict(status='REVIEW_ONLY', fixtureSha256=validate(value, now=int(time.time())),
            requestSha256=n.validate_request(value['request']), maximumCostMicrousd=COST, expiresAt=value['expiresAt'],
            applied=False, **BOUNDARY)
        c.write_once(args.output/'review.json', result)
    elif args.command == 'prepare':
        value = c.read(args.request); api = NetworkPreparationApi(value, confirmation=args.confirm)
        result = execute(value, api, args.output, now=int(time.time()))
        c.write_once(args.output/'entry-evidence.json', api.preparation_evidence)
    else:
        result = review_prepared(c.read(args.request), c.read(args.preparation), c.read(args.observation))
        args.output.mkdir(parents=True, exist_ok=False); c.write_once(args.output/'review.json', result)
    print(m.canonical({k: v for k, v in result.items() if k != 'resources'}).decode())
    if result['status'] not in ('REVIEW_ONLY', 'PREPARED', 'PREPARATION_STATE_MATCH'): raise SystemExit(2)


if __name__ == '__main__': main()

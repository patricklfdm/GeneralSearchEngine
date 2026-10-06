"""Source/build/price/approval-bound Runner request inspection, without allocation.

The native constructor owns its GitHub, checkout and WIF boundaries. No injected
transport, token supplier or clock is accepted there. An explicit offline twin
qualifies the same checks; neither entry can mutate resource/control state.
"""
from copy import deepcopy
from pathlib import Path
import re
import time
from urllib.parse import urlsplit, parse_qsl
from scripts import ci_v51_bundle as build
from . import cloud_authority as a, cloud_native_authority as n, cloud_gcp as g, cloud_http as h
from . import cloud_runner_artifacts as artifacts, cloud_experiment_resources as resources
from . import cloud_runner_precheck as precheck, cloud_runner_storage_entry as storage
from . import cloud_runner_review as workflow, cloud_cleanup_credentials as credentials
from . import cloud_cleanup_entry as entry, cloud_preflight as p, cloud_ci as ci
from . import cloud_workload_contract as workload, guest_setup, performance_model as m
from .remote_command import read

FLAGS = dict(paidAdmission=False, resourcesCreated=False, engineWorkloadExecuted=False, fullRemoteQualification=False)
SCHEMA = 'gse-v51-runner-experiment-plan-v1'


def prices(value, now):
    fields = {'observedAt', 'expiresAt', 'region', 'machineType', 'diskType', 'vmMicrousdPerHour',
              'diskMicrousdPerGiBHour', 'pricedThroughSeconds', 'retentionDays', 'otherCostsMicrousd', 'sources'}
    m.need(type(value) is dict and set(value) == fields, 'Runner price fields')
    a.integer(value['observedAt'], 1); a.integer(value['expiresAt'], value['observedAt']+1, value['observedAt']+86400)
    env = workload.load()['environment']
    m.need(value['observedAt'] <= now < value['expiresAt'] and
           (value['region'], value['machineType'], value['diskType']) ==
           (env['zone'].rsplit('-', 1)[0], env['machineType'], env['diskType']), 'Runner price freshness/selection')
    seconds = a.integer(value['pricedThroughSeconds'], 6480, 86400)
    a.integer(value['retentionDays'], 30, 365)
    vm = a.integer(value['vmMicrousdPerHour'], 1, a.MAXIMUM_BUDGET_MICROUSD)
    disk = a.integer(value['diskMicrousdPerGiBHour'], 1, a.MAXIMUM_BUDGET_MICROUSD)
    extra = value['otherCostsMicrousd']
    m.need(type(extra) is dict and set(extra) == {'requests', 'evidenceRetention', 'network', 'actions', 'failureOverhang'},
           'Runner price coverage')
    for cost in extra.values(): a.integer(cost, 1, a.MAXIMUM_BUDGET_MICROUSD)
    sources = value['sources']
    m.need(type(sources) is dict and set(sources) == {'compute', 'disks', 'storage', 'network', 'actions'}, 'Runner price sources')
    for kind, url in sources.items():
        domain = r'docs\.github\.com' if kind == 'actions' else r'(?:cloud|docs\.cloud)\.google\.com'
        m.need(type(url) is str and len(url) <= 1024 and re.fullmatch(r'https://'+domain+r'/[^\s]+', url), 'Runner price source URL')
    return ((3*vm+450*disk)*seconds+3599)//3600 + sum(extra.values())


def plan(cfg, proof, guest, quote, baseline, *, sequence, now, maximum_cost):
    p.configuration(cfg); a.integer(now, 1); guest_setup.access(guest)
    m.need(type(proof) is dict and set(proof) == {'schema','source','ciRun','ciAttempt','artifacts','buildBinding','buildProducer',
           'buildManifestSha256','packageManifestSha256','archiveSha256','workloadSha256'} and
           proof['schema'] == 'gse-v51-runner-artifacts-v1', 'Runner artifact proof shape')
    for key in ('buildManifestSha256','packageManifestSha256','archiveSha256'): a.digest(proof[key])
    a.integer(proof['ciRun'], 1); a.integer(proof['ciAttempt'], 1)
    cost = a.integer(maximum_cost, 1, a.MAXIMUM_BUDGET_MICROUSD); estimate = prices(quote, now)
    m.need(estimate <= cost, 'Runner estimate exceeds approved reservation')
    req = n.request(proof['source'], proof['archiveSha256'], g.config(cfg['provider']), sequence, guest['attempt'],
                    'experiment', now=now, guest_access_sha256=m.sha(m.canonical(guest)))
    inputs = {k:proof[k] for k in ('source','archiveSha256','buildManifestSha256','packageManifestSha256','workloadSha256')}
    inputs['pricesSha256'] = m.sha(m.canonical(quote))
    stage = resources.make(cfg['provider'], req, guest, baseline, inputs, now=now, maximum_cost=cost)
    return m.strict_json(m.canonical(dict(schema=SCHEMA, configuration=deepcopy(cfg), artifacts=deepcopy(proof),
        prices=deepcopy(quote), estimatedCostMicrousd=estimate, resourcePlan=stage,
        expiresAt=min(now+900, quote['expiresAt']), **FLAGS)))


def validate_plan(value, now):
    stage = value['resourcePlan']; req = stage['request']
    expected = plan(value['configuration'], value['artifacts'], stage['guestAccess'], value['prices'], stage['baseline'],
                    sequence=req['sequence'], now=req['createdAt'], maximum_cost=stage['reservation']['maximumCostMicrousd'])
    m.need(value == expected and req['createdAt'] <= now < value['expiresAt'], 'Runner plan drift/expiry')
    prices(value['prices'], now)
    return m.sha(m.canonical(value))


def approval_template(value):
    stage = value['resourcePlan']; req = stage['request']
    return dict(schema='gse-v51-runner-experiment-approval-v1', confirmed=False,
                planSha256=validate_plan(value, req['createdAt']), requestSha256=n.validate_request(req),
                expiresAt=value['expiresAt'], maximumCostMicrousd=stage['reservation']['maximumCostMicrousd'],
                previousCostMicrousd=stage['reservation']['previousCostMicrousd'])


def approval(value, approved, confirmation, now):
    digest = validate_plan(value, now); expected = approval_template(value); expected['confirmed'] = True
    m.need(approved == expected and approved['confirmed'] is True and confirmation == digest, 'Runner exact approval missing/changed')
    return digest


def context(cfg, env, source, checkout, preflight, precheck_root, value, approved, *, get, now):
    binding = precheck.identity(cfg, env, source, checkout)
    m.need(not env.get('RUNNER_STORAGE_REQUEST') and not env.get('RUNNER_STORAGE_CONFIRMATION'), 'Runner mixed execution selections')
    digest = approval(value, approved, env.get('RUNNER_EXPERIMENT_CONFIRMATION'), now)
    m.need(value['configuration'] == cfg and value['artifacts']['source'] == source, 'Runner selected configuration/source')
    jobs = precheck.collect_jobs(binding, get)
    prerequisites = storage.check_inputs(cfg, env, binding, preflight, precheck_root, jobs, now=now)
    # Replay the saved observations, then independently collect the current CI.
    # A user-controlled PASS summary or a now-superseded green run is insufficient.
    github = ci.collect(source, get); ci.check(github, source, now, (ci.ROOT/ci.WORKFLOW).read_text())
    m.need(github['configurationSha256'] == p.configuration(cfg), 'Runner current source configuration changed')
    m.need((github['run']['id'], github['run']['run_attempt']) ==
           (value['artifacts']['ciRun'], value['artifacts']['ciAttempt']), 'Runner current CI changed')
    provider = read(Path(preflight)/'provider.json')['observations']; stage = value['resourcePlan']
    m.need(provider['lease'] is None and m.canonical(provider['ledger']) == m.canonical(stage['baseline']), 'Runner observer ledger changed')
    return dict(binding=binding, prerequisites=prerequisites, github=github, planSha256=digest)


class ControlReads(h.Api):
    """Only the two control objects; no mutation even through the base API."""
    def __init__(self, cfg, *, transport, tokens, clock, expires):
        super().__init__(transport=transport, tokens=tokens, clock=clock)
        self.store = g.Store(cfg, self, authority=n); self.deadline = expires; self.requests = []
    def authorize(self, method, url, body):
        parsed = urlsplit(url); pairs = parse_qsl(parsed.query, strict_parsing=True) if parsed.query else []; query = dict(pairs)
        m.need(method == 'GET' and body is None and len(query) == len(pairs) and
               parsed._replace(query='').geturl() in {self.store.url(n.LEASE), self.store.url(n.LEDGER)}, 'Runner admission control GET only')
        m.need(not query or set(query) == {'alt','generation','ifGenerationMatch'} and query['alt'] == 'media' and
               query['generation'] == query['ifGenerationMatch'] and g.numeric(query['generation']), 'Runner admission pinned control read')
    def call(self, method, url, body=None, **kwargs):
        m.need(len(self.requests) < 32, 'Runner admission read bound')
        kwargs['deadline'] = min(kwargs['deadline'], self.deadline)
        self.requests.append(dict(method=method, url=url))
        return super().call(method, url, body, **kwargs)


def inspect(api, value, bound, artifact_root, checkout_binding, *, get, wall, offline_controls=None):
    github = bound['github']; records = read(Path(artifact_root)/'artifacts.json')
    for record in records.values(): m.need(get(f"actions/artifacts/{record['id']}") == record, 'Runner retained artifact metadata changed')
    original_job = read(Path(artifact_root)/'build-job.json')
    m.need(artifacts.collect_build_job(records['build'], github, get) == original_job, 'Runner original build job changed')
    m.need(offline_controls is None or api.offline is True, 'Runner synthetic controls require offline admission')
    proof = artifacts.verify(artifact_root, github, checkout_binding, controls=offline_controls)
    m.need(proof == value['artifacts'], 'Runner prepared package/build changed')
    # Credential exchange starts only after exact approval and original byte checks.
    baseline = value['resourcePlan']['baseline']
    for _ in range(2):
        m.need(api.store.get(n.LEASE) is None and m.canonical(api.store.get(n.LEDGER)) == m.canonical(baseline),
               'Runner current control state changed')
    for record in records.values(): m.need(get(f"actions/artifacts/{record['id']}") == record, 'Runner artifact changed during inspection')
    m.need(artifacts.collect_build_job(records['build'], github, get) == original_job, 'Runner build job changed during inspection')
    entry.collect_run(bound['binding'], get)
    current = ci.collect(proof['source'], get)
    ci.check(current, proof['source'], int(wall()), (ci.ROOT/ci.WORKFLOW).read_text())
    m.need(current == github, 'Runner CI/master moved during inspection')
    now = int(wall()); validate_plan(value, now)
    m.need(now < bound['prerequisites']['expiresAt'] and api.clock() <= api.deadline, 'Runner admission original deadline')
    return dict(schema='gse-v51-runner-request-inspection-v1', status='REQUEST_BOUND',
        execution='offline-runner-request-inspection' if api.offline else 'native-runner-request-inspection',
        binding=bound['binding'], prerequisites=bound['prerequisites'], artifacts=proof,
        planSha256=bound['planSha256'], resourcePlan=deepcopy(value['resourcePlan']), checkedAt=now,
        expiresAt=min(value['expiresAt'], bound['prerequisites']['expiresAt']),
        credentialExchangeCompleted=api.tokens.exchanges > 0, paidCloud=False, **FLAGS)


class NetworkAdmission:
    def __init__(self, cfg, env, source, checkout, preflight, precheck_root, value, approved, artifact_root):
        workflow.workflow()
        bound = context(cfg, env, source, checkout, preflight, precheck_root, value, approved, get=ci.github, now=int(time.time()))
        checkout_binding = build.binding(ci.ROOT, source)
        tokens = credentials.NetworkCredentials(bound['binding'], env, entry.credential_file(env))
        now = time.time(); expires = min(value['expiresAt'], bound['prerequisites']['expiresAt'])
        self.api = ControlReads(cfg['provider'], transport=h.Network(), tokens=tokens, clock=time.monotonic,
                                expires=time.monotonic()+min(180, expires-now))
        self.result = inspect(self.api, value, bound, artifact_root, checkout_binding, get=ci.github, wall=time.time)


class OfflineAdmission:
    def __init__(self, cfg, env, source, preflight, precheck_root, value, approved, artifact_root, checkout_binding,
                 *, transport, issuer, descriptor, clock, wall, get, controls=None):
        m.need(transport.offline is True and issuer.offline is True, 'Runner admission offline constructors')
        bound = context(cfg, env, source, source, preflight, precheck_root, value, approved, get=get, now=int(wall()))
        tokens = credentials.Credentials(bound['binding'], env, descriptor, transport=issuer, clock=clock, wall=wall)
        expires = min(value['expiresAt'], bound['prerequisites']['expiresAt'])
        self.api = ControlReads(cfg['provider'], transport=transport, tokens=tokens, clock=clock, expires=clock()+min(180, expires-wall()))
        self.result = inspect(self.api, value, bound, artifact_root, checkout_binding, get=get, wall=wall, offline_controls=controls)

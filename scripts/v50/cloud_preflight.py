"""Read-only, expiring observations. Missing permissions/allowlists fail closed."""
import argparse
from datetime import datetime
import itertools
import json
import math
from pathlib import Path
import re
import subprocess
import time
import urllib.parse
from .cloud_common import PLAN, canonical, plan, read, require, save, sha
from .cloud_gcp import Api
from .cloud_presets import SEQUENCES
from .cloud_runner import BUDGET, LEASE

PROJECT_PERMISSIONS = ['compute.disks.create', 'compute.disks.delete', 'compute.disks.get', 'compute.disks.use',
    'compute.instances.create', 'compute.instances.delete', 'compute.instances.get', 'compute.instances.attachDisk',
    'compute.instances.detachDisk', 'compute.instances.setMetadata', 'compute.instances.setDiskAutoDelete',
    'compute.firewalls.create', 'compute.firewalls.delete', 'compute.firewalls.get', 'compute.networks.getEffectiveFirewalls',
    'compute.subnetworks.use', 'compute.zoneOperations.get', 'compute.globalOperations.get',
    'compute.zoneOperations.list', 'compute.globalOperations.list', 'iap.tunnelInstances.accessViaIAP',
    'compute.projects.get', 'compute.regions.get', 'compute.zones.get', 'compute.machineTypes.get',
    'compute.subnetworks.get', 'iam.workloadIdentityPoolProviders.get']
STORAGE_PERMISSIONS = ['storage.buckets.get', 'storage.objects.create', 'storage.objects.get', 'storage.objects.list']
CONTROL_OBJECTS = (LEASE, BUDGET, SEQUENCES)


def check_permissions(observation, required, scope):
    require(isinstance(observation, dict), scope + ' permission response malformed')
    require('error' not in observation, scope + ' permission query failed: ' + str(observation.get('error')))
    permissions = observation.get('permissions', [])
    require(isinstance(permissions, list) and all(isinstance(v, str) for v in permissions), scope + ' permission response malformed')
    missing = sorted(set(required) - set(permissions))
    require(not missing, scope + ' missing permissions: ' + ', '.join(missing))


def collect_control_permissions(p, api):
    """Test effective delete access at each exact control object, without writing it."""
    base = 'https://storage.googleapis.com/storage/v1/b/' + p['bucket'] + '/o/'
    responses = {}
    for name in CONTROL_OBJECTS:
        # Create/list are bucket permissions; sending them to the object method
        # returns HTTP 400. Delete must be evaluated with the object resource name
        # so prefix-conditioned grants apply, including before the object exists.
        url = base + urllib.parse.quote(name, safe='') + '/iam/testPermissions?permissions=storage.objects.delete'
        try: responses[name] = api.call('GET', url)
        except Exception as error: responses[name] = dict(error=str(error))
    return dict(bucket=p['bucket'], objects=responses)


def check_control_permissions(p, observation):
    require(isinstance(observation, dict) and observation.get('bucket') == p['bucket'], 'control permission bucket mismatch')
    responses = observation.get('objects')
    require(isinstance(responses, dict) and set(responses) == set(CONTROL_OBJECTS), 'control permission object set mismatch')
    for name in CONTROL_OBJECTS:
        response = responses[name]
        require(isinstance(response, dict) and 'error' not in response, 'control permission query failed: ' + name)
        permissions = response.get('permissions', [])
        require(isinstance(permissions, list) and 'storage.objects.delete' in permissions,
                'missing storage.objects.delete on control object: ' + name)


def condition_allows_only(condition, claims):
    """Evaluate a closed equality/AND/OR CEL subset over all distinct literal values."""
    pattern = r"assertion\.[a-z_]+|'[^'\\]*'|==|&&|\|\||[()]"
    tokens = re.findall(pattern, condition)
    require(''.join(tokens) == re.sub(r'\s+', '', re.sub(r"'[^']*'", lambda m: m[0].replace(' ', '\x01'), condition)).replace('\x01', ' '), 'unsupported WIF condition syntax')
    pos = 0; alternatives = {k: {v, '__untrusted__'} for k, v in claims.items()}
    def atom():
        nonlocal pos
        require(pos < len(tokens), 'incomplete WIF condition')
        if tokens[pos] == '(':
            pos += 1; value = expression()
            require(pos < len(tokens) and tokens[pos] == ')', 'WIF parentheses'); pos += 1; return value
        name = tokens[pos].removeprefix('assertion.'); pos += 1
        require(name in claims and tokens[pos:pos + 1] == ['=='], 'unsupported WIF claim/operator'); pos += 1
        require(pos < len(tokens) and tokens[pos].startswith("'"), 'WIF literal')
        literal = tokens[pos][1:-1]; pos += 1; alternatives[name].add(literal)
        return ('eq', name, literal)
    def conjunction():
        nonlocal pos
        value = atom()
        while pos < len(tokens) and tokens[pos] == '&&':
            pos += 1; value = ('and', value, atom())
        return value
    def expression():
        nonlocal pos
        value = conjunction()
        while pos < len(tokens) and tokens[pos] == '||':
            pos += 1; value = ('or', value, conjunction())
        return value
    tree = expression(); require(pos == len(tokens), 'trailing WIF condition')
    def evaluate(node, values):
        kind, a, b = node
        if kind == 'eq': return values[a] == b
        return evaluate(a, values) and evaluate(b, values) if kind == 'and' else evaluate(a, values) or evaluate(b, values)
    require(evaluate(tree, claims), 'new workflow is not allowed by WIF')
    keys = list(claims)
    require(math.prod(map(len, alternatives.values())) <= 100_000, 'WIF condition complexity')
    for values in itertools.product(*(alternatives[k] for k in keys)):
        candidate = dict(zip(keys, values))
        # Existing workflows may remain allowed; every repository/ref/environment guard must still hold.
        if any(candidate[k] != claims[k] for k in keys if k != 'workflow_ref'):
            require(not evaluate(tree, candidate), 'WIF allows an untrusted repository/ref/environment')


def claims(p):
    return dict(repository=p['repository'], repository_id=p['repositoryId'], repository_owner_id=p['repositoryOwnerId'],
                ref=p['ref'], environment=p['environment'], workflow_ref=p['repository'] + '/' + p['workflow'] + '@' + p['ref'])


def check_observations(p, observations, source, now=None):
    now = int(time.time()) if now is None else now
    failures = []
    def check(label, function):
        try: function()
        except (KeyError, TypeError, ValueError) as error: failures.append(label + ': ' + str(error))
    check('source', lambda: require(observations['github']['master'] == source and observations['github']['ciHead'] == source and
                observations['github']['ciStatus'] == 'completed' and observations['github']['ciConclusion'] == 'success', 'exact-master CI is not green'))
    check('CI gates', lambda: require(all(observations['github']['jobs'].get(name) == 'success' for name in
                ('Reactor tests', 'Compatibility', 'Release artifacts', 'Cloud runner (no GCP)', 'Required')) and
                observations['github']['runnerGate'] == 'success', 'full exact-source gates including 6B must execute'))
    def watchdog():
        receipt = observations['github']['cleanup']
        require(isinstance(receipt, dict), 'scheduled cleanup response malformed')
        require('error' not in receipt, 'scheduled cleanup unavailable: ' + str(receipt.get('error')))
        require(receipt['head'] == source and receipt['conclusion'] == receipt['stepConclusion'] == 'success' and
                0 <= now - receipt['updatedAt'] <= 7200, 'no recent successful scheduled cleanup for the exact source')
    check('cleanup watchdog', watchdog)
    check('identity', lambda: require(observations['principal'] == p['serviceAccount'], 'observation is not made as the workflow service account'))
    check('WIF', lambda: condition_allows_only(observations['provider']['attributeCondition'], claims(p)))
    check('provider', lambda: require(observations['provider']['state'] == 'ACTIVE' and
                not observations['provider'].get('disabled', False) and
                observations['provider']['oidc']['issuerUri'] == 'https://token.actions.githubusercontent.com', 'inactive/wrong issuer'))
    check('image', lambda: require(observations['image']['id'] == p['imageId'] and observations['image']['status'] == 'READY' and
                not observations['image'].get('deprecated') and observations['image']['architecture'] == 'X86_64', 'image identity/status changed'))
    check('machine', lambda: require(observations['machine']['guestCpus'] == 8 and observations['machine']['memoryMb'] == 32768, 'machine shape changed'))
    check('zone', lambda: require(observations['zone']['status'] == 'UP', 'zone unavailable'))
    def quota():
        region = {v['metric']: v for v in observations['region']['quotas']}
        project = {v['metric']: v for v in observations['project']['quotas']}
        for values, metric, needed in ((region, 'N2_CPUS', 24), (region, 'CPUS', 24), (region, 'SSD_TOTAL_GB', 450),
                                       (project, 'CPUS_ALL_REGIONS', 24), (project, 'FIREWALLS', 4)):
            require(values[metric]['limit'] - values[metric]['usage'] >= needed, metric + ' headroom')
    check('quota', quota)
    check('network', lambda: require(observations['subnetwork']['network'].endswith('/networks/' + p['network']) and
                observations['subnetwork']['region'].endswith('/regions/' + p['region']), 'subnet/network mismatch'))
    def firewalls():
        effective = observations['effectiveFirewalls']; regional = observations['regionalFirewalls']
        require('error' not in effective and 'error' not in regional and
                all(not response.get(key) for response in (effective, regional) for key in ('firewallPolicys', 'firewallPolicies')), 'unreviewed hierarchical/network firewall policy')
        for rule in [*effective.get('firewalls', []), *regional.get('firewalls', [])]:
            if rule.get('disabled') or rule.get('direction', 'INGRESS') != 'INGRESS': continue
            require(rule.get('priority', 1000) > 950, 'existing firewall can override exact owned peer/IAP scope')
    check('firewall', firewalls)
    check('project permissions', lambda: check_permissions(observations['permissions'], PROJECT_PERMISSIONS, 'project'))
    check('bucket permissions', lambda: check_permissions(observations['storagePermissions'], STORAGE_PERMISSIONS, 'bucket'))
    check('control object permissions', lambda: check_control_permissions(p, observations['controlObjectPermissions']))
    check('storage', lambda: require(observations['bucket']['name'] == p['bucket'] and
                observations['bucket']['iamConfiguration']['uniformBucketLevelAccess']['enabled'], 'bucket identity/access boundary'))
    def budget():
        ledger = observations['budget']
        require(ledger['schema'] == 'gse-v50-budget-v1' and all(type(v['maximumCostMicrousd']) is int and v['maximumCostMicrousd'] > 0 for v in ledger['reservations']), 'invalid budget ledger')
        require(sum(v['maximumCostMicrousd'] for v in ledger['reservations']) < p['maximumSequenceCostMicrousd'], 'sequence budget exhausted')
    check('budget', budget)
    return dict(schema='gse-v50-cloud-preflight-v1', execution='read-only-gcp', source=source,
                planSha256=sha(canonical(p)), observedAt=now, expiresAt=now + p['receiptTtlSeconds'],
                status='READY_FOR_PAID_REVIEW' if not failures else 'BLOCKED', blockers=failures,
                observations=observations, allocationGuaranteed=False, resourcesCreated=False)


def collect(p, source, api=None):
    api = api or Api()
    base = 'https://compute.googleapis.com/compute/v1/projects/' + p['project']
    queries = {
        'project': base, 'region': base + '/regions/' + p['region'], 'zone': base + '/zones/' + p['zone'],
        'machine': base + '/zones/' + p['zone'] + '/machineTypes/' + p['machineType'],
        'image': 'https://compute.googleapis.com/compute/v1/projects/' + p['imageProject'] + '/global/images/' + p['image'],
        'subnetwork': base + '/regions/' + p['region'] + '/subnetworks/' + p['subnetwork'],
        'provider': 'https://iam.googleapis.com/v1/' + p['wifProvider'],
        'bucket': 'https://storage.googleapis.com/storage/v1/b/' + p['bucket'],
        'effectiveFirewalls': base + '/global/networks/' + p['network'] + '/getEffectiveFirewalls',
        'regionalFirewalls': base + '/regions/' + p['region'] + '/firewallPolicies/getEffectiveFirewalls?network=' +
                            urllib.parse.quote(base + '/global/networks/' + p['network'], safe=''),
    }
    observed = {}
    for label, url in queries.items():
        try: observed[label] = api.call('GET', url)
        except Exception as error: observed[label] = dict(error=str(error))
    try:
        from .cloud_gcp import Gcp
        stored = Gcp(p, {}, '.', api=api).get_object(BUDGET)
        observed['budget'] = json.loads(stored[1]) if stored else dict(schema='gse-v50-budget-v1', reservations=[])
    except Exception as error: observed['budget'] = dict(error=str(error))
    for label, url, permissions in (
            ('permissions', 'https://cloudresourcemanager.googleapis.com/v1/projects/' + p['project'] + ':testIamPermissions', PROJECT_PERMISSIONS),
            ('storagePermissions', 'https://storage.googleapis.com/storage/v1/b/' + p['bucket'] + '/iam/testPermissions', STORAGE_PERMISSIONS)):
        try:
            if label == 'storagePermissions':
                observed[label] = api.call('GET', url + '?' + urllib.parse.urlencode({'permissions': permissions}, doseq=True))
            else: observed[label] = api.call('POST', url, {'permissions': permissions})
        except Exception as error: observed[label] = dict(error=str(error))
    observed['controlObjectPermissions'] = collect_control_permissions(p, api)
    try:
        active = subprocess.run(['gcloud', 'auth', 'list', '--filter=status:ACTIVE', '--format=value(account)'], capture_output=True, text=True, timeout=30)
        require(active.returncode == 0, 'principal query failed'); observed['principal'] = active.stdout.strip()
        def github(path):
            result = subprocess.run(['gh', 'api', 'repos/' + p['repository'] + '/' + path], capture_output=True, timeout=30)
            require(result.returncode == 0, 'GitHub source query failed'); return json.loads(result.stdout)
        master = github('branches/master')['commit']['sha']
        runs = github('actions/workflows/ci.yml/runs?branch=master&per_page=10')['workflow_runs']
        ci = next((r for r in runs if r['head_sha'] == source), None)
        require(ci is not None, 'no CI run for the exact source')
        jobs = github('actions/runs/' + str(ci['id']) + '/jobs?per_page=100')['jobs']
        gate = next((s['conclusion'] for j in jobs for s in j.get('steps', []) if s['name'] ==
                    'Verify V5.0 Phase 6B runner failures and offline volume-layout probe'), None)
        # GITHUB_TOKEN has Actions read access, not Variables API permission. A
        # successful *executed* scheduled cleanup proves more than a config flag.
        try:
            candidates = github('actions/workflows/v50-replication-evidence.yml/runs?event=schedule&per_page=10')['workflow_runs']
            cleanup = next((r for r in candidates if r['head_sha'] == source and r['status'] == 'completed'), None)
            require(cleanup is not None, 'no completed scheduled cleanup for the exact source')
            cleanup_jobs = github('actions/runs/' + str(cleanup['id']) + '/jobs?per_page=100')['jobs']
            step = next((s['conclusion'] for j in cleanup_jobs for s in j.get('steps', []) if s['name'] == 'Reconcile only an expired retained ownership lease'), None)
            require(step is not None, 'scheduled cleanup step did not execute (job may be skipped)')
            watchdog = dict(head=cleanup['head_sha'], conclusion=cleanup['conclusion'], stepConclusion=step, run=cleanup['id'],
                updatedAt=int(datetime.fromisoformat(cleanup['updated_at'].replace('Z', '+00:00')).timestamp()))
        except Exception as error: watchdog = dict(error=str(error))
        observed['github'] = dict(master=master, ciHead=ci['head_sha'], ciStatus=ci['status'], ciConclusion=ci['conclusion'], ciRun=ci['id'],
            jobs={j['name']: j['conclusion'] for j in jobs}, runnerGate=gate, cleanup=watchdog)
        observed['github']['remoteGate']=next((s['conclusion'] for j in jobs for s in j.get('steps',[]) if s['name']==
            'Verify V5.0 remote workload adapter and bounded evidence'),None)
    except Exception as error: observed['github'] = dict(error=str(error))
    return check_observations(p, observed, source)


def admission(p, receipt, request, approval, *, now=None):
    now = int(time.time()) if now is None else now
    require(receipt['schema'] == 'gse-v50-cloud-preflight-v1' and receipt['execution'] == 'read-only-gcp' and
            receipt['source'] == request['source'] and receipt['planSha256'] == sha(canonical(p)), 'preflight identity')
    require(receipt['observedAt'] <= now <= receipt['expiresAt'] <= receipt['observedAt'] + p['receiptTtlSeconds'], 'stale preflight')
    checked = check_observations(p, receipt['observations'], request['source'], receipt['observedAt'])
    require(receipt == checked and receipt['status'] == 'READY_FOR_PAID_REVIEW', 'preflight not admitted')
    if request['profile']!='admission-probe':
        from .cloud_presets import validate_request
        validate_request(request)
        require(receipt['observations']['github'].get('remoteGate')=='success','exact-source remote workload gate must execute')
    require(approval['schema'] == 'gse-v50-paid-admission-v1' and approval['confirmed'] is True and
            approval['requestSha256'] == sha(canonical(request)) and approval['preflightSha256'] == sha(canonical(receipt)) and
            approval['planSha256'] == sha(canonical(p)) and approval['expiresAt'] >= now and approval['expiresAt'] <= receipt['expiresAt'], 'exact paid confirmation required')
    require(0 < approval['maximumCostMicrousd'] and 0 <= approval['previousAttemptsCostMicrousd'] and
            approval['maximumCostMicrousd'] + approval['previousAttemptsCostMicrousd'] <= p['maximumSequenceCostMicrousd'] and
            approval['priceSources'] and approval['estimateIncludes'] == ['three-vms', 'boot-disks', 'data-disks', 'control', 'evidence', 'cleanup', 'failed-attempts'], 'complete sequence budget')
    require(all(type(approval[k]) is int for k in ('maximumCostMicrousd', 'previousAttemptsCostMicrousd', 'expiresAt')) and
            approval['pricedThroughTopologySeconds'] >= p['maximumTopologySeconds'] and approval['cleanupOverhangSeconds'] >= 1080,
            'cost estimate must cover VM watchdog and scheduled cleanup overhang')
    require(approval['previousAttemptsCostMicrousd'] == sum(v['maximumCostMicrousd'] for v in receipt['observations']['budget']['reservations']), 'reviewed budget balance mismatch')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=PLAN); parser.add_argument('--source', required=True); parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(); require(re.fullmatch('[0-9a-f]{40}', args.source), 'source SHA')
    receipt = collect(plan(args.plan), args.source); save(args.output, receipt)
    print(json.dumps(dict(status=receipt['status'], blockers=receipt['blockers']), sort_keys=True))
    raise SystemExit(0 if receipt['status'] == 'READY_FOR_PAID_REVIEW' else 2)

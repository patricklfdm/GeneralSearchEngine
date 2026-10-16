"""A distinct hosted cohort: frozen whole histories, six isolated runner groups.

This does not relax or replace the committed single-machine local admission.
"""
import copy
import os
import re
from pathlib import Path
from . import measurement_machine as machine, measurement_m01_set as m01_set
from . import measurement_model as model, measurement_bundle as bundle
from .evidence import need, digest, encoded

BRANCH = 'experiment/v52-hosted-measurements'
SCHEMA = 'gse-v52-hosted-measurements-v1'
ROOT = Path(__file__).resolve().parents[2]


def shards():
    specs = machine.members()
    result = {f'm01-r{rep}': [m01_set.name(mode, rep) for mode in model.MODES] for rep in (1, 2, 3)}
    result.update({key: [name for name, spec in specs.items() if spec['family'] == family]
                   for key, family in [('minimum-waits', 'M02'), ('capacity', 'M03'), ('recovery', 'M04')]})
    return result


def contract():
    value = copy.deepcopy(machine.contract())
    value['execution'].update(order=[name for names in shards().values() for name in names],
        shards=shards(), concurrentHistories=6, concurrentHistoriesPerRunner=1,
        environment='one frozen runner per shard; all five M01 modes of a repetition share that runner',
        acceptance='original replay plus independent downloaded replay, exact negatives and complete hosted aggregate',
        failure='stop failed shard; retain other shards; new complete workflow attempt required for acceptance')
    return value


def context():
    need(os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_EVENT_NAME') == 'push' and
         os.environ.get('GITHUB_REF') == 'refs/heads/' + BRANCH and
         os.environ.get('GITHUB_REPOSITORY') == 'patricklfdm/GeneralSearchEngine', 'hosted experiment event/ref/repository')
    run, attempt = os.environ.get('GITHUB_RUN_ID', ''), os.environ.get('GITHUB_RUN_ATTEMPT', '')
    need(re.fullmatch('[1-9][0-9]*', run) and re.fullmatch('[1-9][0-9]*', attempt), 'hosted run/attempt')
    need(re.fullmatch('[0-9a-f]{40}', os.environ.get('GITHUB_SHA', '')), 'hosted source SHA')
    return dict(run=run, attempt=int(attempt))


def hash_value(value):
    return digest(encoded(value))


def sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def validate_plan(plan, actual, identity, manifest):
    need(plan['schema'] == SCHEMA and plan['status'] == 'FROZEN_BEFORE_MEASUREMENTS' and plan['paidCloud'] is False,
         'hosted plan identity')
    need(plan['binding'] == actual and plan['identity'] == identity, 'hosted mixed source/run/attempt')
    need(encoded(plan['contract']) == encoded(contract()), 'hosted workload/partition contract changed')
    need(manifest['schema'] == machine.build.SCHEMA and manifest['binding'] == actual and
         plan['buildManifestSha256'] == hash_value(manifest) and plan['buildArchiveSha256'] == manifest['archiveSha256'],
         'hosted build manifest mismatch')
    need(set(plan['compiled']) == {'published', 'candidate'}, 'hosted compiled families')
    published = machine.runtime.evidence.reads.read(model.PLAN.parent / 'published-controls.json')
    published = {v['artifact'] + '-' + v['version'] + '.jar': v['sha256'] for v in published['artifacts']}
    files = {v['path']: v for v in manifest['files']}
    need(len(files) == len(manifest['files']), 'hosted duplicate build paths')
    candidate = {Path(p).name: files[p]['sha256'] for p in machine.build.layout(ROOT)[:2]}
    candidate['general-search-engine-4.4.0.jar'] = published['general-search-engine-4.4.0.jar']
    for family, artifacts in [('published', published), ('candidate', candidate)]:
        compiled = plan['compiled'][family]
        need(set(compiled) == {'artifacts', 'classes'} and compiled['artifacts'] == artifacts and compiled['classes'] and
             all(sha(v) for v in [*compiled['artifacts'].values(), *compiled['classes'].values()]), 'hosted compiled artifact drift')
    return plan


def check_binding(plan, freeze, name, binding):
    spec = plan['contract']['members'][name]
    need({k: binding[k] for k in plan['binding']} == plan['binding'] and
         {k: binding[k] for k in plan['identity']} == plan['identity'], 'hosted member source/run/attempt')
    need(binding['mode'] == spec['mode'] and binding['measurementProfile'] == spec['profile'] and
         binding['programSha256'] == model.PLAN_SHA, 'hosted member profile')
    family = 'published' if binding['mode'].startswith('published') else 'candidate'
    need({k: binding[k] for k in ('artifacts', 'classes')} == plan['compiled'][family], 'hosted member artifacts/classes')
    need(name in plan['contract']['execution']['shards'][freeze['shard']] and
         binding['origin'] == str(Path(freeze['storageRoot']) / 'histories' / name), 'hosted member origin/shard')
    return spec


def validate_freeze(plan, freeze, shard):
    need(freeze['schema'] == SCHEMA and freeze['shard'] == shard and freeze['planSha256'] == hash_value(plan) and
         freeze['identity'] == plan['identity'] and freeze['binding'] == plan['binding'], 'hosted machine freeze binding')
    need(freeze['status'] == 'FROZEN_BEFORE_MEASUREMENTS' and freeze['paidCloud'] is False and
         type(freeze['createdUnixNs']) is int and freeze['createdUnixNs'] > 0 and
         Path(freeze['storageRoot']).is_absolute(), 'hosted machine freeze shape')
    env = freeze['environment']
    need(isinstance(env.get('bootId'), str) and env['bootId'] and env['storage']['fstype'] in ('ext4', 'xfs', 'btrfs') and
         env['cpuModels'] and env['logicalCpus'] > 0 and env['affinity'] and env['memTotal'] and
         env['javaExecutable']['sha256'] and env['javacExecutable']['sha256'], 'hosted machine environment missing')
    return freeze


def validate_results(plan, expected, results):
    """Only called with results emitted by the independent downloaded replay jobs."""
    specs = plan['contract']['members']
    need(set(expected) == set(results) == set(specs), 'hosted incomplete 28-history cohort')
    groups, histories, manifests, origins = set(), set(), set(), set()
    reads = updates = negatives = 0
    outcomes = {}
    for name in plan['contract']['execution']['order']:
        binding, result, spec = expected[name], results[name], specs[name]
        family = spec['family']
        prefix = {'M01': 'm01', 'M02': 'minimum', 'M03': 'minimum', 'M04': 'recovery'}[family]
        need(result['status'] == 'PASS' and result['execution'] == prefix + '-portable-member' and
             result['binding'] == binding and result['qualifiedMeasurement'] is False and result['paidCloud'] is False,
             'hosted unqualified member')
        body = result['result']
        need(body['status'] == 'PASS' and body['execution'] == prefix + '-member-physical-replay' and
             body['qualifiedMeasurement'] is False and body['paidCloud'] is False and
             body['negatives'] == plan['contract']['negativeRules'][name], 'hosted exact physical/negative results')
        if family != 'M01':
            need(body['case'] == name, 'hosted case identity')
        for seen, value in [(groups, result['domain']['groupId']), (histories, result['domain']['historyId']),
                            (manifests, result['manifestSha256']), (origins, binding['origin'])]:
            need(value not in seen, 'hosted reused history/domain/origin'); seen.add(value)
        outcomes[name] = body['ledger']['outcomes']
        reads += sum(outcomes[name]['read'].values()); updates += sum(outcomes[name]['update'].values())
        negatives += len(body['negatives'])
    healthy = {name: result for name, result in results.items() if specs[name]['family'] == 'M01'}
    m01 = m01_set.validate_results(healthy, {name: expected[name] for name in healthy})
    need((reads, updates, negatives) == (27373, 2745, 439), 'hosted original call/negative counts')
    return dict(status='PASS', execution='complete-hosted-m01-m04-measurement', qualifiedMeasurement=True,
                localMachineAcceptance=False, hostedAcceptance=True, cloudAcceptance=False, paidCloud=False,
                protectedFullCI=False, planSha256=hash_value(plan), binding=plan['binding'], identity=plan['identity'],
                histories=28, originalReads=reads, originalUpdates=updates, negativeCasesPerLocation=negatives,
                negativeRejections=2*negatives, nominalM01Seconds=2700, m01=m01, outcomes=outcomes,
                boundary='Six hosted runner environments; not the single-machine local cohort, protected CI or GCP acceptance.')

"""Closed V5.2 cloud suite selection. No provider, workload or admission entry.

This is a logical pre-cloud contract. A source-bound selection is not evidence
that CI, permissions, cleanup, a lease or the selected workloads have passed.
"""
from copy import deepcopy
from pathlib import Path
import re
from . import measurement_machine as machine, measurement_model as model
from . import measurement_m01_set as m01, measurement_minimum as minimum, measurement_recovery as recovery
from .evidence import need, digest, encoded
from .public_reads_evidence import read

PLAN = Path(__file__).resolve().parents[2] / 'docs/v5x/v5.2/phase6-cloud-suite.json'
PLAN_SHA = 'b889dd7e1deccc9373a2453240b894a708524dc807bff3daccb709df8e18a535'
LEGACY_SHA = 'f8556b7e143e0fc5d85664503bc02a6e583b7227215a3258c9ea8545981cd5b0'
LEGACY_PLAN = PLAN.with_name('phase6-cloud-suite-v1.json')
DRILL_SHARDS = {
    'failure-drill-m02-below': tuple(f'm02-below-{v}' for v in (0,1000,5000)),
    'failure-drill-m02-equal': tuple(f'm02-equal-{v}' for v in (0,1000,5000)),
    'failure-drill-m02-above': tuple(f'm02-above-{v}' for v in (0,1000,5000)),
    'failure-drill-m03': ('m03-p4','m03-p65'),
    'failure-drill-m04': recovery.CASES,
}
LOGICAL_MEMBERS = ('experiment', 'failure-drill', 'canonical-1', 'canonical-2', 'canonical-3')
MEMBERS = ('experiment', *DRILL_SHARDS, 'canonical-1', 'canonical-2', 'canonical-3')
BINDING_FIELDS = frozenset(('source', 'checkoutSha256', 'sequence', 'suiteSha256', 'programSha256',
                            'buildManifestSha256', 'packageSha256', 'controlsManifestSha256'))


def definition():
    """Derive the reviewed grouping from the existing whole-history programs."""
    formal = machine.members()
    histories = deepcopy(formal)
    smoke = []
    for mode in model.MODES:
        name = mode + '-untimed-smoke'; smoke.append(name)
        histories[name] = dict(family='UNTIMED', mode=mode, reads=11, updates=3,
                               initialization='read-write-targets-confirmed-updates-v1', measurement=False)
    members = dict(experiment=dict(histories=smoke, reads=55, updates=15, nominalM01Seconds=0))
    for name, names in DRILL_SHARDS.items():
        # M02/M03 counts include setup updates, the release update when present,
        # and all original reads; derive from the frozen controllers, not a cut.
        reads=updates=0
        for history in names:
            if history in minimum.CASES:
                profile=minimum.profile(history)
                reads+=profile['readCount']+1+int(profile['family']=='M03')
                updates+=profile['setupUpdates']+int(profile['releaseUpdate'])
            else:
                reads+=4
                updates+=4
        members[name]=dict(histories=list(names),reads=reads,updates=updates,nominalM01Seconds=0)
    for repetition in (1, 2, 3):
        members['canonical-' + str(repetition)] = dict(
            histories=[m01.name(mode, repetition) for mode in model.MODES],
            reads=9005, updates=900, nominalM01Seconds=900)
    return dict(schema='gse-v52-cloud-suite-v2', status='LOGICAL_PLAN_NOT_ADMISSION',
        programSha256=model.PLAN_SHA,
        controlsManifestSha256=digest((PLAN.parent / 'published-controls.json').read_bytes()),
        members=members, histories=histories,
        logicalMembers={name:list(DRILL_SHARDS) if name=='failure-drill' else [name] for name in LOGICAL_MEMBERS},
        formalNegativeRules={name: machine.negative_rules(spec) for name, spec in formal.items()},
        totals=dict(members=9, logicalMembers=5, histories=33, formalHistories=28, reads=27428, updates=2760,
                    nominalM01Seconds=2700, formalNegativesPerLocation=439),
        topology=dict(voters=3, hosts=3, placement='one voter per owned host',
                      bootstrap='same immutable source backup; public bootstrap on every receiver',
                      addresses='explicit admitted private peer addresses',
                      paths='per-node original roots and receiver-local seals'),
        execution=dict(memberOrder='any', concurrentMembers=1, concurrentHistories=1,
                       businessRetries=0, workloadRetries=0,
                       responseLoss='observe original command only; never resubmit business work',
                       failedAttempts='retain separately; never splice successful history fragments',
                       historyBoundary='one complete history, original session and retained lease'),
        qualification=dict(requiredMembers=list(MEMBERS), source='one exact source and sequence',
                           crossSourceContinuation=False,
                           replay='original and relocated physical/public/query/resource evidence plus exact negatives',
                           incompleteSet='NOT_QUALIFIED', localReceiptIsCloudEvidence=False),
        budgets=dict(operationalTime='soft warning', operationalCost='soft warning',
                     apiReadDeadlines='unchanged finite semantic outcomes',
                     authorityAndDecoderLimits='finite enforced bounds'),
        liveAdmission='exact-source Cloud Build or full CI, provider facts, permissions, cleanup, lease and operator authorization')


def validate(value):
    model.load()
    need(digest(encoded(value)) == PLAN_SHA, 'unreviewed V5.2 cloud suite')
    need(encoded(value) == encoded(definition()), 'V5.2 cloud suite/program drift')
    return value


def load():
    return validate(read(PLAN))


def member(name):
    plan = load()
    need(type(name) is str and name in MEMBERS, 'V5.2 cloud member')
    selected = plan['members'][name]
    return dict(name=name, **deepcopy(selected),
                profiles={key: deepcopy(plan['histories'][key]) for key in selected['histories']})


def validate_binding(value, *, historical=False):
    need(type(value) is dict and set(value) == BINDING_FIELDS, 'V5.2 cloud binding fields')
    for key, raw in value.items():
        size = 40 if key == 'source' else 32 if key == 'sequence' else 64
        need(type(raw) is str and re.fullmatch('[0-9a-f]{%d}' % size, raw), 'V5.2 cloud binding ' + key)
    legacy=historical and value['suiteSha256']==LEGACY_SHA
    plan = read(LEGACY_PLAN) if legacy else load()
    if legacy: need(digest(encoded(plan))==LEGACY_SHA,'V5.2 legacy suite changed')
    need(value['suiteSha256'] == (LEGACY_SHA if legacy else PLAN_SHA) and value['programSha256'] == model.PLAN_SHA and
         value['controlsManifestSha256'] == plan['controlsManifestSha256'], 'V5.2 cloud bound plan/control drift')
    return value


def selection(binding, name, attempt):
    """Create only the immutable whole-member selection, not a paid request."""
    validate_binding(binding)
    need(type(attempt) is str and re.fullmatch('[0-9a-f]{32}', attempt), 'V5.2 cloud attempt identity')
    return dict(schema='gse-v52-cloud-selection-v1', status='SELECTED_NOT_ADMITTED',
                binding=deepcopy(binding), member=member(name), attempt=attempt, qualified=False)


def validate_selection(value, *, historical=False):
    need(type(value) is dict and set(value) == {'schema', 'status', 'binding', 'member', 'attempt', 'qualified'},
         'V5.2 cloud selection fields')
    selected = value['member']
    need(type(selected) is dict and type(selected.get('name')) is str, 'V5.2 cloud selected member')
    if historical and type(value['binding']) is dict and value['binding'].get('suiteSha256')==LEGACY_SHA:
        validate_binding(value['binding'],historical=True);plan=read(LEGACY_PLAN)
        need(selected['name'] in plan['members'],'V5.2 legacy member')
        spec=plan['members'][selected['name']]
        chosen=dict(name=selected['name'],**deepcopy(spec),profiles={k:deepcopy(plan['histories'][k]) for k in spec['histories']})
        need(type(value['attempt']) is str and re.fullmatch('[0-9a-f]{32}',value['attempt']),'V5.2 cloud attempt identity')
        expected=dict(schema='gse-v52-cloud-selection-v1',status='SELECTED_NOT_ADMITTED',binding=value['binding'],
                      member=chosen,attempt=value['attempt'],qualified=False)
    else: expected=selection(value['binding'],selected['name'],value['attempt'])
    need(encoded(value) == encoded(expected),
         'V5.2 cloud selection changed')
    return value


def complete_selection(values):
    """Check all nine execution selections in any order; never promote them to execution PASS.

    The future aggregate must independently replay each original retained member.
    Passing this function alone grants no acceptance and performs no I/O besides
    reading the frozen local plan.
    """
    need(type(values) is list and len(values) == len(MEMBERS), 'V5.2 incomplete cloud selection set')
    names = set(); attempts = set(); bound = None
    for value in values:
        validate_selection(value)
        name = value['member']['name']
        need(name not in names and value['attempt'] not in attempts, 'V5.2 reused cloud member/attempt')
        names.add(name); attempts.add(value['attempt'])
        if bound is None: bound = value['binding']
        else: need(value['binding'] == bound, 'V5.2 mixed source/sequence/build selection')
    need(names == set(MEMBERS), 'V5.2 incomplete cloud member set')
    return dict(status='COMPLETE_SELECTION_NOT_QUALIFIED', qualified=False, paidCloud=False,
                binding=deepcopy(bound), members=list(MEMBERS), logicalMembers=list(LOGICAL_MEMBERS), totals=deepcopy(load()['totals']))

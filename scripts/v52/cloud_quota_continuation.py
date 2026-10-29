"""One operator-authorized batch, not a general mixed-source acceptance rule.

Original records retain their true source, build, sequence and invocation. Only
the ten frozen originals and five exact-current-source continuations can join.
This module grants neither execution admission nor qualification by itself.
"""
from copy import deepcopy
from pathlib import Path
from . import cloud_authority as a, cloud_suite as suite, cloud_inputs as inputs
from . import cloud_preflight as preflight, cloud_ci as ci
from .evidence import need, encoded, digest, strict

POLICY = 'docs/v5x/v5.2/quota-continuation.json'
CORE_SHA256 = '256b313a09028b66db1f68fbecc2b6c6b61e472b7102e0c16d3685294f887af6'

# Reconstruct the exact old tree from the narrowly approved support changes.
# Works with the Runner's shallow checkout; no historical git fetch is needed.
ORIGINAL_TREE_SHA256 = 'ac50990179e7439ed91adf5d07c6ef9541844fef257035da2aabcc8a6ea1f61c'
ORIGINAL_ENTRIES = {
    'scripts/v52/cloud_preflight.py': '100644 blob 1416513fd972781ce78263e1116a3e9f89536abc',
    'scripts/v52/test_cloud_preflight.py': '100644 blob f7a7f399c2bd97e31451dbeee94ef30b61c217ab',
    'scripts/v52/test_cloud_quota_normalization.py': None,
    'scripts/v52/cloud_acceptance.py': '100644 blob a2cdc1e72df6866a21567004e2818c86faed5328',
    'scripts/v52/cloud_evidence_read.py': '100644 blob c95ef6fa88101b86d332258625d15388c180e96d',
    'scripts/v52/cloud_runner_provenance.py': '100644 blob c47830300f47bc55142e99029359bbd2c62bc41f',
    'scripts/v52/cloud_set_evidence.py': '100644 blob 42ad718b3bd9a37b23c63067711a325c064c3995',
    'scripts/v52/cloud_member_evidence.py': '100644 blob b175f58c7512fe4d1ed1656006d6f4ae29816678',
    'scripts/v52/cloud_operator.py': '100644 blob e8abfd02f416d0c371c485fbb05b4f565a1f3761',
    'scripts/v52/cloud_quota_continuation.py': None,
    'scripts/v52/test_cloud_quota_continuation.py': None,
    'docs/v5x/v5.2/PHASE_6_QUOTA_CONTINUATION.md': None,
    'scripts/v52/cloud_retention_recovery.py': None,
    'scripts/v52/test_cloud_retention_recovery.py': None,
    'docs/v5x/v5.2/experiment-retention-recovery.json': None,
    'docs/v5x/v5.2/PHASE_6_RETENTION_RECOVERY.md': None,
}


def load(root=ci.ROOT):
    value = strict(inputs.regular(Path(root)/POLICY, 65536))
    need(digest(encoded({k:v for k,v in value.items() if k != 'approvedSourceChanges'})) == CORE_SHA256,
         'V5.2 continuation frozen batch changed')
    approved = value['approvedSourceChanges']
    need(type(approved) is dict and set(approved) == set(ORIGINAL_ENTRIES), 'V5.2 continuation source inventory')
    for name, sha in approved.items():
        need(type(name) is str and not Path(name).is_absolute() and '..' not in Path(name).parts,
             'V5.2 continuation source path')
        a.hex_value(sha)
    return value


def request(value):
    from .cloud_acceptance import selection
    a.fields(value, 'continuation selected', 'quota continuation request')
    policy = load()
    need(value['continuation'] == policy['id'], 'V5.2 unknown continuation batch')
    chosen = selection(value['selected'])
    for name, pin in policy['inherited'].items():
        need(chosen[name] == {k:pin[k] for k in ('requestSha256', 'runId', 'runAttempt')},
             'V5.2 continuation original selection changed')
    return chosen


def source_compatible(source, policy, root=ci.ROOT):
    """Inspect committed bytes, including verifier support; never trust a label."""
    a.hex_value(source, 40); root = Path(root)
    git = lambda *args: inputs.build.git(root, *args)
    rows = git('ls-tree', '-r', '-z', source).split(b'\0')
    tree = {row.split(b'\t')[1].decode():row.split(b'\t')[0].decode() for row in rows if row}
    need(set(policy['approvedSourceChanges']) == set(ORIGINAL_ENTRIES) and POLICY in tree,
         'V5.2 continuation source inventory')
    tree.pop(POLICY)
    for name, original in ORIGINAL_ENTRIES.items():
        need(name in tree and tree[name].startswith('100644 blob '), 'V5.2 continuation source file type')
        if original is None: tree.pop(name)
        else: tree[name] = original
    need(digest(encoded(tree)) == ORIGINAL_TREE_SHA256, 'V5.2 continuation unapproved source changes')
    for name, sha in policy['approvedSourceChanges'].items():
        need(digest(git('show', source+':'+name)) == sha, 'V5.2 continuation approved source bytes changed: '+name)
    need(strict(git('show', source+':'+POLICY)) == policy, 'V5.2 continuation committed policy changed')


def artifacts_match(files, pins):
    need({name for name in files if name.startswith('artifacts/')} == set(pins), 'V5.2 continuation JAR inventory')
    for name, pin in pins.items():
        need(dict(bytes=len(files[name]), sha256=digest(files[name])) == pin,
             'V5.2 continuation executable bytes differ: '+name)


class Scope:
    def __init__(self, cfg, source, chosen):
        self.policy = load(); source_compatible(source['source'], self.policy)
        inputs.identity(source)
        self.cfg = deepcopy(cfg); self.source = deepcopy(source)
        self.chosen = request(dict(continuation=self.policy['id'], selected=chosen))
        need(preflight.configuration(cfg) == self.policy['configurationSha256'] and
             source['java'] == self.policy['oldSource']['java'] and source['source'] != self.policy['oldSource']['source'],
             'V5.2 continuation configuration/Java/source changed')
        self.frozen = digest(encoded([self.policy, self.cfg, self.source, self.chosen]))

    def guard(self, source=None, cfg=None):
        need(type(self) is Scope and digest(encoded([self.policy, self.cfg, self.source, self.chosen])) == self.frozen and
             (source is None or source == self.source) and (cfg is None or cfg == self.cfg), 'V5.2 continuation scope changed')

    def member_source(self, name):
        self.guard(); need(name in self.chosen, 'V5.2 continuation unknown member')
        return deepcopy(self.policy['oldSource'] if name in self.policy['inherited'] else self.source)

    def validate_request(self, req):
        self.guard(); sha = a.validate_request(req, domain='native')
        name = req['selection']['member']['name']; bound = req['selection']['binding']
        need(name in self.chosen and sha == self.chosen[name]['requestSha256'] and
             req['configurationSha256'] == preflight.p.config(self.cfg['provider']) and
             req['layout'] == self.cfg['layout'] and req['policy'] == self.cfg['policy'],
             'V5.2 continuation request changed')
        old = self.policy['oldBinding']
        if name in self.policy['inherited']:
            need(bound == old, 'V5.2 continuation inherited binding changed')
        else:
            need(name in self.policy['remaining'] and bound['source'] == self.source['source'] and
                 bound['checkoutSha256'] == self.source['checkoutSha256'] and bound['sequence'] == self.policy['newSequence'] and
                 all(bound[k] == old[k] for k in ('programSha256', 'suiteSha256', 'controlsManifestSha256')),
                 'V5.2 continuation remaining binding changed')
        return name

    def selections(self, requests):
        need(len(requests) == len(suite.MEMBERS), 'V5.2 continuation incomplete set')
        names = set(); attempts = set(); bindings = {}
        for req in requests:
            name = self.validate_request(req); value = req['selection']; suite.validate_selection(value)
            need(name not in names and value['attempt'] not in attempts, 'V5.2 continuation reused member/attempt')
            names.add(name); attempts.add(value['attempt']); bindings[name] = deepcopy(value['binding'])
        need(names == set(suite.MEMBERS), 'V5.2 continuation missing member')
        new = bindings[self.policy['remaining'][0]]
        need(all(bindings[n] == new for n in self.policy['remaining']), 'V5.2 continuation mixed new build/package')
        return dict(binding=new, originalBindings=bindings)

    def original(self, name, record):
        self.guard(); selected = self.chosen[name]
        need(record['status'] == 'ORIGINAL_RUNNER_VERIFIED_NOT_QUALIFIED' and
             record['selected'] == {k:selected[k] for k in ('runId', 'runAttempt')} and
             record['source'] == self.member_source(name) and record['seal']['requestSha256'] == selected['requestSha256'],
             'V5.2 continuation original Runner changed')
        if name in self.policy['inherited']:
            pin = self.policy['inherited'][name]
            need(all(record[k] == pin[k] for k in ('artifactId', 'artifactSha256')) and
                 all(record['seal'][k] == pin[k] for k in ('completionSha256', 'manifestSha256', 'cleanupSha256')),
                 'V5.2 continuation inherited original bytes changed')

    def report(self):
        self.guard()
        return deepcopy(dict(id=self.policy['id'], scope=self.policy['scope'], policySha256=digest(encoded(self.policy)),
                    oldSource=self.policy['oldSource'], newSource=self.source,
                    oldSequence=self.policy['oldBinding']['sequence'], newSequence=self.policy['newSequence'],
                    inherited=list(self.policy['inherited']), remaining=self.policy['remaining']))

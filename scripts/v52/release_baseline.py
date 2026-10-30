"""Offline correlation of the already accepted protected cloud set, never a replay."""
from pathlib import Path

from .evidence import digest, encoded, need, strict

ROOT = Path(__file__).resolve().parents[2]
DOCS = 'docs/v5x/v5.2'
POLICY_SHA256 = '6d58dca98af4e2098318b3cffa49f8f3217ecb7f2e1b3545810505a607d9d319'
RELEASE_POMS = {'pom.xml', 'reactor/pom.xml', 'general-search-engine-replication/pom.xml',
                'general-search-engine-processor/pom.xml'}


def source_bytes(root, name):
    raw = regular(root/name)
    # Compare with the ORIGINAL accepted snapshot inventory. Only the project
    # version line may differ; dependencies, plugins, timestamp and source stay
    # byte-for-byte bound. Never regenerate the cloud baseline for a release.
    if name in RELEASE_POMS:
        final = b'    <version>5.2.0</version>\n'
        if raw.count(final) == 1:
            raw = raw.replace(final, b'    <version>5.2.0-SNAPSHOT</version>\n', 1)
    return raw


def regular(path):
    path = Path(path)
    need(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)),
         'release input must be an original regular file: '+str(path))
    return path.read_bytes()


def policy(root=ROOT):
    raw = regular(root/DOCS/'release-preparation.json')
    need(digest(raw) == POLICY_SHA256, 'release preparation policy changed')
    return strict(raw)


def runtime_inventory(root, spec):
    paths = set(spec['files'])
    for directory in spec['directories']:
        base = root/directory
        need(base.is_dir() and not base.is_symlink(), 'missing runtime source directory')
        for path in base.rglob('*'):
            need(not path.is_symlink(), 'runtime source symlink')
            if path.is_file(): paths.add(path.relative_to(root).as_posix())
    return {name: digest(source_bytes(root, name)) for name in sorted(paths)}


def check(root=ROOT):
    root = Path(root); rules = policy(root)
    values = {}
    for name, sha in rules['cloudFiles'].items():
        raw = regular(root/DOCS/name)
        need(digest(raw) == sha, 'accepted release input changed: '+name)
        values[name] = strict(raw)
    review = values['phase6-cloud-review.json']; provenance = values['phase6-cloud-provenance.json']
    registry = values['cloud-benchmark-baselines.json']; waiver = values['experiment-retention-recovery.json']
    need(registry['schema'] == 'gse-v52-cloud-baseline-registry-v1' and len(registry['baselines']) == 1,
         'release cloud registry')
    entry = registry['baselines'][0]; run = provenance['acceptanceRun']; jobs = provenance['acceptanceJobs']
    need(run['id'] == 40841038976 and run['run_attempt'] == 1 and run['conclusion'] == 'success' and
         run['event'] == 'workflow_dispatch' and run['head_branch'] == 'master' and
         run['head_sha'] == rules['acceptedVerifierSource'] == review['source']['source'], 'protected acceptance source/attempt')
    need(jobs['total_count'] == len(jobs['jobs']) == 1 and jobs['jobs'][0]['conclusion'] == 'success' and
         jobs['jobs'][0]['steps'] and all(s['conclusion'] == 'success' for s in jobs['jobs'][0]['steps']),
         'protected acceptance jobs/steps')
    chosen = {name: {k: v[k] for k in ('requestSha256', 'runId', 'runAttempt')}
              for name, v in waiver['originals'].items()}
    need(len(chosen) == 15 and review['selected'] == chosen and
         review['originalBindings'] == {k: v['binding'] for k, v in waiver['originals'].items()}, 'original cloud bindings')
    need(provenance['artifactPins'] == waiver['artifactPins'] and len(provenance['artifactPins']) == 5,
         'measured executable pins')
    need(review['status'] == 'PASS' and review['fullRemoteQualification'] is True and
         entry['releaseCandidateQualified'] is False and review['totals'] == entry['totals'], 'cloud acceptance scope')
    need(entry['exceptions'][1] == review['continuation'] and
         review['continuation']['waivedOriginal'] == chosen['experiment'] and
         review['continuation']['originalCompletionStatus'] == 'FAIL' and
         review['continuation']['originalLedgerRewritten'] is False, 'retention-only exception')
    spec = rules['runtimeSource']; inventory = runtime_inventory(root, spec)
    need(len(inventory) == spec['filesCount'] and digest(encoded(inventory)) == spec['inventorySha256'],
         'runtime/build source differs from accepted snapshot; evidence-impact review required')
    return dict(scope='registered compact evidence and unchanged runtime/build sources except exact project version lines; no raw replay',
                verification=entry['verification'], measuredSources=entry['measuredSources'],
                measuredSequences=entry['measuredSequences'], totals=entry['totals'],
                exceptions=entry['exceptions'], measuredArtifactPins=provenance['artifactPins'],
                runtimeSource=dict(filesCount=len(inventory), inventorySha256=digest(encoded(inventory))),
                candidateJarEqualityToCloudNotAsserted=True)

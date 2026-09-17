"""Bounded cloud documents, immutable run identity and exact resource inventory."""
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'docs/v5x/v5.0/phase6-runner-plan.json'
LIMIT = 128 << 20


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, maximum=4 << 20):
    path = Path(path)
    require(not path.is_symlink() and path.is_file() and path.stat().st_size <= maximum, 'invalid/oversized document')
    def unique(pairs):
        result = dict(pairs); require(len(result) == len(pairs), 'duplicate JSON key'); return result
    return json.loads(path.read_bytes(), object_pairs_hook=unique, parse_constant=lambda _: require(False, 'nonfinite JSON'))


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(value); require(len(raw) <= 16 << 20, 'document byte bound')
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def plan(path=PLAN):
    value = read(path)
    require(value['schema'] == 'gse-v50-cloud-runner-plan-v1' and value['stage'] == '6B' and
            value['measurementClaim'] == 'admission-probe-only' and value['paidProfiles'] == ['admission-probe'], 'runner plan scope')
    require((value['voters'], value['vcpusPerVoter'], value['bootDiskGiB'], value['dataDiskGiB']) == (3, 8, 50, 100), 'resource ceilings')
    require(value['maximumTopologySeconds'] == 5400 and value['cleanupReserveSeconds'] == 300 and
            value['maximumSequenceCostMicrousd'] == 100_000_000, 'time/cost ceilings')
    require(value['project'] == 'gse-benchmark' and value['zone'] == 'us-west4-a' and value['machineType'] == 'n2-standard-8', 'catalog selection')
    require(value['ref'] == 'refs/heads/master' and value['environment'] == 'cloud-benchmark' and
            value['workflow'] == '.github/workflows/v50-replication-evidence.yml', 'workflow boundary')
    require(value['imageId'].isdigit() and not '/' in value['image'] and
            re.fullmatch('[a-z0-9][a-z0-9.-]{2,61}[a-z0-9]', value['bucket']), 'image/bucket identity')
    require(sha((ROOT / value['workloadPlan']).read_bytes()) == value['workloadPlanSha256'], 'local workload plan drift')
    return value


def request(source, run_id, attempt, bundle_sha, nonce=None):
    require(re.fullmatch('[0-9a-f]{40}', source) and re.fullmatch('[0-9a-f]{64}', bundle_sha), 'source/bundle digest')
    require(re.fullmatch('[1-9][0-9]{0,19}', str(run_id)) and re.fullmatch('[1-9][0-9]{0,3}', str(attempt)), 'run identity')
    nonce = nonce or uuid.uuid4().hex[:12]
    require(re.fullmatch('[0-9a-f]{12}', nonce), 'run nonce')
    return dict(source=source, runId=str(run_id), attempt=str(attempt), nonce=nonce,
                bundleSha256=bundle_sha, profile='admission-probe', owner='gse-v50-' + nonce,
                createdAt=int(time.time()))


def resources(p, r):
    prefix = r['owner']
    rows = []
    for suffix, mode in [('peer', 'peer'), ('deny-replication', 'deny-replication'), ('iap', 'iap'), ('deny-ssh', 'deny-ssh')]:
        rows.append(dict(kind='firewalls', name=prefix + '-' + suffix, purpose=mode))
    for node in range(1, 4):
        for kind, size in [('boot', p['bootDiskGiB']), ('data', p['dataDiskGiB'])]:
            rows.append(dict(kind='disks', name=f'{prefix}-n{node}-{kind}', purpose=kind, node=node, sizeGiB=size))
    for node in range(1, 4):
        rows.append(dict(kind='instances', name=f'{prefix}-n{node}', purpose='voter', node=node))
    return rows


def replacement_resource(p, r, node):
    from .cloud_presets import validate_request
    require(node in validate_request(r)['replacementNodes'], 'replacement outside preset')
    return dict(kind='disks', name=f"{r['owner']}-n{node}-data-g2", purpose='data', node=node,
                sizeGiB=p['dataDiskGiB'], generation=2, replaces=f"{r['owner']}-n{node}-data")


def validate_inventory(p, r, rows):
    """Closed initial inventory plus an ordered prefix of reviewed disk generations."""
    expected = resources(p, r)
    if r['profile'] != 'admission-probe':
        from .cloud_presets import validate_request
        allowed = validate_request(r)['replacementNodes']
        count = len(rows) - len(expected)
        require(0 <= count <= len(allowed), 'replacement inventory count')
        expected += [replacement_resource(p, r, node) for node in allowed[:count]]
    require(len(rows) == len(expected) and
            [{k: row.get(k) for k in item} for row, item in zip(rows, expected)] == expected,
            'cleanup inventory scope')
    return expected


def deletion_order(rows):
    # Appended replacement disks come after VMs in the journal, but are still
    # attached to those VMs. Always delete instances before any disk generation.
    return sorted(reversed(rows), key=lambda row: {'instances': 0, 'disks': 1, 'firewalls': 2}[row['kind']])


def prefix(p, r):
    return '/'.join((p['evidencePrefix'], r['source'], r['runId'] + '-' + r['attempt'] + '-' + r['nonce']))


def inventory(root):
    result = {}; total = 0
    for path in sorted(Path(root).rglob('*')):
        require(not path.is_symlink(), 'evidence symlink')
        if not path.is_file(): continue
        size = path.stat().st_size; total += size
        require(size <= 32 << 20 and total <= LIMIT and len(result) < 2000, 'evidence size/count')
        result[str(path.relative_to(root))] = dict(bytes=size, sha256=sha(path.read_bytes()))
    return result

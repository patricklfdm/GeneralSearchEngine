"""Offline replay of a pinned native four-cell experiment archive.

Caller-supplied pins must come from the original Actions run/artifact. This does
not fetch provenance, re-admit an expired request, or inspect live cloud state.
"""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import stat
import zipfile

from . import cloud_native_authority as n, cloud_runner_admission as admission
from . import guest_experiment_evidence as evidence, performance_model as m
from . import remote_collection as parts, remote_command as c
from .guest_owned_experiment import CELLS, SCOPE

PREFIX = 'execution/workload/retained/'
CONTROL = ('receipt.json', 'execution/receipt.json', 'approval.json',
           'handoff/prepared/plan.json', 'execution/preparation/resources/receipt.json')
FLAGS = dict(paidCloud=False, paidAdmission=False, fullRemoteQualification=False,
             liveCloudStateChecked=False, artifactProvenanceFetched=False)


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            result.update(block)
    return result.hexdigest()


def extract(archive, target, expected_sha):
    """Check the whole ZIP inventory, then retain only receipts and binary parts."""
    m.need(re.fullmatch('[0-9a-f]{64}', expected_sha), 'archive pin')
    c.directory(archive.parent)
    m.need(not archive.is_symlink() and archive.is_file() and
           archive.stat().st_size <= parts.LIMITS['expandedBytes'], 'archive size/type')
    m.need(digest(archive) == expected_sha, 'archive digest')
    with zipfile.ZipFile(archive) as source:
        rows = source.infolist(); names = [row.filename for row in rows]
        m.need(len(rows) <= parts.LIMITS['files'] and len(names) == len(set(names)), 'ZIP inventory count/duplicates')
        m.need(sum(row.file_size for row in rows) <= parts.LIMITS['expandedBytes'], 'ZIP expanded budget')
        for row in rows:
            name = row.filename[:-1] if row.is_dir() else row.filename
            m.need(row.orig_filename == row.filename and name not in ('', '.'), 'ZIP member name')
            parts.safe_name(name)
            kind = stat.S_IFMT(row.external_attr >> 16)
            m.need(kind in (0, stat.S_IFDIR if row.is_dir() else stat.S_IFREG) and not row.flag_bits & 1,
                   'ZIP special/encrypted member')
        wanted = [name for name in names if name in CONTROL or name.startswith(PREFIX) and not name.endswith('/')]
        m.need(set(CONTROL) <= set(wanted) and PREFIX+'parts.json' in wanted, 'archive review inputs')
        for name in wanted:
            row = source.getinfo(name)
            limit = parts.LIMITS['partBytes'] if name.startswith(PREFIX) and name.endswith('.bin') else c.RESPONSE_BYTES
            m.need(not row.is_dir() and row.file_size <= limit, 'review member budget')
            if name.startswith(PREFIX):
                m.need(re.fullmatch(r'(parts\.json|part-[0-9]{4}\.bin)', name[len(PREFIX):]), 'unexpected retained part')
            path = target/name; path.parent.mkdir(parents=True, exist_ok=True)
            with source.open(row) as src, path.open('xb') as dst:
                shutil.copyfileobj(src, dst, 1 << 20)


def budget(value, timing):
    """Recompute disjoint accounting instead of trusting recorded PASS booleans."""
    limits = timing['limitsSeconds']; spent = dict.fromkeys(limits, 0)
    rows = value['intervals']; m.need(rows, 'missing budget intervals')
    start = previous = rows[0]['startNanos']; stages = []
    for row in rows:
        name = row['category']; begin, end, elapsed = (row[k] for k in ('startNanos', 'endNanos', 'elapsedNanos'))
        m.need(name in spent and all(type(v) is int and v >= 0 for v in (begin, end, elapsed)) and
               begin == previous and end >= begin and elapsed == end-begin, 'budget interval arithmetic')
        spent[name] += elapsed; previous = end
        m.need(row['withinBudget'] is True and spent[name] <= limits[name]*10**9 and
               end-start <= timing['leaseSeconds']*10**9, 'budget limit')
        if name != 'control': stages.append(name)
    m.need(stages == ['preparation', *CELLS, 'validation-retention', 'cleanup'], 'budget stage coverage/order')
    m.need(value['clock'] == 'controller-monotonic' and value['status'] == 'PASS' and
           all(type(v) is int for v in value['spentNanos'].values()) and type(value['elapsedNanos']) is int and
           value['spentNanos'] == spent and value['elapsedNanos'] == previous-start == sum(spent.values()),
           'budget totals')


def metadata(root, *, source, run, attempt, request_sha):
    plan = c.read(root/'handoff/prepared/plan.json'); req = plan['resourcePlan']['request']
    # Historical validation uses original creation time. The result grants no
    # current admission, regardless of whether the approval has since expired.
    plan_sha = admission.approval(plan, c.read(root/'approval.json'),
                                  m.sha(m.canonical(plan)), req['createdAt'])
    wrapper = c.read(root/'receipt.json'); result = c.read(root/'execution/receipt.json')
    bound = wrapper['binding']
    m.need(wrapper['schema'] == 'gse-v51-runner-experiment-entry-v1' and wrapper['mode'] == 'run' and
           wrapper['status'] == 'PASS' and wrapper['source'] == source == req['source'] == plan['artifacts']['source'] and
           wrapper['planSha256'] == plan_sha and wrapper['result'] == result, 'Runner completion binding')
    m.need((bound['runId'], bound['runAttempt'], bound['source'], bound['event'], bound['workflow'], bound['role']) ==
           (run, attempt, source, 'workflow_dispatch', '.github/workflows/v51-replication-evidence.yml', 'runner'),
           'Runner run binding')
    m.need(n.validate_request(req) == request_sha == result['requestSha256'], 'request binding')
    for value in (wrapper, result):
        m.need(value['paidCloud'] is True and value['engineWorkloadExecuted'] is True and
               value['fullRemoteQualification'] is False, 'native experiment scope')
    m.need(result['schema'] == n.COMPLETION_SCHEMA and result['execution'] == n.EXECUTION and
           result['status'] == 'PASS' and result['errors'] == [] and result['qualificationScope'] == SCOPE and
           result['retention'] == 'VERIFIED' and result['leaseReleased'] is True, 'native completion status')
    recorded = result['evidence']
    m.need(recorded['status'] == 'PASS' and recorded['scope'] == SCOPE and recorded['errors'] == [] and
           recorded['physicalHistoryQualified'] is True and recorded['backupRestoreQualified'] is True and
           m.sha(m.canonical(recorded)) == result['evidenceSha256'], 'recorded evidence binding')
    resources = c.read(root/'execution/preparation/resources/receipt.json')
    m.need(resources['requestSha256'] == request_sha and resources['status'] == 'RESOURCES_PREPARED' and
           [r['spec'] for r in resources['resources']] == n.resources(req), 'resource request inventory')
    expected = {}
    for row in resources['resources']:
        m.need(row['attempted'] is True and type(row['id']) is str and re.fullmatch('[1-9][0-9]*', row['id']), 'resource ID')
        expected[row['spec']['name']] = row['id']
    cleanup = result['cleanup']; checks = cleanup['checks']
    m.need(cleanup['status'] == 'PASS' and cleanup['errors'] == [] and cleanup['leftovers'] == [] and
           len(checks) == len(expected) and {r['name'] for r in checks} == set(expected) and
           all(r['expectedId'] == expected[r['name']] and r['absent'] is True and r['observed'] is None for r in checks),
           'cleanup exact-ID absence')
    for key in ('budgetBeforeCompletion', 'budget'): budget(result[key], plan['timing'])
    earlier = result['budgetBeforeCompletion']['intervals']; final = result['budget']['intervals']
    m.need(final[:len(earlier)] == earlier and all(r['category'] == 'control' for r in final[len(earlier):]),
           'completion budget changed')
    return plan, result


def review(archive, output, *, source, run, attempt, archive_sha, request_sha):
    m.need(re.fullmatch('[0-9a-f]{40}', source) and re.fullmatch('[0-9a-f]{64}', request_sha) and
           type(run) is int and run > 0 and type(attempt) is int and attempt > 0, 'review pins')
    archive = Path(archive).absolute(); output = Path(output).absolute()
    output.parent.mkdir(parents=True, exist_ok=True); c.directory(output.parent)
    output.mkdir(mode=0o700)  # A fresh directory preserves every prior review.
    base = dict(schema='gse-v51-native-experiment-review-v1', source=source, runId=run, runAttempt=attempt,
                archiveSha256=archive_sha, requestSha256=request_sha, scope='native-experiment-archive-review-only', **FLAGS)
    try:
        retained = output/'originals'; retained.mkdir()
        extract(archive, retained, archive_sha)
        plan, result = metadata(retained, source=source, run=run, attempt=attempt, request_sha=request_sha)
        binding = m.sha(m.canonical(dict(scope=SCOPE, requestSha256=request_sha)))
        raw = output/'raw'; unpacked = parts.unpack(retained/PREFIX, raw, binding)
        # unpack verifies this inventory against every byte. Retain it outside
        # the disposable replay root, whose validator reserves this filename.
        (raw/parts.INDEX).rename(output/parts.INDEX)
        m.need(c.read(raw/'plan.json')['request'] == plan['resourcePlan']['request'] and
               c.read(raw/'validation.json') == result['evidence'], 'packed evidence/request binding')
        for cell in CELLS:
            row = c.read(raw/(cell+'-timeline.json'))
            charged = next(r for r in result['budget']['intervals'] if r['category'] == cell)
            m.need(charged['startNanos'] <= row['startNanos'] < row['endNanos'] <= charged['endNanos'], 'cell charged interval')
        replay = evidence.validate(raw, output/'replay', authority=n)
        c.write_once(output/'aggregate.json', replay)
        m.need(replay == result['evidence']['aggregate'], 'independent aggregate differs')
        m.need(digest(archive) == archive_sha, 'archive changed during review')
        report = dict(base, status='PASS', ownedExperimentQualified=True, planSha256=m.sha(m.canonical(plan)),
                      evidenceSha256=result['evidenceSha256'], unpacked=unpacked,
                      recordedBudget=result['budget'], recordedCleanup=result['cleanup'])
    except Exception as exc:
        c.write_once(output/'review.json', dict(base, status='FAIL', ownedExperimentQualified=False,
                                              failure=dict(type=type(exc).__name__, message=str(exc))))
        raise
    c.write_once(output/'review.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', required=True); parser.add_argument('--run', type=int, required=True)
    parser.add_argument('--attempt', type=int, required=True); parser.add_argument('--archive-sha256', required=True)
    parser.add_argument('--request-sha256', required=True); args = parser.parse_args()
    result = review(args.archive, args.output, source=args.source, run=args.run, attempt=args.attempt,
                    archive_sha=args.archive_sha256, request_sha=args.request_sha256)
    print(m.canonical({k:v for k,v in result.items() if k not in ('recordedBudget', 'recordedCleanup')}).decode())


if __name__ == '__main__': main()

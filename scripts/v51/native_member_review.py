"""Offline native full-preset replay from an authenticated original Actions ZIP.

Pins and GitHub metadata are supplied by the caller. This tool never fetches
credentials, executes the measured workload or renews historical admission.
"""
import argparse
from pathlib import Path

from . import native_experiment_review as old, native_preset_timing as timing
from . import cloud_ci as ci, cloud_native_authority as n, performance_model as m
from . import remote_command as c, remote_collection as parts
from . import guest_canonical_evidence as canonical, guest_fault_evidence as faults
from . import guest_experiment_evidence as experiment

SCHEMA = 'gse-v51-native-member-review-v1'


def provenance(root, member):
    """Validate retained API metadata; authenticity still belongs to the caller."""
    run = c.read(root/'run.json'); jobs = c.read(root/'jobs.json')
    listing = c.read(root/'artifacts.json')
    m.need(run['run_attempt'] == 1 and run['head_branch'] == 'master' and
           run['event'] == 'workflow_dispatch' and run['status'] == 'completed' and
           run['conclusion'] == 'success' and run['repository']['full_name'] == ci.REPOSITORY and
           run['repository']['id'] == ci.REPOSITORY_ID and
           run['path'] == '.github/workflows/v51-replication-evidence.yml', 'member run provenance')
    m.need(jobs['total_count'] == len(jobs['jobs']) == 2 and
           {j['name'] for j in jobs['jobs']} == {'observations', 'Runner precheck and approved execution'} and
           all(j['run_id'] == run['id'] and j['run_attempt'] == 1 and j['head_sha'] == run['head_sha'] and
               j['conclusion'] == 'success' for j in jobs['jobs']), 'member jobs provenance')
    steps = [s for j in jobs['jobs'] for s in j['steps']]
    for name in ('Run exact approved native V5.1 experiment', 'Retain native experiment evidence including failures'):
        found = [s for s in steps if s['name'] == name]
        m.need(len(found) == 1 and found[0]['conclusion'] == 'success', 'member producing step')
    m.need(listing['total_count'] == len(listing['artifacts']) <= 100, 'member artifact inventory')
    found = [v for v in listing['artifacts'] if v['name'] == f"v51-experiment-{run['id']}-1"]
    m.need(len(found) == 1, 'member original artifact')
    artifact = found[0]; bound = artifact['workflow_run']
    m.need(bound['id'] == run['id'] and bound['head_sha'] == run['head_sha'] and bound['head_branch'] == 'master' and
           bound['repository_id'] == bound['head_repository_id'] == ci.REPOSITORY_ID and
           artifact['digest'].startswith('sha256:'), 'member artifact provenance')
    sha = artifact['digest'][7:]; n.a.digest(sha)
    archive = root/'experiment.zip'
    m.need(archive.stat().st_size == artifact['size_in_bytes'], 'member archive size')
    timing.selection(member)
    return run, artifact, sha


def replay(raw, output, member, *, progress=lambda row: None):
    if member.startswith('canonical-'):
        return canonical.validate(raw, output, authority=n, progress=progress)
    if member == 'failure-drill':
        return faults.validate(raw, output, cases=timing.allocation(member)['cells'],
                               scope='owned-complete-failure-drill', authority=n)
    return experiment.validate(raw, output, authority=n)


def review(root, output, member, *, request_sha, progress=lambda row: None):
    root = c.directory(root); output = Path(output).absolute()
    output.parent.mkdir(parents=True, exist_ok=True); c.directory(output.parent)
    output.mkdir(mode=0o700)
    base = dict(schema=SCHEMA, member=member, requestSha256=request_sha,
                scope='native-member-archive-review-only', **old.FLAGS)
    try:
        run, artifact, sha = provenance(root, member)
        base.update(source=run['head_sha'], runId=run['id'], runAttempt=1, artifactId=artifact['id'], archiveSha256=sha)
        original = output/'originals'; original.mkdir()
        old.extract(root/'experiment.zip', original, sha)
        plan, result = old.metadata(original, source=run['head_sha'], run=run['id'], attempt=1,
                                    request_sha=request_sha, member=member)
        req = plan['resourcePlan']['request']; allocation = timing.validate(req)
        scope = result['qualificationScope']; recorded = result['evidence']
        identity = dict(scope=scope, requestSha256=request_sha)
        if allocation['preset'] == 'canonical': identity['repetition'] = allocation['repetition']
        binding = m.sha(m.canonical(identity))
        raw = output/'raw'; unpacked = parts.unpack(original/old.PREFIX, raw, binding)
        (raw/parts.INDEX).rename(output/parts.INDEX)
        m.need(c.read(raw/'plan.json')['request'] == req and c.read(raw/'validation.json') == recorded,
               'member packed evidence binding')
        for cell in allocation['cells']:
            path = raw/cell/'receipt.json' if member == 'failure-drill' else raw/(cell+'-timeline.json')
            row = c.read(path); charged = next(v for v in result['budget']['intervals'] if v['category'] == cell)
            m.need(charged['startNanos'] <= row['startNanos'] < row['endNanos'] <= charged['endNanos'],
                   'member cell charged interval')
        aggregate = replay(raw, output/'replay', member, progress=progress)
        c.write_once(output/'aggregate.json', aggregate)
        m.need(aggregate == recorded['aggregate'], 'member independent aggregate differs')
        m.need(old.digest(root/'experiment.zip') == sha, 'member archive changed during review')
        report = dict(base, status='PASS', rawEvidenceReplayed=True, sequence=req['sequence'],
                      preparedRun=c.read(original/'receipt.json')['preparedRun'],
                      planSha256=m.sha(m.canonical(plan)), evidenceSha256=result['evidenceSha256'],
                      aggregateSha256=m.sha(m.canonical(aggregate)), unpacked=unpacked,
                      cells=allocation['cells'], stageSeconds={k:v/1e9 for k,v in result['budget']['spentNanos'].items()},
                      timingWarnings=result['budget'].get('warnings', []), retention=result['retention'],
                      cleanup=result['cleanup'], leaseReleased=result['leaseReleased'])
    except Exception as error:
        c.write_once(output/'review.json', dict(base, status='FAIL', rawEvidenceReplayed=False,
                                              failure=dict(type=type(error).__name__, message=str(error))))
        raise
    c.write_once(output/'review.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--member', choices=timing.MEMBERS, required=True)
    parser.add_argument('--request-sha256', required=True); args = parser.parse_args()
    result = review(args.input, args.output, args.member, request_sha=args.request_sha256,
                    progress=lambda row: print(m.canonical(row).decode(), flush=True))
    print(m.canonical({k:v for k,v in result.items() if k != 'cleanup'}).decode())


if __name__ == '__main__': main()

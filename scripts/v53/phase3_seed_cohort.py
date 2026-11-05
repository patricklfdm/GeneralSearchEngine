"""Reconcile all declared hosted seeds before expensive Phase 3 replay.

This offline gate executes no producer or workflow. Independent preparations
must have the same complete source, compiled bytes, tools and dependencies.
Reader sets may differ, but every reader byte must belong to that source.
A PARTIAL result is seed provenance only, never runtime/phase acceptance.
"""
import argparse
import importlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from . import phase3_qualification_plan as plan
from . import remove_process_hosted as shared

SCHEMA = 'gse-v53-phase3-seed-cohort-v1'
INDEX_SCHEMA = 'gse-v53-phase3-seed-set-v1'
COMMON_PINS = ('sourceSha256', 'buildSha256', 'toolchainSha256', 'repositorySha256')
CONTEXT_FIELDS = {'kind', 'repository', 'source', 'ref', 'event', 'run', 'attempt', 'workflow'}
ROOT, need, h = plan.ROOT, plan.need, shared.h
canonical = shared.m.gate.f.canonical


def adapters():
    return {name: importlib.import_module('.'+entry[2], __package__) for name, entry in plan.COHORTS.items()}


def unlinked(path):
    path = Path(path).absolute()
    need('..' not in path.parts, 'seed cohort parent traversal')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'seed cohort linked path')
    return path


def read_bytes(path):
    path = unlinked(path)
    need(path.is_file() and path.stat().st_nlink == 1 and 0 < path.stat().st_size <= 8*1024*1024,
         'seed cohort bounded regular JSON')
    raw = h.snapshot.s.regular(path, 8*1024*1024)
    need(raw, 'seed cohort empty JSON')
    return raw


def read(path):
    return plan.decode(read_bytes(path))


def context(value, adapter, source):
    need(type(value) is dict and set(value) == CONTEXT_FIELDS, 'seed cohort exact context fields')
    need(value['kind'] == 'github' and value['repository'] == 'patricklfdm/GeneralSearchEngine' and
         value['workflow'] == adapter.WORKFLOW and value['source'] == source, 'seed cohort context identity')
    ref = value['ref']
    need(type(ref) is str and re.fullmatch(r'refs/heads/[A-Za-z0-9_./-]+', ref) and
         '..' not in ref and not ref.endswith(('/', '.', '.lock')) and
         (value['event'] == 'workflow_dispatch' or value['event'] == 'push' and ref == adapter.BRANCH),
         'seed cohort event/ref')
    need(all(type(value[k]) is str and re.fullmatch('[1-9][0-9]{0,19}', value[k]) for k in ('run', 'attempt')),
         'seed cohort run/attempt')


def validate_index(value, modules):
    need(type(value) is dict and set(value) == {'schema', 'source', 'cohorts'} and value['schema'] == INDEX_SCHEMA,
         'seed cohort index envelope')
    source = value['source']
    need(type(source) is str and re.fullmatch('[0-9a-f]{40}', source), 'seed cohort source SHA')
    need(type(value['cohorts']) is dict and set(value['cohorts']) == set(modules), 'seed cohort complete subset inventory')
    runs = set()
    for name, adapter in modules.items():
        ctx = value['cohorts'][name]; context(ctx, adapter, source)
        need(ctx['run'] not in runs, 'seed cohort duplicate workflow run')
        runs.add(ctx['run'])
    return source


def checkout_source(source):
    """Read actual Git blobs, not a claimed HEAD or a subset of source paths."""
    def git(*args, **options):
        return subprocess.check_output(['git', *args], cwd=ROOT, **options)
    need(git('rev-parse', 'HEAD').decode().strip() == source, 'seed cohort reader checkout')
    need(not git('status', '--porcelain=v1', '--untracked-files=normal'), 'seed cohort dirty checkout')
    entries = []; total = 0
    for row in git('ls-tree', '-rlz', '--full-tree', source).split(b'\0'):
        if not row: continue
        metadata, name = row.split(b'\t', 1); mode, kind, oid, size = metadata.split()
        need(mode in (b'100644', b'100755') and kind == b'blob', 'seed cohort nonregular Git source')
        size = int(size); total += size
        need(0 <= size <= 64*1024*1024 and total <= 256*1024*1024 and len(entries) < 20000,
             'seed cohort Git source capacity')
        entries.append((name.decode(), oid, size))
    need(entries, 'seed cohort empty Git source')
    raw = git('cat-file', '--batch', input=b''.join(oid+b'\n' for _, oid, _ in entries))
    stream = io.BytesIO(raw); files = {}
    for name, oid, size in entries:
        need(stream.readline() == oid+b' blob '+str(size).encode()+b'\n', 'seed cohort Git object header')
        body = stream.read(size)
        need(len(body) == size and stream.read(1) == b'\n', 'seed cohort Git object length')
        files[name] = h.digest(body)
    need(not stream.read(1), 'seed cohort Git object trailing bytes')
    return dict(head=source, files=files)


def bundle_identity(directory):
    directory = unlinked(directory)
    need(directory.is_dir() and {p.name for p in directory.iterdir()} == {'manifest.json', 'bundle.tar.gz'},
         'seed cohort exact artifact files')
    archive = unlinked(directory/'bundle.tar.gz')
    need(archive.is_file() and archive.stat().st_nlink == 1 and 0 < archive.stat().st_size <= shared.MAX_BYTES,
         'seed cohort archive capacity/type')
    raw = read_bytes(directory/'manifest.json'); manifest = plan.decode(raw)
    need(type(manifest) is dict, 'seed cohort artifact manifest')
    sha = shared.tc.file_hash(archive)
    need(manifest.get('archiveSha256') == sha, 'seed cohort archive digest')
    return dict(manifestSha256=h.digest(raw), archiveSha256=sha)


def preparation(data, value):
    """Require the retained prepare test, not only the seed's PARTIAL label."""
    execution = value.get('preparationExecution')
    need(type(execution) is dict and set(execution) == {'exit', 'elapsedSeconds'} and
         type(execution['exit']) is int and execution['exit'] == 0 and
         type(execution['elapsedSeconds']) in (int, float) and math.isfinite(execution['elapsedSeconds']) and
         execution['elapsedSeconds'] >= 0, 'seed cohort preparation execution')
    reports = list((data/'producer/workspace'/h.MODULE/'target/surefire-reports').glob('TEST-*.xml'))
    need(len(reports) == 1, 'seed cohort preparation exact report')
    raw = h.snapshot.s.regular(reports[0], 8*1024*1024); suite = ET.fromstring(raw)
    cls = 'io.github.patricklfdm.generalsearch.replication.V53BallotAllocatorTest'
    cases = suite.findall('testcase')
    need(suite.tag == 'testsuite' and suite.get('name') == cls and cases and
         suite.get('tests') == str(len(cases)) and all(suite.get(k) == '0' for k in ('failures', 'errors', 'skipped')) and
         all(row.get('classname') == cls and row.get('name') for row in cases) and
         not any(row.tag in {'failure', 'error', 'skipped', 'flakyFailure', 'flakyError', 'rerunFailure', 'rerunError'}
                 for row in suite.iter()), 'seed cohort preparation unretried test')
    return dict(reportSha256=h.digest(raw), tests=len(cases), execution=execution), raw


def inspect_seed(name, adapter, bundle, output, ctx, source):
    """Reuse the owning reader; retain small manifests, discard only our scratch."""
    before = bundle_identity(bundle)
    with tempfile.TemporaryDirectory(prefix='unpack-', dir=output) as temporary:
        data, manifest = adapter.unpack(bundle, Path(temporary)/'original', ctx, 'seed')
        # Duplicate-key rejection also covers JSON read by legacy adapters.
        for filename in ('seed.json', 'producer/source.json', 'producer/build.json', 'producer/toolchain.json'):
            read(data/filename)
        value = adapter.seed_inputs(data, ctx)
        prepared, report = preparation(data, value)
        need(read(data/'producer/source.json') == source, 'seed cohort incomplete/different Git source: '+name)
        shared.tc.validate(read(data/'producer/toolchain.json'))
        reader = value['reader']
        need(type(reader) is dict and set(reader) == {'files', 'sha256'} and type(reader['files']) is dict and
             reader['files'] and reader['sha256'] == value['readerSha256'] == h.digest(canonical(reader['files'])),
             'seed cohort reader manifest digest')
        need(all(source['files'].get(k) == v for k, v in reader['files'].items()), 'seed cohort reader/source binding')
        pins = {key: value[key] for key in COMMON_PINS}
        need(all(type(v) is str and re.fullmatch('[0-9a-f]{64}', v) for v in pins.values()), 'seed cohort common pins')
        need(h.inventory(data, maximum=shared.MAX_BYTES) == manifest['inventory'], 'seed cohort extracted inputs changed')
        kept = output/name; kept.mkdir()
        for filename in ('seed.json', 'producer/source.json', 'producer/build.json', 'producer/toolchain.json'):
            (kept/Path(filename).name).write_bytes((data/filename).read_bytes())
        (kept/'preparation.xml').write_bytes(report)
        result = dict(context=ctx, artifactName=adapter.artifact_name(ctx, 'seed'), **before, **pins,
                      readerSha256=reader['sha256'], readerFiles=reader['files'], preparation=prepared)
    need(bundle_identity(bundle) == before, 'seed cohort bundle changed during inspection')
    return result


def run(index, inputs, output):
    index, inputs, output = unlinked(index), unlinked(inputs), unlinked(output)
    need(not output.is_relative_to(inputs) and not inputs.is_relative_to(output) and
         not index.is_relative_to(output), 'seed cohort output overlaps inputs')
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema=SCHEMA, status='FAIL', execution='offline-seed-provenance-only', phase3Complete=False,
                   runtimeQualified=False, workflowExecutionAttested=False, seedCohortVerified=False,
                   historiesReplayed=0, seeds={})
    try:
        raw = read_bytes(index); value = plan.decode(raw); modules = adapters(); source_sha = validate_index(value, modules)
        index_sha = h.digest(raw); (output/'index.json').write_bytes(raw)
        need(inputs.is_dir() and {p.name for p in inputs.iterdir()} == set(modules), 'seed cohort complete artifact inventory')
        source = checkout_source(source_sha); catalogs = plan.catalogues(); common = None; readers = {}
        for name, adapter in modules.items():
            member = inspect_seed(name, adapter, inputs/name, output, value['cohorts'][name], source)
            pins = {k: member[k] for k in COMMON_PINS}
            if common is None: common = pins
            need(pins == common, 'seed cohort mixed source/build/tools/dependencies: '+name)
            for path, sha in member['readerFiles'].items():
                need(path not in readers or readers[path] == sha, 'seed cohort conflicting reader')
                readers[path] = sha
            receipt['seeds'][name] = member
            h.save(output/'receipt.json', receipt)
        # Recheck original archives after the whole collection, not only each visit.
        for name, member in receipt['seeds'].items():
            need(bundle_identity(inputs/name) == {k: member[k] for k in ('manifestSha256', 'archiveSha256')},
                 'seed cohort input changed after inspection')
        need({p.name for p in inputs.iterdir()} == set(modules), 'seed cohort changed artifact inventory')
        need(h.digest(read_bytes(index)) == index_sha and checkout_source(source_sha) == source,
             'seed cohort index/checkout changed')
        receipt.update(status='PARTIAL', seedCohortVerified=True, source=source_sha, indexSha256=index_sha,
                       commonPins=common, readerUnionSha256=h.digest(plan.encoded(readers)),
                       subsets=len(modules), plannedHostedHistories=sum(v['members'] for v in catalogs.values()),
                       cataloguesSha256=h.digest(plan.encoded(catalogs)))
    except BaseException as error:
        receipt.update(failure=dict(type=type(error).__name__, message=str(error))); raise
    finally:
        h.save(output/'receipt.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', required=True); parser.add_argument('--inputs', required=True)
    parser.add_argument('--output', required=True); args = parser.parse_args()
    with shared.progress('phase3-seed-provenance', 'all-declared-subsets'):
        result = run(args.index, args.inputs, args.output)
    print(json.dumps({k: result[k] for k in ('status', 'seedCohortVerified', 'subsets', 'plannedHostedHistories',
                                             'historiesReplayed', 'phase3Complete')}, sort_keys=True))


if __name__ == '__main__': main()

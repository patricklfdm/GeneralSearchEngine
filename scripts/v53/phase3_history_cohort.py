"""Offline original-first replay of every declared Phase 3 hosted history.

This consumes retained seeds and raw artifacts, never downloaded PASS receipts.
Each owning verifier and aggregate keeps its exact negative/physical contract.
Even a complete replay is PARTIAL: workflow execution, frozen coverage and the
simultaneous resource maximum are separate obligations.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from . import phase3_seed_cohort as seeds
from . import phase3_witness_observations as witnesses

SCHEMA = 'gse-v53-phase3-history-cohort-v1'
plan, shared, need, h = seeds.plan, seeds.shared, seeds.need, seeds.h


def groups(name, adapter, catalog):
    if name in ('joining-process', 'transfer-histories', 'automatic-histories'):
        return {key: tuple(value) for key, value in adapter.SHARDS.items()}
    return {case: (case,) for case in catalog['cases']}


def exact_directory(path, names):
    path = seeds.unlinked(path)
    need(path.is_dir() and {p.name for p in path.iterdir()} == set(names),
         'history cohort exact artifact inventory: '+str(path))


def raw_inventory(inputs, index, modules, catalogs):
    """Bind every original before replay, including every grouped child archive."""
    exact_directory(inputs, modules)
    result = {}; archives = set()
    for name, adapter in modules.items():
        ctx = index['cohorts'][name]; selected = groups(name, adapter, catalogs[name])
        directory = inputs/name
        exact_directory(directory, [adapter.artifact_name(ctx, 'raw', key) for key in selected])
        for key, cases in selected.items():
            group = directory/adapter.artifact_name(ctx, 'raw', key)
            if name == 'joining-process':
                exact_directory(group, [adapter.m.slug(case) for case in cases])
                bundles = [(case, group/adapter.m.slug(case)) for case in cases]
            else: bundles = [(key, group)]
            for case, bundle in bundles:
                identity = seeds.bundle_identity(bundle)
                manifest = seeds.read(bundle/'manifest.json')
                need(manifest.get('schema') == adapter.SCHEMA and manifest.get('context') == ctx and
                     manifest.get('kind') == 'raw' and manifest.get('case') == case,
                     'history cohort original context/case binding')
                need(identity['archiveSha256'] not in archives, 'history cohort duplicate original archive')
                archives.add(identity['archiveSha256'])
                result[bundle.relative_to(inputs).as_posix()] = identity
    return result


def retained_call(output, action):
    """Retain diagnostics, prune only our successful extraction, keep failures."""
    output.mkdir(parents=True, exist_ok=False)
    scratch = Path(tempfile.mkdtemp(prefix='scratch-', dir=output)); work = scratch/'replay'
    try:
        result = action(work)
        need(seeds.read(work/'receipt.json') == result, 'history cohort retained reader result')
        # Only reader diagnostics outside the extracted seed/raw trees are copied.
        # Joining groups also retain one child receipt/progress stream per original.
        for path in sorted(work.glob('*')):
            selected = [path] if path.is_file() else [path/'receipt.json', path/'progress.jsonl']
            if path.name in ('seed', 'original', 'data'): continue
            for item in selected:
                if item.name not in ('receipt.json', 'progress.jsonl') or not item.exists(): continue
                seeds.unlinked(item)
                need(item.is_file() and item.stat().st_nlink == 1, 'history cohort diagnostic regular file')
                raw = h.snapshot.s.regular(item, 8*1024*1024)
                target = output/item.relative_to(work); target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
        need((output/'receipt.json').is_file(), 'history cohort missing retained receipt')
        shutil.rmtree(scratch)
        return result
    except BaseException as error:
        h.save(output/'failure.json', dict(status='FAIL', failure=dict(type=type(error).__name__, message=str(error)),
                                          retainedScratch=scratch.name))
        raise


def replay_group(name, adapter, seed_bundle, raw, output, key, ctx):
    if name == 'joining-process':
        return retained_call(output, lambda work: adapter.group(seed_bundle, work, key, ctx, inputs=raw))
    return retained_call(output, lambda work: adapter.verify(seed_bundle, raw, work, key, ctx))


def run(index, seed_inputs, inputs, output):
    index, seed_inputs, inputs, output = map(seeds.unlinked, (index, seed_inputs, inputs, output))
    need(all(not output.is_relative_to(p) and not p.is_relative_to(output) for p in (seed_inputs, inputs)) and
         not index.is_relative_to(output), 'history cohort output overlaps inputs')
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema=SCHEMA, status='FAIL', execution='offline-original-history-replay',
                   phase3Complete=False, runtimeQualified=False, workflowExecutionAttested=False,
                   frozenScenarioCoverageQualified=False, combinedPeakResourcesQualified=False,
                   allDeclaredHistoriesReplayed=False, historiesReplayed=0, groupsReplayed=0, cohorts={})
    try:
        index_raw = seeds.read_bytes(index); value = plan.decode(index_raw); modules = seeds.adapters()
        source_sha = seeds.validate_index(value, modules); catalogs = plan.catalogues()
        source = seeds.checkout_source(source_sha)
        witness_bytes, witness_plan = witnesses.prepare(); observed_witnesses = []
        (output/'coverage-plan.json').write_bytes(witness_bytes)
        (output/'index.json').write_bytes(index_raw)
        original = raw_inventory(inputs, value, modules, catalogs)
        h.save(output/'raw-inventory.json', original)
        seed_receipt = seeds.run(index, seed_inputs, output/'seeds')
        need(seed_receipt['seedCohortVerified'] is True and seed_receipt['source'] == source_sha and
             seed_receipt['indexSha256'] == h.digest(index_raw), 'history cohort seed provenance')
        receipt.update(source=source_sha, indexSha256=h.digest(index_raw),
                       cataloguesSha256=h.digest(plan.encoded(catalogs)),
                       rawInventorySha256=h.digest(plan.encoded(original)), rawArchives=len(original),
                       seedReceiptSha256=shared.tc.file_hash(output/'seeds/receipt.json'))
        for name, adapter in modules.items():
            ctx = value['cohorts'][name]; selected = groups(name, adapter, catalogs[name])
            cohort_output = output/name; cohort_output.mkdir(); verified = cohort_output/'verified'; verified.mkdir()
            for key, cases in selected.items():
                receipt['active'] = dict(cohort=name, group=key, stage='original-first-replay')
                h.save(output/'receipt.json', receipt)
                print(json.dumps(dict(receipt['active'], completed=receipt['groupsReplayed'])), flush=True)
                raw = inputs/name/adapter.artifact_name(ctx, 'raw', key)
                with shared.progress('phase3-original-first-replay', name+'/'+key):
                    result = replay_group(name, adapter, seed_inputs/name, raw, cohort_output/'groups'/key, key, ctx)
                need(result.get('status') == 'PARTIAL' and result.get('phase3Complete') is False,
                     'history cohort owning verifier scope')
                observed_witnesses.extend(witnesses.observe_group(witness_plan, name, key, result, adapter, ctx, original))
                h.save(output/'witness-observations.json', observed_witnesses)
                artifact = verified/adapter.artifact_name(ctx, 'verified', key); artifact.mkdir()
                h.save(artifact/'receipt.json', result)
                receipt['groupsReplayed'] += 1
                h.save(output/'receipt.json', receipt)
            receipt['active'] = dict(cohort=name, stage='owning-aggregate'); h.save(output/'receipt.json', receipt)
            result = retained_call(cohort_output/'aggregate', lambda work: adapter.aggregate(
                seed_inputs/name, verified, work, ctx, None, None, offline_replay=True))
            need(result.get('status') == 'PARTIAL' and result.get('offlineEvidenceOnly') is True and
                 result.get('workflowExecutionAttested') is False and result.get('phase3Complete') is False and
                 result.get('wholeHistories', result.get('wholeOwnershipHistories')) == catalogs[name]['members'],
                 'history cohort owning aggregate scope/count')
            receipt['cohorts'][name] = dict(histories=catalogs[name]['members'], groups=len(selected),
                aggregateReceiptSha256=shared.tc.file_hash(cohort_output/'aggregate/receipt.json'))
            receipt['historiesReplayed'] += catalogs[name]['members']; h.save(output/'receipt.json', receipt)
        # Verify every original again after the final reader, including old seeds.
        need(raw_inventory(inputs, value, modules, catalogs) == original, 'history cohort originals changed during replay')
        exact_directory(seed_inputs, modules)
        for name, member in seed_receipt['seeds'].items():
            need(seeds.bundle_identity(seed_inputs/name) == {k:member[k] for k in ('manifestSha256', 'archiveSha256')},
                 'history cohort seed changed during replay')
        need(seeds.read_bytes(index) == index_raw and seeds.checkout_source(source_sha) == source,
             'history cohort index/checkout changed during replay')
        need(plan.catalogues() == catalogs and receipt['historiesReplayed'] == sum(v['members'] for v in catalogs.values()),
             'history cohort complete unchanged catalogues')
        need(witnesses.prepare() == (witness_bytes, witness_plan), 'history cohort witness plan changed during replay')
        coverage = witnesses.finish(witness_plan, observed_witnesses); h.save(output/'coverage.json', coverage)
        receipt['candidateWitnesses'] = dict(path='coverage.json', sha256=shared.tc.file_hash(output/'coverage.json'),
            rejected=coverage['rejected'], notApplicable=coverage['notApplicable'], phase3Complete=False)
        receipt.pop('active', None)
        receipt.update(status='PARTIAL', allDeclaredHistoriesReplayed=True,
                       acceptanceAuthority='all declared original histories replayed; workflow, coverage and resource closure remain separate')
    except BaseException as error:
        receipt.update(failure=dict(type=type(error).__name__, message=str(error))); raise
    finally: h.save(output/'receipt.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('index', 'seeds', 'inputs', 'output'): parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    with shared.progress('phase3-history-cohort', 'all-declared-originals'):
        result = run(args.index, args.seeds, args.inputs, args.output)
    print(json.dumps({k:result[k] for k in ('status', 'historiesReplayed', 'groupsReplayed', 'phase3Complete')}, sort_keys=True))


if __name__ == '__main__': main()

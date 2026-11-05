"""120 groups of three whole joining histories and independent downloaded replay.

Grouping only amortizes runner setup; each history retains its own original
producer and artifact. The exact 360-case set, not a successful group, qualifies.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

from . import joining_process_matrix as m
from . import remove_process_hosted as shared

h, need, tc, pins = m.h, m.need, shared.tc, shared.pins
WORKFLOW = '.github/workflows/v53-joining-process.yml'
BRANCH = 'refs/heads/experiment/v53-joining-process'
SCHEMA = 'gse-v53-joining-process-hosted-v1'
GROUP_SIZE = 3
SHARDS = {f'group-{i//GROUP_SIZE+1:03}': tuple(m.KINDS[i:i+GROUP_SIZE]) for i in range(0, len(m.KINDS), GROUP_SIZE)}


def selected(shard):
    need(type(shard) is str and shard in SHARDS, 'joining hosted declared group')
    return SHARDS[shard]


def context(): return shared.context(workflow=WORKFLOW, branch=BRANCH)


def artifact_name(ctx, kind, shard=None):
    if shard is not None: selected(shard)
    return 'v53-joining-process-'+kind+'-'+ctx['run']+'-'+ctx['attempt']+'-'+ctx['source']+('-'+shard if shard else '')


def pack(root, output, ctx, kind, case=None): return shared.pack(root, output, ctx, kind, case, schema=SCHEMA)


def unpack(bundle, output, ctx, kind, case=None):
    bundle = Path(bundle)
    need(bundle.is_dir() and not bundle.is_symlink() and {p.name for p in bundle.iterdir()} == {'manifest.json','bundle.tar.gz'},
         'joining hosted artifact directory')
    return shared.unpack(bundle, output, ctx, kind, case, schema=SCHEMA)


def seed_inputs(data, ctx):
    value = m.read(data/'seed.json')
    need(value.get('schema') == SCHEMA and value.get('context') == ctx and value.get('status') == 'PARTIAL' and
         value.get('phase3Complete') is False and value.get('cases') == list(m.KINDS) and
         value.get('groups') == {k:list(v) for k,v in SHARDS.items()}, 'joining hosted seed scope')
    m.check_pins(*pins(value)); source, _ = h.read_recorded_source(data/'producer')
    need(source['head'] == ctx['source'] and h.digest((data/'producer/source.json').read_bytes()) == value['sourceSha256'],
         'joining hosted seed source')
    build = m.read(data/'producer/build.json')
    need(type(build) is dict and set(build) == set(m.BUILDS) and
         h.digest((data/'producer/build.json').read_bytes()) == value['buildSha256'], 'joining hosted seed build')
    for name in m.BUILDS: need(h.inventory(data/'producer/workspace'/name) == build[name], 'joining hosted seed classes')
    tc.validate(m.read(data/'producer/toolchain.json'))
    need(tc.pin((data/'producer/toolchain.json').read_bytes()) == value['toolchainSha256'] and
         m.reader_manifest() == value.get('reader'), 'joining hosted seed tools/reader')
    need(all(source['files'].get(k) == v for k,v in value['reader']['files'].items()), 'joining hosted reader differs from producer source')
    need(shared.dependencies(data/'repository') == value['repositorySha256'], 'joining hosted seed dependencies')
    return value


def prepare(output, maven, ctx):
    output = Path(output); output.mkdir(parents=True, exist_ok=False); data = output/'data'; data.mkdir()
    receipt = dict(schema=SCHEMA, context=ctx, status='FAIL', phase3Complete=False)
    try:
        prepared = shared.prepare_source(data, maven, ctx); reader = m.reader_manifest()
        receipt.update(status='PARTIAL', cases=list(m.KINDS), groups={k:list(v) for k,v in SHARDS.items()},
                       readerSha256=reader['sha256'], reader=reader, **prepared)
        h.save(data/'seed.json', receipt); seed_inputs(data, ctx); pack(data, output/'artifact', ctx, 'seed')
    except BaseException as error:
        receipt.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error))); raise
    finally: h.save(output/'receipt.json', receipt)
    return receipt


def execute_member(seed_root, seed, manifest, output, archive, maven, case, ctx):
    output.mkdir(parents=True, exist_ok=False); data = output/'data'; data.mkdir()
    receipt = dict(schema=SCHEMA, context=ctx, case=case, status='FAIL', phase3Complete=False)
    try:
        repository = output/'repository'; shutil.copytree(seed_root/'repository', repository)
        with shared.repository_env(repository):
            need(tc.pin(m.gate.f.canonical(tc.capture(maven, h.ROOT))) == seed['toolchainSha256'], 'joining hosted worker toolchain')
            m.run.run(data/'producer', maven, case, source_from=seed_root/'producer')
        need(shared.dependencies(repository) == seed['repositorySha256'], 'joining hosted runtime dependency drift')
        original = m.member(data/'producer', case, *pins(seed)); seed_inputs(seed_root, ctx)
        receipt.update(status='PARTIAL', seedArchiveSha256=manifest['archiveSha256'],
                       producerReceiptSha256=original['receiptSha256'], originalPlanSha256=original['plan'],
                       **{name+'Sha256': value for name,value in zip(('source','build','toolchain','reader'), pins(seed))})
    except BaseException as error:
        receipt.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error))); raise
    finally:
        h.save(data/'hosted-member.json', receipt); h.save(output/'receipt.json', receipt)
        failing = sys.exc_info()[0] is not None
        try: pack(data, archive, ctx, 'raw', case)
        except BaseException as error:
            receipt.update(status='FAIL', artifactFailure=dict(type=type(error).__name__, message=str(error)))
            h.save(data/'hosted-member.json', receipt); h.save(output/'receipt.json', receipt)
            if not failing: raise
    return receipt


def verify_member(seed_root, seed, seed_manifest, bundle, output, case, ctx):
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema=SCHEMA, context=ctx, case=case, status='FAIL', phase3Complete=False)
    try:
        raw, manifest = unpack(bundle, output/'original', ctx, 'raw', case); claimed = m.read(raw/'hosted-member.json')
        need(claimed.get('schema') == SCHEMA and claimed.get('context') == ctx and claimed.get('case') == case and
             claimed.get('status') == 'PARTIAL' and claimed.get('phase3Complete') is False and
             [claimed.get(name+'Sha256') for name in ('source','build','toolchain','reader')] == pins(seed) and
             claimed.get('seedArchiveSha256') == seed_manifest['archiveSha256'], 'joining hosted original member binding')
        with (output/'progress.jsonl').open('x') as stream:
            def progress(value):
                stream.write(json.dumps(value, sort_keys=True)+'\n'); stream.flush()
                print(json.dumps(dict(stage='negative', member=case, **value), sort_keys=True), flush=True)
            member = m.qualify_member(raw/'producer', case, *pins(seed), progress=progress)
        need(member['producerReceiptSha256'] == claimed.get('producerReceiptSha256') and
             member['originalPlanSha256'] == claimed.get('originalPlanSha256'), 'joining hosted original receipt binding')
        seed_inputs(seed_root, ctx)
        need(h.inventory(raw, maximum=shared.MAX_BYTES) == manifest['inventory'], 'joining hosted downloaded original changed')
        receipt.update(status='PARTIAL', seedArchiveSha256=seed_manifest['archiveSha256'], rawArchiveSha256=manifest['archiveSha256'],
                       originalFirstDownloadedReplay=True, member=member)
    except BaseException as error:
        receipt.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error))); raise
    finally: h.save(output/'receipt.json', receipt)
    return receipt


def group(seed_bundle, output, shard, ctx, *, maven=None, inputs=None):
    cases = selected(shard); stage = 'execute' if maven is not None else 'verify'
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema=SCHEMA, context=ctx, shard=shard, stage=stage, status='RUNNING', cases=[], phase3Complete=False)
    h.save(output/'receipt.json', receipt)
    try:
        seed_root, manifest = unpack(seed_bundle, output/'seed', ctx, 'seed'); seed = seed_inputs(seed_root, ctx)
        if stage == 'execute': (output/'artifact').mkdir()
        else:
            inputs = Path(inputs)
            need(inputs.is_dir() and not inputs.is_symlink() and
                 {p.name for p in inputs.iterdir()} <= {m.slug(case) for case in cases}, 'joining hosted raw group inventory')
        for case in cases:
            print(json.dumps(dict(stage=stage+'-start', shard=shard, case=case)), flush=True)
            try:
                if stage == 'execute':
                    value = execute_member(seed_root, seed, manifest, output/m.slug(case), output/'artifact'/m.slug(case), maven, case, ctx)
                else: value = verify_member(seed_root, seed, manifest, inputs/m.slug(case), output/m.slug(case), case, ctx)
            except Exception as error:
                value = dict(case=case, status='FAIL', failure=dict(type=type(error).__name__, message=str(error)))
            receipt['cases'].append(value); h.save(output/'receipt.json', receipt)
            print(json.dumps(dict(stage=stage+'-terminal', shard=shard, case=case, status=value['status'])), flush=True)
        seed_inputs(seed_root, ctx)
        need(all(v['status'] == 'PARTIAL' for v in receipt['cases']), 'joining hosted failed group members')
        receipt.update(status='PARTIAL', seedArchiveSha256=manifest['archiveSha256'],
                       **{name+'Sha256': value for name,value in zip(('source','build','toolchain','reader'), pins(seed))})
    except BaseException as error:
        receipt.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error))); raise
    finally: h.save(output/'receipt.json', receipt)
    return receipt


def checked_verifier(value, case, seed, manifest, ctx):
    member = value.get('member', {})
    need(value.get('schema') == SCHEMA and value.get('context') == ctx and value.get('case') == case and value.get('status') == 'PARTIAL' and
         value.get('phase3Complete') is False and value.get('originalFirstDownloadedReplay') is True and
         value.get('seedArchiveSha256') == manifest['archiveSha256'], 'joining hosted verifier context')
    need(member.get('schema') == m.SCHEMA and member.get('case') == case and member.get('status') == 'PASS' and
         member.get('phase3Complete') is False and member.get('declaredJoiningProcessMatrixQualified') is False and
         [member.get(name+'Sha256') for name in ('source','build','toolchain','reader')] == pins(seed), 'joining hosted verifier pins')
    m.check_result(member['qualification'], case)
    need(all(m.hash_field(member.get(k)) for k in ('originalPlanSha256','producerReceiptSha256')) and
         m.hash_field(value.get('rawArchiveSha256')), 'joining hosted original digest')
    qualification = member['qualification']
    negatives = qualification['authority']['negatives']+qualification['physical']['negatives']+qualification['transactionNegatives']
    return dict(case=case, producerReceiptSha256=member['producerReceiptSha256'], originalPlanSha256=member['originalPlanSha256'],
                rawArchiveSha256=value['rawArchiveSha256'], negativeCases=len(negatives),
                rejected=sum(v['status'] == 'REJECTED' for v in negatives), notApplicable=sum(v['status'] == 'NOT_APPLICABLE' for v in negatives))


def aggregate(seed_bundle, inputs, output, ctx, execute_result, verify_result, *, offline_replay=False):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema=SCHEMA, context=ctx, status='FAIL', phase3Complete=False)
    try:
        shared.aggregate_precondition(execute_result, verify_result, offline_replay, 'joining hosted failed/missing workflow stage')
        seed_root, manifest = unpack(seed_bundle, output/'seed', ctx, 'seed'); seed = seed_inputs(seed_root, ctx); inputs = Path(inputs)
        need(inputs.is_dir() and not inputs.is_symlink() and {p.name for p in inputs.iterdir()} ==
             {artifact_name(ctx, 'verified', shard) for shard in SHARDS}, 'joining hosted complete verified inventory')
        cases = []; histories = set(); archives = set()
        for shard, expected in SHARDS.items():
            artifact = artifact_name(ctx, 'verified', shard); directory = inputs/artifact
            need(directory.is_dir() and not directory.is_symlink() and {p.name for p in directory.iterdir()} == {'receipt.json'},
                 'joining hosted verifier artifact shape')
            value = m.read(directory/'receipt.json')
            need(value.get('schema') == SCHEMA and value.get('context') == ctx and value.get('shard') == shard and
                 value.get('stage') == 'verify' and value.get('status') == 'PARTIAL' and value.get('phase3Complete') is False and
                 value.get('seedArchiveSha256') == manifest['archiveSha256'] and
                 [value.get(name+'Sha256') for name in ('source','build','toolchain','reader')] == pins(seed), 'joining hosted verifier group binding')
            members = value.get('cases')
            need(type(members) is list and [v.get('case') for v in members] == list(expected), 'joining hosted exact verifier group cases')
            for member, case in zip(members, expected):
                checked = checked_verifier(member, case, seed, manifest, ctx)
                need(checked['originalPlanSha256'] not in histories and checked['rawArchiveSha256'] not in archives,
                     'joining hosted duplicated original history')
                histories.add(checked['originalPlanSha256']); archives.add(checked['rawArchiveSha256'])
                cases.append(dict(checked, verifierArtifact=artifact, verifierReceiptSha256=tc.file_hash(directory/'receipt.json')))
        need([v['case'] for v in cases] == list(m.KINDS), 'joining hosted complete ordered cases'); seed_inputs(seed_root, ctx)
        receipt.update(status='PASS', cases=cases, wholeHistories=len(cases), groups=len(SHARDS),
                       negativeCases=sum(v['negativeCases'] for v in cases), rejected=sum(v['rejected'] for v in cases),
                       notApplicable=sum(v['notApplicable'] for v in cases), seedArchiveSha256=manifest['archiveSha256'],
                       **{name+'Sha256': value for name,value in zip(('source','build','toolchain','reader'), pins(seed))},
                       declaredJoiningProcessMatrixQualified=True, allMembershipProfilesQualified=False,
                       originalObservationCoverageComplete=False,
                       acceptanceAuthority='complete exact-attempt workflow stages and 360 independent downloaded original-first verifier receipts')
        shared.complete_aggregate(receipt, offline_replay)
    except BaseException as error:
        receipt.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error))); raise
    finally: h.save(output/'receipt.json', receipt)
    return receipt


def summary(path, ctx, command, shard, result):
    rows = [('Source', ctx['source']), ('Run / attempt', ctx['run']+' / '+ctx['attempt']), ('Group', shard or 'all 120'),
            ('Status', result['status']), ('Declared histories', len(m.KINDS)), ('Histories per group', GROUP_SIZE), ('Phase 3 complete', False)]
    if shard: rows += [('History '+str(i), case) for i,case in enumerate(selected(shard), 1)]
    for name in ('wholeHistories','negativeCases','rejected','notApplicable','sourceSha256','buildSha256','toolchainSha256','readerSha256'):
        if name in result: rows.append((name, result[name]))
    with Path(path).open('a') as stream:
        stream.write('### V5.3 joining processes '+command+'\n\n| Parameter | Value |\n| --- | --- |\n'+
                     ''.join('| '+k+' | `'+str(v)+'` |\n' for k,v in rows)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan','prepare','execute','verify','aggregate')); parser.add_argument('--output')
    parser.add_argument('--seed'); parser.add_argument('--inputs'); parser.add_argument('--shard', choices=SHARDS)
    args = parser.parse_args(); ctx = context()
    if args.command == 'plan':
        print(json.dumps(dict(include=[dict(id=shard) for shard in SHARDS]), separators=(',',':'))); return
    need(args.output, 'joining hosted output required'); result = dict(status='FAIL')
    try:
        with shared.progress(args.command, args.shard):
            if args.command == 'prepare': result = prepare(args.output, tc.locate(h.ROOT/'mvnw', h.ROOT), ctx)
            elif args.command == 'execute': result = group(args.seed, args.output, args.shard, ctx, maven=tc.locate(h.ROOT/'mvnw', h.ROOT))
            elif args.command == 'verify': result = group(args.seed, args.output, args.shard, ctx, inputs=args.inputs)
            else: result = aggregate(args.seed, args.inputs, args.output, ctx, os.environ.get('EXECUTE_RESULT'), os.environ.get('VERIFY_RESULT'))
        print(json.dumps(dict(status=result['status'], phase3Complete=False, receipt=str(Path(args.output)/'receipt.json')), sort_keys=True))
    finally:
        if os.environ.get('GITHUB_STEP_SUMMARY'): summary(os.environ['GITHUB_STEP_SUMMARY'], ctx, args.command, args.shard, result)


if __name__ == '__main__': main()

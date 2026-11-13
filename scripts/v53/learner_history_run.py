"""Capture one indivisible native learner history on an immutable source copy.

No native retry, deadline override or qualification claim. Original-first replay
and negative qualification belong to learner_history_cohort.
"""
import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from . import joining_history_run as h
from . import learner_cycles_evidence as cycles
from . import learner_cancellation_evidence as cancellation
from . import native_learner_resources as resources
from . import native_learner_byte_pressure as pressure
from . import process_toolchain as tc
from . import remove_process_matrix as shared

SCHEMA = 'gse-v53-learner-history-execution-v1'
PACKAGE = 'io.github.patricklfdm.generalsearch.replication.'
METHODS = {
    'alternating-slots': ('V53LearnerAlternationNetworkTest', 'nativeSixRevisionsAlternateFixedSlotsAndColdReopenWithinOneReservation'),
    'retained-cancellation': ('V53NativeLearnerBytePressureQualification', 'actualCancelledLearnerRejectsBytePressureAndCompletesColdRecovery'),
}
CASES = tuple(METHODS)
BUILDS = shared.BUILDS
reader_manifest = shared.reader_manifest
RESULTS = {'alternating-slots':'current-head-result.json', 'retained-cancellation':'learner-cancellation-result.json'}


def directory(case):
    selected(case)
    return 'v53-native-dispatch' if case=='alternating-slots' else 'v53-native-learner-byte-pressure'


def original(raw,case):
    selected(case);return Path(raw) if case=='alternating-slots' else Path(raw)/'original/original'


def selected(case):
    h.need(type(case) is str and case in METHODS, 'learner history exact case')
    return METHODS[case]


def command(case):
    cls, method = selected(case)
    return ['-o', '-B', '-ntp', '-f', 'reactor/pom.xml', '-pl', '../'+h.MODULE, '-am',
            '-Dsurefire.failIfNoSpecifiedTests=false', '-Dtest='+cls+'#'+method,
            *(['-Dv53.transport.diagnostics=true'] if case=='alternating-slots' else []), 'test']


def junit(reports, case):
    cls, method = selected(case); cls = PACKAGE+cls
    reports = Path(reports); paths = sorted(reports.glob('TEST-*.xml'))
    h.need(len(paths) == 1, 'learner history exact report')
    suite = ET.fromstring(h.snapshot.s.regular(paths[0], 8*h.snapshot.MIB)); tests = suite.findall('testcase')
    h.need(suite.get('name') == cls and suite.get('tests') == '1' and len(tests) == 1 and
           all(suite.get(k) == '0' for k in ('failures', 'errors', 'skipped')) and
           tests[0].get('classname') == cls and tests[0].get('name') == method and
           not any(v.tag in {'failure', 'error', 'skipped'} or v.tag.startswith(('flaky', 'rerun')) for v in suite.iter()),
           'learner history exact passing unretried test')
    return dict(className=cls, method=method, tests=1, failures=0, errors=0, skipped=0, retries=0)


def fixture(result, case):
    selected(case)
    common = dict(status='PASS', voter=False, publicReady=False, phase3Complete=False, independentReplayQualified=False)
    if case == 'alternating-slots':
        expected = dict(common, scope='native-alternating-learner-slots', installedThirdRevision=True,
                        selectedThirdRevision=True, seedRetired=True, lastRevision=6, testBudgetSeconds=900)
        h.need(type(result) is dict and set(result) == set(expected)|{'cycles'} and
               type(result['cycles']) is list and len(result['cycles']) == 3 and
               all(type(v) is dict and type(v.get('revision')) is int and v['revision'] == i
                   for i,v in enumerate(result['cycles'], 4)), 'learner history six-revision fixture')
    else:
        expected = dict(common, scope='native-learner-cancellation', liveCore=False, testBudgetSeconds=600)
        h.need(type(result) is dict and set(result) == set(expected), 'learner history cancellation fixture')
    h.need(h.snapshot.f.canonical({k:result.get(k) for k in expected}) == h.snapshot.f.canonical(expected),
           'learner history original fixture scope')


def collect(raw, case):
    selected(case); raw = Path(raw); before = h.inventory(raw)
    path=original(raw,case);observations={}
    if case=='alternating-slots':cycles.inventory(path)
    else:
        h.need({v.name for v in raw.iterdir()}=={'original','pressure'} and
               {v.name for v in (raw/'pressure').iterdir()}==set(pressure.MODES) and
               {v.name for v in (raw/'original').iterdir()}=={'original','resources'} and
               {v.name for v in (raw/'original/resources').iterdir()}=={'index.json','trace.json','boundaries.json'},
               'learner history complete original resource wrapper')
        index=h.read_json(raw,'original/resources/index.json',65536)
        h.need(type(index) is dict and set(index)=={'schema','status','pid','planSha256','wholeRuntimeResourcesQualified','phase3Complete'} and
               index['schema']==resources.SCHEMA and index['status']=='PARTIAL' and type(index['pid']) is int and index['pid']>0 and
               index['planSha256']==h.digest(h.snapshot.s.regular(path/'learner-plan.gslp',h.snapshot.MIB)) and
               index['wholeRuntimeResourcesQualified'] is False and index['phase3Complete'] is False,'learner history resource capture index')
        _,trace=resources.t.read(raw/'original/resources/trace.json');bounds=shared.read(raw/'original/resources/boundaries.json')
        h.need(type(bounds) is list and 1<=len(bounds)<=4096,'learner history resource boundary collection')
        observations.update(resourceTransitions=len(trace['changes']),resourceBoundaries=len(bounds))
        observations['bytePressure']={}
        for mode in pressure.MODES:
            folder=raw/'pressure'/mode
            h.need({v.name for v in folder.iterdir()}=={'resources','events.json','probe.json','result.json',*pressure.STAGES}|
                   ({'received'} if mode=='source-exact' else set()) and
                   {v.name for v in (folder/'resources').iterdir()}=={'index.json','trace.json','boundaries.json'},
                   'learner history complete byte pressure mode')
            h.need(h.snapshot.f.canonical(h.read_json(folder,'resources/index.json',65536))==h.snapshot.f.canonical(index),
                   'learner history original byte pressure index')
            _,captured=resources.t.read(folder/'resources/trace.json');boundaries=h.read_json(folder,'resources/boundaries.json',4*h.snapshot.MIB)
            h.need(type(boundaries) is list and 1<=len(boundaries)<=4096,'learner history byte pressure boundaries')
            status=h.read_json(folder,'result.json',65536)
            h.need(type(status) is dict and status.get('status')=='PARTIAL' and status.get('mode')==mode and
                   status.get('sameOriginalColdRecovery') is True and status.get('phase3Complete') is False and
                   status.get('wholeRuntimeResourcesQualified') is False,'learner history byte pressure result scope')
            observations['bytePressure'][mode]=dict(transitions=len(captured['changes']),boundaries=len(boundaries))
        cancellation.inventory(path,current_retention=True)
    result = h.read_json(path, RESULTS[case], 65536); fixture(result, case)
    rows = {name:h.read_json(path, name+'.json', maximum) for name,maximum in
            (('events',h.EVENT_BYTES), ('wire',h.WIRE_BYTES), ('calls',8*h.snapshot.MIB), ('failures',h.snapshot.MIB))}
    h.need(all(type(v) is list and all(type(row) is dict for row in v) for v in rows.values()) and
           all(rows[k] for k in ('events', 'wire', 'calls')), 'learner history complete observation containers')
    h.need(h.inventory(raw) == before, 'learner history changed during collection')
    return dict(status='PARTIAL', case=case, collectionComplete=True, nativeHistoryQualified=False,
                phase3Complete=False, scope='learner-history-observations-only', fixture=result,
                observations=dict(observations,**{k:len(v) for k,v in rows.items()}), inventory=before)


def run(output, maven, case, *, source_from=None):
    selected(case); output = Path(output).absolute()
    h.need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()), 'learner history source separation')
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema=SCHEMA, case=case, status='RUNNING', executionStatus='NOT_RUN',
                   collectionComplete=False, nativeHistoryQualified=False, phase3Complete=False, retries=0)
    try:
        work = output/'workspace'
        source = h.source_copy(h.ROOT, work) if source_from is None else h.recorded_source(source_from, work)
        h.save(output/'source.json', source)
        reader = reader_manifest()
        h.need(all(source['files'].get(k) == v for k,v in reader['files'].items()), 'learner history reader belongs to source')
        receipt.update(baseHead=source['head'], sourceSha256=h.digest((output/'source.json').read_bytes()), readerSha256=reader['sha256'])
        h.save(output/'toolchain.json', tc.capture(maven, work))
        receipt['toolchainSha256'] = h.digest((output/'toolchain.json').read_bytes())
        receipt['command'] = [maven, *command(case)]; h.save(output/'receipt.json', receipt)
        execution = h.execute(receipt['command'], work, output/'maven.log', stage='learner-history-'+case)
        receipt['execution'] = execution; h.save(output/'execution.json', execution); h.check_source(work, source)
        h.need(type(execution['exit']) is int and execution['exit'] == 0, 'learner history Maven failed; original retained')
        receipt['junit'] = junit(work/h.MODULE/'target/surefire-reports', case); receipt['executionStatus'] = 'PASS'
        h.save(output/'build.json', {name:h.inventory(work/name) for name in BUILDS})
        receipt['buildSha256'] = h.digest((output/'build.json').read_bytes())
        roots = list((work/h.MODULE/'target'/directory(case)).iterdir())
        h.need(len(roots) == 1, 'learner history exact original directory')
        raw = roots[0]; receipt['raw'] = raw.relative_to(output).as_posix()
        # Freeze the collector too: do not read a concurrently edited live checkout.
        collected = h.execute([sys.executable, '-B', '-m', 'scripts.v53.learner_history_run', str(output/'collection.json'),
                               '--case', case, '--collect', str(raw)], work, output/'collection.log', stage='learner-collection-'+case)
        receipt['collectionExecution'] = collected
        h.need(type(collected['exit']) is int and collected['exit'] == 0, 'learner history collection failed; original retained')
        collection = shared.read(output/'collection.json')
        h.need(collection.get('case') == case and collection.get('status') == 'PARTIAL' and collection.get('collectionComplete') is True and
               all(collection.get(k) is False for k in ('nativeHistoryQualified','phase3Complete')) and
               collection.get('inventory') == h.inventory(raw), 'learner history collection scope')
        h.check_source(work, source)
        receipt.update(status='PARTIAL', collectionComplete=True, collectionSha256=h.digest((output/'collection.json').read_bytes()))
    except BaseException as error:
        if receipt['executionStatus'] == 'NOT_RUN': receipt['executionStatus'] = 'FAIL'
        receipt.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error))); raise
    finally:
        h.save(output/'receipt.json', receipt); print(json.dumps(receipt, sort_keys=True), flush=True)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('output')
    parser.add_argument('--case', required=True, choices=CASES); parser.add_argument('--maven', default='mvn')
    parser.add_argument('--source-from'); parser.add_argument('--collect')
    args = parser.parse_args()
    if args.collect:
        h.need(args.source_from is None, 'learner collection cannot select source')
        value = collect(args.collect, args.case)
        with Path(args.output).open('x') as stream: json.dump(value, stream, sort_keys=True, indent=2); stream.write('\n')
    else: run(args.output, args.maven, args.case, source_from=args.source_from)

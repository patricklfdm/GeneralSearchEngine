"""One indivisible joining execution and collection check; not full qualification.

Run only the declared JUnit history in a fresh source copy. Keep failures, report
progress each minute, and never retry, clean, or stitch histories. Native bounds
remain in the fixture. Physical/network replay beyond the original ledger reader
is still required even when execution and collection both succeed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from . import joining_snapshot as snapshot
from . import joining_retention_evidence as ledgers
from . import joining_grant_captures as grants
from . import joining_source_retirement as retirements

ROOT = Path(__file__).resolve().parents[2]
MODULE = 'general-search-engine-replication'
CLASS = 'io.github.patricklfdm.generalsearch.replication.V53JoiningIntentExportTest'
METHOD = 'joiningInitializerStartsBeforeOldPreparationAndCompletesNativeHistory'
TEST = CLASS.rsplit('.', 1)[-1] + '#' + METHOD
SCHEMA = 'gse-v53-joining-history-collection-v3'
WIRE_BYTES = 64 * 1024 * 1024
EVENT_BYTES = 32 * 1024 * 1024
HISTORY_ROWS = 65536
ROW_BYTES = 16 * 1024 * 1024
need = snapshot.need


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def inventory(root, *, maximum=512 * 1024 * 1024):
    """Bounded inventory of this copy, never authority for original identities."""
    need(root.is_dir() and not root.is_symlink(), 'collection root')
    files, directories, total, pending = {}, [], 0, [root]
    while pending:
        directory = pending.pop()
        for p in directory.iterdir():
            need(not p.is_symlink(), 'collection linked member')
            name = p.relative_to(root).as_posix()
            if p.is_dir():
                directories.append(name); pending.append(p)
            else:
                need(p.is_file() and p.stat().st_nlink == 1, 'collection regular member')
                total += p.stat().st_size
                need(total <= maximum, 'collection byte capacity')
                files[name] = digest(snapshot.s.regular(p, maximum))
            need(len(files) + len(directories) <= 65536, 'collection member capacity')
    return dict(files=files, directories=sorted(directories), bytes=total)


def source_copy(repo, destination):
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=repo).split(b'\0')
    pending = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z', '--',
        MODULE + '/src', 'scripts/v53', 'docs/v5x/v5.3'], cwd=repo).split(b'\0')
    names = sorted(set(os.fsdecode(v) for v in tracked + pending if v))
    destination.mkdir()
    files = {}
    for name in names:
        source = repo / name
        need(source.is_file() and not source.is_symlink(), 'source missing/linked: ' + name)
        target = destination / name; target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes(); target.write_bytes(data); shutil.copymode(source, target)
        files[name] = digest(data)
    return dict(head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
                files=files)


def check_source(work, source):
    for name, expected in source['files'].items():
        p = work / name
        need(p.is_file() and not p.is_symlink() and digest(p.read_bytes()) == expected,
             'source copy changed: ' + name)


def read_recorded_source(producer):
    """Bound and verify every immutable source member without executing it."""
    producer=Path(producer);raw=snapshot.s.regular(producer/'source.json',8*snapshot.MIB)
    def unique(rows):
        need(len(rows)==len(dict(rows)),'recorded source duplicate key');return dict(rows)
    source=json.loads(raw,object_pairs_hook=unique)
    need(type(source) is dict and set(source)=={'head','files'} and type(source['head']) is str and
         re.fullmatch('[0-9a-f]{40}',source['head']) and type(source['files']) is dict and 0<len(source['files'])<=20000,
         'recorded source manifest')
    files={};total=0;work=producer/'workspace'
    need(work.is_dir() and not work.is_symlink(),'recorded source workspace')
    # Validate the complete source before creating any new workspace. No receipt
    # label can turn changed or linked bytes into the earlier producer source.
    for name,digest_value in source['files'].items():
        path=Path(name)
        need(name and len(name)<=4096 and not path.is_absolute() and path.as_posix()==name and
             '..' not in path.parts and '\\' not in name and type(digest_value) is str and
             re.fullmatch('[0-9a-f]{64}',digest_value),'recorded source member path/hash')
        need(all((work/parent).is_dir() and not (work/parent).is_symlink() for parent in path.parents),
             'recorded source linked parent')
        data=snapshot.s.regular(work/path,64*snapshot.MIB);total+=len(data)
        need(total<=256*snapshot.MIB,'recorded source byte capacity')
        need(digest(data)==digest_value,'recorded source changed: '+name);files[name]=data
    return source,files


def recorded_source(producer, destination):
    """Copy an existing immutable producer source, never its generated state."""
    source,files=read_recorded_source(producer);work=Path(producer)/'workspace'
    destination.mkdir()
    for name,data in files.items():
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        shutil.copymode(work/name,target)
    return source


def junit(reports):
    paths = sorted(reports.glob('TEST-*.xml'))
    need(len(paths) == 1, 'whole joining exact test report')
    suite = ET.parse(paths[0]).getroot()
    need(suite.get('name') == CLASS and suite.get('tests') == '1' and
         all(suite.get(k) == '0' for k in ('failures', 'errors', 'skipped')), 'whole joining test did not pass')
    cases = suite.findall('testcase')
    need(len(cases) == 1 and cases[0].get('classname') == CLASS and cases[0].get('name') == METHOD and
         not any(cases[0].find(k) is not None for k in ('failure', 'error', 'skipped')), 'whole joining exact test case')
    return dict(className=CLASS, method=METHOD, tests=1, failures=0, errors=0, skipped=0)


def read_json(root, name, maximum):
    raw = snapshot.s.regular(root / name, maximum)
    def unique(rows):
        need(len(rows) == len(dict(rows)), 'collection duplicate JSON key')
        return dict(rows)
    value = json.loads(raw, object_pairs_hook=unique)
    need(type(value) is not list or len(value)<=HISTORY_ROWS,'collection history row capacity')
    need(snapshot.f.canonical(value) == raw, 'collection noncanonical JSON')
    # Like the Java history writer, bound individual messages instead of
    # applying a one-message token budget to the entire event history.
    for row in value if type(value) is list else [value]:
        encoded=snapshot.f.canonical(row)
        need(len(encoded)<=ROW_BYTES,'collection individual row capacity')
        snapshot.f.parse_budget(encoded)
    return value


def collection(raw):
    # This detects missing observations. It does not prove their causal validity.
    original = inventory(raw)
    events = read_json(raw, 'events.json', EVENT_BYTES)
    wire = read_json(raw, 'wire.json', WIRE_BYTES)
    calls = read_json(raw, 'calls.json', 8 * snapshot.MIB)
    failures = read_json(raw, 'failures.json', snapshot.MIB)
    need(all(type(v) is list for v in (events, wire, calls, failures)) and events and wire and calls,
         'whole joining traces missing')
    need(all(type(v) is dict for v in events + wire + calls + failures), 'whole joining trace rows')
    intent = read_json(raw, 'joining-intent-result.json', 4096)
    result = read_json(raw, 'joining-continuation-result.json', 65536)
    need(intent.get('status') == result.get('status') == 'PASS' and result.get('stableColdReopened') is True,
         'whole joining fixture incomplete')
    index = result['cut']['index']
    need(type(index) is int and 3 <= index <= 64, 'whole joining collection cut')
    for phase in ('applied', 'published'):
        for cut in range(1, index + 1):
            for node in ('node-1', 'node-2', 'node-3'):
                p = raw / f'{phase}-{cut}' / node
                need(p.is_dir() and any(p.iterdir()), 'whole joining old-owner snapshot missing')
    for group in ('before-network', 'before-joint-continuation', 'after-close',
                  f'continuation-installed-{index-2}', f'continuation-installed-{index-1}'):
        need(all((raw / group / node).is_dir() and any((raw / group / node).iterdir())
                 for node in ('node-1', 'node-2', 'node-3')), 'whole joining lifecycle snapshot missing')
    snapshot.read(raw / 'joining-originals-placed', stage='placed')
    for group in ('joining-originals-native', 'joining-originals-continuation', 'joining-originals-stable-cold',
                  f'joining-installed-{index-2}', f'joining-installed-{index-1}',
                  f'joining-applied-{index-1}', f'joining-published-{index-1}',
                  f'joining-applied-{index}', f'joining-published-{index}'):
        snapshot.read(raw / group)
    joining = [v for v in events if v.get('node') == 'node-4']
    for scope in ('learner-plan', 'learner-admission', 'learner-materialization', 'pending-intent',
                  'published-intent', 'voter-stage', 'custody', 'placement', 'joined-admission', 'retirement',
                  'initial-owner', 'retaining-owner', 'repeated-basis-owner', 'continuation-owner'):
        need(any(v.get('scope') == scope for v in joining), 'whole joining callback scope missing: ' + scope)
    cold = [v.get('event') for v in joining if v.get('scope') == 'stable-cold-owner' and
            v.get('event') in ('FIXTURE_OPEN_RETURNED', 'FIXTURE_CLOSE_RETURNED')]
    need(cold == ['FIXTURE_OPEN_RETURNED', 'FIXTURE_CLOSE_RETURNED'], 'whole joining cold observations missing')
    for phase in ('APPLIED', 'PUBLISHED', 'FUTURE_QUORUM_COMPLETE'):
        for cut in (index - 1, index):
            need(any(v.get('event') == 'JOINING_SLOT_' + phase and v.get('index') == cut for v in events),
                 'whole joining slot observations missing')
    need(any(v.get('scope') == 'continuation-endpoint' and v.get('event') == 'BEFORE_RESPONSE_WRITE' for v in joining),
         'whole joining response observations missing')
    grant_result = grants.validate(raw, events, whole_history=True)
    retirement_result = retirements.validate(raw, events)
    ledger_result = ledgers.validate(raw, confirmed_peers=True)
    need(inventory(raw) == original, 'whole joining evidence changed during collection')
    return dict(status='PARTIAL', collectionComplete=True, scope='joining-history-collection-and-ledger-only',
                nativeHistoryQualified=False, forceAndNetworkQualified=False, phase3Complete=False,
                events=len(events), wirePairs=len(wire), finalIndex=index, ledger=ledger_result, grants=grant_result,
                sourceRetirements=retirement_result, inventory=original)


def tail(path):
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - 4096))
        lines = stream.read().decode(errors='replace').splitlines()
    return lines[-1] if lines else ''


def execute(command, work, log, *, stage='whole-joining'):
    start = time.monotonic()
    with log.open('x') as output:
        process = subprocess.Popen(command, cwd=work, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while True:
                try:
                    code = process.wait(timeout=60)
                    return dict(exit=code, elapsedSeconds=round(time.monotonic() - start, 3))
                except subprocess.TimeoutExpired:
                    print(json.dumps(dict(stage=stage, pid=process.pid,
                        elapsedSeconds=round(time.monotonic() - start, 1), last=tail(log))), flush=True)
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.wait()
            raise


def run(output, maven, *, fault=None, source_from=None, portable_toolchain=False):
    need(fault in (None,'SOURCE_OFFER','CHUNK','TRANSFER_COMMIT'),'whole joining source fault selector')
    need(type(portable_toolchain) is bool,'whole joining portable toolchain option')
    output = Path(output).absolute()
    need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),'recorded source execution separation')
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema=SCHEMA, status='RUNNING', executionStatus='NOT_RUN', nativeHistoryQualified=False,
                   phase3Complete=False, retries=0, sourceFault=fault)
    try:
        work = output / 'workspace'
        source = source_copy(ROOT, work) if source_from is None else recorded_source(source_from,work)
        save(output / 'source.json', source)
        if source_from is not None:receipt['sourceOrigin']='recorded-producer'
        receipt.update(sourceSha256=digest((output / 'source.json').read_bytes()), baseHead=source['head'])
        if portable_toolchain:
            from . import process_toolchain
            save(output/'toolchain.json',process_toolchain.capture(maven,work))
        else:
            toolchain = subprocess.run([maven, '-version'], cwd=work, text=True, capture_output=True, timeout=30)
            save(output / 'toolchain.json', dict(exit=toolchain.returncode, stdout=toolchain.stdout, stderr=toolchain.stderr))
            need(toolchain.returncode == 0, 'whole joining Maven toolchain unavailable')
        receipt['toolchainSha256'] = digest((output / 'toolchain.json').read_bytes())
        command = [maven, '-o', '-B', '-ntp', '-f', 'reactor/pom.xml', '-pl', '../' + MODULE, '-am',
                   '-Dsurefire.failIfNoSpecifiedTests=false', '-Dtest=' + TEST, 'test']
        if fault is not None: command[-1:-1]=['-Dv53.transport.connections=true','-Dv53.joining.sourceFault='+fault]
        receipt['command'] = command; save(output / 'receipt.json', receipt)
        execution = execute(command, work, output / 'maven.log'); receipt['execution'] = execution
        save(output / 'execution.json', execution)
        check_source(work, source)
        need(execution['exit'] == 0, 'whole joining Maven failed; retained log and raw evidence')
        receipt['junit'] = junit(work / MODULE / 'target/surefire-reports')
        receipt['executionStatus'] = 'PASS'
        build = {name: inventory(work / name) for name in
                 ('target/classes', MODULE + '/target/classes', MODULE + '/target/test-classes')}
        save(output / 'build.json', build); receipt['buildSha256'] = digest((output / 'build.json').read_bytes())
        roots = sorted((work / MODULE / 'target/v53-native-dispatch').glob('run-*'))
        need(len(roots) == 1, 'whole joining exact original history')
        receipt['raw'] = roots[0].relative_to(output).as_posix()
        # The reader and all its format/catalog imports must come from the same
        # immutable copy, even if the operator edits the original repo meanwhile.
        collected = execute([sys.executable, '-B', '-m', 'scripts.v53.joining_history_run',
            str(output / 'collection.json'), '--collect', str(roots[0])], work, output / 'collection.log', stage='collection')
        receipt['collectionExecution'] = collected
        need(collected['exit'] == 0, 'whole joining collection failed; retained collection log')
        check_source(work, source)
        value = json.loads((output / 'collection.json').read_bytes())
        need(value['status'] == 'PARTIAL' and value['collectionComplete'] is True and
             value['nativeHistoryQualified'] is False and value['forceAndNetworkQualified'] is False and
             value['phase3Complete'] is False, 'whole joining collection scope')
        receipt.update(status='PARTIAL', collectionComplete=True, collectionSha256=digest((output / 'collection.json').read_bytes()))
    except BaseException as error:
        if receipt['executionStatus'] == 'NOT_RUN': receipt['executionStatus'] = 'FAIL'
        receipt.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error)))
        raise
    finally:
        save(output / 'receipt.json', receipt); print(json.dumps(receipt, sort_keys=True), flush=True)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output'); parser.add_argument('--maven', default='mvn')
    parser.add_argument('--collect', help='Only check an existing original history; does not run Java')
    parser.add_argument('--fault',choices=('SOURCE_OFFER','CHUNK','TRANSFER_COMMIT'),help='One declared lost initial learner reply in the complete history')
    parser.add_argument('--source-from',help='Reuse only the exact immutable source of an earlier producer; create a fresh history')
    parser.add_argument('--portable-toolchain',action='store_true')
    args = parser.parse_args()
    if args.collect:
        need(args.fault is None and args.source_from is None and not args.portable_toolchain,'collection cannot select a new fault/source')
        destination = Path(args.output)
        need(not destination.exists(), 'collection output already exists')
        value = collection(Path(args.collect))
        with destination.open('x') as stream: stream.write(json.dumps(value, sort_keys=True, indent=2) + '\n')
        print(json.dumps({k: v for k, v in value.items() if k not in ('inventory', 'ledger')}, sort_keys=True))
    else: run(args.output, args.maven, fault=args.fault,source_from=args.source_from,portable_toolchain=args.portable_toolchain)

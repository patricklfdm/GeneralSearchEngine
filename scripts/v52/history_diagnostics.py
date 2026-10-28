"""Bounded, closed failure telemetry; never acceptance or raw evidence export."""
from collections import Counter
from pathlib import Path
import os
import sys
import tempfile
from . import cloud_suite as suite
from .evidence import encoded, strict

SCHEMA = 'gse-v52-history-failure-v1'
FILE = 'failure-diagnostic.json'
MAX_BYTES = 32768
NODES = ('node-1', 'node-2', 'node-3')
STAGES = ('receiver-create', 'preparation', 'original-workload', 'receiver-close', 'physical-replay', 'complete')
SCENARIO_STAGES = ('activation', 'initialization', 'offered', 'reads', 'observed')
TYPES = frozenset(('ValueError', 'OSError', 'TimeoutError', 'ConnectionError', 'BrokenPipeError',
    'ConnectionResetError', 'JSONDecodeError', 'KeyError', 'AssertionError', 'Empty', 'Full',
    'ProcessError', 'ProcessRejected', 'CalledProcessError', 'TimeoutExpired', 'KeyboardInterrupt', 'OTHER'))
MODULES = frozenset(p.stem for p in Path(__file__).parent.glob('*.py') if not p.stem.startswith('test_'))
OUTCOMES = ('SUCCESS', 'PENDING', 'INDETERMINATE', 'NOT_APPLICABLE', 'REJECTED', 'TIMEOUT', 'OTHER')
REASONS = ('QUORUM_UNAVAILABLE', 'STALE_EPOCH', 'CAPACITY_EXCEEDED', 'NOT_LEADER', 'CLOSED',
    'TIMEOUT', 'INTEGRITY_FAILURE', 'UNAVAILABLE', 'NONE', 'OTHER')
KINDS = ('read', 'update', 'status', 'sample-start', 'sample-mark', 'sample-stop', 'OTHER')
DISPATCH = ('NOT_DISPATCHED', 'DISPATCHED', 'DISPATCH_FAILED', 'OTHER')
COMPLETION = ('UNOBSERVED', 'FUTURE_CANCELLED', 'DISCONNECTED', 'OBSERVED', 'OBSERVER_FAILED', 'NONE', 'OTHER')
# Only these constant codes are exported. Arbitrary text, including a suffix
# containing a public response, credentials or provider stderr, never escapes.
MESSAGES = {
    'measurement M01 activation timeout': 'ACTIVATION_TIMEOUT',
    'measurement M01 voter failed': 'VOTER_FAILED',
    'measurement prepared voter failed': 'VOTER_FAILED',
    'measurement prepared publication unavailable': 'PUBLICATION_UNAVAILABLE',
    'measurement M01 unexpected setup mutation': 'SETUP_SEQUENCE_CHANGED',
    'measurement consumer startup': 'WORKER_STARTUP_REJECTED',
    'measurement worker response bound': 'WORKER_RESPONSE_BOUND',
    'load incomplete dispatch': 'DISPATCH_INCOMPLETE',
    'load shortened/incomplete observation': 'OBSERVATION_INCOMPLETE',
    'load missing/retried offer': 'OFFER_INCOMPLETE',
    'measurement window lacks successful query coverage': 'QUERY_COVERAGE_MISSING',
    'measurement window lacks successful mutation': 'MUTATION_COVERAGE_MISSING',
    'load phase marker response binding': 'MARKER_RESPONSE_REJECTED',
    'load changed/incomplete phase marker': 'MARKER_INCOMPLETE',
    'voter stream unavailable; query original': 'VOTER_STREAM_UNAVAILABLE',
}
PREFIXES = {
    'measurement public call failed: ': 'PUBLIC_CALL_REJECTED',
    'measurement worker unavailable: ': 'WORKER_UNAVAILABLE',
    'measurement response reader failed: ': 'WORKER_READER_FAILED',
    'measurement close failed: ': 'WORKER_CLOSE_FAILED',
    'load incomplete observation: ': 'ORIGINAL_RESPONSES_MISSING',
    'voter incomplete close: ': 'VOTER_CLOSE_INCOMPLETE',
    'remote receiver cleanup failed: ': 'RECEIVER_CLOSE_FAILED',
}
CODES = frozenset((*MESSAGES.values(), *PREFIXES.values(), 'TIMEOUT', 'CONNECTION_LOST',
    'IO_FAILED', 'VALIDATION_REJECTED', 'UNCLASSIFIED'))


def reason(typ, message):
    if type(message) is str:
        if message in MESSAGES: return MESSAGES[message]
        for prefix, code in PREFIXES.items():
            if message.startswith(prefix): return code
    if typ in ('TimeoutError', 'TimeoutExpired', 'Empty'): return 'TIMEOUT'
    if typ in ('ConnectionError', 'BrokenPipeError', 'ConnectionResetError'): return 'CONNECTION_LOST'
    if typ == 'OSError': return 'IO_FAILED'
    return 'VALIDATION_REJECTED' if typ == 'ValueError' else 'UNCLASSIFIED'


def exception(error):
    typ = type(error).__name__; typ = typ if typ in TYPES else 'OTHER'
    message = error.args[0] if error.args and type(error.args[0]) is str else None
    site = None; trace = error.__traceback__; root = Path(__file__).resolve().parent
    while trace is not None:
        path = Path(trace.tb_frame.f_code.co_filename)
        if path.parent == root and path.stem in MODULES and path.stem != 'evidence' and 0 < trace.tb_lineno <= 100000:
            site = dict(module=path.stem, line=trace.tb_lineno)
        trace = trace.tb_next
    return dict(errorType=typ, reasonCode=reason(typ, message), origin=site)


def read(path, maximum):
    # No globs, symlinks, raw logs, recursive copies or private workspace export.
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('diagnostic input unavailable')
    with path.open('rb') as stream: raw = stream.read(maximum + 1)
    if len(raw) > maximum: raise ValueError('diagnostic input oversized')
    return strict(raw)


def choice(value, allowed, missing='OTHER'):
    if value is None:return missing
    return value if type(value) is str and value in allowed else 'OTHER'


def count(rows, field, allowed, missing='OTHER'):
    return dict(Counter(choice(row.get(field), allowed, missing) for row in rows))


def observations(owner):
    result = {}; root = Path(owner.collected)
    try:
        scenario = read(root/'scenario.json', 65536)
        result['scenario'] = {key:choice(scenario.get(key), allowed) for key, allowed in
            (('stage', SCENARIO_STAGES), ('leader', NODES), ('readTarget', NODES))}
    except Exception: pass
    try:
        offered = read(root/'offered.json', 8 << 20); rows = offered['offers']
        if type(rows) is list and len(rows) <= 4096 and all(type(row) is dict for row in rows):
            result['offers'] = dict(total=len(rows), dispatch=count(rows, 'status', DISPATCH),
                completion=count(rows, 'completionStatus', COMPLETION, 'NONE'))
    except Exception: pass
    try:
        # Original shared history only; no status probes or resubmissions.
        rows = list(owner.history[-16384:])
        result['calls'] = dict(sampled=len(rows), truncated=len(owner.history) > 16384,
            kinds=count(rows, 'kind', KINDS), outcomes=count(rows, 'outcome', OUTCOMES),
            reasons=count([row.get('response') or {} for row in rows], 'reasonCode', REASONS, 'NONE'))
    except Exception: pass
    return result


def closure(owner):
    result = {}
    try:
        rows = read(Path(owner.collected)/'processes.json', 65536)
        result['processes'] = [dict(node=row['node'], generation=row['generation'], exitCode=row['exitCode'])
            for row in rows if row.get('node') in NODES][:6]
    except Exception: pass
    try:
        value = read(Path(owner.collected)/'execution.json', 65536)
        result['closeErrors'] = [dict(node=choice(row.get('node'), (*NODES, 'reserved-ports', 'collected-network-controls')),
            errorType=choice(row.get('type'), TYPES), reasonCode=reason(row.get('type'), row.get('message')))
            for row in value['closeErrors'][:8]]
    except Exception: pass
    return result


def project(value):
    """Revalidate every field before public export; extra/private keys disappear."""
    def number(v, maximum=16384): return type(v) is int and 0 <= v <= maximum
    def error(row):
        if row['errorType'] not in TYPES or row['reasonCode'] not in CODES: raise ValueError('error')
        site = row['origin']
        if site is not None:
            if site['module'] not in MODULES or not number(site['line'], 100000) or not site['line']: raise ValueError('site')
            site = dict(module=site['module'], line=site['line'])
        return dict(errorType=row['errorType'], reasonCode=row['reasonCode'], origin=site)
    def histogram(row, allowed, total):
        if type(row) is not dict or not set(row) <= set(allowed) or any(not number(v) for v in row.values()) or sum(row.values()) != total:
            raise ValueError('histogram')
        return dict(row)
    try:
        if value['schema'] != SCHEMA or value['status'] != 'FAIL' or value['fullRemoteQualification'] is not False or \
           value['history'] not in suite.load()['histories'] or value['stage'] not in STAGES: return None
        result = dict(schema=SCHEMA, status='FAIL', fullRemoteQualification=False, history=value['history'],
                      stage=value['stage'], failure=error(value['failure']))
        if 'cleanupFailure' in value: result['cleanupFailure'] = error(value['cleanupFailure'])
        observed = value.get('observations', {}); output = {}
        if 'scenario' in observed:
            row = observed['scenario']
            if row['stage'] not in (*SCENARIO_STAGES, 'OTHER') or any(row[k] not in (*NODES, 'OTHER') for k in ('leader', 'readTarget')): return None
            output['scenario'] = {k:row[k] for k in ('stage', 'leader', 'readTarget')}
        if 'offers' in observed:
            row = observed['offers']; total = row['total']
            if not number(total, 4096): return None
            output['offers'] = dict(total=total, dispatch=histogram(row['dispatch'], DISPATCH, total),
                                   completion=histogram(row['completion'], COMPLETION, total))
        if 'calls' in observed:
            row = observed['calls']; total = row['sampled']
            if not number(total) or type(row['truncated']) is not bool: return None
            output['calls'] = dict(sampled=total, truncated=row['truncated'],
                **{key:histogram(row[key], allowed, total) for key, allowed in
                   (('kinds', KINDS), ('outcomes', OUTCOMES), ('reasons', REASONS))})
        result['observations'] = output
        close = value.get('closure', {}); output = {}
        if 'processes' in close:
            rows = close['processes']
            if type(rows) is not list or len(rows) > 6: return None
            for row in rows:
                if row['node'] not in NODES or type(row['generation']) is not int or row['generation'] not in (1, 2) or \
                   (row['exitCode'] is not None and (type(row['exitCode']) is not int or not -255 <= row['exitCode'] <= 255)): return None
            output['processes'] = [{k:row[k] for k in ('node', 'generation', 'exitCode')} for row in rows]
        if 'closeErrors' in close:
            rows = close['closeErrors']
            if type(rows) is not list or len(rows) > 8: return None
            for row in rows:
                if row['node'] not in (*NODES, 'reserved-ports', 'collected-network-controls', 'OTHER') or row['errorType'] not in TYPES or row['reasonCode'] not in CODES: return None
            output['closeErrors'] = [{k:row[k] for k in ('node', 'errorType', 'reasonCode')} for row in rows]
        result['closure'] = output
        return result
    except (KeyError, TypeError, ValueError): return None


def retain(root, name, stage, error, owner, *, previous=None, cleanup_error=None):
    """Best effort before/after receiver close; never replace the original error."""
    try:
        row = previous or dict(schema=SCHEMA, status='FAIL', fullRemoteQualification=False, history=name,
            stage=stage, failure=exception(error), observations={} if owner is None else observations(owner))
        row = dict(row)
        if cleanup_error is not None: row['cleanupFailure'] = exception(cleanup_error)
        if owner is not None: row['closure'] = closure(owner)
        row = project(row)
        if row is None: raise ValueError('diagnostic rejected')
        raw = encoded(row) + b'\n'; path = Path(root)/FILE
        if len(raw) > MAX_BYTES or any(p.is_symlink() for p in (path, *path.parents)): raise ValueError('diagnostic path/bound')
        # Keep the first failure intact if the after-close write runs out of disk.
        fd, temporary = tempfile.mkstemp(prefix='.history-diagnostic-', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream: stream.write(raw)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return row
    except Exception:
        try: print('v52HistoryDiagnosticRetention=FAIL', file=sys.stderr, flush=True)
        except Exception: pass
        return previous


def report(root, name):
    try:
        if name not in suite.load()['histories']: return None
        value = project(read(Path(root)/name/FILE, MAX_BYTES))
        return value if value is not None and value['history'] == name else None
    except Exception: return None

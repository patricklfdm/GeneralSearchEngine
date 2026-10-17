"""Owned native expiry reconciliation; no force-delete or Runner admission entry.

The factory obtains its own tracked configuration, exact workflow credentials and
fresh observations. Existing lease bytes retain their original source and IDs.
Private constructor tickets keep trusted code paths separate, not a Python sandbox.
"""
import argparse
from copy import deepcopy
import math
import os
from pathlib import Path
import threading
import time
from scripts.v51 import cloud_http as h, cloud_cleanup_credentials as exchange
from . import cloud_authority as a, cloud_control as c, cloud_provider as p
from . import cloud_preflight as f, cloud_preflight_read as r, cloud_credentials as credentials
from . import cloud_artifacts as artifacts, cloud_wire_policy as w
from .evidence import need, encoded, digest

_CAPABILITY = object()


class _NativeGate(w._Gate):
    offline = False

    def exchange(self, method, endpoint, headers, body, timeout, maximum):
        api = self.api; api.calls += 1
        operation = api.policy.route(method, endpoint, None if body is None else w.strict(body))['operation']
        if method != 'GET': api.writes += 1
        if operation == 'delete': api.deletes += 1
        row = dict(exchange=api.calls, method=method, url=endpoint, operation=operation)
        # Retain the intent before sending; never headers/tokens or error bodies.
        api.log.write(encoded(dict(row, phase='send'))+b'\n'); api.log.flush()
        try:
            status, raw = self.server.send(method, endpoint, headers, body, timeout, maximum)
        except BaseException as error:
            api.log.write(encoded(dict(row, phase='uncertain', errorType=type(error).__name__))+b'\n'); api.log.flush()
            raise
        api.log.write(encoded(dict(row, phase='response', status=status,
                                   bytes=len(raw) if 200 <= status < 300 else 0))+b'\n'); api.log.flush()
        return status, raw


class NativeCleanupApi(w._ScopedApi):
    """Factory-owned credentials/transport and cleanup-only original request scope."""
    def __init__(self, reader, original, log, ticket):
        need(ticket is _CAPABILITY and type(reader) is r.NetworkReader and reader.role in ('manual','schedule'),
             'V5.2 native cleanup factory required')
        reader.guard(); value = original['value']; req = value['request']
        a.validate_request(req, domain='native')
        need(encoded(value) == encoded(p.context(value['configuration'], req, domain='native')), 'V5.2 native original context')
        need(all(value['configuration'][k] == reader.configuration['provider'][k] for k in ('project','bucket')),
             'V5.2 native cleanup control location')
        self.reader = reader; self.original = deepcopy(value); self.closed = False
        self.policy = w.Policy(value['configuration'], req, role='cleanup', previous_cost=None, cost=None, wall=time.time)
        self.lock = threading.RLock(); self.deadline = math.inf
        self.calls = self.writes = self.deletes = 0; self.log = log
        super().__init__(transport=_NativeGate(self, reader.transport), tokens=reader.tokens, clock=time.monotonic)

    def validate_adapter(self):
        need(not self.closed and type(self.reader) is r.NetworkReader, 'V5.2 native cleanup closed/reader')
        self.reader.guard()
        need(type(self.transport) is _NativeGate and self.transport.api is self and
             type(self.transport.server) is h.Network and self.transport.server is self.reader.transport and
             type(self.tokens) is credentials.NetworkCredentials and self.tokens is self.reader.tokens and
             self.clock is time.monotonic and self.reader.role in ('manual','schedule') and
             self.policy.role == 'cleanup' and self.policy.domain == 'native' and
             encoded(self.policy.context()) == encoded(self.original), 'V5.2 native cleanup adapter changed')

    def close(self):
        self.closed = True; self.token = None; self.expires = 0
        # The factory owns the Reader, including the shared transport and tokens.


def control(reader, expected):
    observed = {name: reader.object(name) for name in ('ledger','lease')}
    need(encoded(observed) == encoded(expected), 'V5.2 cleanup control generation changed')
    return observed


def reconcile_native(source, output, *, role='manual'):
    """No injected request, token, transport, clock, or stored PASS opens deletion."""
    need(role in ('manual','schedule'), 'V5.2 cleanup role')
    output = Path(output)
    need(not any(p.is_symlink() for p in (output,*output.parents)), 'V5.2 cleanup output symlink')
    output.mkdir(parents=True, exist_ok=False)
    reader = api = None; phase = 'source'
    try:
        cfg = r.source_configuration(source); phase = 'credentials'
        reader = r.NetworkReader(cfg, source, role, dict(os.environ), output/'reads', r._NATIVE)
        phase = 'preflight'; observations = r.collect(reader, wall=time.time)
        preflight = f.evaluate(cfg, source, role, observations, now=int(time.time()))
        artifacts.save(output/'observations.json', observations); artifacts.save(output/'preflight.json', preflight)
        need(preflight['status'] == 'PREFLIGHT_OBSERVED_NOT_ADMITTED', 'V5.2 cleanup preflight rejected')
        phase = 'control'; original = control(reader, observations['controlAfter'])
        ledger = original['ledger']; lease = original['lease']
        view = a.inspect_ledger(ledger['value'] if ledger else a.empty_ledger(domain='native'), domain='native')
        pending = [row for row in view['attempts'].values() if row['status'] == 'PENDING']
        decision = int(time.time())
        result = dict(status='PASS', scope='native-v52-cleanup-only', activeLease=lease is not None,
                      fullRemoteQualification=False, paidCloud=True)
        if lease is None:
            need(not pending, 'V5.2 orphan pending reservation')
        else:
            value = lease['value']; req = value['request']; sha = a.validate_request(req, domain='native')
            row = view['attempts'].get(sha)
            need(not pending or len(pending) == 1 and pending[0]['request'] == req, 'V5.2 cleanup pending owner mismatch')
            need(row is not None and row['request'] == req or not any(v['attempted'] for v in value['resources']),
                 'V5.2 cleanup reservation missing')
            if value['phase'] != 'CLEANING' and decision < value['expiresAt']+value['graceSeconds']:
                result.update(status='WAITING', expiresAt=value['expiresAt'], graceSeconds=value['graceSeconds'])
            else:
                phase = 'original-context'; context = reader.original_context(lease)
                artifacts.save(output/'original-context.json', context)
                phase = 'final-source'
                need(encoded(r.source_configuration(source)) == encoded(cfg), 'V5.2 cleanup source/configuration changed')
                reader.tokens.recheck(time.monotonic()+30)
                need(f.evaluate(cfg, source, role, observations, now=int(time.time()))['status'] ==
                     'PREFLIGHT_OBSERVED_NOT_ADMITTED', 'V5.2 cleanup observation no longer current')
                control(reader, original); phase = 'reconciliation'
                with (output/'exchanges.jsonl').open('xb') as log:
                    api = NativeCleanupApi(reader, context, log, _CAPABILITY)
                    store = p.Store(context['value']['configuration'], api)
                    provider = p.reconstruct(store, req)
                    decision = int(time.time())
                    result = c.reconcile(store, provider, trigger=credentials.ROLES[role][2], now=decision)
                artifacts.save(output/'reconciliation.json', result)
        phase = 'final-observation'
        if api is None: control(reader, original)
        final = {name: reader.object(name) for name in ('ledger','lease')}
        if result['status'] == 'PASS':
            need(final['lease'] is None, 'V5.2 cleanup final lease not absent')
            state = a.inspect_ledger(final['ledger']['value'] if final['ledger'] else a.empty_ledger(domain='native'),domain='native')
            need(not any(v['status']=='PENDING' for v in state['attempts'].values()), 'V5.2 cleanup final reservation pending')
        phase = 'final-source'
        need(encoded(r.source_configuration(source)) == encoded(cfg), 'V5.2 cleanup source/configuration changed')
        reader.tokens.recheck(time.monotonic()+30)
        token = reader.tokens.receipt()
        f.credential_receipt(token,reader.context['credentialSelection'],source,reader.execution)
        result.update(schema='gse-v52-native-cleanup-v1', source=source, role=role, trigger=credentials.ROLES[role][2],
            checkedAt=int(time.time()), decisionAt=decision, context=reader.context, credentials=token,
            originalRequestSha256=a.validate_request(lease['value']['request'],domain='native') if lease else None,
            observationsSha256=digest(encoded(observations)), controlBefore=original, controlAfter=final,
            providerWrites=api.writes if api else 0, resourceDeletesSubmitted=api.deletes if api else 0,
            deletionPathExercised=bool(api and api.deletes and result['status']=='PASS'),
            paidAdmission=False, effectiveIamQualified=False, fullRemoteQualification=False)
        artifacts.save(output/'receipt.json', result)
        return result
    except BaseException as error:
        failure = dict(status='FAIL', phase=phase, code='V52_CLEANUP_'+phase.upper().replace('-','_')+'_REJECTED',
                       errorType=type(error).__name__, paidAdmission=False, fullRemoteQualification=False)
        if type(error) is h.ApiError: failure['httpStatus'] = error.status
        if type(error) in (credentials.ContextError,exchange.CredentialError): failure['credentialCode'] = error.reason_code
        artifacts.save(output/'failure.json', failure)
        raise
    finally:
        if api is not None: api.close()
        if reader is not None: reader.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--role', choices=('manual','schedule'), default='manual'); args = parser.parse_args()
    try:
        result = reconcile_native(args.source,args.output,role=args.role)
    except Exception:
        print('{"status":"FAIL","code":"V52_CLEANUP_REJECTED"}'); raise SystemExit(2)
    print(encoded({k:result[k] for k in ('status','role','resourceDeletesSubmitted','deletionPathExercised','fullRemoteQualification')}).decode())
    raise SystemExit(0 if result['status'] in ('PASS','WAITING') else 2)

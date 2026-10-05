"""Ordinary thirteen-resource HTTP lifecycle and fresh-process cleanup replay."""
import argparse
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from . import cloud_experiment_resources as r, cloud_topology_qualification as topology
from . import cloud_cleanup_qualification as retained, cloud_cleanup_entry_qualification as entries
from . import cloud_native_authority as n, cloud_gcp as g, cloud_cleanup as cleanup
from . import performance_model as m, remote_command as c

COST = 5_000_000  # Synthetic qualification reservation, never a current cloud quote.
CASES = ('complete', 'async-delete', 'timed-vms-absent', 'lost-lease', 'lost-ledger', 'lost-context', 'lost-plan',
         *('lost-insert-'+str(i) for i in range(1, 14)),
         *('lost-identity-'+str(i) for i in range(1, 14)),
         'lost-intent', 'image-drift', 'pending-operation', 'reused-instance', 'missing-context',
         'delete-denied', 'deadline', 'completion-loss')


def fixture(source='c'*40):
    old, clock, http, reader, _ = topology.fixture(source)
    cfg = old['configuration']['provider']; guest = old['guestAccess']
    inputs = dict(source=source, archiveSha256='1'*64, buildManifestSha256='2'*64,
                  packageManifestSha256='3'*64, workloadSha256=r.workload.PLAN_SHA256, pricesSha256='4'*64)
    req = n.request(source, inputs['archiveSha256'], g.config(cfg), 'b'*32, guest['attempt'],
                    'experiment', now=clock.wall(), guest_access_sha256=m.sha(m.canonical(guest)))
    value = r.make(cfg, req, guest, old['before']['ledger'], inputs, now=clock.wall(), maximum_cost=COST)
    api = r.OfflineApi(value, clock.wall(), transport=http, tokens=lambda _: 'offline-token', clock=clock.seconds)
    return value, clock, http, reader, api


def inject(name, clock, http):
    send = http.send
    target = int(name.rsplit('-', 1)[1]) if name.startswith(('lost-insert-', 'lost-identity-')) else None
    def wrapped(method, url, *args):
        result = send(method, url, *args)
        if method != 'POST': return result
        path = urlsplit(url).path
        if path.startswith('/compute/'):
            if name == 'pending-operation' and http.inserts == 11:
                op = next(reversed(http.operations.values())); op.update(status='RUNNING'); op.pop('targetId')
                raise ConnectionError('offline pending original operation')
            if name == 'deadline' and http.inserts == 11: clock.sleep(601)
            if name.startswith('lost-insert-') and http.inserts == target:
                raise ConnectionError('offline original insert response lost')
        else:
            from urllib.parse import parse_qs
            key = parse_qs(urlsplit(url).query)['name'][0]
            value = m.strict_json(args[1])
            if name in ('lost-lease', 'lost-ledger', 'lost-context', 'lost-plan') and (
                    key == n.LEASE if name == 'lost-lease' else
                    key == n.LEDGER if name == 'lost-ledger' else
                    key.endswith('/cleanup-context.json') if name == 'lost-context' else key.endswith('/resource-plan.json')):
                raise ConnectionError('offline authority upload response lost')
            if key == n.LEASE:
                ids = sum(row['id'] is not None for row in value['resources'])
                attempted = sum(row['attempted'] for row in value['resources'])
                if name.startswith('lost-identity-') and ids == target or name == 'lost-intent' and attempted == 1:
                    raise ConnectionError('offline durable lease response lost')
        return result
    http.send = wrapped
    if name == 'image-drift': http.fault = 'image-drift'
    return send


def replay(cfg, source, saved, output, now, trigger='manual'):
    """New interpreter receives only original retained provider bytes and context."""
    output = Path(output)
    invocation = entries.fixture(cfg, trigger)
    invocation.update(source=source, checkout=source)
    invocation['env'].update(GITHUB_SHA=source, GITHUB_WORKFLOW_SHA=source)
    invocation['observation']['head_sha'] = source
    c.write_once(output.with_suffix('.input.json'), saved)
    c.write_once(output.with_suffix('.invocation.json'), invocation)
    done = subprocess.run([sys.executable, '-m', 'scripts.v51.cloud_cleanup_entry_qualification',
        'offline-replay', str(output.with_suffix('.input.json')), str(output.with_suffix('.invocation.json')),
        str(output), '--now', str(now), '--integrated'], capture_output=True, timeout=30)
    output.with_suffix('.stdout').write_bytes(done.stdout); output.with_suffix('.stderr').write_bytes(done.stderr)
    m.need(done.returncode == 0, 'resource cleanup replay process: '+output.name)
    return c.read(output/'receipt.json'), c.read(output/'state.json'), c.read(output/'http.json')


def qualify(output, source):
    root = Path(output); root.mkdir(parents=True, exist_ok=False); cases = []
    for name in CASES:
        out = root/name; out.mkdir()
        value, clock, http, reader, api = fixture(source)
        send = inject(name, clock, http)
        prepared = r.prepare(value, api, out/'prepare', now=clock.wall(), sleep=clock.sleep)
        failed = name.startswith('lost-') or name in ('image-drift', 'pending-operation', 'deadline')
        m.need(prepared['status'] == ('FAIL' if failed else 'RESOURCES_PREPARED'), 'resource preparation result: '+name)
        if failed:
            phase = (name.removeprefix('lost-') if name in ('lost-lease', 'lost-ledger', 'lost-context', 'lost-plan', 'lost-intent') else
                     'identity' if name.startswith('lost-identity-') else 'insert')
            error_type = 'ValueError' if name in ('image-drift', 'deadline') else 'ConnectionError'
            m.need(prepared['failure'] == dict(phase=phase, type=error_type), 'resource unrelated preparation failure: '+name)
        expected_inserts = (int(name.rsplit('-', 1)[1]) if name.startswith(('lost-insert-', 'lost-identity-')) else
                            0 if name in ('lost-lease', 'lost-ledger', 'lost-context', 'lost-plan', 'lost-intent') else
                            4 if name == 'image-drift' else 11 if name in ('pending-operation', 'deadline') else 13)
        inserts = [v for v in http.requests if v['method'] == 'POST' and v['path'].startswith('/compute/')]
        m.need(http.inserts == len(inserts) == expected_inserts and
               len({v['query']['requestId'] for v in inserts}) == expected_inserts, 'resource insertion replay/count: '+name)
        http.send = send; http.fault = None
        before = deepcopy(http.resources)
        for vm in (v for v in before.values() if 'machineType' in v):
            m.need(vm['scheduling']['instanceTerminationAction'] == 'DELETE' and vm['serviceAccounts'] == [] and
                   vm['networkInterfaces'][0]['accessConfigs'] == [], 'ordinary private experiment VM profile')
        if name in ('async-delete', 'delete-denied'): http.fault = name
        if name == 'timed-vms-absent':
            http.resources = {k: v for k, v in http.resources.items() if 'machineType' not in v}
        if name == 'reused-instance':
            next(v for v in http.resources.values() if 'machineType' in v)['id'] = '999999999'
        if name == 'missing-context': del http.objects[cleanup.context_key(api.req, authority=n)]
        saved = retained.snapshot(http)
        if name == 'complete':
            for label, now in (('active', api.lease['startedAt']), ('grace', api.lease['expiresAt']+1079)):
                observed, after, calls = replay(api.cfg, source, saved, out/label, now)
                m.need(observed['status'] == 'WAITING' and after == saved and all(v['method'] == 'GET' for v in calls),
                       'resource active/grace must remain untouched')
        eligible = api.lease['expiresAt']+api.lease['graceSeconds']
        if name == 'completion-loss':
            # Persisted completion + lost reply: a new reconciler must reuse it.
            from . import cloud_native_cleanup as native
            local_clock, model, transport, _ = retained.restore(saved)
            original = model.send
            def lose_completion(method, url, *args):
                result = original(method, url, *args)
                if method == 'POST' and 'completion.json' in url: raise ConnectionError('lost completed upload')
                return result
            model.send = lose_completion
            first = native.reconcile(api.cfg, transport, out/'first-cleanup', trigger='manual', now=eligible)
            m.need(first['status'] == 'FAIL' and n.LEASE in model.objects, 'completion interruption must retain lease')
            saved = retained.snapshot(model)
        result, after, calls = replay(api.cfg, source, saved, out/'manual', eligible)
        blocked = name in ('lost-intent', 'image-drift', 'pending-operation', 'reused-instance', 'missing-context', 'delete-denied')
        m.need(result['status'] == ('FAIL' if blocked else 'PASS'), 'resource cleanup result: '+name)
        _, model, transport, _ = retained.restore(after)
        store = g.Store(api.cfg, transport, authority=n); ledger = store.get(n.LEDGER)[1]
        total, attempts = n.inspect_ledger(ledger)
        charged = name != 'lost-lease'
        m.need(total == topology.PRIOR_COST+(COST if charged else 0) and
               ledger['entries'][:2] == value['baseline'][1]['entries'], 'resource reservation/history changed')
        deletes = [v for v in calls if v['method'] == 'DELETE' and v['path'].startswith('/compute/')]
        m.need(all(v['path'].rsplit('/', 1)[1] in {r['id'] for r in before.values()} for v in deletes), 'resource foreign deletion')
        m.need(not any(v['method'] == 'POST' and v['path'].startswith('/compute/') for v in calls), 'cleanup submitted insertion')
        if blocked:
            m.need(n.LEASE in model.objects, 'unresolved resource released lease')
            if name == 'reused-instance': m.need(any(v['id'] == '999999999' for v in model.resources.values()), 'replacement deleted')
        else:
            m.need(not model.resources and n.LEASE not in model.objects, 'resource cleanup incomplete')
            if charged: m.need(attempts[n.validate_request(api.req)]['status'] == 'FAIL', 'interrupted experiment marked successful')
        if name == 'complete':
            scheduled, scheduled_after, _ = replay(api.cfg, source, saved, out/'schedule', eligible, 'schedule')
            m.need(scheduled['status'] == 'PASS' and not scheduled_after['resources'] and
                   n.LEASE not in scheduled_after['objects'] and
                   scheduled_after['objects'][n.LEDGER] == after['objects'][n.LEDGER], 'resource trigger divergence')
        cases.append(dict(case=name, status='PASS', preparation=prepared['status'], cleanup=result['status'],
                          insertRequests=http.inserts, numericDeleteRequests=len(deletes), retainedCostMicrousd=total))
        print(m.canonical(cases[-1]).decode(), flush=True)
    result = dict(schema='gse-v51-experiment-resource-qualification-v1', status='PASS', source=source,
                  execution=r.EXECUTION, cases=cases, **r.FLAGS)
    c.write_once(root/'receipt.json', result); print(m.canonical(result).decode()); return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('output', type=Path)
    parser.add_argument('--source', required=True); args = parser.parse_args()
    qualify(args.output, args.source)

"""Fresh-process, no-network qualification of retained cleanup reconstruction."""
import argparse
import base64
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from . import cloud_authority as a, cloud_cleanup as c, cloud_fake, cloud_gcp as g, cloud_http_fake as f, performance_model as m
from .cloud_http import Api
from .remote_command import write_once

SCHEMA = 'gse-v51-offline-cleanup-state-v1'
KEY = 'ssh-ed25519 '+base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'+bytes(range(32))).decode()
CASES = ('no-lease', 'active', 'grace', 'expired-schedule', 'expired-manual', 'empty-reservation',
         'missing-context', 'changed-context', 'missing-reservation', 'lost-insert-ack',
         'pending-insert', 'missing-operation', 'reused-name', 'delete-denied')


def snapshot(http):
    return dict(schema=SCHEMA, configuration=deepcopy(http.configuration),
                objects={key: dict(generation=gen, data=base64.b64encode(raw).decode(), contentType=content)
                         for key, (gen, raw, content) in http.objects.items()},
                resources=deepcopy(http.resources), operations=deepcopy(http.operations), serial=http.serial,
                fault=http.fault)


def restore(value):
    m.need(value['schema'] == SCHEMA, 'offline cleanup fixture schema')
    clock = cloud_fake.Clock(); http = f.Http(value['configuration'], value['fault'])
    http.objects = {key: (row['generation'], base64.b64decode(row['data'], validate=True), row['contentType'])
                    for key, row in value['objects'].items()}
    http.resources, http.operations, http.serial = deepcopy(value['resources']), deepcopy(value['operations']), value['serial']
    api = Api(transport=http, tokens=lambda timeout: 'offline-token', clock=clock.seconds)
    return clock, http, api, g.Store(value['configuration'], api)


def interrupted(*, ssh=True, allocate=True):
    req, _, approval, clock, http, store, original = f.fixture()
    guest = dict(attempt=req['attempt'], user='gse-'+req['attempt'][:24], publicKey=KEY) if ssh else None
    if guest is not None:
        req.update(schema='gse-v51-cloud-request-v2', guestAccessSha256=m.sha(m.canonical(guest)))
    provider = g.Compute(http.configuration, req, original.api, guest_access=guest, sleep=clock.sleep)
    lease = a.lease(req, clock.wall())
    generation = store.put(a.LEASE, lease, 0)
    store.put(a.LEDGER, a.reserve(a.empty_ledger(), req, approval), 0)
    if allocate:
        c.retain_context(store, req, provider.cleanup_context())
        for row in lease['resources']:
            row['attempted'] = True; generation = store.put(a.LEASE, lease, generation)
            row['id'] = provider.create(row['spec'], clock.nanos()+30*10**9)['id']
            generation = store.put(a.LEASE, lease, generation)
    return req, lease, http


def rewrite(http, key, change):
    generation, raw, content = http.objects[key]
    value = m.strict_json(raw); change(value)
    http.objects[key] = generation+1, m.canonical(value), content


def case_state(case):
    req, lease, http = interrupted(allocate=case != 'empty-reservation')
    boundary = lease['expiresAt']+lease['graceSeconds']
    now = lease['startedAt'] if case == 'active' else boundary-1 if case == 'grace' else boundary
    trigger = 'schedule' if case == 'expired-schedule' else 'manual'
    if case == 'no-lease': http.objects.clear(); http.resources.clear(); http.operations.clear()
    elif case == 'missing-context': del http.objects[c.context_key(req)]
    elif case == 'changed-context': rewrite(http, c.context_key(req), lambda value: value.update(requestSha256='0'*64))
    elif case == 'missing-reservation': del http.objects[a.LEDGER]
    elif case == 'lost-insert-ack': rewrite(http, a.LEASE, lambda value: value['resources'][-1].update(id=None))
    elif case == 'pending-insert': next(iter(http.operations.values())).update(status='RUNNING')
    elif case == 'missing-operation': http.operations.pop(next(iter(http.operations)))
    elif case == 'reused-name': next(iter(http.resources.values())).update(id='99999999')
    elif case == 'delete-denied': http.fault = 'delete-denied'
    return snapshot(http), now, trigger


def replay(state, output, trigger, now):
    _, http, api, _ = restore(state)
    result = c.reconcile(state['configuration'], api, output, trigger=trigger, now=now)
    output = Path(output)
    write_once(output/'http.json', http.requests)
    write_once(output/'state.json', snapshot(http))
    return result


def qualify(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False); rows = []
    for case in CASES:
        state, now, trigger = case_state(case)
        root = output/case; root.mkdir(); write_once(root/'input.json', state)
        command = [sys.executable, '-m', 'scripts.v51.cloud_cleanup_qualification', 'offline-replay',
                   str(root/'input.json'), str(root/'replay'), '--trigger', trigger, '--now', str(now)]
        done = subprocess.run(command, capture_output=True, timeout=30)
        (root/'stdout').write_bytes(done.stdout); (root/'stderr').write_bytes(done.stderr)
        m.need(done.returncode == 0, 'fresh-process cleanup replay: '+case)
        result = m.strict_json((root/'replay/receipt.json').read_bytes())
        after = m.strict_json((root/'replay/state.json').read_bytes())
        calls = m.strict_json((root/'replay/http.json').read_bytes())
        expected = ('WAITING' if case in ('active', 'grace') else 'PASS' if case in
                    ('no-lease', 'expired-schedule', 'expired-manual', 'empty-reservation', 'lost-insert-ack') else 'FAIL')
        m.need(result['status'] == expected, 'cleanup case outcome: '+case)
        compute = [v for v in calls if v['path'].startswith('/compute/')]
        m.need(all(v['method'] != 'POST' for v in compute), 'cleanup allocated resources')
        m.need(all(v['path'].rsplit('/', 1)[-1].isdecimal() for v in compute if v['method'] == 'DELETE'), 'cleanup used resource name')
        if case in ('no-lease', 'active', 'grace', 'missing-context', 'changed-context', 'missing-reservation'):
            m.need(after == state and all(v['method'] == 'GET' for v in calls), 'blocked cleanup mutated authority')
        if case != 'no-lease' and case != 'missing-reservation':
            _, _, _, store = restore(after)
            total, attempts = a.inspect_ledger(store.get(a.LEDGER)[1])
            m.need(total == 1_000_000, 'cleanup lost failed charge')
            if expected == 'PASS':
                m.need(not after['resources'] and store.get(a.LEASE) is None and
                       all(v['status'] == 'FAIL' for v in attempts.values()), 'cleanup incorrectly accepted workload/released state')
            else: m.need(store.get(a.LEASE) is not None, 'unsafe lease release')
        row = dict(case=case, status='PASS', observed=expected, requests=len(calls),
                   resourceDeletes=sum(v['method'] == 'DELETE' for v in compute))
        rows.append(row); print(m.canonical(row).decode(), flush=True)
    receipt = dict(schema='gse-v51-cleanup-qualification-v1', status='PASS', execution='offline-provider-cleanup',
                   source=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                   dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True)),
                   inputs={p.name: m.sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('cloud_*.py'))},
                   paidCloud=False, fullRemoteQualification=False, cleanupReady=False, cases=rows)
    write_once(output/'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('qualify'); check.add_argument('output', type=Path)
    child = sub.add_parser('offline-replay'); child.add_argument('state', type=Path); child.add_argument('output', type=Path)
    child.add_argument('--trigger', choices=('schedule', 'manual'), required=True); child.add_argument('--now', type=int, required=True)
    args = parser.parse_args()
    if args.command == 'qualify': qualify(args.output)
    else: replay(m.strict_json(args.state.read_bytes()), args.output, args.trigger, args.now)

"""Offline topology preparation and fresh-process expired cleanup qualification."""
import argparse
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from . import cloud_topology_fixture as f, cloud_preflight_qualification as preflight
from . import cloud_fake, cloud_http_fake, cloud_http as h, cloud_native_authority as n
from . import cloud_cleanup_qualification as q, cloud_cleanup_entry_qualification as entries
from . import cloud_cleanup_observation as observation, cloud_cleanup as cleanup
from . import performance_model as m, remote_command as c

CASES = ('full-topology', 'async-delete', 'lost-firewall', 'lost-boot', 'lost-instance', 'pending-instance',
         'reused-instance', 'delete-denied', 'missing-context', 'generation-conflict',
         'retention-failure', 'image-drift')
PRIOR_COST = 1_000_000


def fixture(source='c'*40):
    cfg, _, provider = preflight.fixture(); clock = cloud_fake.Clock(); http = cloud_http_fake.Http(cfg['provider'])
    reader = h.Api(transport=http, tokens=lambda _: 'offline-token', clock=clock.seconds)
    store = f.g.Store(cfg['provider'], reader, authority=n)
    old = n.request(source, 'a'*64, f.g.config(cfg['provider']), 'd'*32, 'e'*32, 'experiment',
                    now=clock.wall(), guest_access_sha256='f'*64)
    ledger = n.reserve(n.empty_ledger(), old, dict(previousCostMicrousd=0, maximumCostMicrousd=PRIOR_COST))
    ledger = n.finish(ledger, old, dict(requestSha256=n.validate_request(old), status='FAIL'))
    store.put(n.LEDGER, ledger, 0)
    before = observation.capture(cfg, source, api=reader, wall=clock.wall)
    provider.update(startedAt=clock.wall(), completedAt=clock.wall())
    provider['observations']['principal'] = 'operator@example.com'
    prices = dict(observedAt=clock.wall(), expiresAt=clock.wall()+86400, region='us-west4', diskType='pd-balanced',
        machineType='n2-standard-8', vmMicrousdPerHour=500000, diskMicrousdPerGiBHour=200,
        pricedThroughSeconds=7200, otherCostsMicrousd=dict(requests=10000, retention30Days=10000,
        actions=10000, failureOverhang=100000), sources=['https://cloud.google.com/compute/disks-image-pricing'])
    value = f.make(cfg, source, 'operator@example.com', q.KEY, prices, before, provider,
        now=clock.wall(), attempt='a'*32, sequence='b'*32, offline=True)
    api = f.PreparationApi(value, clock.wall(), transport=http, tokens=lambda _: 'offline-token', clock=clock.seconds)
    return value, clock, http, reader, api


def qualify(output, source):
    root = Path(output); root.mkdir(parents=True, exist_ok=False); cases = []
    for name in CASES:
        out = root/name; out.mkdir(); value, clock, http, reader, api = fixture(source)
        req = value['request']; send = http.send
        target = {'lost-firewall': 1, 'lost-boot': 5, 'lost-instance': 11, 'pending-instance': 11}.get(name)
        if target:
            def lose(method, url, *args):
                result = send(method, url, *args)
                if method == 'POST' and 'compute.googleapis.com' in url and http.inserts == target:
                    if name == 'pending-instance':
                        op = next(reversed(http.operations.values())); op.update(status='RUNNING'); op.pop('targetId')
                    raise ConnectionError('offline lost original insert response')
                return result
            http.send = lose
        if name == 'image-drift': http.fault = 'image-drift'
        prepared = f.execute(value, api, out/'prepare', now=clock.wall(), sleep=clock.sleep)
        m.need(prepared['status'] == ('FAIL' if target or name == 'image-drift' else 'PREPARED'), 'topology preparation outcome')
        http.send = send; http.fault = None
        m.need(http.inserts == (target or (4 if name == 'image-drift' else 13)), 'topology insert count')
        original = deepcopy(http.resources)
        if name == 'full-topology':
            for resource in http.resources.values():
                if 'machineType' in resource:
                    m.need(resource['scheduling']['instanceTerminationAction'] == 'STOP', 'fixture VM would disappear before cleanup')
                    resource['status'] = 'TERMINATED'  # Model the provider's timed stop, not a cloud observation.
        if name == 'reused-instance':
            next(r for r in http.resources.values() if 'machineType' in r)['id'] = '999999999'
        if name in ('delete-denied', 'async-delete'): http.fault = name
        if name == 'missing-context': del http.objects[cleanup.context_key(req, authority=n)]
        if name in ('generation-conflict', 'retention-failure'):
            # Hook exercised in-process below; fresh-process reconstruction is used by all other cases.
            def block(method, path, query, body):
                if method == 'POST' and (query.get('name') == n.LEASE if name == 'generation-conflict'
                    else query.get('name', '').endswith('/completion.json')): return 412, b''
            http.hook = block
        saved = q.snapshot(http); c.write_once(out/'input.json', saved)
        expected = 'PASS' if name in ('full-topology', 'async-delete', 'lost-firewall', 'lost-boot', 'lost-instance') else 'FAIL'
        # A rejected boot insert never has an original Compute operation, so the
        # retained intent remains unresolved. Do not fabricate absence authority.
        for trigger in ('manual', 'schedule'):
            destination = out/trigger
            invocation = entries.fixture(value['configuration']['provider'], trigger)
            invocation.update(source=source, checkout=source)
            invocation['env'].update(GITHUB_SHA=source, GITHUB_WORKFLOW_SHA=source)
            invocation['observation']['head_sha'] = source
            c.write_once(out/(trigger+'-invocation.json'), invocation)
            if name in ('generation-conflict', 'retention-failure'):
                from . import cloud_native_cleanup as native
                local_clock, model, transport, _ = q.restore(saved); model.hook = block
                result = native.reconcile(value['configuration']['provider'], transport, destination,
                                          trigger=trigger, now=clock.wall()+6480)
                after = q.snapshot(model); calls = model.requests
                c.write_once(destination/'state.json', after); c.write_once(destination/'http.json', calls)
            else:
                command = [sys.executable, '-m', 'scripts.v51.cloud_cleanup_entry_qualification', 'offline-replay',
                    str(out/'input.json'), str(out/(trigger+'-invocation.json')), str(destination),
                    '--now', str(clock.wall()+6480), '--integrated']
                done = subprocess.run(command, capture_output=True, timeout=30)
                (out/(trigger+'.stdout')).write_bytes(done.stdout); (out/(trigger+'.stderr')).write_bytes(done.stderr)
                m.need(done.returncode == 0, 'topology cleanup process failed: '+name+'/'+trigger)
                result = c.read(destination/'receipt.json'); after = c.read(destination/'state.json'); calls = c.read(destination/'http.json')
            m.need(result['status'] == expected, 'topology cleanup outcome: '+name+'/'+trigger)
            _, restored, transport, _ = q.restore(after)
            store = f.g.Store(value['configuration']['provider'], transport, authority=n)
            ledger = store.get(n.LEDGER)[1]; total, attempts = n.inspect_ledger(ledger)
            m.need(total == PRIOR_COST+f.COST and ledger['entries'][:2] == value['before']['ledger'][1]['entries'], 'topology erased history/cost')
            deletes = [r for r in calls if r['method'] == 'DELETE' and r['path'].startswith('/compute/')]
            ids = {v['id'] for v in original.values()}
            m.need(all(r['path'].rsplit('/', 1)[1] in ids for r in deletes), 'topology deleted foreign identity')
            m.need(not any(r['method'] == 'POST' and r['path'].startswith('/compute/') for r in calls), 'cleanup allocated resource')
            if expected == 'PASS':
                m.need(not after['resources'] and n.LEASE not in after['objects'] and
                       attempts[n.validate_request(req)]['status'] == 'FAIL', 'topology terminal cleanup')
                m.need(len(deletes) == len(original), 'missing actual numeric deletes')
                kinds = [r['path'].split('/')[-2] for r in deletes]
                m.need(kinds == sorted(kinds, key={'instances': 0, 'disks': 1, 'firewalls': 2}.get), 'topology dependency deletion order')
            else:
                m.need(n.LEASE in after['objects'], 'unresolved topology released lease')
                if name == 'reused-instance': m.need(any(v['id'] == '999999999' for v in after['resources'].values()), 'replacement was deleted')
            cases.append(dict(case=name, trigger=trigger, status='PASS', observed=expected, insertRequests=http.inserts,
                              numericDeleteRequests=len(deletes), retainedCostMicrousd=total))
    result = dict(status='PASS', execution='offline-topology-cleanup-qualification', source=source,
                  cases=cases, paidCloud=False, applied=False, **f.BOUNDARY)
    c.write_once(root/'receipt.json', result); print(m.canonical(result).decode()); return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('output', type=Path)
    parser.add_argument('--source', required=True); args = parser.parse_args(); qualify(args.output, args.source)

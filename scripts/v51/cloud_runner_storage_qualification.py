"""No-network storage lifecycle qualification and fresh-process cleanup replay."""
import argparse
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote
from . import cloud_runner_storage as s, cloud_native_authority as n, cloud_gcp as g
from . import cloud_http_fake as f, cloud_fake, cloud_cleanup_qualification as c, performance_model as m
from .remote_command import write_once

CASES = ('healthy', 'lost-acquire', 'lost-reserve', 'lost-create', 'lost-report',
         'lost-complete', 'lost-finish', 'lost-release', 'lost-create-readback')


class Http(f.Http):
    """Independent namespace ACL double; generation checks precede IAM checks.

    Deliberately model 412 before 403 so wrong-generation probes cannot pass.
    The double cannot establish the effective permissions of a cloud identity.
    """
    def __init__(self, cfg, req, fault=None, *, denial=403, allow=()):
        super().__init__(cfg)
        self.req, self.keys, self.inject = req, s.inventory(req), fault
        self.denial, self.allow, self.lost = denial, set(allow), False
        self.hook = self.intercept

    def intercept(self, method, parsed, query, body):
        m.need(parsed.hostname == 'storage.googleapis.com', 'storage qualification attempted Compute')
        key = query['name'] if method == 'POST' else unquote(parsed.path.split('/o/', 1)[1])
        current = self.objects.get(key)
        if 'ifGenerationMatch' in query and int(query['ifGenerationMatch']) != (current[0] if current else 0):
            return 412, b''
        denied = not key.startswith(n.PREFIX)
        if method in ('POST', 'DELETE') and key not in (n.LEASE, n.LEDGER):
            denied = (not key.startswith(n.PREFIX+'attempts/') or method == 'DELETE' or current is not None)
        if denied and (method, key) not in self.allow: return self.denial, b''
        action = None
        if method == 'DELETE' and key == n.LEASE: action = 'release'
        if method == 'POST':
            value = m.strict_json(body)
            if key == n.LEASE: action = 'acquire'
            elif key == n.LEDGER: action = 'reserve' if value['entries'][-1]['kind'] == 'RESERVED' else 'finish'
            else: action = {self.keys[k]: v for k, v in [('created', 'create'), ('report', 'report'), ('completion', 'complete')]}.get(key)
        if not self.lost and self.inject == 'lost-'+str(action):
            self.storage(method, parsed.path, query, body, 'application/json')
            self.lost = True
            raise ConnectionError('injected lost '+action+' response')
        if (not self.lost and self.inject == 'lost-create-readback' and method == 'GET'
                and key == self.keys['created'] and current is not None):
            self.lost = True
            raise ConnectionError('injected created object readback interruption')
        return None


def fixture(fault=None, *, denial=403, allow=(), ledger_present=True):
    cfg = f.configuration(); clock = cloud_fake.Clock()
    req = n.request('1'*40, '2'*64, g.config(cfg), '3'*32, '4'*32, 'experiment', now=clock.wall(), guest_access_sha256='5'*64)
    http = Http(cfg, req, fault, denial=denial, allow=allow)
    # Retain a previous failed attempt. A new qualification must never reset it.
    prior = n.request('6'*40, '7'*64, g.config(cfg), '8'*32, '9'*32, 'experiment', now=clock.wall(), guest_access_sha256='a'*64)
    ledger = n.reserve(n.empty_ledger(), prior, dict(previousCostMicrousd=0, maximumCostMicrousd=2_000_000))
    ledger = n.finish(ledger, prior, s.completion(prior))
    baseline = {n.LEDGER: None}
    values = {http.keys[k]: s.canary(req, k) for k in ('existing', 'outside')}
    if ledger_present: values[n.LEDGER] = ledger
    for key, value in values.items():
        http.serial += 1
        http.objects[key] = http.serial, m.canonical(value), 'application/json'
        baseline[key] = (http.serial, deepcopy(value))
    api = s.OfflineApi(cfg, req, baseline, maximum_cost=1_000_000, transport=http, clock=clock.seconds)
    return api, http, clock


def check_state(before, after, api, *, reserved, released):
    m.need(not after['resources'] and not after['operations'], 'storage created provider resources')
    for name in ('existing', 'outside'):
        key = api.keys[name]
        m.need(after['objects'].get(key) == before['objects'][key], 'protected canary changed: '+name)
    _, _, _, store = c.restore(after)
    m.need((store.get(n.LEASE) is None) == released, 'storage lease outcome')
    observed = store.get(n.LEDGER)
    total, attempts = n.inspect_ledger(observed[1])
    previous, _ = n.inspect_ledger(api.original)
    m.need(total == previous+(1_000_000 if reserved else 0), 'storage discarded reserved cost')
    m.need(observed[1]['entries'][:len(api.original['entries'])] == api.original['entries'], 'storage rewrote previous ledger')
    m.need(all(row['status'] == 'FAIL' for row in attempts.values()), 'storage incorrectly passed/pended engine workload')
    if reserved:
        complete = store.get(api.keys['completion'])[1]
        m.need(attempts[api.sha]['status'] == 'FAIL' and complete['engineWorkloadExecuted'] is False and
               complete['fullRemoteQualification'] is False and
               observed[1]['entries'][-1]['completionSha256'] == m.sha(m.canonical(complete)), 'terminal completion binding')


def replay(root, state, trigger, now):
    root.mkdir(parents=True)
    write_once(root/'input.json', state)
    done = subprocess.run([sys.executable, '-m', 'scripts.v51.cloud_cleanup_qualification', 'offline-replay',
                           str(root/'input.json'), str(root/'replay'), '--trigger', trigger, '--now', str(now), '--native'],
                          capture_output=True, timeout=30)
    (root/'stdout').write_bytes(done.stdout); (root/'stderr').write_bytes(done.stderr)
    m.need(done.returncode == 0, 'Runner storage fresh-process cleanup')
    result = m.strict_json((root/'replay/receipt.json').read_bytes())
    after = m.strict_json((root/'replay/state.json').read_bytes())
    calls = m.strict_json((root/'replay/http.json').read_bytes())
    m.need(all('/compute/' not in row['path'] for row in calls), 'storage cleanup used Compute')
    return result, after, calls


def qualify(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    rows = []
    for case in CASES:
        root = output/case; root.mkdir()
        api, http, _ = fixture(case if case != 'healthy' else None)
        before = c.snapshot(http); write_once(root/'before.json', before)
        try:
            value = s.run(api)
        except Exception as error:
            value = dict(status='FAIL', failure=dict(type=type(error).__name__, message=str(error)),
                         execution=s.EXECUTION, paidCloud=False, fullRemoteQualification=False)
        state = c.snapshot(http)
        write_once(root/'original.json', value); write_once(root/'interrupted.json', state); write_once(root/'http.json', http.requests)
        if case == 'healthy':
            m.need(value == dict(s.report(api.req), leaseReleased=True, maximumCostMicrousd=1_000_000),
                   'unexpected storage qualification failure')
        else:
            m.need(value['status'] == 'FAIL' and value['failure']['type'] == 'ConnectionError' and http.lost,
                   'storage fault not observed at original submission')
        mutations = [v for v in http.requests if v['method'] != 'GET']
        fingerprints = [m.sha(m.canonical(v)) for v in mutations]
        m.need(len(fingerprints) == len(set(fingerprints)), 'storage replayed a mutation')
        m.need(all('/compute/' not in v['path'] for v in http.requests), 'storage used Compute')
        reserved = case != 'lost-acquire'
        if case == 'healthy':
            check_state(before, state, api, reserved=True, released=True)
        else:
            boundary = api.lease['expiresAt']+api.lease['graceSeconds']
            for name, now in [('active', api.req['createdAt']), ('grace', boundary-1), ('expired', boundary)]:
                for trigger in ('manual', 'schedule'):
                    result, after, calls = replay(root/(name+'-'+trigger), state, trigger, now)
                    expected = 'PASS' if name == 'expired' or case == 'lost-release' else 'WAITING'
                    m.need(result['status'] == expected, 'storage cleanup boundary')
                    if expected == 'WAITING':
                        m.need(after == state and all(row['method'] == 'GET' for row in calls), 'active/grace storage owner changed')
                    else: check_state(before, after, api, reserved=reserved, released=True)
                    # Cleanup never replaces/deletes any already retained attempt evidence.
                    for key, row in state['objects'].items():
                        if key not in (n.LEASE, n.LEDGER):
                            m.need(after['objects'].get(key) == row, 'cleanup overwrote retained evidence')
        row = dict(case=case, status='PASS', original=value['status'], mutations=len(mutations))
        rows.append(row); print(m.canonical(row).decode(), flush=True)
    receipt = dict(schema=s.SCHEMA, execution=s.EXECUTION, status='PASS', paidCloud=False,
                   objectPermissionsQualified=False, engineWorkloadExecuted=False, fullRemoteQualification=False,
                   source=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                   dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True)),
                   inputs={p.name: m.sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('cloud_*.py'))}, cases=rows)
    write_once(output/'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output', type=Path)
    qualify(parser.parse_args().output)

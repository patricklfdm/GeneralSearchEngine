"""Immediate cleanup of this invocation's failed native preparation.

This is an internal continuation, not an operator cleanup entry. It needs the
original admitted creation API, consumes it once, and re-reads retained CAS
authority. Manual/scheduled cleanup still requires expiry plus operation grace.
No workload success, create replay, refund or paid workflow is implemented here.
"""
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlsplit
from . import cloud_native_cleanup as cleanup, cloud_native_authority as n
from . import cloud_gcp as g, cloud_http as h, cloud_runner as runner
from . import performance_model as m, remote_command as c
from . import cloud_workload_contract as workload

SCHEMA = 'gse-v51-runner-failure-recovery-v1'
FILES = frozenset({'receipt.json', 'inspection.json', 'plan.json', 'http.json', 'admission-http.json',
    'lease-observation.json', 'iap-preparation.json', 'provider-timings.json', 'resources/plan.json', 'resources/receipt.json', 'resources/http.json'} |
    {f'iap/node-{node}{suffix}' for node in (1, 2, 3) for suffix in ('.json', '-probe.json', '.known_hosts')} |
    {f'guest-setup/node-{node}/{name}.json' for node in (1, 2, 3) for name in
     ('request', 'volume', 'package-request', 'package', 'readiness', 'connections')})
MAX_FILE = 8 << 20
MAX_TOTAL = 32 << 20


def evidence(root, *, status='FAIL'):
    """Closed diagnostic inventory; never recursively collect credentials."""
    root = Path(root); files = {}; total = 0
    m.need(root.is_dir() and not root.is_symlink(), 'owner evidence root')
    for name in sorted(FILES):
        path = root/name
        for parent in path.parents:
            if parent == root: break
            m.need(not parent.is_symlink(), 'owner evidence parent symlink')
        m.need(not path.is_symlink(), 'owner evidence file symlink')
        if not path.exists(): continue
        m.need(path.is_file() and path.stat().st_size <= MAX_FILE, 'owner evidence file bound')
        with path.open('rb') as stream: data = stream.read(MAX_FILE+1)
        total += len(data)
        m.need(len(data) <= MAX_FILE and total <= MAX_TOTAL, 'owner evidence total bound')
        files[name] = data
    m.need('receipt.json' in files and m.strict_json(files['receipt.json'])['status'] == status, 'owner original receipt missing')
    return files


class _Api(cleanup._Policy, h.Api):
    execution = 'native-v51-owner-failure'

    def __init__(self, source):
        from .cloud_runner_resources import _Api as CreationApi
        m.need(type(source) is CreationApi and source.gate_open and source.failed and
               not source.failure_claimed and not source.owner_claimed and source.last_lease_write is not None,
               'owner failure requires original consumed creation authority')
        source.failure_claimed = True
        self._initialize(source)

    def _initialize(self, source):
        h.Api.__init__(self, transport=source.transport, tokens=source.tokens, clock=source.clock)
        self.token, self.expires = source.token, source.expires
        self.initialize(source.cfg)
        self.source = source
        self.started = self.clock()
        self.deadline = min(source.owner_deadline, self.started+workload.load()['budgets']['cleanupSeconds'])
        self.mutations = set(); self.requests = []; self.retained = {}; self.verified = set()
        self.expected_completion = None; self.retention_started = False

    def admit(self):
        store = g.Store(self.config, self, authority=n)
        current = store.get(n.LEASE)
        m.need(current is not None, 'owner lease absent; no mutation')
        generation, lease = current
        key, sent, prior = self.source.last_lease_write
        m.need(key == n.LEASE and lease == sent and generation > prior and
               lease['request'] == self.source.req and
               (not self.source.generation or generation >= self.source.generation), 'owner retained lease changed')
        # Shared identity validation, reached only from the original in-memory
        # admission. The public bind() retains its independent expiry check.
        self._bind(lease, generation)
        ledger = store.get(n.LEDGER)
        baseline = self.source.value['baseline']
        expected_old = None if baseline is None else (baseline[0], baseline[1])
        reserved = ledger is not None and ledger[1] == self.source.reserved and ledger[0] > self.source.prior_generation
        m.need(reserved or ledger == expected_old, 'owner ledger changed')
        if any(row['attempted'] for row in lease['resources']):
            m.need(reserved, 'owner attempted resources require retained charge')
            retained = store.get(self.attempt+'cleanup-context.json')
            m.need(retained is not None and retained[1] == self.source.context(), 'owner cleanup context changed')
        return store

    def object_key(self, base):
        for key in self.retained:
            if base == self.objects+quote(key, safe=''): return key
        return super().object_key(base)

    def check(self, method, url, body):
        m.need(self.clock() < self.deadline and self.clock() < self.source.owner_deadline,
               'owner original stage/lease deadline')
        parsed = urlsplit(url); base = parsed._replace(query='').geturl()
        m.need(not self.retention_started or parsed.netloc == 'storage.googleapis.com',
               'owner retention cannot reopen compute cleanup')
        if method == 'POST' and base == self.upload:
            pairs = parse_qsl(parsed.query, strict_parsing=True); query = dict(pairs)
            m.need(len(pairs) == len(query), 'owner duplicate query')
            key = query.get('name')
            if key in self.retained or self.lease is not None and key == self.attempt+'completion.json':
                m.need(query == dict(uploadType='media', name=key, ifGenerationMatch='0'), 'owner immutable retention')
                if key in self.retained:
                    m.need(body == self.retained[key], 'owner evidence changed')
                else:
                    m.need(self.expected_completion is not None and body == self.expected_completion and
                           body.get('status') == 'FAIL' and body.get('engineWorkloadExecuted') is False and
                           body.get('fullRemoteQualification') is False and set(self.retained) == self.verified,
                           'owner completion before evidence read-back')
                    self.completion_value(body)
                return ('object', key, 'upload')
            m.need(key in (n.LEASE, n.LEDGER) and not (self.retention_started and key == n.LEASE),
                   'owner control write outside stage')
        if method == 'DELETE' and parsed.netloc == 'storage.googleapis.com':
            m.need(self.expected_completion is not None and self.completion == self.expected_completion and
                   set(self.retained) == self.verified, 'owner release before retention')
        return super().check(method, url, body)

    def authorize(self, method, url, body):
        self.check(method, url, body)
        if method != 'GET':
            fingerprint = m.sha(m.canonical([method, url, m.sha(body if isinstance(body, bytes) else m.canonical(body))]))
            m.need(fingerprint not in self.mutations, 'owner mutation already submitted; no replay')
            self.mutations.add(fingerprint)

    def observe(self, checked, value):
        kind, key, detail = checked
        if kind == 'object' and key in self.retained and detail.startswith('media:'):
            m.need(value == self.retained[key], 'owner evidence read-back differs')
            self.verified.add(key)
            return
        super().observe(checked, value)

    def request_http(self, method, url, body=None, **kwargs):
        kwargs['deadline'] = min(kwargs['deadline'], self.deadline, self.source.owner_deadline)
        self.requests.append(dict(method=method, url=url, bodySha256=m.sha(body if isinstance(body, bytes) else m.canonical(body))
                                 if body is not None else None))
        return h.Api.call(self, method, url, body, **kwargs)

    def retention(self, files, *, started=None):
        m.need(not self.retention_started and self.lease is not None, 'owner retention stage consumed')
        started = self.clock() if started is None else started
        m.need(self.started <= started <= self.clock(), 'owner retention original start')
        self.retention_started = True
        self.deadline = min(self.source.owner_deadline, started+workload.load()['budgets']['validationRetentionSeconds'])
        self.retained = {self.attempt+'preparation-failure/'+name: data for name, data in files.items()}


def recover(source, root, preparation):
    """Always retain the original failure locally; release only after read-back.

    Shared exact-ID cleanup runs before remote diagnostic retention so a failed
    evidence upload cannot prevent a deletion attempt. Uncertain authority or
    unresolved cleanup keeps the lease for the independent expired reconciler.
    """
    output = Path(root)/'owner-recovery'
    result = dict(schema=SCHEMA, status='FAIL', execution='offline-owner-failure' if source.offline else _Api.execution,
                  paidCloud=not source.offline, engineWorkloadExecuted=False, fullRemoteQualification=False,
                  cleanup=None, retention='INCOMPLETE', leaseReleased=False, errors=[])
    api = None
    try:
        api = _Api(source); store = api.admit()
        lease = deepcopy(api.lease); generation = api.lease_generation
        def persist():
            nonlocal generation
            generation = store.put(n.LEASE, lease, generation)
        result['cleanup'] = runner.cleanup(api.provider, lease, persist, authority=n, redact=True)
        retention_started = api.clock()
        output.mkdir(exist_ok=False)
        c.write_once(output/'cleanup.json', result['cleanup'])
        files = evidence(root)
        m.need(m.strict_json(files['receipt.json']) == preparation and
               preparation['requestSha256'] == api.sha, 'owner original preparation receipt changed')
        files['cleanup.json'] = m.canonical(result['cleanup'])
        files['cleanup-http.json'] = m.canonical(api.requests)
        inventory = [dict(path=name, bytes=len(data), sha256=m.sha(data)) for name, data in sorted(files.items())]
        manifest = dict(schema='gse-v51-preparation-failure-evidence-v1', requestSha256=api.sha, files=inventory)
        files['manifest.json'] = m.canonical(manifest); api.retention(files, started=retention_started)
        for name, data in sorted(files.items()): runner.retain(store, api.attempt+'preparation-failure/'+name, data)
        # This continuation can only finish a failed preparation. A successful
        # package receipt remains PARTIAL in its original entry.
        completion = dict(schema=n.COMPLETION_SCHEMA, execution=n.EXECUTION, paidCloud=True,
            requestSha256=api.sha, status='FAIL', engineWorkloadExecuted=False, fullRemoteQualification=False,
            reason='preparation failed', failure=deepcopy(preparation['failure']), cleanup=deepcopy(result['cleanup']),
            evidenceSha256=m.sha(files['manifest.json']))
        api.expected_completion = deepcopy(completion)
        runner.finalize(store, lease, completion, authority=n)
        result['retention'] = 'VERIFIED'
        if result['cleanup']['status'] == 'PASS':
            store.delete(n.LEASE, generation)
            result.update(status='PASS', leaseReleased=True)
    except (Exception, KeyboardInterrupt) as error:
        result['errors'].append(runner.failure('owner-recovery', error, redact=True))
    finally:
        if api is not None:
            result.update(elapsedSeconds=max(0,api.clock()-api.started), ownerDeadline=source.owner_deadline)
        try:
            output.mkdir(exist_ok=True)
            if api is not None: c.write_once(output/'http.json', api.requests)
            c.write_once(output/'receipt.json', result)
        except (Exception, KeyboardInterrupt) as error:
            result['status'] = 'FAIL'
            result['errors'].append(runner.failure('local-recovery-evidence', error, redact=True))
    return result

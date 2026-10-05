"""Offline native Runner storage transaction; no network or paid entry point.

Use the real native formats, generation-bound Store and expired-owner cleanup.
This qualifies the storage protocol against a provider double, not actual IAM.
Every original mutation is consumed before submission, including denied probes.
"""
from copy import deepcopy
from urllib.parse import quote, urlencode, urlsplit, parse_qsl
from . import cloud_authority as a, cloud_native_authority as n, cloud_gcp as g
from . import cloud_http as h, performance_model as m

SCHEMA = 'gse-v51-runner-storage-v1'
EXECUTION = 'offline-v51-runner-storage'
CASES = ('create', 'read-created', 'read-existing', 'overwrite-denied',
         'delete-denied', 'outside-read-denied', 'outside-write-denied', 'outside-delete-denied')


def inventory(req):
    sha = n.validate_request(req)
    prefix = n.PREFIX+'attempts/'+sha+'/'
    return dict(created=prefix+'runner-storage-created.json', existing=prefix+'runner-storage-existing.json',
                outside='v5.1-runner-storage-outside/'+sha+'.json',
                report=prefix+'runner-storage.json', completion=prefix+'completion.json')


def canary(req, kind):
    return dict(schema='gse-v51-runner-storage-canary-v1', requestSha256=n.validate_request(req), kind=kind)


def report(req):
    return dict(schema=SCHEMA, execution=EXECUTION, requestSha256=n.validate_request(req), status='PASS',
                cases=[dict(case=name, status='PASS') for name in CASES], paidCloud=False,
                objectPermissionsQualified=False, engineWorkloadExecuted=False, fullRemoteQualification=False)


def completion(req):
    # Passing a storage protocol test is not passing an engine workload.
    return dict(schema=n.COMPLETION_SCHEMA, execution=n.EXECUTION, requestSha256=n.validate_request(req),
                status='FAIL', paidCloud=True, engineWorkloadExecuted=False, fullRemoteQualification=False,
                reason='storage-only qualification; no engine workload')


class OfflineApi(h.Api):
    """Finite request/body policy. No live transport, token or approval overload.

    baseline contains independently captured generation/value pairs for ledger
    and two operator canaries. None means an absent ledger only. It is synthetic
    input here; a future live entry needs its own reviewed provenance/admission.
    """
    def __init__(self, cfg, req, baseline, *, maximum_cost, transport, clock):
        m.need(transport.offline is True, 'Runner storage has no network entry')
        sha = n.validate_request(req)
        m.need(g.config(cfg) == req['configurationSha256'], 'Runner storage configuration binding')
        self.cfg, self.req, self.keys = deepcopy(cfg), deepcopy(req), inventory(req)
        m.need(set(baseline) == {n.LEDGER, self.keys['existing'], self.keys['outside']}, 'storage baseline inventory')
        self.baseline = deepcopy(baseline)
        for key, row in self.baseline.items():
            m.need(row is None and key == n.LEDGER or type(row) in (tuple, list) and len(row) == 2,
                   'storage baseline object')
            if row is not None: a.integer(row[0], 1)
        for name in ('existing', 'outside'):
            m.need(self.baseline[self.keys[name]][1] == canary(req, name), 'storage canary binding')
        ledger = baseline[n.LEDGER]
        self.original = deepcopy(ledger[1]) if ledger else n.empty_ledger()
        self.original_generation = ledger[0] if ledger else 0
        total, _ = n.inspect_ledger(self.original)
        self.reserved = n.reserve(self.original, req, dict(previousCostMicrousd=total, maximumCostMicrousd=maximum_cost))
        self.terminal = n.finish(self.reserved, req, completion(req))
        self.lease = n.lease(req, req['createdAt'])
        self.used, self.denied, self.observed, self.metadata = set(), set(), {}, {}
        self.base = 'https://storage.googleapis.com/storage/v1/b/'+cfg['bucket']+'/o/'
        self.upload = 'https://storage.googleapis.com/upload/storage/v1/b/'+cfg['bucket']+'/o'
        self.sha = sha
        super().__init__(transport=transport, tokens=lambda timeout: 'offline-token', clock=clock)
        self.deadline = clock()+self.lease['expiresAt']-self.lease['startedAt']

    def url(self, key): return self.base+quote(key, safe='')

    def put_url(self, key, generation):
        return self.upload+'?'+urlencode(dict(uploadType='media', name=key, ifGenerationMatch=generation))

    def delete_url(self, key, generation):
        return self.url(key)+'?'+urlencode(dict(ifGenerationMatch=generation))

    def retained(self, key, value):
        row = self.observed.get(key)
        m.need(row is not None and row[1] == value, 'storage prerequisite not observed: '+key)
        return row[0]

    def check(self, method, url, body):
        m.need(self.offline, 'Runner storage has no network entry')
        parsed = urlsplit(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True) if parsed.query else []
        query = dict(pairs)
        m.need(len(pairs) == len(query), 'storage duplicate query')
        base = parsed._replace(query='').geturl()
        keys = [n.LEASE, n.LEDGER, *self.keys.values()]
        key = next((key for key in keys if base == self.url(key)), None)
        if method == 'GET':
            m.need(key is not None and body is None, 'storage read scope')
            m.need(not query or set(query) == {'alt', 'generation', 'ifGenerationMatch'} and query['alt'] == 'media'
                   and query['generation'] == query['ifGenerationMatch'] and
                   query['generation'] == str(self.metadata.get(key)), 'storage pinned read')
            if key == self.keys['outside']:
                m.need(not query, 'outside read must be a permission probe')
                self.retained(n.LEDGER, self.reserved)
                return 'outside-read-denied', key
            return 'media' if query else 'metadata', key
        m.need(method in ('POST', 'DELETE'), 'storage method')
        if method == 'POST':
            m.need(base == self.upload and set(query) == {'uploadType', 'name', 'ifGenerationMatch'} and
                   query['uploadType'] == 'media' and query['name'] in keys, 'storage upload scope')
            key = query['name']
        else:
            m.need(key is not None and body is None and set(query) == {'ifGenerationMatch'}, 'storage delete scope')
        expected = query['ifGenerationMatch']
        action = None
        if key == n.LEASE:
            if method == 'POST':
                m.need(expected == '0' and body == self.lease and n.LEASE in self.observed and
                       self.observed[n.LEASE] is None, 'storage lease acquisition')
                # Re-read ledger before acquiring; a stale plan never acquires a lease.
                m.need(n.LEDGER in self.observed and self.observed[n.LEDGER] ==
                       (tuple(self.baseline[n.LEDGER]) if self.baseline[n.LEDGER] else None), 'storage stale ledger baseline')
                m.need(all(self.keys[name] in self.observed and self.observed[self.keys[name]] is None
                           for name in ('created', 'report', 'completion')), 'storage attempt already retained')
                action = 'acquire'
            else:
                generation = self.retained(n.LEASE, self.lease)
                self.retained(n.LEDGER, self.terminal)
                self.retained(self.keys['completion'], completion(self.req))
                m.need(expected == str(generation), 'storage lease release generation')
                action = 'release'
        elif key == n.LEDGER:
            m.need(method == 'POST', 'ledger deletion forbidden')
            self.retained(n.LEASE, self.lease)
            if body == self.reserved:
                m.need(expected == str(self.original_generation), 'storage reservation generation')
                action = 'reserve'
            else:
                generation = self.retained(n.LEDGER, self.reserved)
                self.retained(self.keys['completion'], completion(self.req))
                m.need(body == self.terminal and expected == str(generation), 'storage append-only terminal ledger')
                action = 'finish'
        else:
            self.retained(n.LEASE, self.lease)
            self.retained(n.LEDGER, self.reserved)
            if key in (self.keys['existing'], self.keys['outside']):
                m.need(expected == str(self.baseline[key][0]) and
                       (method == 'DELETE' or body == canary(self.req, 'replacement')), 'permission probe exact generation/body')
                action = ('outside-' if key == self.keys['outside'] else '')+('write-denied' if method == 'POST' else 'delete-denied')
                if action == 'write-denied': action = 'overwrite-denied'
            else:
                m.need(method == 'POST' and expected == '0', 'immutable storage evidence')
                if key == self.keys['created']:
                    m.need(body == canary(self.req, 'created'), 'created canary body'); action = 'create'
                elif key == self.keys['report']:
                    self.retained(self.keys['created'], canary(self.req, 'created'))
                    m.need(self.observed.get(self.keys['existing']) == tuple(self.baseline[self.keys['existing']]) and
                           self.denied == set(CASES[3:]) and body == report(self.req), 'storage probes incomplete')
                    action = 'report'
                elif key == self.keys['completion']:
                    self.retained(self.keys['report'], report(self.req))
                    m.need(body == completion(self.req), 'storage cannot accept engine workload'); action = 'complete'
        m.need(action is not None, 'storage operation scope')
        return action, key

    def authorize(self, method, url, body):
        action, _ = self.check(method, url, body)
        if action not in ('metadata', 'media'):
            m.need(self.clock() < self.deadline, 'storage original owner deadline expired')
            m.need(action not in self.used, 'storage original operation already submitted: '+action)
            self.used.add(action)  # Consume before credentials/transport, including an ambiguous result.

    def call(self, method, url, body=None, **kwargs):
        action, key = self.check(method, url, body)
        kwargs['deadline'] = min(kwargs['deadline'], self.deadline)
        try: value = super().call(method, url, body, **kwargs)
        except h.ApiError as error:
            if action in CASES[3:] and error.status == 403: self.denied.add(action)
            elif action == 'metadata' and error.status == 404:
                self.observed[key] = None; self.metadata.pop(key, None)
            raise
        m.need(action not in CASES[3:], 'permission probe unexpectedly succeeded: '+action)
        if action == 'media':
            self.observed[key] = self.metadata[key], m.strict_json(value)
        elif method in ('GET', 'POST'):
            m.need(value['name'] == key and value['bucket'] == self.cfg['bucket'], 'storage metadata binding')
            self.metadata[key] = int(g.numeric(value['generation']))
        return value


def run(api):
    m.need(type(api) is OfflineApi and api.offline, 'offline Runner storage policy required')
    store = g.Store(api.cfg, api, authority=n)
    m.need(store.get(n.LEASE) is None, 'Runner storage lease occupied')
    ledger = store.get(n.LEDGER)
    m.need(ledger == (tuple(api.baseline[n.LEDGER]) if api.baseline[n.LEDGER] else None), 'Runner storage ledger changed')
    for name in ('created', 'report', 'completion'):
        m.need(store.get(api.keys[name]) is None, 'Runner storage attempt already retained')
    generation = store.put(n.LEASE, api.lease, 0)
    reserved_generation = store.put(n.LEDGER, api.reserved, api.original_generation)
    store.put(api.keys['created'], canary(api.req, 'created'), 0)
    m.need(store.get(api.keys['existing']) == tuple(api.baseline[api.keys['existing']]), 'existing canary changed')
    probes = [('POST', 'existing'), ('DELETE', 'existing'), ('GET', 'outside'), ('POST', 'outside'), ('DELETE', 'outside')]
    for method, name in probes:
        key = api.keys[name]; expected = api.baseline[key][0]
        url = api.put_url(key, expected) if method == 'POST' else api.delete_url(key, expected) if method == 'DELETE' else api.url(key)
        try: api.call(method, url, canary(api.req, 'replacement') if method == 'POST' else None, deadline=api.clock()+30)
        except h.ApiError as error:
            m.need(error.status == 403, 'permission probe inconclusive: HTTP '+str(error.status))
        else: raise ValueError('permission probe was not denied')
    store.put(api.keys['report'], report(api.req), 0)
    store.put(api.keys['completion'], completion(api.req), 0)
    store.put(n.LEDGER, api.terminal, reserved_generation)
    store.delete(n.LEASE, generation)
    return dict(report(api.req), leaseReleased=True, maximumCostMicrousd=api.reserved['entries'][-1]['maximumCostMicrousd'])

"""Shared closed, once-only native resource creation state machine.

Callers validate their own request/entry before initialization. This class does
not authorize network access. The topology fixture and ordinary experiment
qualifier use the same durable intent, CAS, operation and dependency handling.
"""
from copy import deepcopy
import time
from urllib.parse import parse_qsl, urlencode, urlsplit
from . import cloud_native_authority as n, cloud_gcp as g, cloud_cleanup as cleanup
from . import cloud_workload_contract as workload, performance_model as m


class CreationPolicy:
    def initialize_creation(self, configuration, req, guest_access, prior, approval, now, *, qualification_manifest=None,
                            intent_record=None):
        n.validate_request(req); g.config(configuration)
        self.req = deepcopy(req); self.cfg = deepcopy(configuration)
        self.store = g.Store(self.cfg, self, authority=n)
        self.keys = {n.LEASE, n.LEDGER, cleanup.context_key(self.req, authority=n), self.marker_key()}
        self.intent_record = deepcopy(intent_record)
        if self.intent_record is not None: self.keys.add(self.intent_record[0])
        self.lease = n.lease(self.req, now); self.generation = 0
        self.prior_generation = prior[0] if prior is not None else 0
        self.reserved = n.reserve(prior[1] if prior is not None else n.empty_ledger(), self.req, approval)
        self.state = 'lease'; self.index = 0; self.created_id = None; self.polls = set()
        self.armed = None; self.failed = False; self.requests = []
        self.deadline = self.clock()+workload.load()['budgets']['preparationSeconds']
        self._provider = g.Compute(self.cfg, self.req, self, guest_access=guest_access, authority=n,
                                   qualification_manifest=qualification_manifest)

    def provider(self, sleep=None):
        if sleep is not None: self._provider.sleep = sleep
        return self._provider

    def context(self):
        return self.provider().cleanup_context()

    def write_step(self):
        if self.state == 'lease': return n.LEASE, deepcopy(self.lease), 0
        if self.state == 'ledger': return n.LEDGER, self.reserved, self.prior_generation
        if self.state == 'context':
            return cleanup.context_key(self.req, authority=n), self.context(), 0
        if self.state == 'plan': return *deepcopy(self.intent_record), 0
        if self.state in ('intent', 'identity'):
            lease = deepcopy(self.lease); row = lease['resources'][self.index]; row['attempted'] = True
            if self.state == 'identity': row['id'] = g.numeric(self.created_id)
            return n.LEASE, lease, self.generation
        if self.state == 'manifest': return self.marker_key(), self.marker_value(), 0
        raise ValueError('resource creation write order')

    def authorize(self, method, url, body):
        parsed = urlsplit(url); base = parsed._replace(query='').geturl()
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True) if parsed.query else []
        query = dict(pairs); m.need(len(query) == len(pairs), 'resource creation duplicate query')
        if method != 'GET':
            m.need(not self.failed and method == 'POST' and self.armed == (method, url, body), 'resource creation unexpected mutation')
            # Recompute scope even if a caller tries to arm an arbitrary request.
            if self.state == 'insert':
                provider = self.provider(); spec = self.lease['resources'][self.index]['spec']
                expected = (provider.url(spec).rsplit('/', 1)[0]+'?'+urlencode(dict(requestId=provider.operation_id(spec))), provider.body(spec))
            else:
                key, value, generation = self.write_step()
                expected = ('https://storage.googleapis.com/upload/storage/v1/b/'+self.cfg['bucket']+'/o?'+
                    urlencode(dict(uploadType='media', name=key, ifGenerationMatch=generation)), value)
            m.need((url, body) == expected, 'resource creation mutation scope/body/generation')
            self.armed = None
            return
        m.need(body is None, 'resource creation read body')
        if parsed.netloc == 'storage.googleapis.com':
            m.need(base in {self.store.url(k) for k in self.keys} and (not query or
                set(query) == {'alt', 'generation', 'ifGenerationMatch'} and query['alt'] == 'media' and
                query['generation'] == query['ifGenerationMatch'] and g.numeric(query['generation'])), 'resource creation object read scope')
            return
        provider = self.provider()
        image = 'https://compute.googleapis.com/compute/v1/projects/'+self.cfg['imageProject']+'/global/images/'+self.cfg['imageName']
        if base == image and not query: return
        for row in self.lease['resources']:
            spec = row['spec']
            if base == provider.url(spec) and not query: return
            identities = [row['id']]
            if self.state == 'insert' and row is self.lease['resources'][self.index]: identities.append(self.created_id)
            if not query and any(identity is not None and base == provider.url(spec, identity) for identity in identities): return
            if base == provider.scope(spec)+'/operations' and query == {'filter': 'clientOperationId = "'+provider.operation_id(spec)+'"'}: return
        m.need(not query and base in self.polls, 'resource creation compute read scope')

    def call(self, method, url, body=None, **kwargs):
        kwargs['deadline'] = min(kwargs['deadline'], self.deadline)
        self.requests.append(dict(method=method, url=url, bodySha256=m.sha(m.canonical(body)) if body is not None else None))
        result = super().call(method, url, body, **kwargs)
        if self.state == 'insert' and isinstance(result, dict) and result.get('operationType') == 'insert':
            provider = self.provider(); spec = self.lease['resources'][self.index]['spec']
            decoded = provider.decode_operation(spec, result)
            self.polls.add(provider.scope(spec)+'/operations/'+result['name'])
            if decoded['state'] == 'DONE': self.created_id = decoded['id']
        return result

    def upload(self):
        m.need(not self.failed, 'resource creation preparation already failed')
        key, body, generation = self.write_step()
        url = 'https://storage.googleapis.com/upload/storage/v1/b/'+self.cfg['bucket']+'/o?'+urlencode(
            dict(uploadType='media', name=key, ifGenerationMatch=generation))
        self.armed = ('POST', url, deepcopy(body))
        try: result = self.store.put(key, body, generation)
        except BaseException:
            self.failed = True; raise
        if key == n.LEASE: self.lease = deepcopy(body); self.generation = result
        if self.state == 'identity':
            self.index += 1; self.created_id = None; self.polls.clear()
            self.state = 'manifest' if self.index == len(self.lease['resources']) else 'intent'
        else:
            self.state = {'lease': 'ledger', 'ledger': 'context', 'context': 'plan' if self.intent_record else 'intent',
                          'plan': 'intent', 'intent': 'insert', 'manifest': 'done'}[self.state]

    def insert(self, sleep=time.sleep):
        m.need(not self.failed and self.state == 'insert', 'resource creation insert order')
        try:
            m.need(self.store.get(n.LEASE) == (self.generation, self.lease) and
                   self.store.get(n.LEDGER)[1] == self.reserved and
                   self.store.get(cleanup.context_key(self.req, authority=n))[1] ==
                   self.context(), 'resource creation durable authority changed')
            if self.intent_record is not None:
                m.need(self.store.get(self.intent_record[0])[1] == self.intent_record[1], 'resource retained input plan changed')
            provider = self.provider(sleep); spec = self.lease['resources'][self.index]['spec']
            if spec['kind'] == 'instance':
                for row in self.lease['resources']:
                    dep = row['spec']
                    if dep['kind'] == 'firewall' or dep['kind'] == 'disk' and dep['node'] == spec['node']:
                        m.need(row['id'] is not None and provider.describe(dep) == dict(spec=dep, id=row['id']), 'resource creation prerequisite identity changed')
            url = provider.url(spec).rsplit('/', 1)[0]+'?'+urlencode(dict(requestId=provider.operation_id(spec)))
            self.armed = ('POST', url, provider.body(spec))
            result = provider.create(spec, int(self.deadline*10**9))
            m.need(result['id'] == self.created_id, 'resource creation created ID mismatch')
            self.state = 'identity'
        except BaseException:
            self.failed = True; raise

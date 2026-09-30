"""Native-format cleanup through a closed HTTP policy; offline qualification only.

There is no activation flag or workflow entry point. Api's live mutation barrier
remains closed independently of this narrower method/path/body policy.
"""
from copy import deepcopy
import re
from urllib.parse import urlsplit, parse_qsl, quote
from . import cloud_authority as a, cloud_native_authority as n, cloud_cleanup as c
from . import cloud_gcp as g, performance_model as m
from .cloud_http import ApiError


class CleanupApi:
    def __init__(self, configuration, api):
        m.need(api.offline is True, 'native cleanup activation unavailable')
        g.config(configuration)
        self.config, self.api = deepcopy(configuration), api
        self.clock, self.offline = api.clock, True
        self.lease = self.provider = self.ledger = self.completion = None
        self.lease_generation = self.observed_lease_generation = self.ledger_generation = None
        self.observed_lease = None
        self.resolved, self.absent, self.polls = {}, set(), {}
        bucket = configuration['bucket']
        self.objects = 'https://storage.googleapis.com/storage/v1/b/'+bucket+'/o/'
        self.upload = 'https://storage.googleapis.com/upload/storage/v1/b/'+bucket+'/o'

    def bind(self, lease, generation, *, now):
        n.validate_lease(lease); a.integer(generation, 1)
        m.need(self.lease is None and self.observed_lease == lease and self.lease_generation == self.observed_lease_generation == generation,
               'cleanup lease observation binding')
        m.need(now >= lease['expiresAt']+lease['graceSeconds'], 'cleanup lease still active/grace')
        m.need(g.config(self.config) == lease['request']['configurationSha256'], 'native cleanup configuration')
        self.lease = deepcopy(lease)
        self.request = lease['request']; self.sha = n.validate_request(self.request)
        self.attempt = n.PREFIX+'attempts/'+self.sha+'/'

    def object_key(self, base):
        keys = [n.LEASE, n.LEDGER]
        if self.lease is not None:
            keys += [self.attempt+'cleanup-context.json', self.attempt+'completion.json',
                     self.attempt+f'cleanup-{self.lease_generation}.json']
        for key in keys:
            if base == self.objects+quote(key, safe=''): return key
        raise ValueError('cleanup object scope')

    def completion_value(self, value):
        m.need(type(value) is dict and value.get('schema') == n.COMPLETION_SCHEMA and
               value.get('execution') == n.EXECUTION and value.get('paidCloud') is True and
               value.get('requestSha256') == self.sha and value.get('status') in ('PASS', 'FAIL'),
               'native cleanup completion identity')
        return value

    def check(self, method, url, body):
        parsed = urlsplit(url)
        m.need(parsed.scheme == 'https' and parsed.netloc in ('compute.googleapis.com', 'storage.googleapis.com') and
               not parsed.fragment and not parsed.username, 'cleanup endpoint')
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True) if parsed.query else []
        query = dict(pairs); m.need(len(pairs) == len(query), 'cleanup duplicate query')
        base = parsed._replace(query='').geturl()
        if parsed.netloc == 'storage.googleapis.com':
            if method == 'POST':
                m.need(self.lease is not None and base == self.upload and
                       set(query) == {'uploadType', 'name', 'ifGenerationMatch'} and query['uploadType'] == 'media',
                       'cleanup storage upload scope')
                key = query['name']; expected = query['ifGenerationMatch']
                m.need(re.fullmatch('0|[1-9][0-9]{0,19}', expected) is not None, 'cleanup generation condition')
                if key == n.LEASE:
                    n.validate_lease(body)
                    m.need(int(expected) == self.lease_generation and
                           all(body[k] == v for k, v in self.lease.items() if k != 'resources'), 'cleanup lease replacement')
                    for old, row in zip(self.lease['resources'], body['resources']):
                        m.need(row['spec'] == old['spec'] and row['attempted'] == old['attempted'] and
                               row['id'] in (old['id'], self.resolved.get(row['spec']['name'])), 'cleanup lease intent/ID changed')
                        m.need(old['id'] is None or row['id'] == old['id'], 'cleanup retained ID erased')
                elif key == n.LEDGER:
                    m.need(int(expected) == self.ledger_generation and self.ledger is not None and self.completion is not None,
                           'cleanup terminal ledger prerequisites')
                    m.need(body == n.finish(self.ledger, self.request, self.completion), 'cleanup append-only terminal ledger')
                elif key == self.attempt+'completion.json':
                    m.need(expected == '0', 'cleanup completion overwrite'); self.completion_value(body)
                    m.need(body == dict(schema=n.COMPLETION_SCHEMA, execution=n.EXECUTION, requestSha256=self.sha,
                           status='FAIL', paidCloud=True, engineWorkloadExecuted=False, fullRemoteQualification=False,
                           reason='expired interrupted owner'), 'cleanup cannot manufacture successful workload evidence')
                elif key == self.attempt+f'cleanup-{self.lease_generation}.json':
                    m.need(expected == '0' and type(body) is dict and body.get('execution') == n.ADAPTER_EXECUTION and
                           body.get('trigger') in ('manual', 'schedule') and body.get('leaseReleased') is False and
                           body.get('status') == 'FAIL' and type(body.get('cleanup')) is dict, 'cleanup receipt scope')
                else: raise ValueError('cleanup upload outside terminal authority')
                return ('object', key, 'upload')
            key = self.object_key(base)
            if method == 'GET':
                m.need(body is None and (not query or set(query) == {'alt', 'generation', 'ifGenerationMatch'} and
                       query['alt'] == 'media' and query['generation'] == query['ifGenerationMatch'] and
                       re.fullmatch('[1-9][0-9]{0,19}', query['generation']) is not None), 'cleanup pinned object read')
                return ('object', key, 'media:'+query['generation'] if query else 'metadata')
            m.need(method == 'DELETE' and body is None and key == n.LEASE and self.lease is not None and
                   query == {'ifGenerationMatch': str(self.lease_generation)}, 'cleanup object deletion scope')
            m.need(self.completion is not None and all(row['spec']['name'] in self.absent
                   for row in self.lease['resources'] if row['attempted']), 'cleanup absence/completion not established')
            if self.ledger is not None:
                _, attempts = n.inspect_ledger(self.ledger)
                m.need(self.sha not in attempts or attempts[self.sha]['status'] != 'PENDING', 'cleanup terminal ledger missing')
            return ('object', key, 'delete')
        m.need(self.provider is not None and self.lease is not None and body is None, 'cleanup resource authority unavailable')
        for row in self.lease['resources']:
            if not row['attempted']: continue
            spec = row['spec']; name = spec['name']; provider = self.provider
            if method == 'GET' and base == provider.scope(spec)+'/operations' and query == {
                    'filter': 'clientOperationId = "'+provider.operation_id(spec)+'"'}:
                return ('insert-operation', spec, None)
            if method == 'GET' and not query and base == provider.url(spec): return ('resource', spec, None)
            identity = self.resolved.get(name)
            if identity is not None and base == provider.url(spec, identity):
                if method == 'GET' and not query: return ('resource', spec, identity)
                if method == 'DELETE' and query == {'requestId': provider.operation_id(spec, 'delete', identity)}:
                    return ('delete-operation', spec, identity)
        if method == 'GET' and not query and base in self.polls:
            spec, identity = self.polls[base]; return ('delete-operation', spec, identity)
        raise ValueError('cleanup compute method/path/operation scope')

    def observe(self, checked, value):
        kind, item, detail = checked
        if kind == 'object':
            if detail in ('metadata', 'upload'):
                m.need(value['name'] == item and value['bucket'] == self.config['bucket'], 'cleanup object metadata')
                generation = int(g.numeric(value['generation']))
                if item == n.LEASE:
                    if detail == 'metadata' and self.lease is not None:
                        m.need(generation == self.lease_generation, 'cleanup bound lease generation changed')
                    self.lease_generation = generation
            elif detail.startswith('media:'):
                generation = int(detail.split(':', 1)[1])
                value = m.strict_json(value)  # Store requests pinned media as bytes.
                if item == n.LEASE:
                    n.validate_lease(value); self.observed_lease = deepcopy(value); self.observed_lease_generation = generation
                elif item == n.LEDGER:
                    n.inspect_ledger(value); self.ledger = deepcopy(value); self.ledger_generation = generation
                elif item == self.attempt+'cleanup-context.json':
                    c.validate_context(value, self.request, authority=n)
                    self.provider = g.Compute(self.config, self.request, self.api, guest_access=value['guestAccess'], authority=n)
                elif item == self.attempt+'completion.json': self.completion = deepcopy(self.completion_value(value))
        elif kind == 'insert-operation':
            m.need(type(value) is dict and not value.get('nextPageToken') and len(value.get('items', [])) <= 1,
                   'cleanup ambiguous insert operation')
            if value.get('items'):
                result = self.provider.decode_operation(item, value['items'][0])
                if result['state'] == 'DONE':
                    old = next(row['id'] for row in self.lease['resources'] if row['spec'] == item)
                    m.need(old is None or old == result['id'], 'cleanup original operation ID changed')
                    self.resolved[item['name']] = result['id']
        elif kind == 'resource':
            self.absent.discard(item['name'])
            result = self.provider.inspect(item, value)
            m.need(detail is None or result['id'] == detail, 'cleanup numeric lookup identity')
        elif kind == 'delete-operation':
            self.provider.decode_operation(item, value, 'delete', detail)
            self.polls[self.provider.scope(item)+'/operations/'+value['name']] = (item, detail)

    def call(self, method, url, body=None, **kwargs):
        checked = self.check(method, url, body)
        try: result = self.api.call(method, url, body, **kwargs)
        except ApiError as error:
            if error.status == 404 and checked[0] == 'resource' and checked[2] is None:
                self.absent.add(checked[1]['name'])
            raise
        self.observe(checked, result)
        return result


def reconcile(configuration, api, output, *, trigger, now):
    policy = CleanupApi(configuration, api)
    return c.reconcile(configuration, policy, output, trigger=trigger, now=now, authority=n,
                       on_expired=lambda lease, generation: policy.bind(lease, generation, now=now))

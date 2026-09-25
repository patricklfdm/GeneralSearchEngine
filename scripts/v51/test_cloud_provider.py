import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from . import cloud_authority as a, cloud_fake, cloud_http_fake as f, cloud_gcp, cloud_runner, performance_model as m
from .cloud_http import Api, ApiError, NoRedirect


class HttpTest(unittest.TestCase):
    def setUp(self): self.clock = cloud_fake.Clock(); self.calls = []; self.tokens = []
    def api(self, responses, offline=True):
        owner = self
        class Transport:
            def send(self, *args): owner.calls.append(args); return responses.pop(0)
        transport = Transport(); transport.offline = offline
        def token(timeout): self.tokens.append(timeout); return 'secret-token'
        return Api(transport=transport, tokens=token, clock=self.clock.seconds)
    def test_get_401_renews_once(self):
        api = self.api([(401, b''), (200, b'{}')]); api.call('GET', 'https://storage.googleapis.com/a', deadline=10)
        self.assertEqual((len(self.calls), len(self.tokens)), (2, 2))
    def test_mutation_401_never_replays(self):
        api = self.api([(401, b'private-detail')])
        with self.assertRaises(ApiError) as caught: api.call('POST', 'https://compute.googleapis.com/a', {}, deadline=10)
        self.assertEqual(len(self.calls), 1); self.assertNotIn('private', str(caught.exception)); self.assertNotIn('secret', str(caught.exception))
    def test_live_mutations_and_host_confusion_blocked_before_credentials(self):
        api = self.api([], False)
        for method, url in [('POST', 'https://compute.googleapis.com/a'), ('DELETE', 'https://storage.googleapis.com/a'),
                ('GET', 'https://compute.googleapis.com.evil/a'), ('GET', 'https://x@compute.googleapis.com/a'), ('GET', 'http://compute.googleapis.com/a')]:
            with self.subTest(url=url, method=method), self.assertRaises(ValueError): api.call(method, url, deadline=10)
        self.assertFalse(self.calls); self.assertFalse(self.tokens)
    def test_original_deadline_and_response_size(self):
        api = self.api([(200, b'1234')])
        with self.assertRaisesRegex(ValueError, 'deadline'): api.call('GET', 'https://compute.googleapis.com/a', deadline=1)
        with self.assertRaisesRegex(ValueError, 'size'): api.call('GET', 'https://compute.googleapis.com/a', deadline=10, maximum=3)
    def test_redirect_forbidden(self):
        with self.assertRaisesRegex(ValueError, 'redirect'): NoRedirect().redirect_request(None, None, None, None, None, None)
    def test_token_renewed_by_age(self):
        api = self.api([(200, b'{}'), (200, b'{}')]); api.call('GET', 'https://compute.googleapis.com/a', deadline=10)
        self.clock.sleep(2401); api.call('GET', 'https://compute.googleapis.com/a', deadline=2500)
        self.assertEqual(len(self.tokens), 2)


class ProviderTest(unittest.TestCase):
    def setUp(self):
        self.req, self.preflight, self.approval, self.clock, self.http, self.store, self.provider = f.fixture()
    def create(self, spec=None):
        spec = spec or a.resources(self.req)[0]
        lease = a.lease(self.req, self.clock.wall()); next(r for r in lease['resources'] if r['spec'] == spec)['attempted'] = True
        self.store.put(a.LEASE, lease, 0)
        return spec, self.provider.create(spec, self.clock.nanos()+30*10**9)
    def test_generation_cas_and_binary_retention(self):
        gen = self.store.put(a.LEDGER, {'value': 1}, 0)
        with self.assertRaises(ApiError): self.store.put(a.LEDGER, {'value': 2}, 0)
        with self.assertRaises(ApiError): self.store.delete(a.LEDGER, gen+1)
        self.assertEqual(self.store.get(a.LEDGER), (gen, {'value': 1}))
        new = self.store.put(a.LEDGER, b'\x00binary\xff', gen)
        self.assertEqual(self.store.get(a.LEDGER), (new, b'\x00binary\xff'))
        self.store.delete(a.LEDGER, new); self.assertIsNone(self.store.get(a.LEDGER))
    def test_metadata_media_race_rejected(self):
        self.store.put(a.LEDGER, {'value': 1}, 0)
        def race(method, path, query, body):
            if query.get('alt') == 'media':
                gen, data, content = self.http.objects[a.LEDGER]; self.http.objects[a.LEDGER] = gen+1, data, content
        self.http.hook = race
        with self.assertRaises(ApiError): self.store.get(a.LEDGER)
    def test_namespace_and_configuration_closed(self):
        for key in ('v5.0/active.json', a.PREFIX+'../a', a.PREFIX+'x//a'):
            with self.assertRaises(ValueError): self.store.get(key)
        for key, value in [('zone', 'us-east1-a'), ('imageId', '123'), ('extra', True)]:
            cfg = f.configuration(); cfg[key] = value
            with self.assertRaises(ValueError): cloud_gcp.config(cfg)
    def test_numeric_delete_does_not_touch_reused_name(self):
        spec, made = self.create(); path = self.provider.url(spec).split('compute.googleapis.com')[1]
        def replace(method, parsed, query, body):
            if method == 'DELETE' and '/firewalls/' in parsed.path:
                self.http.resources[path]['id'] = '9999999'
        self.http.hook = replace
        self.provider.delete(spec, made['id'])
        self.assertEqual(self.http.resources[path]['id'], '9999999')
        deletes = [r for r in self.http.requests if r['method'] == 'DELETE']
        self.assertTrue(all(r['path'].endswith('/'+made['id']) for r in deletes))
    def test_foreign_owner_or_shape_rejected(self):
        spec, _ = self.create(); path = self.provider.url(spec).split('compute.googleapis.com')[1]
        self.http.resources[path]['description'] = '{}'
        with self.assertRaisesRegex(ValueError, 'ownership'): self.provider.describe(spec)
    def test_operation_mismatch_and_pagination_rejected(self):
        spec, _ = self.create(); op = next(iter(self.http.operations.values()))
        for key, value in [('clientOperationId', 'foreign'), ('targetLink', 'https://compute.googleapis.com/wrong'), ('operationType', 'delete')]:
            changed = dict(op, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError): self.provider.decode_operation(spec, changed)
        self.http.hook = lambda method, path, query, body: self.http.reply(dict(items=[op], nextPageToken='more')) if path.path.endswith('/operations') else None
        with self.assertRaisesRegex(ValueError, 'ambiguous'): self.provider.operation(spec)
    def test_private_fixed_topology_and_image_identity(self):
        specs = a.resources(self.req)
        for spec in specs:
            body = self.provider.body(spec)
            if spec['kind'] == 'instance':
                self.assertFalse(body['networkInterfaces'][0]['accessConfigs']); self.assertFalse(body['serviceAccounts'])
                self.assertTrue(all(d['autoDelete'] is False for d in body['disks']))
                self.assertEqual(body['scheduling']['maxRunDuration']['seconds'], '5400')
        boot = next(s for s in specs if s['kind'] == 'disk' and s['purpose'] == 'boot')
        self.http.fault = 'image-drift'
        with self.assertRaisesRegex(ValueError, 'image'): self.create(boot)
        self.assertEqual(self.http.inserts, 0)
    def test_live_adapters_rejected_by_runner(self):
        api = Api(); cfg = f.configuration()
        with self.assertRaisesRegex(ValueError, 'unqualified'):
            cloud_runner.adapters(cloud_gcp.Store(cfg, api), cloud_gcp.Compute(cfg, self.req, api))
    def test_http_lifecycle_and_failures(self):
        for fault in (None, 'lost-insert', 'pending-insert', 'delete-denied', 'image-drift'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                req, pre, approval, clock, http, store, provider = f.fixture(fault)
                probe = cloud_fake.Probe(Path(temp)/'guest', clock)
                result = cloud_runner.Runner(store, provider, probe, Path(temp)/'run', clock=clock.nanos, wall=clock.wall).run(req, pre, approval)
                self.assertEqual(result['status'], 'PASS' if fault is None else 'FAIL')
                self.assertEqual(result['cleanup']['status'], 'FAIL' if fault in ('pending-insert', 'delete-denied', 'image-drift') else 'PASS')
                if fault == 'lost-insert': self.assertEqual(http.inserts, 3); self.assertFalse(http.resources)
                self.assertFalse(result['paidCloud']); self.assertFalse(result['engineWorkloadExecuted'])

if __name__ == '__main__': unittest.main()

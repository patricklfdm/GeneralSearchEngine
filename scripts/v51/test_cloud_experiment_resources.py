from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode, urlsplit
from . import cloud_experiment_resources as r, cloud_experiment_resource_qualification as q
from . import cloud_native_authority as n, cloud_authority as a, cloud_http as h
from . import cloud_cleanup as cleanup, cloud_cleanup_qualification as retained
from . import performance_model as m


class ExperimentResourceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.value, self.clock, self.http, self.reader, self.api = q.fixture()

    def prepare(self):
        return r.prepare(self.value, self.api, self.root/'prepare', now=self.clock.wall(), sleep=self.clock.sleep)

    def test_resources_ready_is_not_experiment_success_and_preserves_ordinary_profile(self):
        result = self.prepare()
        self.assertEqual('RESOURCES_PREPARED', result['status'], result)
        self.assertEqual(13, self.http.inserts)
        for flag in r.FLAGS: self.assertIs(result[flag], False)
        context = self.api.store.get(cleanup.context_key(self.api.req, authority=n))[1]
        self.assertEqual(n.CONTEXT_SCHEMA, context['schema'])
        self.assertNotIn('qualificationManifest', context)
        for vm in (v for v in self.http.resources.values() if 'machineType' in v):
            self.assertEqual('DELETE', vm['scheduling']['instanceTerminationAction'])
            self.assertEqual('5400', vm['scheduling']['maxRunDuration']['seconds'])
            self.assertEqual([], vm['serviceAccounts'])
            self.assertEqual([], vm['networkInterfaces'][0]['accessConfigs'])
            self.assertTrue(all(not disk['autoDelete'] for disk in vm['disks']))
        total, attempts = n.inspect_ledger(self.api.store.get(n.LEDGER)[1])
        self.assertEqual(q.COST+q.topology.PRIOR_COST, total)
        self.assertEqual('PENDING', attempts[n.validate_request(self.api.req)]['status'])
        self.assertEqual(self.api.marker_value(), self.api.store.get(r.marker_key(self.api.req))[1])
        self.assertEqual(self.value, self.api.store.get(r.plan_key(self.api.req))[1])
        self.assertEqual(13, len({row['id'] for row in result['resources']}))

    def test_plan_rejects_domain_scope_inputs_cost_and_expiry_drift(self):
        for mutate in (lambda v: v.update(execution='gcp-v51-owned-control'),
                       lambda v: v.update(paidCloud=True), lambda v: v.update(paidAdmission=True),
                       lambda v: v['request'].update(member='canonical-1'),
                       lambda v: v['request'].update(schema='gse-v51-cloud-request-v2'),
                       lambda v: v['request'].update(guestAccessSha256='9'*64),
                       lambda v: v['configuration'].update(imageId='123'),
                       lambda v: v['inputs'].update(source='d'*40),
                       lambda v: v['inputs'].update(archiveSha256='9'*64),
                       lambda v: v['inputs'].update(buildManifestSha256='bad'),
                       lambda v: v['inputs'].update(workloadSha256='9'*64),
                       lambda v: v['inputs'].update(arbitrary='9'*64),
                       lambda v: v['reservation'].update(previousCostMicrousd=0),
                       lambda v: v['reservation'].update(maximumCostMicrousd=a.MAXIMUM_BUDGET_MICROUSD),
                       lambda v: v.update(expiresAt=v['expiresAt']+1)):
            value = deepcopy(self.value); mutate(value)
            with self.subTest(value=value), self.assertRaises(ValueError): r.validate(value, now=self.clock.wall())
        with self.assertRaises(ValueError): r.validate(self.value, now=self.value['expiresAt'])
        self.assertEqual(0, self.http.inserts)

    def test_network_constructor_and_fake_runner_are_not_exposed(self):
        with self.assertRaisesRegex(ValueError, 'offline HTTP'):
            r.OfflineApi(self.value, self.clock.wall(), transport=h.Network(), tokens=lambda _: 'no', clock=self.clock.seconds)
        self.assertFalse(hasattr(r, 'NetworkApi'))
        with self.assertRaises(ValueError): a.validate_request(self.value['request'])
        from . import cloud_runner
        with self.assertRaises(ValueError): cloud_runner.adapters(self.api.store, self.api.provider())

    def test_duplicate_preparation_cannot_recharge_or_reallocate(self):
        self.assertEqual('RESOURCES_PREPARED', self.prepare()['status'])
        before = retained.snapshot(self.http)
        fresh = r.OfflineApi(self.value, self.clock.wall(), transport=self.http, tokens=lambda _: 'offline', clock=self.clock.seconds)
        result = r.prepare(self.value, fresh, self.root/'repeat', now=self.clock.wall(), sleep=self.clock.sleep)
        self.assertEqual('FAIL', result['status']); self.assertEqual(before, retained.snapshot(self.http))
        self.assertEqual(13, self.http.inserts)

    def test_stale_control_and_existing_operation_fail_before_mutations(self):
        for kind in ('ledger', 'lease', 'context', 'operation'):
            value, clock, http, reader, api = q.fixture()
            if kind == 'ledger':
                gen, body = api.store.get(n.LEDGER); api.store.api = reader
                api.store.put(n.LEDGER, body, gen); api.store.api = api
            elif kind == 'lease':
                http.objects[n.LEASE] = (123, m.canonical(api.lease), 'application/json')
            elif kind == 'context':
                http.objects[cleanup.context_key(api.req, authority=n)] = (123, m.canonical(api.context()), 'application/json')
            else:
                spec = api.lease['resources'][0]['spec']; provider = api.provider()
                http.operations['old'] = dict(name='old', operationType='insert', clientOperationId=provider.operation_id(spec),
                    targetLink=provider.url(spec), targetId='777', status='DONE')
            before = retained.snapshot(http)
            result = r.prepare(value, api, self.root/kind, now=clock.wall(), sleep=clock.sleep)
            self.assertEqual('FAIL', result['status'], kind); self.assertEqual(before, retained.snapshot(http))
            self.assertEqual(0, http.inserts)

    def test_raw_base_call_cannot_expand_scope_body_generation_or_repeat_mutation(self):
        self.api.upload(); key, body, generation = self.api.write_step()
        correct = 'https://storage.googleapis.com/upload/storage/v1/b/'+self.api.cfg['bucket']+'/o?'+urlencode(
            dict(uploadType='media', name=key, ifGenerationMatch=generation))
        changed = deepcopy(body); changed['entries'][-1]['maximumCostMicrousd'] += 1
        calls = [('POST', correct, changed), ('POST', correct+'0', body),
                 ('DELETE', self.api.store.url(n.LEASE), None), ('GET', self.api.store.url(n.PREFIX+'foreign'), None),
                 ('GET', self.api.provider().base+'/zones/us-west4-a/operations/foreign', None),
                 ('POST', self.api.provider().base+'/zones/us-west4-a/instances', {})]
        before = retained.snapshot(self.http)
        for method, url, payload in calls:
            self.api.armed = (method, url, payload)
            with self.assertRaises(ValueError): h.Api.call(self.api, method, url, payload, deadline=self.clock.seconds()+30)
        self.assertEqual(before, retained.snapshot(self.http))
        self.api.armed = ('POST', correct, body)
        h.Api.call(self.api, 'POST', correct, body, deadline=self.clock.seconds()+30)
        with self.assertRaises(ValueError): h.Api.call(self.api, 'POST', correct, body, deadline=self.clock.seconds()+30)

    def test_401_insert_is_never_retried_or_credential_refreshed(self):
        exchanges = []
        def token(_): exchanges.append(True); return 'offline'
        self.api.tokens = token
        def deny(method, path, query, body):
            if method == 'POST' and path.path.startswith('/compute/'): return 401, b''
        self.http.hook = deny
        result = self.prepare(); self.assertEqual('FAIL', result['status'])
        self.assertEqual(401, result['failure']['httpStatus']); self.assertEqual(1, len(exchanges))
        self.assertEqual(1, len([v for v in self.http.requests if v['method'] == 'POST' and v['path'].startswith('/compute/')]))
        before = retained.snapshot(self.http)
        with self.assertRaises(ValueError): self.api.insert(self.clock.sleep)
        with self.assertRaises(ValueError): self.api.upload()
        self.assertEqual(before, retained.snapshot(self.http))

    def test_read_only_401_refresh_preserves_original_preparation_deadline(self):
        sends = self.http.send; exchanges = []; denied = []
        def token(_): exchanges.append(True); return 'offline-'+str(len(exchanges))
        def send(method, url, *args):
            if method == 'GET' and not denied: denied.append(True); self.clock.sleep(1); return 401, b''
            return sends(method, url, *args)
        self.api.tokens = token; self.http.send = send
        deadline = self.api.deadline
        self.assertEqual('RESOURCES_PREPARED', self.prepare()['status'])
        self.assertEqual(2, len(exchanges)); self.assertEqual(deadline, self.api.deadline)

    def test_missing_or_replaced_dependency_prevents_vm_insert(self):
        send = self.http.send
        def drift(method, url, *args):
            if self.http.inserts == 10 and method == 'GET' and url.endswith('-n1-data'):
                self.http.resources[urlsplit(url).path]['id'] = '999999'
            return send(method, url, *args)
        self.http.send = drift
        self.assertEqual('FAIL', self.prepare()['status']); self.assertEqual(10, self.http.inserts)
        self.assertFalse(any('machineType' in v for v in self.http.resources.values()))

    def test_image_denial_retains_only_prior_resources_and_original_boot_intent(self):
        def deny(method, path, query, body):
            if '/global/images/' in path.path: return 403, b''
        self.http.hook = deny
        result = self.prepare(); self.assertEqual('FAIL', result['status'])
        self.assertEqual(403, result['failure']['httpStatus']); self.assertEqual(4, self.http.inserts)
        _, lease = self.api.store.get(n.LEASE)
        self.assertTrue(lease['resources'][4]['attempted']); self.assertIsNone(lease['resources'][4]['id'])

    def test_inputs_retained_before_first_insert_and_drift_stops_the_next_insert(self):
        send = self.http.send
        def change(method, url, *args):
            if method == 'POST' and urlsplit(url).path.startswith('/compute/'):
                key = r.plan_key(self.api.req)
                self.assertEqual(self.value, m.strict_json(self.http.objects[key][1]))
                result = send(method, url, *args)
                retained.rewrite(self.http, key, lambda v: v['inputs'].update(pricesSha256='9'*64))
                return result
            return send(method, url, *args)
        self.http.send = change
        self.assertEqual('FAIL', self.prepare()['status']); self.assertEqual(1, self.http.inserts)

    def test_lost_identity_response_is_not_locally_replayed(self):
        q.inject('lost-identity-1', self.clock, self.http)
        self.assertEqual('FAIL', self.prepare()['status'])
        self.assertEqual(1, self.http.inserts)
        row = m.strict_json(self.http.objects[n.LEASE][1])['resources'][0]
        self.assertIsNotNone(row['id'])
        before = retained.snapshot(self.http)
        with self.assertRaises(ValueError): self.api.upload()
        with self.assertRaises(ValueError): self.api.insert(self.clock.sleep)
        self.assertEqual(before, retained.snapshot(self.http))

    def test_ledger_cas_conflict_stops_before_context_or_allocation(self):
        def conflict(method, path, query, body):
            if method == 'POST' and query.get('name') == n.LEDGER: return 412, b''
        self.http.hook = conflict
        result = self.prepare(); self.assertEqual('FAIL', result['status'])
        self.assertEqual(412, result['failure']['httpStatus']); self.assertEqual(0, self.http.inserts)
        self.assertEqual(self.value['baseline'][1], self.api.store.get(n.LEDGER)[1])
        self.assertIsNone(self.api.store.get(cleanup.context_key(self.api.req, authority=n)))


if __name__ == '__main__': unittest.main()

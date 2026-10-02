from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit, urlencode
from . import cloud_topology_fixture as f, cloud_topology_contract as contract
from . import cloud_topology_qualification as q, cloud_cleanup_qualification as retained
from . import cloud_cleanup as cleanup, cloud_native_cleanup as native
from . import cloud_native_authority as n, cloud_gcp as g, cloud_http as h
from . import cloud_cleanup_observation as observation, cloud_runner, performance_model as m


class TopologyFixtureTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.value, self.clock, self.http, self.reader, self.api = q.fixture()

    def prepare(self):
        return f.execute(self.value, self.api, self.root/'prepare', now=self.clock.wall(), sleep=self.clock.sleep)

    def test_full_topology_waits_unchanged_then_deletes_all_kinds_in_dependency_order(self):
        result = self.prepare(); self.assertEqual('PREPARED', result['status'], result)
        self.assertEqual((13, 13), (self.http.inserts, len(self.http.resources)))
        self.assertEqual(450, sum(int(v.get('sizeGb', 0)) for v in self.http.resources.values()))
        vms = [v for v in self.http.resources.values() if 'machineType' in v]
        self.assertEqual(3, len(vms))
        for vm in vms:
            self.assertEqual('STOP', vm['scheduling']['instanceTerminationAction'])
            self.assertEqual('5400', vm['scheduling']['maxRunDuration']['seconds'])
            self.assertEqual([], vm['serviceAccounts']); self.assertEqual([], vm['networkInterfaces'][0]['accessConfigs'])
            self.assertTrue(all(d['autoDelete'] is False for d in vm['disks']))
        before = retained.snapshot(self.http)
        for elapsed in (0, 5400, 1079):
            self.clock.sleep(elapsed); start = len(self.http.requests)
            result = native.reconcile(self.api.cfg, self.reader, self.root/('waiting-'+str(elapsed)), trigger='manual', now=self.clock.wall())
            self.assertEqual('WAITING', result['status']); self.assertEqual(before, retained.snapshot(self.http))
            self.assertTrue(all(v['method'] == 'GET' for v in self.http.requests[start:]))
        self.clock.sleep(1)
        result = native.reconcile(self.api.cfg, self.reader, self.root/'expired', trigger='manual', now=self.clock.wall())
        self.assertEqual('PASS', result['status']); self.assertFalse(self.http.resources)
        store = g.Store(self.api.cfg, self.reader, authority=n)
        self.assertIsNone(store.get(n.LEASE))
        deletes = [r for r in self.http.requests if r['method'] == 'DELETE' and r['path'].startswith('/compute/')]
        self.assertEqual(['instances']*3+['disks']*6+['firewalls']*4, [r['path'].split('/')[-2] for r in deletes])
        self.assertEqual({r['id'] for r in before['resources'].values()}, {r['path'].split('/')[-1] for r in deletes})
        ledger = store.get(n.LEDGER)[1]; total, attempts = n.inspect_ledger(ledger)
        self.assertEqual(q.PRIOR_COST+f.COST, total)
        self.assertEqual(self.value['before']['ledger'][1]['entries'], ledger['entries'][:2])
        self.assertEqual('FAIL', attempts[n.validate_request(self.value['request'])]['status'])

    def test_lost_insert_at_each_inventory_position_never_replays_and_is_reconstructed(self):
        for position in range(1, 14):
            with self.subTest(position=position):
                value, clock, http, reader, api = q.fixture(); send = http.send
                def lose(method, url, *args):
                    result = send(method, url, *args)
                    if method == 'POST' and 'compute.googleapis.com' in url and http.inserts == position:
                        raise ConnectionError('private-provider-diagnostic')
                    return result
                http.send = lose
                result = f.execute(value, api, self.root/str(position)/'prepare', now=clock.wall(), sleep=clock.sleep)
                self.assertEqual('FAIL', result['status']); self.assertEqual(position, http.inserts)
                self.assertNotIn('private-provider-diagnostic', str(result))
                row = api.store.get(n.LEASE)[1]['resources'][position-1]
                self.assertTrue(row['attempted']); self.assertIsNone(row['id'])
                with self.assertRaises(ValueError): api.insert(clock.sleep)
                http.send = send; clock.sleep(6480)
                result = native.reconcile(api.cfg, reader, self.root/str(position)/'cleanup', trigger='manual', now=clock.wall())
                self.assertEqual('PASS', result['status'], result); self.assertFalse(http.resources)
                self.assertEqual(position, http.inserts)

    def test_repeated_prepare_cannot_reallocate_or_overwrite(self):
        self.assertEqual('PREPARED', self.prepare()['status']); original = retained.snapshot(self.http)
        api = f.PreparationApi(self.value, self.clock.wall(), transport=self.http, tokens=lambda _: 'offline-token', clock=self.clock.seconds)
        result = f.execute(self.value, api, self.root/'repeat', now=self.clock.wall(), sleep=self.clock.sleep)
        self.assertEqual('FAIL', result['status']); self.assertEqual(original, retained.snapshot(self.http))
        self.assertEqual(13, self.http.inserts)

    def test_price_bounds_bind_entire_topology_and_all_cost_categories(self):
        self.assertEqual(3_310_000, f.price(self.value['prices'], self.clock.wall()))
        for mutate in (lambda p: p.update(vmMicrousdPerHour=5_000_000), lambda p: p.update(pricedThroughSeconds=6479),
                       lambda p: p.update(region='us-central1'), lambda p: p.pop('vmMicrousdPerHour'),
                       lambda p: p['otherCostsMicrousd'].pop('retention30Days')):
            price = deepcopy(self.value['prices']); mutate(price)
            with self.assertRaises(ValueError): f.price(price, self.clock.wall())

    def test_request_tampering_cannot_expand_or_relabel_fixture(self):
        for mutate in (lambda v: v.update(maximumCostMicrousd=1), lambda v: v.update(paidAdmission=True),
                       lambda v: v['qualificationManifest'].update(instanceTerminationAction='DELETE'),
                       lambda v: v['qualificationManifest']['topology'].update(instances=4),
                       lambda v: v['qualificationManifest'].update(graceSeconds=0),
                       lambda v: v['request'].update(member='canonical-1'),
                       lambda v: v.update(operator='gse-v51-runner@example.com')):
            value = deepcopy(self.value); mutate(value)
            with self.assertRaises(ValueError): f.validate(value, now=self.clock.wall())
        with self.assertRaises(ValueError): f.validate(self.value, now=self.value['expiresAt'])
        self.assertEqual(0, self.http.inserts)

    def test_unready_image_quota_network_retention_and_stale_observations_block_review(self):
        for mutate in (lambda p: p['observations']['image'].update(status='DEPRECATED'),
                       lambda p: p['observations']['machine'].update(guestCpus=4),
                       lambda p: p['observations']['region']['quotas'][0].update(usage=1),
                       lambda p: p['observations']['subnetwork'].update(privateIpGoogleAccess=False),
                       lambda p: p['observations']['bucket'].update(retentionPolicy={'retentionPeriod': 1}),
                       lambda p: p['observations'].update(principal='other@example.com'),
                       lambda p: p.update(startedAt=self.clock.wall()-301)):
            provider = deepcopy(self.value['providerObservation']); mutate(provider)
            with self.assertRaises(ValueError):
                f.provider_checks(self.value['configuration'], provider, self.value['operator'], self.clock.wall(), True)

    def test_pending_lease_or_budget_cannot_be_reset_by_review(self):
        before = deepcopy(self.value['before'])
        before['lease'] = [5, self.api.lease]
        args = [self.value['configuration'], self.value['request']['source'], self.value['operator'], retained.KEY,
                self.value['prices'], before, self.value['providerObservation']]
        kwargs = dict(now=self.clock.wall(), attempt='a'*32, sequence='b'*32, offline=True)
        with self.assertRaises(ValueError): f.make(*args, **kwargs)
        before['lease'] = None
        ledger = n.reserve(n.empty_ledger(), self.value['request'], dict(previousCostMicrousd=0, maximumCostMicrousd=f.COST))
        before['ledger'] = [5, ledger]
        with self.assertRaises(ValueError): f.make(*args, **kwargs)
        ledger = n.reserve(n.empty_ledger(), self.value['request'], dict(previousCostMicrousd=0,
                            maximumCostMicrousd=f.a.MAXIMUM_BUDGET_MICROUSD-f.COST+1))
        before['ledger'] = [5, n.finish(ledger, self.value['request'],
                               dict(status='FAIL', requestSha256=n.validate_request(self.value['request'])))]
        with self.assertRaises(ValueError): f.make(*args, **kwargs)

    def test_raw_requests_cannot_bypass_scope_generation_or_state_machine(self):
        self.api.upload()  # Lease acquired; next authorized mutation is only ledger reservation.
        key, body, generation = self.api.write_step()
        url = 'https://storage.googleapis.com/upload/storage/v1/b/'+self.api.cfg['bucket']+'/o?'+urlencode(
            dict(uploadType='media', name=key, ifGenerationMatch=generation+1))
        calls = [('POST', url, body), ('DELETE', self.api.store.url(n.LEASE), None),
                 ('GET', self.api.store.url(n.PREFIX+'foreign.json'), None),
                 ('GET', self.api.provider().base+'/zones/us-west4-a/operations/arbitrary', None),
                 ('POST', self.api.provider().base+'/zones/us-west4-a/instances', {})]
        original = retained.snapshot(self.http)
        for method, url, body in calls:
            self.api.armed = (method, url, body)
            with self.assertRaises(ValueError): h.Api.call(self.api, method, url, body, deadline=self.clock.seconds()+30)
        self.assertEqual(original, retained.snapshot(self.http))
        with self.assertRaises(ValueError): self.api.insert(self.clock.sleep)

    def test_lost_authority_upload_stops_before_compute_and_does_not_retry(self):
        for index, key in enumerate((n.LEASE, n.LEDGER, cleanup.context_key(self.value['request'], authority=n))):
            value, clock, http, reader, api = q.fixture(); send = http.send
            def lose(method, url, *args):
                result = send(method, url, *args)
                if method == 'POST' and parse_qs(urlsplit(url).query).get('name') == [key]: raise ConnectionError('lost write')
                return result
            http.send = lose
            result = f.execute(value, api, self.root/str(index), now=clock.wall(), sleep=clock.sleep)
            self.assertEqual('FAIL', result['status']); self.assertEqual(0, http.inserts)
            before = retained.snapshot(http)
            with self.assertRaises(ValueError): api.upload()
            self.assertEqual(before, retained.snapshot(http))

    def test_existing_resource_or_original_operation_blocks_before_any_write(self):
        for kind in ('resource', 'operation'):
            value, clock, http, reader, api = q.fixture(); spec = api.lease['resources'][0]['spec']; provider = api.provider()
            body = provider.body(spec); body['id'] = '777'
            if kind == 'resource': http.resources[urlsplit(provider.url(spec)).path] = body
            else: http.operations['original'] = dict(name='original', operationType='insert', clientOperationId=provider.operation_id(spec),
                targetLink=provider.url(spec), targetId='777', status='DONE')
            before = retained.snapshot(http)
            result = f.execute(value, api, self.root/kind, now=clock.wall(), sleep=clock.sleep)
            self.assertEqual('FAIL', result['status']); self.assertEqual(before, retained.snapshot(http))

    def test_changed_disk_identity_blocks_instance_creation(self):
        send = self.http.send
        def drift(method, url, *args):
            # Last disk was successfully retained; replace n1-data before VM dependency inspection.
            if self.http.inserts == 10 and method == 'GET' and url.endswith('-n1-data'):
                self.http.resources[urlsplit(url).path]['id'] = '999999'
            return send(method, url, *args)
        self.http.send = drift
        result = self.prepare(); self.assertEqual('FAIL', result['status']); self.assertEqual(10, self.http.inserts)
        self.assertFalse(any('machineType' in v for v in self.http.resources.values()))

    def test_preparation_uses_one_original_deadline(self):
        send = self.http.send
        def slow(method, url, *args):
            if method == 'POST' and 'compute.googleapis.com' in url: self.clock.sleep(201)
            return send(method, url, *args)
        self.http.send = slow
        result = self.prepare(); self.assertEqual('FAIL', result['status']); self.assertEqual(3, self.http.inserts)
        self.assertEqual('insert', result['failure']['phase'])

    def test_profile_is_bound_and_workload_resources_keep_automatic_delete(self):
        provider = self.api.provider(); vm = next(r for r in provider.inventory if r['kind'] == 'instance')
        default = g.Compute(self.api.cfg, self.api.req, self.reader, guest_access=self.value['guestAccess'], authority=n)
        self.assertEqual('DELETE', default.body(vm)['scheduling']['instanceTerminationAction'])
        self.assertEqual('STOP', provider.body(vm)['scheduling']['instanceTerminationAction'])
        context = provider.cleanup_context(); restored = cleanup.provider_from_context(context, self.api.req, self.reader, authority=n)
        self.assertEqual(provider.body(vm), restored.body(vm))
        for mutate in (lambda v: v.pop('qualificationManifest'),
                       lambda v: v['qualificationManifest'].update(maxRunSeconds=6480),
                       lambda v: v['qualificationManifest'].update(instanceTerminationAction='DELETE')):
            changed = deepcopy(context); mutate(changed)
            with self.assertRaises(ValueError): cleanup.validate_context(changed, self.api.req, authority=n)
        changed = deepcopy(self.api.req); changed['bundleSha256'] = 'f'*64
        with self.assertRaises(ValueError): contract.validate(self.value['qualificationManifest'], changed, self.api.cfg)

    def test_independent_observer_can_inspect_profile_and_expired_absence(self):
        prepared = self.prepare(); self.assertEqual('PREPARED', prepared['status'])
        before = observation.capture(self.value['configuration'], self.api.req['source'], api=self.reader, wall=self.clock.wall)
        self.assertEqual('OBSERVED', before['status'], before); self.assertEqual(13, len(before['resources']))
        self.assertEqual('PREPARATION_STATE_MATCH', f.review_prepared(self.value, prepared, before)['status'])
        for mutate in (lambda v: v['resources'][0].update(byId=None),
                       lambda v: v['resources'][0]['operation'].update(id='999999'),
                       lambda v: v['resources'].pop(), lambda v: v.update(source='d'*40),
                       lambda v: v['context'][1]['qualificationManifest'].update(instanceTerminationAction='DELETE')):
            damaged = deepcopy(before); mutate(damaged)
            with self.assertRaises(ValueError): f.review_prepared(self.value, prepared, damaged)
        self.clock.sleep(6480)
        result = native.reconcile(self.api.cfg, self.reader, self.root/'cleanup', trigger='manual', now=self.clock.wall())
        self.assertEqual('PASS', result['status'])
        after = observation.capture(self.value['configuration'], self.api.req['source'], before=before, api=self.reader, wall=self.clock.wall)
        self.assertEqual('OBSERVED', after['status'], after)
        self.assertTrue(all(r['byName'] is r['byId'] is None for r in after['resources']))

    def test_live_confirmation_and_protected_checks_precede_mutation_credentials(self):
        value = deepcopy(self.value); value['execution'] = 'operator-topology-request'
        value['before']['execution'] = 'read-only-native-cleanup-observation'
        value['providerObservation']['execution'] = 'read-only-provider-observations'
        with patch.object(f.time, 'time', self.clock.wall), patch.object(f.subprocess, 'check_output'), \
             patch.object(f.single, 'protected_checks', side_effect=ValueError('not accepted source')) as check, \
             patch.object(h.Network, 'send', side_effect=AssertionError('network write')) as send:
            with self.assertRaises(ValueError): f.NetworkPreparationApi(value, confirmation='0'*64)
            check.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'not accepted source'):
                f.NetworkPreparationApi(value, confirmation=f.validate(value, now=self.clock.wall()))
            check.assert_called_once(); send.assert_not_called()
        for key in ('tokens', 'clock', 'transport', 'force'):
            with self.assertRaises(TypeError): f.NetworkPreparationApi(value, confirmation='0'*64, **{key: True})
        api = object.__new__(f.NetworkPreparationApi); api.transport = type('Network', (), {'offline': False})()
        store = g.Store(self.api.cfg, api, authority=n)
        for authority in (f.a, n):
            with self.assertRaises(ValueError): cloud_runner.adapters(store, self.api.provider(), authority=authority)


if __name__ == '__main__': unittest.main()

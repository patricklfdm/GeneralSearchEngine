from copy import deepcopy
import unittest
from urllib.parse import urlsplit, parse_qs, unquote
from . import cloud_runner_storage as s, cloud_runner_storage_qualification as q
from . import cloud_cleanup_qualification as c, cloud_gcp as g, cloud_http as h
from . import cloud_native_authority as n, cloud_authority as a, cloud_fake, performance_model as m


class RunnerStorageTest(unittest.TestCase):
    def setUp(self):
        self.api, self.http, self.clock = q.fixture()

    def prepare(self):
        store = g.Store(self.api.cfg, self.api, authority=n)
        self.assertIsNone(store.get(n.LEASE)); store.get(n.LEDGER)
        for name in ('created', 'report', 'completion'): self.assertIsNone(store.get(self.api.keys[name]))
        generation = store.put(n.LEASE, self.api.lease, 0)
        store.put(n.LEDGER, self.api.reserved, self.api.original_generation)
        return store, generation

    def forbidden(self, method, url, body=None):
        before = deepcopy(self.http.requests)
        for call in (self.api.call, lambda *args, **kw: h.Api.call(self.api, *args, **kw)):
            with self.assertRaises(ValueError): call(method, url, body, deadline=self.clock.seconds()+30)
        self.assertEqual(before, self.http.requests)

    def test_lifecycle_retains_cost_and_never_claims_engine_or_iam_acceptance(self):
        before = c.snapshot(self.http); result = s.run(self.api)
        self.assertEqual('PASS', result['status'])
        self.assertFalse(result['paidCloud'] or result['objectPermissionsQualified'] or result['fullRemoteQualification'])
        q.check_state(before, c.snapshot(self.http), self.api, reserved=True, released=True)
        self.assertEqual(set(s.CASES[3:]), self.api.denied)
        self.assertEqual({}, self.http.resources)
        self.assertFalse(any('/compute/' in v['path'] for v in self.http.requests))

    def test_first_ledger_uses_create_if_absent(self):
        api, http, _ = q.fixture(ledger_present=False)
        s.run(api)
        ledger = m.strict_json(http.objects[n.LEDGER][1])
        self.assertEqual(1_000_000, n.inspect_ledger(ledger)[0])
        writes = [v for v in http.requests if v['method'] == 'POST' and v['query']['name'] == n.LEDGER]
        self.assertEqual('0', writes[0]['query']['ifGenerationMatch'])

    def test_stale_baseline_and_existing_lease_fail_before_any_write(self):
        for key in (n.LEDGER, n.LEASE):
            with self.subTest(key=key):
                api, http, _ = q.fixture()
                value = api.original if key == n.LEDGER else api.lease
                http.objects[key] = (777, m.canonical(value), 'application/json')
                before = c.snapshot(http)
                with self.assertRaises(ValueError): s.run(api)
                self.assertEqual(before, c.snapshot(http))
                self.assertTrue(all(v['method'] == 'GET' for v in http.requests))

    def test_retained_attempt_marker_blocks_even_without_a_ledger_reservation(self):
        # Expired cleanup can retain a completion for a lost acquire before reserve.
        for name in ('created', 'report', 'completion'):
            with self.subTest(name=name):
                api, http, _ = q.fixture()
                value = s.canary(api.req, 'created') if name == 'created' else s.report(api.req) if name == 'report' else s.completion(api.req)
                http.objects[api.keys[name]] = 777, m.canonical(value), 'application/json'
                before = c.snapshot(http)
                with self.assertRaisesRegex(ValueError, 'attempt already retained'): s.run(api)
                self.assertEqual(before, c.snapshot(http))
                self.assertTrue(all(v['method'] == 'GET' for v in http.requests))

    def test_native_request_and_exact_configuration_and_canaries_required(self):
        fake, _, _ = cloud_fake.fixture()
        cases = [(self.api.cfg, fake, self.api.baseline)]
        cfg = deepcopy(self.api.cfg); cfg['bucket'] = 'other-bucket'
        cases.append((cfg, self.api.req, self.api.baseline))
        for field in ('source', 'attempt', 'guestAccessSha256'):
            req = deepcopy(self.api.req); req[field] = 'f'*len(req[field])
            cases.append((self.api.cfg, req, self.api.baseline))
        baseline = deepcopy(self.api.baseline); baseline[self.api.keys['existing']][1]['kind'] = 'forged'
        cases.append((self.api.cfg, self.api.req, baseline))
        for cfg, req, baseline in cases:
            with self.subTest(req=req), self.assertRaises(ValueError):
                s.OfflineApi(cfg, req, baseline, maximum_cost=1, transport=self.http, clock=self.clock.seconds)

    def test_no_network_constructor_or_runtime_transport_substitution(self):
        with self.assertRaisesRegex(ValueError, 'no network entry'):
            s.OfflineApi(self.api.cfg, self.api.req, self.api.baseline, maximum_cost=1,
                         transport=h.Network(), clock=self.clock.seconds)
        self.api.transport = h.Network()
        with self.assertRaisesRegex(ValueError, 'no network entry'):
            self.api.call('GET', self.api.url(n.LEDGER), deadline=self.clock.seconds()+30)

    def test_closed_policy_also_applies_to_base_api_calls(self):
        for method, url, body in [
            ('POST', 'https://compute.googleapis.com/compute/v1/projects/offline-project/zones/us-west4-a/disks', {}),
            ('GET', self.api.url(n.PREFIX+'foreign.json'), None),
            ('GET', self.api.url(n.LEDGER).replace(self.api.cfg['bucket'], 'foreign'), None),
            ('DELETE', self.api.delete_url(n.LEDGER, self.api.original_generation), None),
            ('POST', self.api.put_url(n.LEDGER, self.api.original_generation), self.api.reserved),
            ('POST', self.api.put_url(self.api.keys['completion'], 0), s.completion(self.api.req)),
            ('DELETE', self.api.delete_url(n.LEASE, 123), None),
        ]:
            with self.subTest(url=url): self.forbidden(method, url, body)

    def test_duplicate_queries_and_unpinned_media_never_reach_transport(self):
        self.forbidden('GET', self.api.url(n.LEDGER)+'?alt=media')
        self.forbidden('GET', self.api.url(n.LEDGER)+'?alt=media&generation=1&generation=2&ifGenerationMatch=2')
        self.forbidden('POST', self.api.put_url(n.LEASE, 0)+'&ifGenerationMatch=0', self.api.lease)

    def test_cannot_invent_success_or_change_resource_intent_or_terminal_ledger(self):
        _, generation = self.prepare()
        complete = s.completion(self.api.req); complete['status'] = 'PASS'
        self.forbidden('POST', self.api.put_url(self.api.keys['completion'], 0), complete)
        lease = deepcopy(self.api.lease); lease['resources'][0]['attempted'] = True
        self.forbidden('POST', self.api.put_url(n.LEASE, generation), lease)
        self.forbidden('POST', self.api.put_url(n.LEDGER, self.api.observed[n.LEDGER][0]), self.api.terminal)
        self.forbidden('POST', self.api.put_url(self.api.keys['report'], 0), s.report(self.api.req))
        self.forbidden('DELETE', self.api.delete_url(n.LEASE, generation))

    def test_positive_readback_is_pinned_to_upload_generation(self):
        store, _ = self.prepare()
        send = self.http.send
        def replace(method, url, *args):
            result = send(method, url, *args)
            if method == 'POST' and parse_qs(urlsplit(url).query).get('name') == [self.api.keys['created']]:
                key = self.api.keys['created']; gen, raw, content = self.http.objects[key]
                self.http.objects[key] = gen+1, raw, content
            return result
        self.http.send = replace
        with self.assertRaisesRegex(ValueError, 'upload read-back differs'):
            store.put(self.api.keys['created'], s.canary(self.api.req, 'created'), 0)
        self.assertNotIn(self.api.keys['report'], self.http.objects)

    def test_412_and_other_errors_do_not_qualify_permission_denial(self):
        for status in (401, 404, 412, 429, 500):
            with self.subTest(status=status):
                api, http, _ = q.fixture(denial=status)
                with self.assertRaisesRegex(ValueError, 'inconclusive'): s.run(api)
                self.assertNotIn(api.keys['report'], http.objects)
                self.assertIn(n.LEASE, http.objects)
                self.assertEqual(set(), api.denied)

    def test_unexpected_write_delete_or_read_success_is_a_failure(self):
        # Reach each negative independently by allowing only that operation.
        for method, name in [('POST', 'existing'), ('DELETE', 'existing'), ('GET', 'outside'),
                             ('POST', 'outside'), ('DELETE', 'outside')]:
            with self.subTest(method=method, name=name):
                api, http, _ = q.fixture()
                http.allow.add((method, api.keys[name]))
                with self.assertRaisesRegex(ValueError, 'unexpectedly succeeded'): s.run(api)
                self.assertNotIn(api.keys['report'], http.objects)
                self.assertIn(n.LEASE, http.objects)

    def test_probes_use_actual_existing_generations_not_create_preconditions(self):
        s.run(self.api)
        for row in self.http.requests:
            if row['method'] not in ('POST', 'DELETE'): continue
            key = row['query'].get('name') if row['method'] == 'POST' else unquote(row['path'].split('/o/')[1])
            if key in (self.api.keys['existing'], self.api.keys['outside']):
                self.assertEqual(str(self.api.baseline[key][0]), row['query']['ifGenerationMatch'])

    def test_lost_response_original_mutation_cannot_be_resubmitted(self):
        api, http, clock = q.fixture('lost-reserve')
        with self.assertRaises(ConnectionError): s.run(api)
        before = c.snapshot(http); count = len(http.requests)
        with self.assertRaisesRegex(ValueError, 'already submitted'):
            api.call('POST', api.put_url(n.LEDGER, api.original_generation), api.reserved, deadline=clock.seconds()+30)
        self.assertEqual(count, len(http.requests)); self.assertEqual(before, c.snapshot(http))

    def test_readback_fault_occurs_after_canary_write_not_initial_absence_check(self):
        api, http, _ = q.fixture('lost-create-readback')
        with self.assertRaisesRegex(ConnectionError, 'readback interruption'): s.run(api)
        self.assertIn(n.LEASE, http.objects)
        self.assertEqual(s.canary(api.req, 'created'), m.strict_json(http.objects[api.keys['created']][1]))
        self.assertEqual(api.reserved, m.strict_json(http.objects[n.LEDGER][1]))
        self.assertNotIn(api.keys['report'], http.objects)

    def test_new_session_cannot_repeat_completed_or_ambiguous_request(self):
        for fault in (None, 'lost-release', 'lost-reserve'):
            with self.subTest(fault=fault):
                api, http, clock = q.fixture(fault)
                try: s.run(api)
                except ConnectionError: pass
                before = c.snapshot(http)
                again = s.OfflineApi(api.cfg, api.req, api.baseline, maximum_cost=1_000_000, transport=http, clock=clock.seconds)
                with self.assertRaises(ValueError): s.run(again)
                self.assertEqual(before, c.snapshot(http))

    def test_pending_duplicate_and_budget_exhausted_ledgers_fail_before_transport(self):
        prior = self.api.original['entries'][0]['request']
        exhausted = n.finish(n.reserve(n.empty_ledger(), prior,
                             dict(previousCostMicrousd=0, maximumCostMicrousd=a.MAXIMUM_BUDGET_MICROUSD)),
                             prior, s.completion(prior))
        for ledger in (self.api.reserved, self.api.terminal, exhausted):
            baseline = deepcopy(self.api.baseline); baseline[n.LEDGER] = (99, ledger)
            with self.assertRaises(ValueError):
                s.OfflineApi(self.api.cfg, self.api.req, baseline, maximum_cost=1, transport=self.http, clock=self.clock.seconds)
        self.assertEqual([], self.http.requests)

    def test_owner_deadline_does_not_renew_between_operations(self):
        self.prepare(); self.clock.sleep(5400)
        self.forbidden('POST', self.api.put_url(self.api.keys['created'], 0), s.canary(self.api.req, 'created'))

    def test_late_mutation_reply_is_not_accepted_past_original_owner_deadline(self):
        store, _ = self.prepare(); self.clock.sleep(5399)
        send = self.http.send
        def late(method, url, *args):
            result = send(method, url, *args)
            if method == 'POST': self.clock.sleep(2)
            return result
        self.http.send = late
        with self.assertRaisesRegex(ValueError, 'late response'):
            store.put(self.api.keys['created'], s.canary(self.api.req, 'created'), 0)
        self.assertIn(self.api.keys['created'], self.http.objects)
        self.assertIn(n.LEASE, self.http.objects)
        self.assertNotIn(self.api.keys['report'], self.http.objects)

    def test_cas_race_leaves_foreign_control_bytes_untouched(self):
        for key in (n.LEASE, n.LEDGER):
            with self.subTest(key=key):
                api, http, _ = q.fixture(); intercept = http.hook
                foreign = (888, m.canonical(api.lease if key == n.LEASE else api.original), 'application/json')
                def race(method, parsed, query, body):
                    if method == 'POST' and query.get('name') == key: http.objects[key] = foreign
                    return intercept(method, parsed, query, body)
                http.hook = race
                with self.assertRaises(h.ApiError) as raised: s.run(api)
                self.assertEqual(412, raised.exception.status)
                self.assertEqual(foreign, http.objects[key])
                self.assertNotIn(api.keys['created'], http.objects)


if __name__ == '__main__': unittest.main()

from copy import deepcopy
import unittest
from . import cloud_authority as a, cloud_fake as fake, performance_model as m


class CloudAuthorityTest(unittest.TestCase):
    def setUp(self): self.req, self.preflight, self.approval = fake.fixture()

    def approve(self): self.approval['preflightSha256'] = m.sha(m.canonical(self.preflight))

    def test_fresh_schedule_and_manual_receipts_are_admitted_only_as_control(self):
        for event in a.CLEANUP_WORKFLOWS:
            req, pre, app = fake.fixture(cleanup_event=event)
            self.assertEqual(a.validate_request(req), a.admit(req, pre, app, 10001))
            self.assertIs(req['paidCloud'], False)

    def test_request_closed_scope_and_digest_types(self):
        for key, value in (('suite', 'v5.0'), ('paidCloud', True), ('paidCloud', 0), ('execution', 'gcp'),
                           ('source', 'a'*39), ('bundleSha256', 'x'*64), ('attempt', '../bad'),
                           ('workloadSha256', '0'*64), ('createdAt', True), ('order', 'any'),
                           ('member', 'canonical-4'), ('unexpected', 1)):
            with self.subTest(key=key, value=value):
                changed = dict(self.req, **{key: value})
                with self.assertRaises(ValueError): a.validate_request(changed)

    def test_preflight_original_age_future_and_window_bounds(self):
        self.assertEqual(a.validate_request(self.req), a.admit(self.req, self.preflight, self.approval, 10900))
        for now in (10000, 10901):
            with self.assertRaises(ValueError): a.admit(self.req, self.preflight, self.approval, now)
        self.preflight['expiresAt'] += 1; self.approve()
        with self.assertRaisesRegex(ValueError, 'bounded integer'): a.admit(self.req, self.preflight, self.approval, 10001)

    def test_unavailable_check_and_untrusted_workflow_fail_closed(self):
        for key in a.CHECKS:
            for value in (False, 1, 'PASS'):
                req, pre, app = fake.fixture(); pre['checks'][key] = value
                app['preflightSha256'] = m.sha(m.canonical(pre))
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'blockers'):
                    a.admit(req, pre, app, 10001)
        for key, value in (('workflow', '.github/workflows/v50-replication-evidence.yml'),
                           ('ref', 'refs/heads/feature'), ('environment', 'cloud-benchmark')):
            req, pre, app = fake.fixture(); pre[key] = value
            app['preflightSha256'] = m.sha(m.canonical(pre))
            with self.assertRaisesRegex(ValueError, 'runner identity'): a.admit(req, pre, app, 10001)

    def test_cleanup_must_be_recent_executed_success_on_exact_source(self):
        for key, value in (('source', 'f'*40), ('completedAt', 2800), ('completedAt', 10002),
                           ('executed', False), ('executed', 1), ('conclusion', 'skipped'), ('reconciliation', 'WAITING'),
                           ('event', 'push'), ('workflow', '.github/workflows/v50-expired-cleanup.yml'),
                           ('ref', 'refs/heads/other'), ('runId', False)):
            req, pre, app = fake.fixture(); pre['cleanup'][key] = value
            app['preflightSha256'] = m.sha(m.canonical(pre))
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): a.admit(req, pre, app, 10001)

    def test_approval_binds_original_request_and_preflight_no_automatic_price(self):
        for key, value in (('requestSha256', 'f'*64), ('preflightSha256', 'f'*64), ('confirmed', False),
                           ('confirmed', 1), ('maximumCostMicrousd', True), ('previousCostMicrousd', -1),
                           ('previousCostMicrousd', 100_000_000)):
            app = dict(self.approval, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError): a.admit(self.req, self.preflight, app, 10001)

    def complete(self, ledger, req, status='PASS'):
        return a.finish(ledger, req, dict(status=status, requestSha256=a.validate_request(req)))

    def test_both_complete_sequence_orders(self):
        for order, members in a.ORDERS.items():
            ledger = a.empty_ledger()
            for i, member in enumerate(members):
                req, _, app = fake.fixture(order=order, member=member, attempt=f'{i:032x}', previous=i*1_000_000)
                ledger = self.complete(a.reserve(ledger, req, app), req)
            total, attempts = a.inspect_ledger(ledger)
            self.assertEqual((5_000_000, 5), (total, len(attempts)))
            self.assertTrue(all(v['status'] == 'PASS' for v in attempts.values()))

    def test_failed_experiment_retry_is_new_attempt_and_not_refunded(self):
        ledger = self.complete(a.reserve(a.empty_ledger(), self.req, self.approval), self.req, 'FAIL')
        req, _, app = fake.fixture(attempt='1'*32, previous=1_000_000)
        result = a.reserve(ledger, req, app)
        self.assertEqual(2_000_000, a.inspect_ledger(result)[0])
        self.assertEqual(ledger['entries'], result['entries'][:-1])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            a.reserve(ledger, self.req, dict(app))

    def test_canonical_failure_requires_fresh_sequence(self):
        req, _, app = fake.fixture(order='canonical-first', member='canonical-1')
        ledger = self.complete(a.reserve(a.empty_ledger(), req, app), req, 'FAIL')
        new, _, app = fake.fixture(order='canonical-first', member='canonical-1', attempt='1'*32, previous=1_000_000)
        with self.assertRaisesRegex(ValueError, 'failed canonical'): a.reserve(ledger, new, app)
        new['sequence'] = '2'*32
        self.assertEqual(2_000_000, a.inspect_ledger(a.reserve(ledger, new, app))[0])

    def test_source_bundle_configuration_order_drift_rejected_even_on_new_attempt(self):
        ledger = self.complete(a.reserve(a.empty_ledger(), self.req, self.approval), self.req, 'FAIL')
        for key, value in (('source', 'f'*40), ('bundleSha256', 'f'*64), ('configurationSha256', 'f'*64), ('order', 'canonical-first')):
            req, _, app = fake.fixture(attempt='1'*32, previous=1_000_000)
            req[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'sequence changed'):
                a.reserve(ledger, req, app)

    def test_pending_attempt_stale_budget_and_omitted_member_refused(self):
        pending = a.reserve(a.empty_ledger(), self.req, self.approval)
        req, _, app = fake.fixture(attempt='1'*32, previous=1_000_000)
        with self.assertRaisesRegex(ValueError, 'unresolved'): a.reserve(pending, req, app)
        done = self.complete(pending, self.req)
        with self.assertRaisesRegex(ValueError, 'stale budget'): a.reserve(done, req, dict(app, previousCostMicrousd=0))
        req['member'] = 'canonical-1'
        with self.assertRaisesRegex(ValueError, 'sequence order'): a.reserve(done, req, app)

    def test_suite_wide_budget_cannot_reset_with_new_sequence(self):
        ledger = self.complete(a.reserve(a.empty_ledger(), self.req, dict(self.approval, maximumCostMicrousd=100_000_000)), self.req)
        req, _, app = fake.fixture(sequence='1'*32, attempt='2'*32, previous=100_000_000)
        with self.assertRaisesRegex(ValueError, 'budget ceiling'): a.reserve(ledger, req, app)
        with self.assertRaises(ValueError): a.inspect_ledger(dict(ledger, suite='v5.0'))

    def test_terminal_event_is_single_append_and_cannot_forge_an_attempt(self):
        ledger = a.reserve(a.empty_ledger(), self.req, self.approval)
        done = self.complete(ledger, self.req)
        with self.assertRaisesRegex(ValueError, 'terminal'): self.complete(done, self.req)
        with self.assertRaisesRegex(ValueError, 'terminal'): self.complete(a.empty_ledger(), self.req)
        bad = deepcopy(done); bad['entries'][-1]['completionSha256'] = 'no'
        with self.assertRaisesRegex(ValueError, 'digest'): a.inspect_ledger(bad)

    def test_lease_exact_inventory_and_fixed_expiry(self):
        lease = a.lease(self.req, 10001)
        self.assertEqual(13, len(lease['resources']))
        self.assertEqual(450, sum(r['spec'].get('sizeGiB', 0) for r in lease['resources']))
        self.assertEqual(lease, a.validate_lease(lease))
        for kind in ('extra', 'owner', 'expiry', 'suite', 'id'):
            bad = deepcopy(lease)
            if kind == 'extra': bad['resources'].append(deepcopy(bad['resources'][-1]))
            if kind == 'owner': bad['resources'][0]['spec']['owner'] = 'foreign'
            if kind == 'expiry': bad['expiresAt'] += 1
            if kind == 'suite': bad['suite'] = 'v5.0'
            if kind == 'id': bad['resources'][0]['id'] = '1000'
            with self.subTest(kind=kind), self.assertRaises(ValueError): a.validate_lease(bad)

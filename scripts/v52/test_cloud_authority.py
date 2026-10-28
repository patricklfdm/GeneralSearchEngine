from copy import deepcopy
import itertools
import unittest
from unittest.mock import patch
from . import cloud_authority as a, cloud_suite as suite
from .evidence import encoded, digest


def fixture(member='experiment', attempt='b'*32, *, domain='offline', sequence='c'*32):
    bound = dict(source='a'*40, checkoutSha256='1'*64, sequence=sequence, suiteSha256=suite.PLAN_SHA,
        programSha256=suite.model.PLAN_SHA, buildManifestSha256='2'*64, packageSha256='3'*64,
        controlsManifestSha256=suite.load()['controlsManifestSha256'])
    return a.request(suite.selection(bound, member, attempt), '4'*64,
        dict(bootDiskGiB=50, dataDiskGiB=100), dict(leaseSeconds=60, operationGraceSeconds=30, budgetMicrousd=200_000_000),
        now=1000, domain=domain)


def completion(req, status='PASS'):
    return dict(schema='gse-v52-owned-completion-v1', execution=req['execution'],
        requestSha256=a.validate_request(req, domain=a.domain(req)), status=status,
        evidenceSha256='5'*64 if status == 'PASS' else None, cleanupSha256='6'*64)


class AuthorityTest(unittest.TestCase):
    def test_domains_and_closed_request_fields_do_not_promote_old_or_offline_records(self):
        for domain in a.DOMAINS:
            req = fixture(domain=domain); a.validate_request(req, domain=domain)
            with self.assertRaisesRegex(ValueError, 'request domain'):
                a.validate_request(req, domain='native' if domain == 'offline' else 'offline')
            for change in (lambda r:r.update(execution='gcp-v51-owned-control'), lambda r:r.update(paidCloud=1),
                           lambda r:r.update(schema='gse-v51-native-request-v1')):
                other = deepcopy(req); change(other)
                with self.assertRaises(ValueError): a.validate_request(other, domain=domain)
            other = deepcopy(req); other['authorization'] = True
            with self.assertRaisesRegex(ValueError, 'request fields'): a.validate_request(other, domain=domain)

    def test_request_copies_source_and_exact_whole_member_selection(self):
        req = fixture(); selected = deepcopy(req['selection'])
        copy = a.request(selected, req['configurationSha256'], req['layout'], req['policy'], now=1000, domain='offline')
        selected['member']['histories'].clear(); req['layout']['dataDiskGiB'] = 1
        self.assertEqual(5, len(copy['selection']['member']['histories'])); self.assertEqual(100, copy['layout']['dataDiskGiB'])
        copy['selection']['member']['histories'].pop()
        with self.assertRaises(ValueError): a.validate_request(copy, domain='offline')

    def test_closed_exact_resource_intents_use_a_separate_namespace(self):
        req = fixture(); specs = a.resources(req)
        self.assertEqual(13, len(specs)); self.assertEqual(13, len({r['operationId'] for r in specs}))
        self.assertEqual({'firewall':4, 'disk':6, 'instance':3}, {k:sum(r['kind']==k for r in specs) for k in ('firewall','disk','instance')})
        self.assertTrue(all(r['name'].startswith('gse-v52-') and len(r['name']) <= 63 for r in specs))
        changed = a.resources(fixture(attempt='d'*32))
        self.assertFalse({r['name'] for r in changed} & {r['name'] for r in specs})
        self.assertTrue(a.LEASE.startswith(a.PREFIX)); self.assertNotIn('v5.1', a.LEASE)

    def test_lease_needs_charge_phase_original_plan_exact_ids_and_finite_expiry(self):
        lease = a.lease(fixture(), 1001); a.validate_lease(lease)
        for mutate in (lambda v:v['resources'][0].update(attempted=True),
                       lambda v:v.update(expiresAt=v['expiresAt']+1),
                       lambda v:v['resources'].pop(),
                       lambda v:v['resources'][0]['spec'].update(owner='foreign')):
            wrong = deepcopy(lease); mutate(wrong)
            with self.assertRaises(ValueError): a.validate_lease(wrong)
        lease['phase'] = 'ACTIVE'; lease['resources'][0].update(attempted=True, id='123')
        a.validate_lease(lease); lease['resources'][1].update(attempted=True, id='123')
        with self.assertRaisesRegex(ValueError, 'collision'): a.validate_lease(lease)

    def test_renewal_does_not_revive_expired_or_cleaning_owners(self):
        lease = a.lease(fixture(), 1000); lease['phase'] = 'ACTIVE'
        renewed = a.renew(lease, 1059)
        self.assertEqual(1119, renewed['expiresAt']); self.assertEqual(1060, lease['expiresAt'])
        for now in (999, 1060, 1061):
            with self.assertRaises(ValueError): a.renew(lease, now)
        lease['phase'] = 'CLEANING'
        with self.assertRaisesRegex(ValueError, 'active ownership'): a.renew(lease, 1059)

    def test_time_cost_and_sizes_reject_booleans_overflow_and_unknown_policy(self):
        for key in ('leaseSeconds','operationGraceSeconds','budgetMicrousd'):
            for value in (True, -1, 1<<63):
                req = fixture(); req['policy'][key] = value
                with self.assertRaises(ValueError): a.validate_request(req, domain='offline')
        req = fixture(); req['createdAt'] = a.MAX_INTEGER
        with self.assertRaises(ValueError): a.validate_request(req, domain='offline')
        req = fixture(); req['layout']['dataDiskGiB'] = True
        with self.assertRaises(ValueError): a.validate_request(req, domain='offline')

    def test_every_whole_member_order_is_legal_without_repeating_successes(self):
        # Build the original events directly so this covers every starting member in both directions
        # without repeatedly running unrelated resource provisioning.
        requests = {name: fixture(name, f'{i+1:032x}') for i,name in enumerate(suite.MEMBERS)}
        # Validate the actual frozen file once. The permutation matrix exercises
        # the real ledger/selection logic, not repeated file derivations.
        plan = suite.load()
        with patch.object(suite, 'load', return_value=plan):
            for order in (v[i:]+v[:i] for v in (suite.MEMBERS,tuple(reversed(suite.MEMBERS))) for i in range(len(v))):
                ledger = a.empty_ledger(domain='offline')
                for name in order:
                    req = requests[name]; sha = a.validate_request(req, domain='offline'); done = completion(req)
                    ledger['entries'] += [dict(kind='RESERVED', requestSha256=sha, request=req, reservedCostMicrousd=1),
                        dict(kind='FINISHED', requestSha256=sha, status='PASS', completionSha256=digest(encoded(done)))]
                view = a.inspect_ledger(ledger, domain='offline')
                self.assertEqual(list(order), view['sequences']['c'*32]['passed'])
                self.assertEqual(len(suite.MEMBERS), view['reservedCostMicrousd'])

    def test_partial_or_cleaning_allocation_cannot_supply_a_resource_claim(self):
        value=a.lease(fixture(),1000)
        with self.assertRaisesRegex(ValueError,'complete active allocation'):a.resource_claim(value)
        value['phase']='ACTIVE'
        for i,row in enumerate(value['resources']):row.update(attempted=True,id=str(1000+i))
        claim=a.resource_claim(value);self.assertEqual(3,len(claim['nodes']))
        value['phase']='CLEANING'
        with self.assertRaisesRegex(ValueError,'complete active allocation'):a.resource_claim(value)

    def test_failures_remain_charged_whole_new_attempt_can_retry_member(self):
        req = fixture('canonical-2-legacy'); ledger = a.reserve(a.empty_ledger(domain='offline'), req, previous_cost=0, cost=100)
        failed = a.finish(ledger, req, completion(req, 'FAIL'))
        retry = fixture('canonical-2-legacy', 'd'*32)
        next_ledger = a.reserve(failed, retry, previous_cost=100, cost=200)
        view = a.inspect_ledger(next_ledger, domain='offline')
        self.assertEqual(300, view['reservedCostMicrousd']); self.assertEqual(2, len(view['attempts']))
        self.assertEqual('FAIL', view['attempts'][a.validate_request(req, domain='offline')]['status'])
        self.assertEqual(2, len(failed['entries'])); self.assertEqual(1, len(ledger['entries']))

    def test_pending_reused_passed_and_changed_sequence_records_reject(self):
        req = fixture(); reserved = a.reserve(a.empty_ledger(domain='offline'), req, previous_cost=0, cost=1)
        with self.assertRaisesRegex(ValueError, 'unresolved'): a.reserve(reserved, fixture('canonical-3-legacy', 'd'*32), previous_cost=1, cost=1)
        done = a.finish(reserved, req, completion(req))
        for candidate in (req, fixture(attempt='d'*32)):
            with self.assertRaises(ValueError): a.reserve(done, candidate, previous_cost=1, cost=1)
        for change in (lambda r:r.update(configurationSha256='e'*64),
                       lambda r:r['selection']['binding'].update(source='e'*40),
                       lambda r:r['layout'].update(dataDiskGiB=101)):
            candidate = fixture('canonical-3-legacy', 'd'*32); change(candidate)
            with self.assertRaisesRegex(ValueError, 'sequence identity changed'): a.reserve(done, candidate, previous_cost=1, cost=1)

    def test_soft_cost_threshold_preserves_original_charge_and_warns(self):
        req = fixture(); ledger = a.reserve(a.empty_ledger(domain='offline'), req, previous_cost=0, cost=300_000_000)
        warning = a.budget_warning(req, ledger)
        self.assertTrue(warning['exceeded']); self.assertTrue(warning['estimateOnly'])
        with self.assertRaisesRegex(ValueError, 'stale cost'): a.reserve(ledger, req, previous_cost=0, cost=1)
        with self.assertRaises(ValueError): a.reserve(a.empty_ledger(domain='offline'), req, previous_cost=False, cost=1)

    def test_terminal_record_requires_matching_request_and_evidence_for_success(self):
        req = fixture(); ledger = a.reserve(a.empty_ledger(domain='offline'), req, previous_cost=0, cost=1)
        for change in (lambda c:c.update(requestSha256='e'*64), lambda c:c.update(evidenceSha256=None),
                       lambda c:c.update(execution=a.DOMAINS['native']), lambda c:c.update(status='SKIPPED')):
            wrong = completion(req); change(wrong)
            with self.assertRaises(ValueError): a.finish(ledger, req, wrong)
        done = a.finish(ledger, req, completion(req))
        with self.assertRaisesRegex(ValueError, 'terminal attempt changed'): a.finish(done, req, completion(req))

    def test_native_ledger_records_do_not_become_offline_authority(self):
        req=fixture(domain='native');ledger=a.reserve(a.empty_ledger(domain='native'),req,previous_cost=0,cost=1)
        self.assertEqual(1,a.inspect_ledger(ledger,domain='native')['reservedCostMicrousd'])
        with self.assertRaisesRegex(ValueError,'ledger domain'):a.inspect_ledger(ledger,domain='offline')
        with self.assertRaisesRegex(ValueError,'ledger domain'):
            a.reserve(ledger,fixture(),previous_cost=1,cost=1)

    def test_soft_cost_still_enforces_integer_and_inventory_representation_bounds(self):
        req=fixture();ledger=a.reserve(a.empty_ledger(domain='offline'),req,previous_cost=0,cost=a.MAX_INTEGER)
        ledger=a.finish(ledger,req,completion(req,'FAIL'))
        with self.assertRaisesRegex(ValueError,'bounded integer'):
            a.reserve(ledger,fixture(attempt='d'*32),previous_cost=a.MAX_INTEGER,cost=1)
        lease=a.lease(req,1000);lease['phase']='ACTIVE';lease['resources'][1]['attempted']=True
        with self.assertRaisesRegex(ValueError,'intent gap'):a.validate_lease(lease)


if __name__ == '__main__': unittest.main()
